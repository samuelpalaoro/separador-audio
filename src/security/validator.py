"""
Módulo de Validação e Segurança da Aplicação SamukaLab.
Protege contra SSRF, Path Traversal, injeção de comandos, arquivos falsificados e esgotamento de recursos.
"""
import os
import re
import ipaddress
import urllib.parse
from typing import Tuple, Optional


class SecurityValidationError(ValueError):
    """Exceção levantada quando uma validação de segurança falha."""
    pass


class SecurityValidator:
    """Validações rigorosas de segurança para URLs, caminhos de arquivos e formatos de mídia."""

    # Domínios confiáveis do YouTube
    ALLOWED_DOMAINS = {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtu.be",
    }

    # Tamanho máximo de arquivo de entrada permitido (1.5 GB)
    MAX_FILE_SIZE_BYTES = 1500 * 1024 * 1024

    # Duração máxima permitida para extração de áudio (1 hora / 3600s)
    MAX_DURATION_SECONDS = 3600

    @classmethod
    def validate_url(cls, url: str) -> str:
        """
        Valida que a URL informada utiliza apenas HTTP/HTTPS, pertence a um domínio
        autorizado do YouTube e não aponta para IPs de rede privada/interna (prevenção SSRF).
        """
        if not url or not isinstance(url, str):
            raise SecurityValidationError("A URL não pode estar vazia.")

        clean_url = url.strip()
        parsed = urllib.parse.urlparse(clean_url)

        if parsed.scheme.lower() not in ("http", "https"):
            raise SecurityValidationError(f"Protocolo inseguro ou inválido: '{parsed.scheme}'. Apenas HTTP e HTTPS são aceitos.")

        hostname = (parsed.hostname or "").lower()
        if not hostname:
            raise SecurityValidationError("A URL fornecida não contém um nome de host válido.")

        # Prevenção SSRF: verificar se o hostname é um IP privado ou loopback
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                raise SecurityValidationError(f"Endereço de rede restrito ou privado bloqueado: '{hostname}'.")
        except ValueError:
            # Não é um endereço IP direto, é um domínio textual
            pass

        # Verificar se pertence aos domínios autorizados do YouTube
        is_allowed = False
        for allowed in cls.ALLOWED_DOMAINS:
            if hostname == allowed or hostname.endswith("." + allowed):
                is_allowed = True
                break

        if not is_allowed:
            raise SecurityValidationError(f"O domínio '{hostname}' não é uma fonte suportada do YouTube.")

        return clean_url

    @classmethod
    def sanitize_path_slug(cls, name: str, max_length: int = 80) -> str:
        """
        Sanitiza o nome de arquivo/pasta eliminando qualquer possibilidade de Path Traversal
        ou injeção no sistema de arquivos.
        """
        if not name or not isinstance(name, str):
            return "audio"

        # Remover sequências de traversal '..' e barras
        clean = name.replace("..", "").replace("/", "_").replace("\\", "_")
        # Remover caracteres de controle e proibidos
        clean = re.sub(r'[\x00-\x1f\x7f\\/*?:"<>|]', '_', clean)
        # Compactar espaços e underscores repetidos
        clean = re.sub(r'[\s_]+', '_', clean).strip('_ .')
        if not clean:
            clean = "audio"
        return clean[:max_length]

    @classmethod
    def ensure_path_within_directory(cls, base_dir: str, target_path: str) -> str:
        """
        Garante que o caminho de destino fique estritamente contido dentro do diretório base.
        Previne ataques de Path Traversal.
        """
        base_abs = os.path.abspath(base_dir)
        target_abs = os.path.abspath(target_path)

        try:
            common = os.path.commonpath([base_abs, target_abs])
        except ValueError:
            raise SecurityValidationError(f"Caminho inválido ou em unidade diferente: {target_path}")

        if common != base_abs:
            raise SecurityValidationError(f"Acesso negado: o caminho '{target_path}' tenta escapar do diretório autorizado '{base_dir}'.")

        return target_abs

    @classmethod
    def validate_file_header_magic_bytes(cls, filepath: str) -> Tuple[bool, str]:
        """
        Valida os magic bytes reais do cabeçalho do arquivo para garantir
        que se trata de um arquivo de áudio legítimo e não um arquivo executável mascarado.
        """
        if not os.path.exists(filepath):
            return False, "Arquivo não encontrado."

        size = os.path.getsize(filepath)
        if size == 0:
            return False, "Arquivo está vazio (0 bytes)."

        if size > cls.MAX_FILE_SIZE_BYTES:
            return False, f"Arquivo excede o limite máximo permitido de {cls.MAX_FILE_SIZE_BYTES / (1024*1024):.0f} MB."

        try:
            with open(filepath, "rb") as f:
                header = f.read(32)

            if len(header) < 12:
                return False, "Cabeçalho de arquivo insuficiente."

            # WAV / RIFF
            if header[:4] == b"RIFF" and header[8:12] == b"WAVE":
                return True, "WAV"

            # FLAC
            if header[:4] == b"fLaC":
                return True, "FLAC"

            # Ogg Vorbis/Opus
            if header[:4] == b"OggS":
                return True, "OGG"

            # MP3 (ID3 tag ou sincronização frame 0xFF 0xFB/F3/F2)
            if header[:3] == b"ID3":
                return True, "MP3"
            if header[0] == 0xFF and (header[1] & 0xE0) == 0xE0:
                return True, "MP3"

            # M4A / MP4 / AAC (ftyp no cabeçalho)
            if b"ftyp" in header[:16]:
                return True, "M4A"

            # WebM / Matroska (0x1A 0x45 0xDF 0xA3)
            if header[:4] == b"\x1a\x45\xdf\xa3":
                return True, "WEBM"

            return False, "O cabeçalho do arquivo não corresponde a nenhum formato de áudio válido suportado."

        except Exception as e:
            return False, f"Erro ao inspecionar cabeçalho do arquivo: {str(e)}"
