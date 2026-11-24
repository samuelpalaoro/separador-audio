"""
Testes unitários para o módulo de segurança e validação SecurityValidator.
"""
import os
import sys
import unittest
import tempfile

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from src.security.validator import SecurityValidator, SecurityValidationError


class TestSecurityValidator(unittest.TestCase):
    """Testes rigorosos de validação de segurança."""

    def test_url_ssrf_and_protocol_blocking(self):
        """Testa bloqueio de SSRF e protocolos perigosos."""
        blocked_urls = [
            "file:///etc/passwd",
            "ftp://ftp.example.com/audio.wav",
            "http://127.0.0.1/audio",
            "http://localhost:8080/exploit",
            "http://192.168.1.1/router",
            "http://10.0.0.5/internal",
            "http://169.254.169.254/latest/meta-data/",
            "https://attacker.com/malicious",
            "javascript:alert(1)"
        ]
        for url in blocked_urls:
            with self.subTest(url=url):
                with self.assertRaises(SecurityValidationError):
                    SecurityValidator.validate_url(url)

    def test_url_allowed_youtube_domains(self):
        """Testa se domínios válidos do YouTube passam sem erros."""
        allowed_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://music.youtube.com/watch?v=dQw4w9WgXcQ",
            "http://m.youtube.com/watch?v=dQw4w9WgXcQ"
        ]
        for url in allowed_urls:
            with self.subTest(url=url):
                valid = SecurityValidator.validate_url(url)
                self.assertEqual(valid, url)

    def test_path_traversal_prevention(self):
        """Testa prevenção de Path Traversal."""
        with tempfile.TemporaryDirectory() as tmp_base:
            # Caminho válido dentro da pasta
            valid_target = os.path.join(tmp_base, "minha_musica", "original.wav")
            checked = SecurityValidator.ensure_path_within_directory(tmp_base, valid_target)
            self.assertEqual(checked, os.path.abspath(valid_target))

            # Tentativas de evasão
            evil_target = os.path.join(tmp_base, "..", "etc", "passwd")
            with self.assertRaises(SecurityValidationError):
                SecurityValidator.ensure_path_within_directory(tmp_base, evil_target)

            evil_target2 = os.path.join(tmp_base, "sub", "..", "..", "root")
            with self.assertRaises(SecurityValidationError):
                SecurityValidator.ensure_path_within_directory(tmp_base, evil_target2)

    def test_sanitize_slug(self):
        """Testa sanitização de títulos."""
        dirty = "../../etc/passwd: Faixa * <Demo>? 01 | 2026"
        clean = SecurityValidator.sanitize_path_slug(dirty)
        self.assertNotIn("..", clean)
        self.assertNotIn("/", clean)
        self.assertNotIn("\\", clean)
        self.assertNotIn(":", clean)
        self.assertNotIn("*", clean)

    def test_magic_bytes_detection(self):
        """Testa detecção e validação de magic bytes reais."""
        with tempfile.TemporaryDirectory() as tmp:
            # Arquivo WAV legítimo
            wav_path = os.path.join(tmp, "good.wav")
            with open(wav_path, "wb") as f:
                f.write(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00")
            ok, fmt = SecurityValidator.validate_file_header_magic_bytes(wav_path)
            self.assertTrue(ok)
            self.assertEqual(fmt, "WAV")

            # Arquivo falso com extensão .wav
            fake_path = os.path.join(tmp, "fake.wav")
            with open(fake_path, "wb") as f:
                f.write(b"MZ\x90\x00\x03\x00\x00\x00DOS executable file here")
            ok, fmt = SecurityValidator.validate_file_header_magic_bytes(fake_path)
            self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
