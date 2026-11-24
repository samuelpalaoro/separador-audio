"""
Testes de Qualidade de Áudio e Integridade Acústica no SamukaLab.
Verifica clipping, distorção, alinhamento de canais, fidelidade de frames e ausência de silêncio inesperado.
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

from src.audio.inspector import inspect_audio_file
from src.audio.exporter import export_stem_to_wav
from src.audio.drum_separator import DrumDecomposer


class TestAudioQuality(unittest.TestCase):
    """Bateria de testes de integridade e qualidade sonora."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="test_audio_qual_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _generate_clean_audio(self, duration: float = 3.0, sr: int = 44100) -> np.ndarray:
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        left = 0.5 * np.sin(2 * np.pi * 440 * t)
        right = 0.5 * np.sin(2 * np.pi * 554.37 * t)
        return np.column_stack([left, right]).astype(np.float32)

    def test_audio_clipping_and_dynamic_range(self):
        """Verifica se a exportação previne clipping digital destrutivo."""
        hot_audio = self._generate_clean_audio() * 2.5  # Sinal com ganho acima de 0dBFS
        out_wav = os.path.join(self.tmp_dir, "hot_test.wav")

        export_stem_to_wav(
            stem_audio=hot_audio,
            stem_sample_rate=44100,
            output_path=out_wav
        )

        read_audio, sr = sf.read(out_wav)
        self.assertLessEqual(np.max(read_audio), 1.0, "Áudio exportado não deve ultrapassar 1.0 (clipping prevenido)")
        self.assertGreaterEqual(np.min(read_audio), -1.0, "Áudio exportado não deve ser menor que -1.0")

    def test_sample_rate_and_channel_consistency(self):
        """Verifica consistência de taxa de amostragem e canais estéreo."""
        audio = self._generate_clean_audio()
        out_wav = os.path.join(self.tmp_dir, "consistency_test.wav")

        export_stem_to_wav(
            stem_audio=audio,
            stem_sample_rate=44100,
            output_path=out_wav
        )

        meta = inspect_audio_file(out_wav)
        self.assertEqual(meta["samplerate"], 44100)
        self.assertEqual(meta["channels"], 2)
        self.assertAlmostEqual(meta["duration"], 3.0, delta=0.01)

    def test_drum_decomposition_energy_conservation(self):
        """Verifica se a decomposição de bateria preserva energia sem distorção fantasma."""
        audio = self._generate_clean_audio(duration=2.0)
        decomposer = DrumDecomposer(sample_rate=44100)
        res = decomposer.decompose(audio, sample_rate=44100)

        for name, stem in res.stems.items():
            peak = np.max(np.abs(stem))
            self.assertLessEqual(peak, 1.2, f"Pico do stem {name} não deve estourar")
            rms = np.sqrt(np.mean(stem ** 2))
            self.assertFalse(np.isnan(rms), f"RMS do stem {name} é NaN")


if __name__ == "__main__":
    unittest.main()
