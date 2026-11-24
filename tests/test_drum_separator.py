"""
Testes unitários para o módulo de decomposição de bateria DrumDecomposer.
"""
import os
import sys
import unittest
import numpy as np

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from src.audio.drum_separator import DrumDecomposer, DrumDecompositionResult


class TestDrumDecomposer(unittest.TestCase):
    """Testes para decomposição acústica de bateria."""

    def setUp(self):
        self.decomposer = DrumDecomposer(sample_rate=44100)

    def _generate_synthetic_drum_kit(self, duration: float = 2.0, sr: int = 44100) -> np.ndarray:
        """Gera sinal de teste contendo bumbo (60Hz), caixa (250Hz+ruído) e chimbal (9000Hz)."""
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        # Bumbo (60Hz)
        kick = 0.5 * np.sin(2 * np.pi * 60 * t) * (np.sin(2 * np.pi * 2 * t) > 0)
        # Caixa (corpo 220Hz + ruído branco)
        snare = (0.3 * np.sin(2 * np.pi * 220 * t) + 0.2 * np.random.uniform(-1, 1, len(t))) * (np.sin(2 * np.pi * 4 * t) > 0.5)
        # Chimbal (9000Hz)
        hihat = 0.2 * np.sin(2 * np.pi * 9000 * t) * (np.sin(2 * np.pi * 8 * t) > 0.8)

        mix = kick + snare + hihat
        stereo = np.column_stack([mix, mix])
        return stereo.astype(np.float32)

    def test_drum_decomposition_elements(self):
        """Testa se todos os 5 elementos de bateria são gerados com dimensões corretas."""
        audio = self._generate_synthetic_drum_kit(duration=1.5, sr=44100)
        res = self.decomposer.decompose(audio, sample_rate=44100)

        self.assertIsInstance(res, DrumDecompositionResult)
        expected_stems = ["Kick (Bumbo)", "Snare (Caixa)", "Hi-Hats (Chimbal)", "Cymbals (Pratos)", "Toms (Tons)"]
        for stem in expected_stems:
            self.assertIn(stem, res.stems)
            self.assertEqual(res.stems[stem].shape, audio.shape)
            self.assertIn(stem, res.metrics)
            # Não deve ter valores NaN ou Inf
            self.assertFalse(np.isnan(res.stems[stem]).any())
            self.assertFalse(np.isinf(res.stems[stem]).any())

        # Verificar se as notas de limitação acústica estão documentadas
        self.assertIn("bleed", res.limitations_note.lower())


if __name__ == "__main__":
    unittest.main()
