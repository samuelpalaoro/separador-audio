"""
Worker assíncrono unificado (QThread) para orquestração de download, conversão e separação de áudio.
"""
import os
import shutil
import tempfile
from typing import Dict, Any, Optional
import numpy as np
from PySide6.QtCore import QThread, Signal

from src.downloader.youtube_downloader import YouTubeDownloader, DownloadCancelledError
from src.audio.ffmpeg_converter import FFmpegService, FFmpegError, ConversionCancelledError
from src.audio.inspector import inspect_audio_file
from src.audio.exporter import export_all_stems, sanitize_stem_slug
from src.separator.demucs_engine import DemucsEngine, CancellationRequestedError


class UnifiedPipelineWorker(QThread):
    """
    Worker em thread separada que executa todas as etapas do pipeline sem travar a interface Qt:
    1. Obtenção do áudio (Download YouTube ou Arquivo Local).
    2. Conversão e preparação para WAV 44.1kHz estéreo via FFmpeg.
    3. Separação neural por IA via DemucsEngine.
    4. Organização e exportação automática dos resultados na pasta de destino.
    """

    # Sinais do Qt
    sig_stage_changed = Signal(str, str)             # stage_id ('download', 'convert', 'separate', 'organize'), stage_name
    sig_progress = Signal(int, str)                  # percentual geral (0-100), mensagem de status
    sig_download_details = Signal(dict)              # dict com velocidade, ETA, bytes baixados
    sig_finished = Signal(object, int, object, str)  # stems_dict, sample_rate, metadata, output_dir
    sig_error = Signal(str)                          # mensagem de erro
    sig_cancelled = Signal()                         # cancelamento concluído com sucesso

    def __init__(
        self,
        mode: str,  # "url" ou "file"
        source: str,  # URL do YouTube ou caminho do arquivo local
        output_base_dir: str = "output",
        model_name: str = "htdemucs",
        device_name: Optional[str] = None,
        shifts: int = 1,
        overlap: float = 0.25,
        match_sample_rate: bool = False,
        parent=None
    ):
        super().__init__(parent)
        self.mode = mode
        self.source = source
        self.output_base_dir = os.path.abspath(output_base_dir)
        self.model_name = model_name
        self.device_name = device_name
        self.shifts = shifts
        self.overlap = overlap
        self.match_sample_rate = match_sample_rate

        self._is_cancelled = False
        self._temp_dir: Optional[str] = None

        # Instâncias dos serviços
        self.downloader = YouTubeDownloader()
        self.ffmpeg = FFmpegService()
        self.engine = DemucsEngine()

    def cancel(self):
        """Solicita o cancelamento gracioso de qualquer etapa em execução."""
        self._is_cancelled = True
        self.downloader.cancel()
        self.ffmpeg.cancel()

    def is_cancelled(self) -> bool:
        return self._is_cancelled

    def _cleanup_temp(self):
        """Remove diretório temporário se existir."""
        if self._temp_dir and os.path.exists(self._temp_dir):
            try:
                shutil.rmtree(self._temp_dir, ignore_errors=True)
            except Exception:
                pass
            self._temp_dir = None

    def run(self):
        """Execução sequencial das etapas do pipeline em segundo plano."""
        if self._is_cancelled:
            self.sig_cancelled.emit()
            return

        self._temp_dir = tempfile.mkdtemp(prefix="separador_pipe_")
        target_song_folder = ""

        try:
            prepared_wav_path = ""
            song_title = "audio"
            meta: Dict[str, Any] = {}

            # =================================================================
            # ETAPA 1 & 2: OBTENÇÃO E PREPARAÇÃO DO ÁUDIO
            # =================================================================
            if self.mode == "url":
                if not self.downloader.is_valid_url(self.source):
                    raise ValueError(f"A URL informada não é uma URL válida do YouTube:\n{self.source}")

                # 1.1 Download
                self.sig_stage_changed.emit("download", "Baixando áudio do YouTube...")
                self.sig_progress.emit(5, "Iniciando download do áudio...")

                def on_dl_progress(d: dict):
                    if self._is_cancelled:
                        raise DownloadCancelledError()
                    if d.get("status") == "downloading":
                        dl_pct = d.get("percent", 0.0)
                        # Mapear 0-100% do download para 5-25% do progresso geral
                        global_pct = int(5 + (dl_pct / 100.0) * 20)
                        speed = d.get("speed_str", "")
                        eta = d.get("eta_str", "")
                        msg = f"Baixando áudio: {dl_pct:.1f}% ({speed} • ETA: {eta})"
                        self.sig_progress.emit(global_pct, msg)
                        self.sig_download_details.emit(d)

                downloaded_file = self.downloader.download_audio(
                    url=self.source,
                    output_dir=self._temp_dir,
                    progress_callback=on_dl_progress,
                    cancel_check=self.is_cancelled
                )

                if self._is_cancelled:
                    raise DownloadCancelledError()

                # Obter nome limpo do arquivo baixado
                base_name = os.path.splitext(os.path.basename(downloaded_file))[0]
                # Remover id do final se existir
                clean_title = self.downloader.sanitize_filename(base_name)
                song_title = clean_title

                # 1.2 Conversão via FFmpeg
                self.sig_stage_changed.emit("convert", "Preparando e normalizando áudio via FFmpeg...")
                self.sig_progress.emit(28, "Convertendo fluxo de áudio para formato mestre (WAV 44.1kHz)...")

                target_song_folder = os.path.join(self.output_base_dir, song_title)
                os.makedirs(target_song_folder, exist_ok=True)
                target_original_wav = os.path.join(target_song_folder, "original.wav")

                prepared_wav_path = self.ffmpeg.prepare_for_demucs(
                    input_filepath=downloaded_file,
                    output_filepath=target_original_wav,
                    sample_rate=44100,
                    channels=2,
                    bit_depth="pcm_s24le",
                    progress_callback=lambda msg: self.sig_progress.emit(32, msg),
                    cancel_check=self.is_cancelled
                )

            else:
                # Modo Arquivo Local
                if not os.path.exists(self.source):
                    raise FileNotFoundError(f"Arquivo não encontrado: {self.source}")

                base_filename = os.path.splitext(os.path.basename(self.source))[0]
                song_title = self.downloader.sanitize_filename(base_filename)
                target_song_folder = os.path.join(self.output_base_dir, song_title)
                os.makedirs(target_song_folder, exist_ok=True)
                target_original_wav = os.path.join(target_song_folder, "original.wav")

                # Se o arquivo não for WAV ou precisar de conformidade com FFmpeg
                is_wav = self.source.lower().endswith((".wav", ".wave"))
                if not is_wav:
                    self.sig_stage_changed.emit("convert", "Convertendo arquivo local para WAV via FFmpeg...")
                    self.sig_progress.emit(10, f"Convertendo {os.path.basename(self.source)}...")
                    prepared_wav_path = self.ffmpeg.prepare_for_demucs(
                        input_filepath=self.source,
                        output_filepath=target_original_wav,
                        sample_rate=44100,
                        channels=2,
                        bit_depth="pcm_s24le",
                        progress_callback=lambda msg: self.sig_progress.emit(20, msg),
                        cancel_check=self.is_cancelled
                    )
                else:
                    # É WAV: copiar como original.wav para a pasta de destino
                    shutil.copy2(self.source, target_original_wav)
                    prepared_wav_path = target_original_wav

            if self._is_cancelled:
                raise CancellationRequestedError()

            # Inspecionar metadados do WAV preparado
            meta = inspect_audio_file(prepared_wav_path)

            # =================================================================
            # ETAPA 3: SEPARAÇÃO NEURAL POR IA (DEMUCS)
            # =================================================================
            self.sig_stage_changed.emit("separate", "Separando faixas musicais com IA (Demucs)...")
            self.sig_progress.emit(35, "Iniciando processamento neural das faixas...")

            def on_demucs_progress(pct: int, msg: str):
                if self._is_cancelled:
                    raise CancellationRequestedError()
                # Mapear 0-100% do Demucs para 35-90% do progresso geral
                global_pct = int(35 + (pct / 100.0) * 55)
                self.sig_progress.emit(global_pct, msg)

            stems, sample_rate, _ = self.engine.separate(
                filepath=prepared_wav_path,
                model_name=self.model_name,
                device_name=self.device_name,
                shifts=self.shifts,
                overlap=self.overlap,
                progress_callback=on_demucs_progress,
                cancel_check=self.is_cancelled
            )

            if self._is_cancelled:
                raise CancellationRequestedError()

            # =================================================================
            # ETAPA 4: ORGANIZAÇÃO DOS RESULTADOS NA PASTA FINAL
            # =================================================================
            self.sig_stage_changed.emit("organize", "Organizando e salvando faixas separadas...")
            self.sig_progress.emit(92, "Gravando faixas individuais em alta fidelidade...")

            export_all_stems(
                stems=stems,
                stem_sample_rate=sample_rate,
                output_directory=target_song_folder,
                base_name=song_title,
                original_metadata=meta,
                match_original_sample_rate=self.match_sample_rate
            )

            self.sig_stage_changed.emit("done", "Concluído com sucesso!")
            self.sig_progress.emit(100, f"Processamento concluído! Resultados em: {target_song_folder}")
            self.sig_finished.emit(stems, sample_rate, meta, target_song_folder)

        except (DownloadCancelledError, ConversionCancelledError, CancellationRequestedError):
            self.sig_cancelled.emit()
            # Se cancelou, remover diretório de saída parcial caso esteja vazio ou incompleto
            if target_song_folder and os.path.exists(target_song_folder):
                try:
                    # Só remove se não tiver stems completos
                    shutil.rmtree(target_song_folder, ignore_errors=True)
                except Exception:
                    pass

        except MemoryError:
            self.sig_error.emit(
                "Memória RAM/VRAM insuficiente para processar este áudio com o modelo selecionado.\n"
                "Dica: Selecione um modelo mais leve (ex: htdemucs padrão) e feche outros programas."
            )
        except Exception as e:
            self.sig_error.emit(f"Falha no processamento: {str(e)}")

        finally:
            self._cleanup_temp()
