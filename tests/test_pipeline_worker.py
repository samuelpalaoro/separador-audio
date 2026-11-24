"""
Testes unitários e de integração para o UnifiedPipelineWorker.
"""
import os
import sys
import unittest
import tempfile
import numpy as np
import soundfile as sf
from PySide6.QtWidgets import QApplication

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from src.separator.pipeline_worker import UnifiedPipelineWorker


class TestUnifiedPipelineWorker(unittest.TestCase):
    """Testes para o pipeline assíncrono unificado."""

    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="test_worker_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _generate_test_audio(self, filename: str, sr: int = 44100, duration: float = 1.0) -> str:
        """Gera um arquivo de áudio curto para testes rápidos."""
        filepath = os.path.join(self.tmp_dir, filename)
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        sig = 0.3 * np.sin(2 * np.pi * 220 * t)
        stereo = np.column_stack([sig, sig])
        sf.write(filepath, stereo, sr, subtype="PCM_16", format="WAV")
        return filepath

    def test_pipeline_local_file_execution(self):
        """Testa o processamento completo de um arquivo local via UnifiedPipelineWorker."""
        src_path = self._generate_test_audio("sample_song.wav", duration=1.0)
        output_dir = os.path.join(self.tmp_dir, "output")

        worker = UnifiedPipelineWorker(
            mode="file",
            source=src_path,
            output_base_dir=output_dir,
            model_name="htdemucs"
        )

        stages_recorded = []
        progress_recorded = []
        result_holder = {}

        worker.sig_stage_changed.connect(lambda stage_id, label: stages_recorded.append(stage_id))
        worker.sig_progress.connect(lambda pct, msg: progress_recorded.append(pct))
        worker.sig_finished.connect(lambda stems, sr, meta, folder: result_holder.update({
            "stems": stems,
            "sr": sr,
            "folder": folder
        }))

        # Executa síncrono para o teste
        worker.run()

        # Verificar se as etapas foram reportadas
        self.assertIn("separate", stages_recorded)
        self.assertIn("organize", stages_recorded)
        self.assertIn("done", stages_recorded)

        # Verificar resultados
        self.assertIn("stems", result_holder)
        stems = result_holder["stems"]
        self.assertIn("Vocals (Voz)", stems)
        self.assertIn("Drums (Bateria)", stems)
        self.assertIn("Bass (Baixo)", stems)
        self.assertIn("Other (Outros)", stems)

        # Verificar arquivos salvos na pasta organizada
        folder = result_holder["folder"]
        self.assertTrue(os.path.isdir(folder))
        files = os.listdir(folder)
        self.assertIn("original.wav", files)
        # Deve ter gerado os stems em WAV
        wav_files = [f for f in files if f.endswith(".wav")]
        self.assertGreaterEqual(len(wav_files), 5)  # original + 4 stems

    def test_pipeline_cancellation(self):
        """Testa o cancelamento durante o pipeline."""
        src_path = self._generate_test_audio("sample_song2.wav", duration=2.0)
        output_dir = os.path.join(self.tmp_dir, "output_cancel")

        worker = UnifiedPipelineWorker(
            mode="file",
            source=src_path,
            output_base_dir=output_dir,
            model_name="htdemucs"
        )

        cancelled_called = []
        worker.sig_cancelled.connect(lambda: cancelled_called.append(True))

        # Dispara cancelamento imediatamente
        worker.cancel()
        worker.run()

        self.assertTrue(cancelled_called, "O sinal sig_cancelled deveria ter sido emitido.")


if __name__ == "__main__":
    unittest.main()
