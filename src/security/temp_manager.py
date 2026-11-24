"""
Gerenciador Seguro de Armazenamento e Limpeza de Arquivos Temporários do SamukaLab.
Garante que arquivos temporários (downloads, áudios convertidos, chunks) fiquem isolados,
nunca toquem em arquivos originais ou diretórios de exportação permanente,
e sejam limpos com segurança sem interromper tarefas em execução.
"""
import os
import shutil
import tempfile
import time
import uuid
import threading
from typing import Set, Dict, Optional


class SafeTempManager:
    """Gerenciador centralizado e thread-safe de arquivos temporários do SamukaLab."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(SafeTempManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, root_temp_dir: Optional[str] = None):
        if self._initialized:
            return
        
        self.root_temp_dir = os.path.abspath(
            root_temp_dir or os.path.join(tempfile.gettempdir(), "samukalab_temp")
        )
        os.makedirs(self.root_temp_dir, exist_ok=True)
        
        # Rastreamento de sessões ativas (thread-safe)
        self._active_sessions: Dict[str, str] = {}  # session_id -> dir_path
        self._session_lock = threading.Lock()
        self._initialized = True

    def create_session_dir(self, prefix: str = "task_") -> str:
        """Cria e registra um subdiretório temporário isolado para uma tarefa ou worker."""
        session_id = f"{prefix}{int(time.time())}_{uuid.uuid4().hex[:8]}"
        session_path = os.path.join(self.root_temp_dir, session_id)
        os.makedirs(session_path, exist_ok=True)
        
        with self._session_lock:
            self._active_sessions[session_id] = session_path
            
        return session_path

    def register_active_dir(self, session_id: str, path: str):
        """Registra explicitamente um diretório como ativo sob vigilância."""
        abs_path = os.path.abspath(path)
        with self._session_lock:
            self._active_sessions[session_id] = abs_path

    def unregister_active_session(self, session_id: str):
        """Desregistra uma sessão ativa."""
        with self._session_lock:
            self._active_sessions.pop(session_id, None)

    def is_session_active(self, session_id: str) -> bool:
        """Verifica se a sessão está atualmente em execução."""
        with self._session_lock:
            return session_id in self._active_sessions

    def cleanup_session(self, session_dir_or_id: str):
        """
        Remove com segurança um diretório temporário específico de uma sessão concluída ou cancelada.
        Garante que o diretório pertença à árvore temporária autorizada.
        """
        target_path = None
        target_id = None
        
        with self._session_lock:
            if session_dir_or_id in self._active_sessions:
                target_id = session_dir_or_id
                target_path = self._active_sessions[session_dir_or_id]
            else:
                for sid, path in self._active_sessions.items():
                    if path == session_dir_or_id or os.path.abspath(session_dir_or_id) == path:
                        target_id = sid
                        target_path = path
                        break

            if target_id:
                self._active_sessions.pop(target_id, None)

        if not target_path:
            target_path = os.path.abspath(session_dir_or_id)

        # Verificação rigorosa de segurança: o caminho DEVE estar contido em root_temp_dir
        if not self._is_safe_temp_path(target_path):
            return

        if os.path.exists(target_path):
            try:
                shutil.rmtree(target_path, ignore_errors=True)
            except Exception:
                pass

    def cleanup_orphaned_temporaries(self, max_age_seconds: int = 1800) -> int:
        """
        Limpa diretórios temporários órfãos de sessões anteriores que não estão em execução.
        Nunca toca em:
        - Sessões atualmente ativas no gerenciador
        - Arquivos originais do usuário
        - Pastas de exportação do usuário
        
        Retorna a quantidade de pastas limpas.
        """
        if not os.path.exists(self.root_temp_dir):
            return 0

        with self._session_lock:
            active_paths: Set[str] = set(self._active_sessions.values())

        now = time.time()
        cleaned_count = 0

        try:
            for entry in os.listdir(self.root_temp_dir):
                entry_path = os.path.join(self.root_temp_dir, entry)
                
                # Ignorar sessões ativas
                if entry_path in active_paths:
                    continue

                if not os.path.isdir(entry_path):
                    continue

                # Verificar idade para evitar limpar itens recém-criados
                try:
                    mtime = os.path.getmtime(entry_path)
                    if (now - mtime) >= max_age_seconds:
                        shutil.rmtree(entry_path, ignore_errors=True)
                        cleaned_count += 1
                except Exception:
                    pass
        except Exception:
            pass

        return cleaned_count

    def get_total_temp_size_bytes(self) -> int:
        """Retorna o espaço total ocupado pelo diretório temporário em bytes."""
        if not os.path.exists(self.root_temp_dir):
            return 0

        total_size = 0
        try:
            for root, _, files in os.walk(self.root_temp_dir):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        total_size += os.path.getsize(fp)
                    except Exception:
                        pass
        except Exception:
            pass

        return total_size

    def _is_safe_temp_path(self, target_path: str) -> bool:
        """Valida que o caminho alvo está estritamente dentro do root_temp_dir."""
        try:
            target_abs = os.path.abspath(target_path)
            root_abs = os.path.abspath(self.root_temp_dir)
            
            # Não permitir apagar o root_temp_dir em si
            if target_abs == root_abs:
                return False

            common = os.path.commonpath([root_abs, target_abs])
            return common == root_abs
        except Exception:
            return False
