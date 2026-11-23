"""Utility formatters for time, size, and audio specs."""

def format_duration(seconds: float) -> str:
    """Format duration in seconds to MM:SS or HH:MM:SS format."""
    if seconds is None or seconds < 0:
        return "00:00"
    
    total_seconds = int(round(seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_filesize(num_bytes: int) -> str:
    """Format file size in bytes to human-readable string (KB, MB, GB)."""
    if num_bytes is None or num_bytes <= 0:
        return "0 B"
    
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    unit_index = 0
    
    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1
        
    return f"{size:.2f} {units[unit_index]}"


def format_sample_rate(hz: int) -> str:
    """Format sample rate in Hz to readable kHz."""
    if not hz:
        return "Desconhecido"
    if hz % 1000 == 0:
        return f"{hz // 1000} kHz"
    return f"{hz / 1000:.1f} kHz"


def format_channels(channels: int) -> str:
    """Format channel count to friendly audio description."""
    if channels == 1:
        return "Mono (1 canal)"
    elif channels == 2:
        return "Estéreo (2 canais)"
    elif channels == 6:
        return "5.1 Surround (6 canais)"
    elif channels == 8:
        return "7.1 Surround (8 canais)"
    return f"{channels} canais"
