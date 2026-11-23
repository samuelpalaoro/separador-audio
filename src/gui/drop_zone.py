"""Drag and Drop audio import widget with technical metadata display."""
import os
from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QFileDialog, QGridLayout, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from src.audio.inspector import validate_wav_file
from src.gui.style import COLORS


class DropZoneWidget(QFrame):
    """
    Modern drag-and-drop zone with visual feedback and technical audio inspection.
    """
    sig_file_loaded = Signal(str, object)  # filepath, metadata_dict
    sig_file_cleared = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setProperty("card", "true")
        self.current_filepath: Optional[str] = None
        self.current_metadata: Optional[Dict[str, Any]] = None
        
        self._init_ui()
        self._apply_idle_style()

    def _init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(24, 24, 24, 24)
        self.main_layout.setSpacing(16)

        # Drop instruction container
        self.instruction_container = QWidget()
        inst_layout = QVBoxLayout(self.instruction_container)
        inst_layout.setAlignment(Qt.AlignCenter)
        inst_layout.setSpacing(10)

        # Icon and text
        self.icon_label = QLabel("🎵")
        self.icon_label.setStyleSheet("font-size: 38px;")
        self.icon_label.setAlignment(Qt.AlignCenter)

        self.title_label = QLabel("Arraste e solte seu arquivo de áudio WAV aqui")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #F8FAFC;")
        self.title_label.setAlignment(Qt.AlignCenter)

        self.sub_label = QLabel("Suporte completo a WAV de alta resolução (16-bit, 24-bit, 32-bit Float)")
        self.sub_label.setStyleSheet("font-size: 12px; color: #94A3B8;")
        self.sub_label.setAlignment(Qt.AlignCenter)

        self.btn_browse = QPushButton("Selecionar Arquivo WAV")
        self.btn_browse.setCursor(Qt.PointingHandCursor)
        self.btn_browse.clicked.connect(self._open_file_dialog)

        inst_layout.addWidget(self.icon_label)
        inst_layout.addWidget(self.title_label)
        inst_layout.addWidget(self.sub_label)
        inst_layout.addWidget(self.btn_browse, alignment=Qt.AlignCenter)

        self.main_layout.addWidget(self.instruction_container)

        # Technical Info Card (initially hidden)
        self.info_card = QFrame()
        self.info_card.setStyleSheet("""
            QFrame {
                background-color: #1A1D2C;
                border: 1px solid #2F344B;
                border-radius: 10px;
                padding: 12px;
            }
        """)
        self.info_card.setVisible(False)
        info_layout = QVBoxLayout(self.info_card)
        info_layout.setContentsMargins(16, 12, 16, 12)
        info_layout.setSpacing(12)

        # Top row: File name and Remove button
        header_layout = QHBoxLayout()
        self.lbl_filename = QLabel("arquivo.wav")
        self.lbl_filename.setStyleSheet("font-size: 15px; font-weight: 700; color: #38BDF8;")
        
        self.btn_remove = QPushButton("Trocar Arquivo")
        self.btn_remove.setCursor(Qt.PointingHandCursor)
        self.btn_remove.setStyleSheet("""
            QPushButton {
                background-color: #262A3D;
                border: 1px solid #3B415E;
                padding: 4px 10px;
                font-size: 11px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #323852;
                border-color: #8B5CF6;
            }
        """)
        self.btn_remove.clicked.connect(self._open_file_dialog)

        header_layout.addWidget(self.lbl_filename)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_remove)
        info_layout.addLayout(header_layout)

        # Grid of technical specs
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(8)

        # Labels for values
        self.val_duration = QLabel("-")
        self.val_samplerate = QLabel("-")
        self.val_bitdepth = QLabel("-")
        self.val_channels = QLabel("-")
        self.val_filesize = QLabel("-")

        specs = [
            ("Duração:", self.val_duration, 0, 0),
            ("Sample Rate:", self.val_samplerate, 0, 1),
            ("Bit Depth:", self.val_bitdepth, 0, 2),
            ("Canais:", self.val_channels, 1, 0),
            ("Tamanho:", self.val_filesize, 1, 1),
        ]

        for title, val_lbl, r, c in specs:
            box = QHBoxLayout()
            lbl_title = QLabel(title)
            lbl_title.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 500;")
            val_lbl.setStyleSheet("color: #F8FAFC; font-size: 12px; font-weight: 700;")
            box.addWidget(lbl_title)
            box.addWidget(val_lbl)
            box.addStretch()
            grid.addLayout(box, r, c)

        info_layout.addLayout(grid)
        self.main_layout.addWidget(self.info_card)

    def _apply_idle_style(self):
        self.setStyleSheet("""
            QFrame[card="true"] {
                background-color: #151722;
                border: 2px dashed #2E3349;
                border-radius: 12px;
            }
        """)

    def _apply_drag_hover_style(self):
        self.setStyleSheet("""
            QFrame[card="true"] {
                background-color: #1A1730;
                border: 2px dashed #8B5CF6;
                border-radius: 12px;
            }
        """)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                file_path = urls[0].toLocalFile()
                if file_path.lower().endswith((".wav", ".wave")):
                    event.acceptProposedAction()
                    self._apply_drag_hover_style()
                    return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._apply_idle_style()
        event.accept()

    def dropEvent(self, event: QDropEvent):
        self._apply_idle_style()
        urls = event.mimeData().urls()
        if urls:
            filepath = urls[0].toLocalFile()
            self.load_file(filepath)
            event.acceptProposedAction()

    def _open_file_dialog(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Arquivo de Áudio WAV",
            "",
            "Arquivos WAV (*.wav *.wave)"
        )
        if filepath:
            self.load_file(filepath)

    def load_file(self, filepath: str):
        """Inspect and load audio file."""
        is_valid, err_msg, meta = validate_wav_file(filepath)
        if not is_valid:
            QMessageBox.critical(
                self,
                "Erro ao carregar arquivo",
                f"O arquivo selecionado não é válido:\n{err_msg}"
            )
            return

        self.current_filepath = filepath
        self.current_metadata = meta

        # Update labels
        self.lbl_filename.setText(meta["filename"])
        self.val_duration.setText(meta["duration_formatted"])
        self.val_samplerate.setText(meta["samplerate_formatted"])
        self.val_bitdepth.setText(meta["bit_depth"])
        self.val_channels.setText(meta["channels_formatted"])
        self.val_filesize.setText(meta["filesize_formatted"])

        # Switch views
        self.instruction_container.setVisible(False)
        self.info_card.setVisible(True)

        self.sig_file_loaded.emit(filepath, meta)

    def clear(self):
        """Reset drop zone to empty state."""
        self.current_filepath = None
        self.current_metadata = None
        self.instruction_container.setVisible(True)
        self.info_card.setVisible(False)
        self.sig_file_cleared.emit()
