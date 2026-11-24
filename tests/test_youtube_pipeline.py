"""
Bateria de Testes de Integração e Ponta a Ponta:
Integração de yt-dlp, FFmpeg e Separador de Áudio.
"""
import os
import sys
import unittest
import tempfile
import shutil
import numpy as np
import soundfile as sf
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from src.downloader.youtube_downloader import YouTubeDownloader
from src.audio.ffmpeg_converter import FFmpegService
from src.separator.pipeline_worker import UnifiedPipelineWorker
from src.gui.main_window import MainWindow


class TestYouTubePipelineIntegration(unittest.TestCase):
    """Testes completos de integração do pipeline yt-dlp, FFmpeg e Demucs."""

    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="test_yt_pipe_")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _generate_synthetic_audio(self, filename: str, sr: int = 48000, duration: float = 2.0) -> str:
        """Gera um arquivo de áudio para teste com harmônicos."""
        filepath = os.path.join(self.tmp_dir, filename)
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        sig = 0.4 * np.sin(2 * np.pi * 330 * t) + 0.2 * np.sin(2 * np.pi * 660 * t)
        stereo = np.column_stack([sig, sig])
        sf.write(filepath, stereo, sr, subtype="PCM_24", format="WAV")
        return filepath

    def test_1_youtube_downloader_methods(self):
        """Valida métodos fundamentais de verificação e sanitização do YouTubeDownloader."""
        downloader = YouTubeDownloader()
        
        # Testar formatos de URL suportados
        self.assertTrue(downloader.is_valid_url("https://www.youtube.com/watch?v=kJQP7kiw5Fk"))
        self.assertTrue(downloader.is_valid_url("https://youtu.be/kJQP7kiw5Fk"))
        self.assertTrue(downloader.is_valid_url("https://music.youtube.com/watch?v=kJQP7kiw5Fk"))
        self.assertTrue(downloader.is_valid_url("https://www.youtube.com/shorts/kJQP7kiw5Fk"))
        
        # Rejeição de URLs inválidas
        self.assertFalse(downloader.is_valid_url("https://www.google.com"))
        self.assertFalse(downloader.is_valid_url("invalid_url"))

        # Extração de ID
        self.assertEqual(downloader.extract_video_id("https://youtu.be/kJQP7kiw5Fk"), "kJQP7kiw5Fk")

        # Sanitização de título contra injeção e caracteres ilegais
        clean = downloader.sanitize_filename("Música: Faixa / 01 * Teste? <Versão Demo> | 2026")
        for bad_char in ["/", "\\", "*", "?", ":", "<", ">", "|", '"']:
            self.assertNotIn(bad_char, clean)

    def test_2_ffmpeg_conversion_and_integrity(self):
        """Valida se o FFmpegService converte áudio para WAV 44.1kHz estéreo 24-bit perfeitamente."""
        service = FFmpegService()
        self.assertTrue(service.is_available(), "FFmpeg deve estar instalado no sistema.")

        src_audio = self._generate_synthetic_audio("input_48k.wav", sr=48000, duration=2.0)
        dst_audio = os.path.join(self.tmp_dir, "output_44k.wav")

        result = service.prepare_for_demucs(
            input_filepath=src_audio,
            output_filepath=dst_audio,
            sample_rate=44100,
            channels=2,
            bit_depth="pcm_s24le"
        )

        self.assertTrue(os.path.exists(result))
        info = sf.info(result)
        self.assertEqual(info.samplerate, 44100)
        self.assertEqual(info.channels, 2)
        self.assertIn("24", info.subtype)
        self.assertAlmostEqual(info.duration, 2.0, delta=0.05)

    def test_3_unified_worker_end_to_end_local(self):
        """Valida o UnifiedPipelineWorker processando um arquivo local de ponta a ponta com organização de pastas."""
        src_audio = self._generate_synthetic_audio("minha_cancao.wav", sr=44100, duration=1.5)
        out_base = os.path.join(self.tmp_dir, "output")

        worker = UnifiedPipelineWorker(
            mode="file",
            source=src_audio,
            output_base_dir=out_base,
            model_name="htdemucs"
        )

        finished_data = {}
        worker.sig_finished.connect(lambda stems, sr, meta, folder: finished_data.update({
            "stems": stems,
            "folder": folder
        }))

        worker.run()

        # Verificar se gerou os stems e organizou na pasta
        self.assertIn("folder", finished_data)
        target_dir = finished_data["folder"]
        self.assertTrue(os.path.exists(target_dir))

        # Verificar integridade dos arquivos organizados na pasta
        files = os.listdir(target_dir)
        self.assertIn("original.wav", files)
        
        # Verificar se os 4 stems essenciais foram gerados
        stem_files = [f for f in files if "vocals" in f or "drums" in f or "bass" in f or "other" in f]
        self.assertGreaterEqual(len(stem_files), 4)

    def test_4_gui_components_and_tabs(self):
        """Valida os novos componentes da MainWindow (Abas, URL, DropZone, Estados dos Botões)."""
        window = MainWindow()

        # 1. Testar abas de entrada
        self.assertEqual(window.input_tabs.count(), 2)
        self.assertIn("YouTube", window.input_tabs.tabText(0))
        self.assertIn("Arquivo Local", window.input_tabs.tabText(1))

        # 2. Testar validação de link do YouTube na GUI
        window.input_tabs.setCurrentIndex(0)
        window.txt_youtube_url.setText("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertTrue(window.btn_separate.isEnabled(), "Botão deve estar habilitado com URL válida.")

        window.txt_youtube_url.setText("url_invalida")
        self.assertFalse(window.btn_separate.isEnabled(), "Botão deve estar desabilitado com URL inválida.")

        # 3. Testar aba de arquivo local
        window.input_tabs.setCurrentIndex(1)
        src_audio = self._generate_synthetic_audio("local_test.wav", duration=1.0)
        window.drop_zone.load_file(src_audio)
        self.assertTrue(window.btn_separate.isEnabled(), "Botão deve estar habilitado com arquivo local carregado.")

        # 4. Limpar e fechar
        window.drop_zone.clear()
        self.assertFalse(window.btn_separate.isEnabled())
        window.close()


if __name__ == "__main__":
    unittest.main()
