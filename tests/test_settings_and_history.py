"""
Testes unitários para SettingsManager e ProjectHistoryManager.
"""
import os
import sys
import unittest
import tempfile

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from src.config.settings import SettingsManager
from src.history.project_manager import ProjectHistoryManager


class TestSettingsAndHistory(unittest.TestCase):
    """Testes de configurações e histórico."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="test_cfg_hist_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_settings_persistence(self):
        cfg_file = os.path.join(self.tmp_dir, "test_config.json")
        mgr = SettingsManager(config_path=cfg_file)
        mgr.set("export_format", "FLAC")
        mgr.set("match_sample_rate", False)

        # Recarregar do arquivo em nova instância
        mgr2 = SettingsManager(config_path=cfg_file)
        self.assertEqual(mgr2.get("export_format"), "FLAC")
        self.assertFalse(mgr2.get("match_sample_rate"))

    def test_history_management(self):
        hist_file = os.path.join(self.tmp_dir, "test_history.json")
        mgr = ProjectHistoryManager(history_file=hist_file)

        # Adicionar entrada
        entry = mgr.add_entry(
            title="Minha Musica",
            mode="url",
            source="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            output_dir=self.tmp_dir,
            stems_list=["Vocals", "Drums", "Bass", "Other"],
            duration_s=180.5,
            model_name="htdemucs"
        )
        self.assertEqual(entry["title"], "Minha Musica")

        recent = mgr.get_recent()
        self.assertEqual(len(recent), 1)
        self.assertTrue(recent[0]["exists_on_disk"])

        # Limpar
        mgr.clear()
        self.assertEqual(len(mgr.get_recent()), 0)


if __name__ == "__main__":
    unittest.main()
