"""
Testes de Armazenamento Temporário, Limpeza Segura e Fluxo de Exportação Manual no SamukaLab.
Garante o cumprimento dos requisitos fundamentais:
- O aplicativo não salva stems/músicas em diretórios permanentes automaticamente.
- Fluxo: Importar -> Processar -> Separar -> Reprodução/Avaliação em RAM -> Exportação somente sob solicitação.
- Arquivos originais nunca são apagados ou modificados.
- Arquivos temporários são isolados e limpos com segurança, sem afetar tarefas em execução.
- Slugs de bateria não sofrem colisão de nomes.
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

from src.security.temp_manager import SafeTempManager
from src.audio.exporter import sanitize_stem_slug, export_all_stems
from src.separator.pipeline_worker import UnifiedPipelineWorker
from src.history.project_manager import ProjectHistoryManager


class TestTempStorageAndManualExport(unittest.TestCase):
    """Bateria de testes para armazenamento temporário e controle de exportação do usuário."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="test_temp_export_")
        self.temp_mgr = SafeTempManager(root_temp_dir=os.path.join(self.tmp_dir, "app_temp"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _generate_synthetic_wav(self, filename: str = "orig.wav", duration: float = 1.0, sr: int = 44100) -> str:
        path = os.path.join(self.tmp_dir, filename)
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        sig = 0.3 * np.sin(2 * np.pi * 440 * t)
        stereo = np.column_stack([sig, sig]).astype(np.float32)
        sf.write(path, stereo, sr, subtype="PCM_24", format="WAV")
        return path

    def test_drum_slug_collision_prevention(self):
        """Verifica se os sub-elementos de bateria geram slugs únicos sem colidir como 'drums'."""
        stems = [
            ("Drums (Bateria)", "drums"),
            ("Drum: Kick (Bumbo)", "drum_kick"),
            ("Drum: Snare (Caixa)", "drum_snare"),
            ("Drum: Hi-Hats (Chimbal)", "drum_hihats"),
            ("Drum: Cymbals (Pratos)", "drum_cymbals"),
            ("Drum: Toms (Tons)", "drum_toms"),
            ("Vocals (Voz)", "vocals"),
            ("Bass (Baixo)", "bass"),
            ("Other (Outros)", "other"),
        ]
        slugs = set()
        for stem_name, expected_slug in stems:
            slug = sanitize_stem_slug(stem_name)
            self.assertEqual(slug, expected_slug, f"Slug incorreto para {stem_name}")
            self.assertNotIn(slug, slugs, f"Colisão detectada para o slug {slug}")
            slugs.add(slug)

    def test_safe_temp_manager_lifecycle_and_active_protection(self):
        """Testa criação, registro, proteção de tarefas ativas e limpeza segura de órfãos."""
        # 1. Criação de sessão
        session_dir = self.temp_mgr.create_session_dir(prefix="active_task_")
        self.assertTrue(os.path.isdir(session_dir))
        
        session_id = os.path.basename(session_dir)
        self.assertTrue(self.temp_mgr.is_session_active(session_id))

        # Criar arquivo de teste dentro da sessão ativa
        test_file = os.path.join(session_dir, "chunk.wav")
        with open(test_file, "w") as f:
            f.write("fake audio data")

        # 2. Tentativa de limpeza de órfãos não deve apagar tarefa ativa
        cleaned = self.temp_mgr.cleanup_orphaned_temporaries(max_age_seconds=0)
        self.assertEqual(cleaned, 0)
        self.assertTrue(os.path.exists(test_file), "Arquivo de tarefa ativa NÃO deve ser apagado!")

        # 3. Finalizar tarefa e limpar sessão explicitamente
        self.temp_mgr.cleanup_session(session_dir)
        self.assertFalse(os.path.exists(session_dir), "Diretório de sessão finalizada deve ser removido.")
        self.assertFalse(self.temp_mgr.is_session_active(session_id))

    def test_original_files_strictly_preserved(self):
        """Garante que arquivos originais do usuário nunca sejam apagados ou modificados."""
        orig_file = self._generate_synthetic_wav("usuario_minha_faixa.wav", duration=0.8)
        orig_mtime = os.path.getmtime(orig_file)
        orig_size = os.path.getsize(orig_file)

        # Tentar acionar limpeza no diretório do arquivo original (deve ser rejeitado)
        self.temp_mgr.cleanup_session(orig_file)

        self.assertTrue(os.path.exists(orig_file), "Arquivo original do usuário foi deletado!")
        self.assertEqual(os.path.getsize(orig_file), orig_size, "Tamanho do arquivo original foi alterado!")
        self.assertEqual(os.path.getmtime(orig_file), orig_mtime, "Timestamp do arquivo original foi modificado!")

    def test_pipeline_no_auto_export_stores_temporarily(self):
        """
        Testa o fluxo obrigatório:
        Quando auto_export=False (padrão SamukaLab), nenhum arquivo é gravado no output permanente,
        e os stems ficam disponíveis na memória RAM para reprodução e avaliação.
        """
        orig_audio = self._generate_synthetic_wav("musica_teste.wav", duration=1.0)
        permanent_output_dir = os.path.join(self.tmp_dir, "output_permanente")

        worker = UnifiedPipelineWorker(
            mode="file",
            source=orig_audio,
            output_base_dir=permanent_output_dir,
            model_name="htdemucs",
            auto_export=False  # Exige avaliação no mixer sem salvar no disco
        )

        results = {}
        worker.sig_finished.connect(lambda stems, sr, meta, folder: results.update({
            "stems": stems,
            "sr": sr,
            "meta": meta,
            "folder": folder
        }))

        # Execução síncrona para o teste
        worker.run()

        # 1. Os stems devem estar carregados na memória RAM
        self.assertIn("stems", results)
        stems = results["stems"]
        self.assertIn("Vocals (Voz)", stems)
        self.assertIn("Drums (Bateria)", stems)
        self.assertIn("Bass (Baixo)", stems)
        self.assertIn("Other (Outros)", stems)

        # 2. A pasta retornada deve estar vazia (nenhuma exportação automática)
        self.assertEqual(results["folder"], "")

        # 3. O diretório permanente de saída NÃO deve ter recebido nenhum arquivo automático
        if os.path.exists(permanent_output_dir):
            files_created = os.listdir(permanent_output_dir)
            self.assertEqual(len(files_created), 0, f"Arquivos foram salvos indevidamente em {permanent_output_dir}: {files_created}")

        # 4. Arquivo original foi estritamente preservado
        self.assertTrue(os.path.exists(orig_audio))

    def test_manual_export_flow_and_history(self):
        """
        Testa o fluxo em que o usuário ouviu no mixer e agora aciona a exportação manual:
        Os stems são gravados na pasta escolhida pelo usuário e o histórico é atualizado.
        """
        sr = 44100
        dur = 0.5
        t = np.linspace(0, dur, int(sr * dur), endpoint=False)
        sig = 0.2 * np.sin(2 * np.pi * 440 * t)
        stereo = np.column_stack([sig, sig]).astype(np.float32)

        stems = {
            "Vocals (Voz)": stereo,
            "Drums (Bateria)": stereo,
            "Drum: Kick (Bumbo)": stereo,
            "Drum: Snare (Caixa)": stereo,
            "Bass (Baixo)": stereo,
            "Other (Outros)": stereo
        }

        user_export_dir = os.path.join(self.tmp_dir, "export_do_usuario")
        meta = {"song_title": "Minha_Faixa_Final", "duration": dur, "samplerate": sr}

        # Usuário aciona exportação
        exported = export_all_stems(
            stems=stems,
            stem_sample_rate=sr,
            output_directory=user_export_dir,
            base_name=meta["song_title"],
            original_metadata=meta
        )

        self.assertEqual(len(exported), 6)
        files = os.listdir(user_export_dir)
        self.assertIn("Minha_Faixa_Final_vocals.wav", files)
        self.assertIn("Minha_Faixa_Final_drums.wav", files)
        self.assertIn("Minha_Faixa_Final_drum_kick.wav", files)
        self.assertIn("Minha_Faixa_Final_drum_snare.wav", files)
        self.assertIn("Minha_Faixa_Final_bass.wav", files)
        self.assertIn("Minha_Faixa_Final_other.wav", files)

        # Registro no histórico
        hist_mgr = ProjectHistoryManager(history_file=os.path.join(self.tmp_dir, "history.json"))
        hist_mgr.add_entry(
            title=meta["song_title"],
            mode="file",
            source="arquivo.wav",
            output_dir=user_export_dir,
            stems_list=list(stems.keys()),
            duration_s=dur,
            model_name="htdemucs",
            has_drum_separation=True
        )

        entries = hist_mgr.get_recent()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "Minha_Faixa_Final")
        self.assertTrue(entries[0]["exists_on_disk"])


if __name__ == "__main__":
    unittest.main()
