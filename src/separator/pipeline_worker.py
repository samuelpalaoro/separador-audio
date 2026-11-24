"""
Worker assíncrono unificado (QThread) para orquestração de download, conversão,
separação de áudio por IA e decomposição experimental de bateria no SamukaLab.
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
from src.audio.exporter import export_all_stems, export_stem_to_wav, sanitize_stem_slug
from src.audio.drum_separator import DrumDecomposer, DrumDecompositionResult
from src.separator.demucs_engine import DemucsEngine, CancellationRequestedError
from src.security.validator import SecurityValidator, SecurityValidationError
from src.security.temp_manager import SafeTempManager
from src.history.project_manager import ProjectHistoryManager
from src.config.settings import SettingsManager


class UnifiedPipelineWorker(QThread):
    """
    Worker em thread separada que executa todas as etapas do pipeline no SamukaLab:
    1. Obtenção do áudio (Download YouTube ou Arquivo Local com verificação de magic bytes).
    2. Conversão e preparação para WAV 44.1kHz estéreo via FFmpeg em diretório temporário seguro.
    3. Separação neural por IA via DemucsEngine.
    4. Decomposição individual de bateria por DSP (quando ativada).
    5. Disponibilização em memória para reprodução e avaliação no mixer (fluxo padrão).
    6. Exportação para disco apenas se solicitada (auto_export=True ou via GUI sob demanda).
    """

    # Sinais do Qt
    sig_stage_changed = Signal(str, str)             # stage_id, stage_name
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
        enable_drum_separation: bool = False,
        auto_export: bool = True,
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
        self.enable_drum_separation = enable_drum_separation
        self.auto_export = auto_export

        self._is_cancelled = False
        self._temp_dir: Optional[str] = None

        # Instâncias dos serviços
        self.temp_mgr = SafeTempManager()
        self.downloader = YouTubeDownloader()
        self.ffmpeg = FFmpegService()
        self.engine = DemucsEngine()
        self.history_mgr = ProjectHistoryManager()
        self.settings_mgr = SettingsManager()

    def cancel(self):
        """Solicita o cancelamento gracioso de qualquer etapa em execução."""
        self._is_cancelled = True
        self.downloader.cancel()
        self.ffmpeg.cancel()

    def is_cancelled(self) -> bool:
        return self._is_cancelled

    def _cleanup_temp(self):
        """Remove diretório temporário registrado sob o SafeTempManager."""
        if self._temp_dir:
            self.temp_mgr.cleanup_session(self._temp_dir)
            self._temp_dir = None

    def run(self):
        """Execução sequencial das etapas do pipeline em segundo plano."""
        if self._is_cancelled:
            self.sig_cancelled.emit()
            return

        self._temp_dir = self.temp_mgr.create_session_dir(prefix="samukalab_pipe_")
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
                    raise ValueError(f"A URL informada não é uma URL válida ou segura do YouTube:\n{self.source}")

                # 1.1 Download
                self.sig_stage_changed.emit("download", "Baixando áudio do YouTube...")
                self.sig_progress.emit(5, "Iniciando download seguro via yt-dlp...")

                def on_dl_progress(d):
                    if self._is_cancelled:
                        raise DownloadCancelledError()
                    if d.get("status") == "downloading":
                        pct = d.get("percent", 0.0)
                        # Mapear 0-100% de download para 5-25% do progresso geral
                        global_pct = int(5 + (pct / 100.0) * 20)
                        self.sig_progress.emit(global_pct, f"Baixando: {pct:.1f}%")
                        self.sig_download_details.emit(d)

                downloaded_file = self.downloader.download_audio(
                    url=self.source,
                    output_dir=self._temp_dir,
                    progress_callback=on_dl_progress,
                    cancel_check=self.is_cancelled
                )

                if self._is_cancelled:
                    raise DownloadCancelledError()

                base_name = os.path.splitext(os.path.basename(downloaded_file))[0]
                clean_title = self.downloader.sanitize_filename(base_name)
                song_title = clean_title

                # 1.2 Conversão via FFmpeg
                self.sig_stage_changed.emit("convert", "Preparando e normalizando áudio via FFmpeg...")
                self.sig_progress.emit(28, "Convertendo fluxo de áudio para formato mestre (WAV 44.1kHz)...")

                if self.auto_export:
                    target_song_folder = os.path.join(self.output_base_dir, song_title)
                    SecurityValidator.ensure_path_within_directory(self.output_base_dir, target_song_folder)
                    os.makedirs(target_song_folder, exist_ok=True)
                    conversion_target_wav = os.path.join(target_song_folder, "original.wav")
                else:
                    conversion_target_wav = os.path.join(self._temp_dir, f"{song_title}_master.wav")

                prepared_wav_path = self.ffmpeg.prepare_for_demucs(
                    input_filepath=downloaded_file,
                    output_filepath=conversion_target_wav,
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

                # Validação de magic bytes para segurança
                valid_magic, fmt_label = SecurityValidator.validate_file_header_magic_bytes(self.source)
                if not valid_magic:
                    raise ValueError(f"O arquivo fornecido não é um áudio válido: {fmt_label}")

                base_filename = os.path.splitext(os.path.basename(self.source))[0]
                song_title = self.downloader.sanitize_filename(base_filename)

                if self.auto_export:
                    target_song_folder = os.path.join(self.output_base_dir, song_title)
                    SecurityValidator.ensure_path_within_directory(self.output_base_dir, target_song_folder)
                    os.makedirs(target_song_folder, exist_ok=True)
                    target_original_wav = os.path.join(target_song_folder, "original.wav")
                else:
                    target_original_wav = os.path.join(self._temp_dir, f"{song_title}_master.wav")

                is_wav = self.source.lower().endswith((".wav", ".wave"))
                if not is_wav:
                    self.sig_stage_changed.emit("convert", f"Convertendo {fmt_label} local para WAV via FFmpeg...")
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
                    if self.auto_export:
                        shutil.copy2(self.source, target_original_wav)
                        prepared_wav_path = target_original_wav
                    else:
                        # Em modo sem auto_export, lê diretamente do arquivo original (somente leitura, preservando o original)
                        prepared_wav_path = self.source

            if self._is_cancelled:
                raise CancellationRequestedError()

            # Inspecionar metadados do WAV preparado
            meta = inspect_audio_file(prepared_wav_path)
            meta["song_title"] = song_title

            # =================================================================
            # ETAPA 3: SEPARAÇÃO NEURAL POR IA (DEMUCS)
            # =================================================================
            self.sig_stage_changed.emit("separate", "Separando faixas musicais com IA (Demucs)...")
            self.sig_progress.emit(35, "Iniciando processamento neural das faixas...")

            def on_demucs_progress(pct: int, msg: str):
                if self._is_cancelled:
                    raise CancellationRequestedError()
                global_pct = int(35 + (pct / 100.0) * 50)
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
            # ETAPA 3.5: DECOMPOSIÇÃO INDIVIDUAL DE BATERIA (SE HABILITADA)
            # =================================================================
            drum_metrics_report = None
            if self.enable_drum_separation:
                # Localizar faixa de bateria
                drum_stem_key = None
                for k in stems.keys():
                    if "drum" in k.lower() or "bater" in k.lower():
                        drum_stem_key = k
                        break

                if drum_stem_key and drum_stem_key in stems:
                    self.sig_stage_changed.emit("drums", "Processando decomposição acústica de bateria (DSP)...")
                    self.sig_progress.emit(87, "Isolando Kick, Snare, Hi-Hats, Cymbals e Toms...")

                    decomposer = DrumDecomposer(sample_rate=sample_rate)
                    drum_res = decomposer.decompose(stems[drum_stem_key], sample_rate=sample_rate)

                    # Adicionar os sub-elementos ao dicionário de stems
                    for drum_elem_name, drum_elem_audio in drum_res.stems.items():
                        stems[f"Drum: {drum_elem_name}"] = drum_elem_audio

                    drum_metrics_report = drum_res
                    meta["drum_metrics_report"] = drum_metrics_report

            if self._is_cancelled:
                raise CancellationRequestedError()

            if self.auto_export:
                # =================================================================
                # ETAPA 4: ORGANIZAÇÃO DOS RESULTADOS NA PASTA FINAL (LEGADO / TESTES)
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

                # Gravar relatório de viabilidade de bateria se aplicável
                if drum_metrics_report:
                    report_path = os.path.join(target_song_folder, "drum_separation_report.txt")
                    try:
                        with open(report_path, "w", encoding="utf-8") as f:
                            f.write("=" * 65 + "\n")
                            f.write("   SAMUKALAB — RELATÓRIO DE DECOMPOSIÇÃO DE BATERIA\n")
                            f.write("=" * 65 + "\n\n")
                            f.write(f"Faixa: {song_title}\n")
                            f.write(f"Taxa de amostragem: {sample_rate} Hz\n\n")
                            f.write("MÉTRICAS DE ENERGIA E CONFIANÇA DE ISOLAMENTO:\n")
                            for elem, met in drum_metrics_report.metrics.items():
                                f.write(f"  • {elem:20s}: Confiança={met['isolation_confidence']:8s} | "
                                        f"Energia={met['energy_ratio']:5.1f}% | Pico={met['peak_amplitude']:.3f}\n")
                            f.write("\n" + "-" * 65 + "\n")
                            f.write("AVALIAÇÃO DE LIMITAÇÃO ACÚSTICA:\n")
                            f.write(drum_metrics_report.limitations_note + "\n")
                            f.write("=" * 65 + "\n")
                    except Exception:
                        pass

                # Registrar no histórico de projetos
                self.history_mgr.add_entry(
                    title=song_title,
                    mode=self.mode,
                    source=self.source,
                    output_dir=target_song_folder,
                    stems_list=list(stems.keys()),
                    duration_s=meta.get("duration", 0.0),
                    model_name=self.model_name,
                    has_drum_separation=self.enable_drum_separation
                )

                self.sig_stage_changed.emit("done", "Concluído com sucesso!")
                self.sig_progress.emit(100, f"Processamento concluído! Resultados em: {target_song_folder}")
                self.sig_finished.emit(stems, sample_rate, meta, target_song_folder)
            else:
                # =================================================================
                # MODO PADRÃO SAMUKALAB: ARMAZENAMENTO TEMPORÁRIO E AVALIAÇÃO NO MIXER
                # Nenhum stem é salvo automaticamente em diretórios permanentes.
                # Stems ficam na memória para audição imediata no mixer sincronizado.
                # =================================================================
                self.sig_stage_changed.emit("done", "Separação neural concluída com sucesso!")
                self.sig_progress.emit(100, "Stems carregados no mixer para reprodução e avaliação!")
                self.sig_finished.emit(stems, sample_rate, meta, "")

        except (DownloadCancelledError, ConversionCancelledError, CancellationRequestedError):
            self.sig_cancelled.emit()
            if self.auto_export and target_song_folder and os.path.exists(target_song_folder):
                try:
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
