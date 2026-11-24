#!/usr/bin/env python3
"""
Moises AI — Software Desktop de Separação de Áudio por Inteligência Artificial
Ponto de entrada da aplicação.
"""
import os
import sys
import ctypes.util

# Ensure local libportaudio is resolved if bundled in ./lib
_base_dir = os.path.dirname(os.path.abspath(__file__))
_local_portaudio = os.path.join(_base_dir, "lib", "usr", "lib", "x86_64-linux-gnu", "libportaudio.so.2")

_orig_find_library = ctypes.util.find_library

def _portaudio_find_library(name: str):
    if name in ("portaudio", "libportaudio", "libportaudio.so"):
        if os.path.exists(_local_portaudio):
            return _local_portaudio
    return _orig_find_library(name)

ctypes.util.find_library = _portaudio_find_library

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from src.gui.main_window import MainWindow


def main():
    # Enable high-DPI scaling
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    
    app = QApplication(sys.argv)
    app.setApplicationName("SamukaLab — Audio DSP & AI Workstation")
    app.setOrganizationName("SamukaLab")
    app.setApplicationVersion("2.0.0")

    window = MainWindow()

    # If an audio file was provided as a command-line argument, load it directly
    if len(sys.argv) > 1:
        cli_file = sys.argv[1]
        if os.path.isfile(cli_file):
            window.drop_zone.load_file(cli_file)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
