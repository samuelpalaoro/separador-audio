"""
Módulo de Configurações Persistentes do SamukaLab.
Gerencia preferências do usuário, caminhos padrão, parâmetros de áudio e aceleração.
"""
import os
import json
from typing import Dict, Any


DEFAULT_CONFIG: Dict[str, Any] = {
    "app_name": "SamukaLab",
    "version": "2.0.0",
    "output_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "output")),
    "default_model": "htdemucs",
    "device_preference": "auto",  # 'auto', 'cuda', 'cpu'
    "export_format": "WAV",       # 'WAV', 'FLAC', 'MP3'
    "wav_bit_depth": "PCM_24",    # 'PCM_16', 'PCM_24', 'FLOAT'
    "match_sample_rate": True,
    "experimental_drum_separation": True,
    "max_download_duration_s": 1800,  # 30 minutos máx para proteção
    "theme": "dark_daw",
    "recent_history_limit": 50,
}


class SettingsManager:
    """Gerencia a persistência e acesso seguro às configurações da aplicação."""

    def __init__(self, config_path: str = None):
        if not config_path:
            # Diretório de configuração padrão do usuário no Linux ~/.config/samukalab/
            user_config_dir = os.path.expanduser("~/.config/samukalab")
            os.makedirs(user_config_dir, exist_ok=True)
            self.config_path = os.path.join(user_config_dir, "config.json")
        else:
            self.config_path = os.path.abspath(config_path)

        self._config = dict(DEFAULT_CONFIG)
        self.load()

    def load(self):
        """Carrega configurações do arquivo JSON se existir."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._config.update(data)
            except Exception:
                # Se corrompido, mantém padrões seguros
                pass
        else:
            self.save()

    def save(self):
        """Salva configurações de forma atômica."""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            tmp_path = self.config_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self.config_path)
        except Exception:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any):
        self._config[key] = value
        self.save()

    def get_output_dir(self) -> str:
        out = self.get("output_dir")
        if not out:
            out = os.path.abspath("output")
        os.makedirs(out, exist_ok=True)
        return os.path.abspath(out)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._config)
