"""Audio inspector to extract detailed metadata from WAV files."""
import os
from typing import Dict, Any, Tuple
import soundfile as sf
from src.utils.formatters import format_duration, format_filesize, format_sample_rate, format_channels


def get_bit_depth_label(subtype: str) -> str:
    """Map soundfile subtype to user-friendly bit depth label."""
    subtype_upper = (subtype or "").upper()
    if "PCM_16" in subtype_upper:
        return "16-bit PCM"
    elif "PCM_24" in subtype_upper:
        return "24-bit PCM"
    elif "PCM_32" in subtype_upper:
        return "32-bit PCM"
    elif "FLOAT" in subtype_upper:
        return "32-bit Float"
    elif "DOUBLE" in subtype_upper:
        return "64-bit Float"
    elif "PCM_U8" in subtype_upper:
        return "8-bit PCM"
    return subtype or "Desconhecido"


def inspect_audio_file(filepath: str) -> Dict[str, Any]:
    """
    Read metadata from an audio file.
    Raises ValueError or RuntimeError if file is invalid.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Arquivo não encontrado: {filepath}")

    if not os.path.isfile(filepath):
        raise ValueError(f"O caminho especificado não é um arquivo: {filepath}")

    file_size = os.path.getsize(filepath)
    if file_size == 0:
        raise ValueError("O arquivo de áudio está vazio (0 bytes).")

    try:
        info = sf.info(filepath)
    except Exception as e:
        raise ValueError(f"Não foi possível ler o arquivo de áudio: {str(e)}")

    duration = float(info.frames) / float(info.samplerate) if info.samplerate else 0.0
    if info.frames == 0 or duration <= 0.0:
        raise ValueError("O arquivo de áudio não contém dados de áudio válidos (duração zero).")

    bit_depth = get_bit_depth_label(info.subtype)

    return {
        "filepath": os.path.abspath(filepath),
        "filename": os.path.basename(filepath),
        "filesize": file_size,
        "filesize_formatted": format_filesize(file_size),
        "duration": duration,
        "duration_formatted": format_duration(duration),
        "samplerate": info.samplerate,
        "samplerate_formatted": format_sample_rate(info.samplerate),
        "channels": info.channels,
        "channels_formatted": format_channels(info.channels),
        "subtype": info.subtype,
        "format": info.format,
        "bit_depth": bit_depth,
        "frames": info.frames,
    }


def validate_wav_file(filepath: str) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Validate that the file is an accessible WAV file.
    Returns (is_valid, error_message, metadata_dict).
    """
    try:
        meta = inspect_audio_file(filepath)
        # Verify format is WAV
        if meta["format"].upper() != "WAV":
            return False, f"Formato inválido ({meta['format']}). O programa aceita exclusivamente arquivos no formato WAV.", {}
        return True, "", meta
    except Exception as e:
        return False, str(e), {}
