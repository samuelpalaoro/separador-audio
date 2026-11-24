"""
Testes unitários e de integração para o módulo YouTubeDownloader.
"""
import os
import sys
import unittest

# Adicionar raiz do projeto ao path
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from src.downloader.youtube_downloader import YouTubeDownloader, DownloadCancelledError


class TestYouTubeDownloader(unittest.TestCase):
    """Testes para validação, sanitização e cancelamento do YouTubeDownloader."""

    def setUp(self):
        self.downloader = YouTubeDownloader()

    def test_url_validation_valid(self):
        """Testa se URLs válidas em vários formatos do YouTube são aceitas."""
        valid_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "http://youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "http://youtu.be/dQw4w9WgXcQ",
            "https://music.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.youtube.com/shorts/dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s",
            "https://m.youtube.com/watch?v=dQw4w9WgXcQ&feature=share",
            "https://www.youtube.com/embed/dQw4w9WgXcQ",
        ]
        for url in valid_urls:
            with self.subTest(url=url):
                self.assertTrue(
                    self.downloader.is_valid_url(url),
                    f"A URL deveria ser válida: {url}"
                )

    def test_url_validation_invalid(self):
        """Testa se URLs inválidas ou de outras plataformas são rejeitadas."""
        invalid_urls = [
            "",
            None,
            "   ",
            "https://vimeo.com/12345678",
            "https://soundcloud.com/artist/track",
            "https://www.google.com",
            "not_a_url",
            "https://youtube.com/watch?v=short",  # id com menos de 11 chars
            "https://youtube.com/watch?v=longerthan11charactershere",  # id maior que 11 chars
        ]
        for url in invalid_urls:
            with self.subTest(url=url):
                self.assertFalse(
                    self.downloader.is_valid_url(url),
                    f"A URL deveria ser rejeitada: {url}"
                )

    def test_extract_video_id(self):
        """Testa a extração correta do ID do vídeo de 11 caracteres."""
        self.assertEqual(
            self.downloader.extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            "dQw4w9WgXcQ"
        )
        self.assertEqual(
            self.downloader.extract_video_id("https://youtu.be/dQw4w9WgXcQ"),
            "dQw4w9WgXcQ"
        )
        self.assertEqual(
            self.downloader.extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ?feature=share"),
            "dQw4w9WgXcQ"
        )
        self.assertIsNone(self.downloader.extract_video_id("https://google.com"))

    def test_sanitize_filename(self):
        """Testa sanitização de títulos contra caracteres proibidos no Linux/Unix."""
        raw_name = 'Música / Teste * "Ao Vivo" : Edição Especial ? <Full> | Track #1'
        sanitized = self.downloader.sanitize_filename(raw_name)
        
        # Não deve conter caracteres proibidos
        for char in ['/', '\\', '*', '"', ':', '<', '>', '|', '\0', '?']:
            self.assertNotIn(char, sanitized)

        # Não deve ser vazio
        self.assertTrue(len(sanitized) > 0)

        # Deve limitar o tamanho respeitando max_length
        long_title = "A" * 200
        limited = self.downloader.sanitize_filename(long_title, max_length=50)
        self.assertEqual(len(limited), 50)

    def test_invalid_url_raises_error(self):
        """Testa se chamar get_video_info com URL inválida levanta ValueError."""
        with self.assertRaises(ValueError):
            self.downloader.get_video_info("https://vimeo.com/123456")

    def test_cancellation_flag(self):
        """Testa a mecânica das flags de cancelamento."""
        downloader = YouTubeDownloader()
        self.assertFalse(downloader._cancel_requested)
        downloader.cancel()
        self.assertTrue(downloader._cancel_requested)
        downloader.reset_cancellation()
        self.assertFalse(downloader._cancel_requested)


if __name__ == "__main__":
    unittest.main()
