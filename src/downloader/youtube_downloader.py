"""
Módulo de integração segura com a biblioteca yt-dlp para download de áudio do YouTube.
"""
import os
import re
import unicodedata
from typing import Dict, Any, Optional, Callable
import yt_dlp
from PySide6.QtCore import QThread, Signal


class InfoFetcherWorker(QThread):
    """Worker assíncrono para obter metadados do YouTube sem congelar a interface."""
    sig_info_ready = Signal(dict)
    sig_error = Signal(str)

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.url = url
        self.downloader = YouTubeDownloader()

    def run(self):
        try:
            info = self.downloader.get_video_info(self.url)
            self.sig_info_ready.emit(info)
        except Exception as e:
            self.sig_error.emit(str(e))



class DownloadCancelledError(Exception):
    """Exceção levantada quando o cancelamento do download é solicitado pelo usuário."""
    pass


class YouTubeDownloader:
    """
    Gerencia validação de URLs, extração de metadados e download
    exclusivo do fluxo de áudio utilizando a API Python oficial do yt-dlp.
    """

    # Padrão regex para URLs válidas do YouTube
    YOUTUBE_REGEX = re.compile(
        r'^(https?://)?(www\.|m\.|music\.)?(youtube\.com/(watch\?v=|embed/|v/|shorts/)|youtu\.be/)([\w\-]{11})([?&].*)?$',
        re.IGNORECASE
    )

    def __init__(self):
        self._cancel_requested = False

    def cancel(self):
        """Solicita a interrupção imediata do download em andamento."""
        self._cancel_requested = True

    def reset_cancellation(self):
        """Redefine a flag de cancelamento para novas operações."""
        self._cancel_requested = False

    @classmethod
    def is_valid_url(cls, url: str) -> bool:
        """Verifica se a URL fornecida é uma URL sintaticamente válida do YouTube."""
        if not url or not isinstance(url, str):
            return False
        clean_url = url.strip()
        return bool(cls.YOUTUBE_REGEX.match(clean_url))

    @classmethod
    def extract_video_id(cls, url: str) -> Optional[str]:
        """Extrai o identificador do vídeo (11 caracteres) a partir da URL."""
        if not url:
            return None
        match = cls.YOUTUBE_REGEX.match(url.strip())
        if match:
            return match.group(5)
        return None

    @classmethod
    def sanitize_filename(cls, name: str, max_length: int = 100) -> str:
        """
        Sanitiza o título da faixa para uso seguro em pastas e arquivos no Linux.
        Remove caracteres reservados, normaliza acentos e limita tamanho.
        """
        if not name:
            return "audio"
        # Normalizar unicode (NFC)
        name = unicodedata.normalize('NFC', name)
        # Substituir caracteres proibidos por underscore
        clean = re.sub(r'[\\/*?:"<>|\0]', '_', name)
        # Reduzir múltiplos espaços e underscores consecutivos
        clean = re.sub(r'[\s_]+', '_', clean).strip('_ .')
        if not clean:
            clean = "audio"
        return clean[:max_length]

    def get_video_info(self, url: str) -> Dict[str, Any]:
        """
        Extrai metadados do vídeo (título, duração, canal, thumbnail)
        sem efetuar download do fluxo de mídia.
        """
        if not self.is_valid_url(url):
            raise ValueError(f"URL inválida para o YouTube: '{url}'")

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'skip_download': True,
            'noplaylist': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url.strip(), download=False)
                if not info:
                    raise ValueError("Não foi possível obter informações do vídeo.")

                # Tratar caso seja uma playlist e retorne múltiplos itens
                if 'entries' in info and info['entries']:
                    info = info['entries'][0]

                raw_title = info.get('title') or "Sem Título"
                duration = int(info.get('duration') or 0)
                channel = info.get('uploader') or info.get('channel') or "Desconhecido"
                video_id = info.get('id') or self.extract_video_id(url) or "video"
                thumbnail = info.get('thumbnail') or ""

                return {
                    "id": video_id,
                    "title": raw_title,
                    "clean_title": self.sanitize_filename(raw_title),
                    "duration": duration,
                    "channel": channel,
                    "thumbnail": thumbnail,
                    "url": url.strip(),
                }

        except yt_dlp.utils.DownloadError as e:
            err_msg = str(e)
            if "Private video" in err_msg:
                raise ValueError("Este vídeo é privado e não pode ser acessado.") from e
            elif "Video unavailable" in err_msg:
                raise ValueError("O vídeo solicitado não está disponível no YouTube.") from e
            elif "Sign in to confirm your age" in err_msg:
                raise ValueError("Este vídeo possui restrição de idade do YouTube.") from e
            raise ValueError(f"Erro ao obter informações do vídeo: {err_msg}") from e
        except Exception as e:
            raise ValueError(f"Falha ao consultar URL: {str(e)}") from e

    def download_audio(
        self,
        url: str,
        output_dir: str,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> str:
        """
        Baixa exclusivamente a melhor faixa de áudio da URL fornecida.
        
        Args:
            url: URL válida do YouTube.
            output_dir: Diretório onde o arquivo bruto de áudio será gravado.
            progress_callback: Função que recebe dict com status, percent, speed_str, eta_str.
            cancel_check: Função opcional que retorna True caso o cancelamento tenha sido solicitado.
            
        Returns:
            Caminho absoluto do arquivo de áudio baixado.
        """
        self.reset_cancellation()
        os.makedirs(output_dir, exist_ok=True)

        info = self.get_video_info(url)
        clean_name = info["clean_title"]
        video_id = info["id"]
        
        # Padrão de saída nomeando com o clean_title e video_id para unicidade
        outtmpl = os.path.join(output_dir, f"{clean_name}_{video_id}.%(ext)s")

        def hook(d: dict):
            if self._cancel_requested or (cancel_check and cancel_check()):
                raise DownloadCancelledError("Download cancelado pelo usuário.")

            status = d.get('status')
            if status == 'downloading':
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded_bytes = d.get('downloaded_bytes') or 0
                speed = d.get('speed') or 0
                eta = d.get('eta') or 0

                percent = 0.0
                if total_bytes > 0:
                    percent = min(100.0, (downloaded_bytes / total_bytes) * 100.0)

                speed_str = f"{speed / 1024 / 1024:.1f} MB/s" if speed > 1024 * 1024 else f"{speed / 1024:.0f} kB/s"
                eta_str = f"{eta}s" if eta else "--"

                if progress_callback:
                    progress_callback({
                        "status": "downloading",
                        "percent": percent,
                        "downloaded_bytes": downloaded_bytes,
                        "total_bytes": total_bytes,
                        "speed_str": speed_str,
                        "eta_str": eta_str,
                        "title": info["title"],
                        "clean_title": clean_name,
                        "duration": info["duration"]
                    })
            elif status == 'finished':
                if progress_callback:
                    progress_callback({
                        "status": "finished",
                        "percent": 100.0,
                        "title": info["title"],
                        "clean_title": clean_name,
                        "filename": d.get('filename')
                    })

        ydl_opts = {
            # Baixar estritamente a melhor faixa de áudio disponível
            'format': 'bestaudio/best',
            'outtmpl': outtmpl,
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'progress_hooks': [hook],
            'nocheckcertificate': False,
            # Limitar tentativas automáticas em caso de timeout
            'retries': 3,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                download_res = ydl.extract_info(url.strip(), download=True)
                downloaded_path = ydl.prepare_filename(download_res)
                
                # Se o arquivo não existir exatamente com esse caminho (pode mudar de extensão ex: .m4a, .opus, .webm)
                if not os.path.exists(downloaded_path):
                    base, _ = os.path.splitext(downloaded_path)
                    for ext in [".m4a", ".webm", ".opus", ".mp3", ".aac", ".ogg"]:
                        alt = base + ext
                        if os.path.exists(alt):
                            downloaded_path = alt
                            break

                if not os.path.exists(downloaded_path):
                    raise FileNotFoundError(f"Arquivo de áudio baixado não encontrado em: {downloaded_path}")

                return os.path.abspath(downloaded_path)

        except DownloadCancelledError:
            raise
        except yt_dlp.utils.DownloadError as e:
            if self._cancel_requested or (cancel_check and cancel_check()):
                raise DownloadCancelledError("Download cancelado pelo usuário.") from e
            raise RuntimeError(f"Falha durante o download do áudio: {str(e)}") from e
        except Exception as e:
            if self._cancel_requested or (cancel_check and cancel_check()):
                raise DownloadCancelledError("Download cancelado pelo usuário.") from e
            raise RuntimeError(f"Erro inesperado no download: {str(e)}") from e
