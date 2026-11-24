"""
Módulo de Gerenciamento de Histórico e Projetos Processados no SamukaLab.
Permite aos produtores e músicos acompanhar o histórico de músicas e stems separados.
"""
import os
import json
import time
from typing import List, Dict, Any, Optional


class ProjectHistoryManager:
    """Armazena e gerencia o histórico de processamento do SamukaLab."""

    def __init__(self, history_file: Optional[str] = None):
        if not history_file:
            user_config_dir = os.path.expanduser("~/.config/samukalab")
            os.makedirs(user_config_dir, exist_ok=True)
            self.history_file = os.path.join(user_config_dir, "history.json")
        else:
            self.history_file = os.path.abspath(history_file)

        self._history: List[Dict[str, Any]] = []
        self.load()

    def load(self):
        """Carrega o histórico do disco."""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self._history = data
            except Exception:
                self._history = []
        else:
            self.save()

    def save(self):
        """Salva o histórico de forma segura e atômica."""
        try:
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
            tmp_path = self.history_file + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._history, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self.history_file)
        except Exception:
            pass

    def add_entry(
        self,
        title: str,
        mode: str,
        source: str,
        output_dir: str,
        stems_list: List[str],
        duration_s: float,
        model_name: str,
        has_drum_separation: bool = False
    ) -> Dict[str, Any]:
        """Adiciona um novo registro ao histórico."""
        entry = {
            "id": f"{int(time.time())}_{abs(hash(title)) % 100000}",
            "title": title,
            "mode": mode,
            "source": source,
            "output_dir": os.path.abspath(output_dir),
            "stems": stems_list,
            "duration_s": round(duration_s, 2),
            "model_name": model_name,
            "has_drum_separation": has_drum_separation,
            "timestamp": time.time(),
            "date_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        }

        # Insere no início da lista (mais recente primeiro)
        self._history.insert(0, entry)
        # Limita histórico aos últimos 100 registros
        self._history = self._history[:100]
        self.save()
        return entry

    def get_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retorna as entradas recentes com verificação de existência em disco."""
        results = []
        for item in self._history[:limit]:
            entry = dict(item)
            entry["exists_on_disk"] = os.path.exists(entry["output_dir"])
            results.append(entry)
        return results

    def remove_entry(self, entry_id: str):
        """Remove um registro do histórico."""
        self._history = [e for e in self._history if e.get("id") != entry_id]
        self.save()

    def clear(self):
        """Limpa todo o histórico."""
        self._history.clear()
        self.save()
