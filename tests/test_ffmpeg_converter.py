"""
Testes unitários e de integração para o serviço FFmpegService.
"""
import os
import sys
import unittest
import tempfile
import numpy as np
import soundfile as sf

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from src.audio.ffmpeg_converter import FFmpegService, FFmpegError, ConversionCancelledError


class TestFFmpegService(unittest.TestCase):
    """Testes para o conversor FFmpeg."""

    def setUp(self):
        self.service = FFmpegService()
        self.tmp_dir = tempfile.mkdtemp(prefix="test_ffmpeg_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _generate_dummy_audio(self, filename: str, sr: int = 48000, duration: float = 2.0) -> str:
        """Gera um arquivo de áudio para teste."""
        filepath = os.path.join(self.tmp_dir, filename)
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        sig = 0.5 * np.sin(2 * np.pi * 440 * t)
        sig_stereo = np.column_stack([sig, sig])
        sf.write(filepath, sig_stereo, sr, subtype="PCM_16", format="WAV")
        return filepath

    def test_ffmpeg_availability_and_version(self):
        """Verifica se o FFmpeg está instalado e retorna a versão."""
        self.assertTrue(self.service.is_available(), "FFmpeg deveria estar disponível no sistema.")
        version = self.service.get_version()
        self.assertIn("ffmpeg", version.lower())

    def test_conversion_to_demucs_format(self):
        """Testa conversão de áudio de 48kHz para 44.1kHz estéreo 24-bit."""
        src_path = self._generate_dummy_audio("source_48k.wav", sr=48000, duration=2.5)
        out_path = os.path.join(self.tmp_dir, "converted_44k.wav")

        result = self.service.prepare_for_demucs(
            input_filepath=src_path,
            output_filepath=out_path,
            sample_rate=44100,
            channels=2,
            bit_depth="pcm_s24le"
        )

        self.assertEqual(result, os.path.abspath(out_path))
        self.assertTrue(os.path.exists(out_path))

        # Inspecionar resultado com soundfile
        info = sf.info(out_path)
        self.assertEqual(info.samplerate, 44100)
        self.assertEqual(info.channels, 2)
        self.assertIn("24", info.subtype)
        self.assertAlmostEqual(info.duration, 2.5, delta=0.05)

    def test_conversion_nonexistent_input(self):
        """Testa se arquivo inexistente gera FileNotFoundError."""
        out_path = os.path.join(self.tmp_dir, "out.wav")
        with self.assertRaises(FileNotFoundError):
            self.service.prepare_for_demucs(
                input_filepath=os.path.join(self.tmp_dir, "does_not_exist.mp3"),
                output_filepath=out_path
            )

    def test_conversion_corrupt_file(self):
        """Testa se arquivo com lixo gera FFmpegError e limpa resíduos."""
        corrupt_path = os.path.join(self.tmp_dir, "corrupt.mp3")
        with open(corrupt_path, "wb") as f:
            f.write(b"not an audio file at all!")

        out_path = os.path.join(self.tmp_dir, "out_corrupt.wav")
        with self.assertRaises(FFmpegError):
            self.service.prepare_for_demucs(
                input_filepath=corrupt_path,
                output_filepath=out_path
            )
        self.assertFalse(os.path.exists(out_path), "Arquivo de saída parcial deveria ter sido removido.")

    def test_conversion_cancellation_before_start(self):
        """Testa cancelamento antes do início."""
        src_path = self._generate_dummy_audio("source.wav")
        out_path = os.path.join(self.tmp_dir, "out_cancel.wav")

        with self.assertRaises(ConversionCancelledError):
            self.service.prepare_for_demucs(
                input_filepath=src_path,
                output_filepath=out_path,
                cancel_check=lambda: True
            )
        self.assertFalse(os.path.exists(out_path))


if __name__ == "__main__":
    unittest.main()
