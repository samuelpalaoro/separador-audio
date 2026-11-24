"""
Módulo de serviço e conversão de áudio baseado no FFmpeg.
Fornece preparação, normalização de formato e conversão segura para WAV estéreo 44.1kHz.
"""
import os
import shutil
import subprocess
import signal
from typing import Optional, Callable, Dict, Any, List
import soundfile as sf


class FFmpegError(Exception):
    """Exceção levantada quando ocorre erro durante a execução do FFmpeg."""
    pass


class ConversionCancelledError(Exception):
    """Exceção levantada quando a conversão é cancelada pelo usuário."""
    pass


class FFmpegService:
    """
    Wrapper seguro para operações com o utilitário FFmpeg no sistema operacional Linux.
    Não utiliza shell=True para prevenir riscos de segurança por command injection.
    """

    def __init__(self, ffmpeg_path: Optional[str] = None):
        self.ffmpeg_bin = ffmpeg_path or shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
        self._current_process: Optional[subprocess.Popen] = None
        self._cancel_requested = False

    def is_available(self) -> bool:
        """Verifica se o binário do FFmpeg está presente e executável."""
        if not self.ffmpeg_bin or not os.path.isfile(self.ffmpeg_bin):
            return False
        return os.access(self.ffmpeg_bin, os.X_OK)

    def get_version(self) -> str:
        """Retorna a versão do FFmpeg instalada no sistema."""
        if not self.is_available():
            return "FFmpeg não instalado"
        try:
            res = subprocess.run(
                [self.ffmpeg_bin, "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            first_line = res.stdout.splitlines()[0] if res.stdout else "Desconhecido"
            return first_line
        except Exception as e:
            return f"Erro ao detectar versão: {str(e)}"

    def cancel(self):
        """Cancela a conversão ativa terminando o processo do FFmpeg."""
        self._cancel_requested = True
        proc = self._current_process
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    proc.kill()
            except Exception:
                pass

    def reset_cancellation(self):
        """Redefine a flag de cancelamento."""
        self._cancel_requested = False
        self._current_process = None

    def prepare_for_demucs(
        self,
        input_filepath: str,
        output_filepath: str,
        sample_rate: int = 44100,
        channels: int = 2,
        bit_depth: str = "pcm_s24le",
        progress_callback: Optional[Callable[[str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> str:
        """
        Converte e prepara o áudio para separação no Demucs.
        Gera um arquivo WAV estéreo com sample rate fixado em 44.1 kHz
        e PCM de 24-bit (ou 16-bit), eliminando streams de vídeo.
        
        Args:
            input_filepath: Arquivo de entrada (qualquer formato legível pelo FFmpeg).
            output_filepath: Caminho do arquivo WAV de saída.
            sample_rate: Taxa de amostragem padrão do Demucs (44100 Hz).
            channels: Número de canais (2 para estéreo).
            bit_depth: Codec PCM ('pcm_s24le' para 24-bit ou 'pcm_s16le' para 16-bit).
            progress_callback: Função que recebe mensagens de status.
            cancel_check: Função que indica se deve cancelar.
            
        Returns:
            Caminho absoluto do arquivo WAV preparado.
        """
        self.reset_cancellation()

        if not self.is_available():
            raise FFmpegError(
                "O executável do FFmpeg não foi encontrado no sistema.\n"
                "Instale-o executando: sudo apt install ffmpeg"
            )

        if not os.path.exists(input_filepath):
            raise FileNotFoundError(f"Arquivo de entrada não encontrado: {input_filepath}")

        os.makedirs(os.path.dirname(os.path.abspath(output_filepath)), exist_ok=True)

        if cancel_check and cancel_check():
            raise ConversionCancelledError("Conversão cancelada antes de iniciar.")

        if progress_callback:
            progress_callback("Iniciando conversão com FFmpeg...")

        # Montagem segura da lista de argumentos
        # -vn: sem vídeo
        # -acodec: pcm_s24le (alta resolução sem compressão)
        # -ar: sample_rate (44100 Hz)
        # -ac: channels (2 canais estéreo)
        # -y: sobrescrever saída temporária
        cmd: List[str] = [
            self.ffmpeg_bin,
            "-y",
            "-i", os.path.abspath(input_filepath),
            "-vn",
            "-acodec", bit_depth,
            "-ar", str(sample_rate),
            "-ac", str(channels),
            os.path.abspath(output_filepath)
        ]

        try:
            self._current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Aguardar processo monitorando cancelamento
            while self._current_process.poll() is None:
                if self._cancel_requested or (cancel_check and cancel_check()):
                    self.cancel()
                    # Remover arquivo parcial incompleto
                    if os.path.exists(output_filepath):
                        try:
                            os.remove(output_filepath)
                        except OSError:
                            pass
                    raise ConversionCancelledError("Conversão interrompida pelo usuário.")
                try:
                    self._current_process.wait(timeout=0.2)
                except subprocess.TimeoutExpired:
                    continue

            _, stderr = self._current_process.communicate()

            if self._cancel_requested or (cancel_check and cancel_check()):
                if os.path.exists(output_filepath):
                    try:
                        os.remove(output_filepath)
                    except OSError:
                        pass
                raise ConversionCancelledError("Conversão interrompida pelo usuário.")

            if self._current_process.returncode != 0:
                # Captura as últimas linhas de erro do stderr
                lines = stderr.strip().splitlines()
                err_tail = "\n".join(lines[-5:]) if lines else "Código de saída diferente de zero."
                if os.path.exists(output_filepath):
                    try:
                        os.remove(output_filepath)
                    except OSError:
                        pass
                raise FFmpegError(f"Falha na conversão de áudio via FFmpeg:\n{err_tail}")

            # Validar arquivo gerado
            if not os.path.exists(output_filepath) or os.path.getsize(output_filepath) == 0:
                raise FFmpegError("O FFmpeg concluiu a execução mas o arquivo de saída está vazio ou não foi criado.")

            # Validação via soundfile
            try:
                info = sf.info(output_filepath)
                if info.frames == 0 or info.samplerate != sample_rate:
                    raise FFmpegError(f"Arquivo gerado possui dados inconsistentes: {info.frames} frames, {info.samplerate} Hz")
            except Exception as e:
                raise FFmpegError(f"Arquivo de áudio convertido é inválido: {str(e)}") from e

            if progress_callback:
                progress_callback("Áudio preparado e validado com sucesso!")

            return os.path.abspath(output_filepath)

        finally:
            self._current_process = None
