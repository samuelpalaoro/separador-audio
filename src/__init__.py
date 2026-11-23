"""Moises AI Audio Separator."""
import os
import ctypes.util

__version__ = "1.0.0"

# Ensure local libportaudio is resolved if bundled in ./lib
_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_local_portaudio = os.path.join(_base_dir, "lib", "usr", "lib", "x86_64-linux-gnu", "libportaudio.so.2")
_orig_find_library = ctypes.util.find_library

def _portaudio_find_library(name: str):
    if name in ("portaudio", "libportaudio", "libportaudio.so"):
        if os.path.exists(_local_portaudio):
            return _local_portaudio
    return _orig_find_library(name)

ctypes.util.find_library = _portaudio_find_library

