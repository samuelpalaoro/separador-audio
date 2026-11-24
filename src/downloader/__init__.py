"""Módulo de download e extração de áudio a partir de fontes externas como YouTube."""
from src.downloader.youtube_downloader import YouTubeDownloader, DownloadCancelledError

__all__ = ["YouTubeDownloader", "DownloadCancelledError"]
