"""Audio package initialization with automatic PortAudio library resolution."""
import os
import sys
import ctypes.util

# Ensure PortAudio can be located if bundled in ./lib
_local_portaudio = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "lib", "usr", "lib", "x86_64-linux-gnu", "libportaudio.so.2")
)

_orig_find_library = ctypes.util.find_library

def _portaudio_find_library(name: str):
    if name in ("portaudio", "libportaudio", "libportaudio.so"):
        if os.path.exists(_local_portaudio):
            return _local_portaudio
    return _orig_find_library(name)

ctypes.util.find_library = _portaudio_find_library
