"""Individual Stem Track control widget."""
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QSlider, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from src.gui.style import get_stem_color, COLORS
from src.utils.formatters import format_duration


class StemWidget(QFrame):
    """
    Control row for a single separated audio stem.
    Includes Solo, Mute, Volume, Duration, Audition, and Export WAV.
    """
    sig_volume_changed = Signal(str, float)       # stem_name, volume (0.0 - 1.5)
    sig_mute_toggled = Signal(str, bool)          # stem_name, is_muted
    sig_solo_toggled = Signal(str, bool)          # stem_name, is_solo
    sig_audition_requested = Signal(str)          # stem_name (solo preview)
    sig_export_requested = Signal(str)            # stem_name

    def __init__(self, stem_name: str, duration_sec: float, parent=None):
        super().__init__(parent)
        self.stem_name = stem_name
        self.duration_sec = duration_sec
        self.stem_color = get_stem_color(stem_name)
        
        self.is_solo = False
        self.is_muted = False
        self.volume = 1.0

        self.setProperty("card", "true")
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet(f"""
            QFrame[card="true"] {{
                background-color: #151722;
                border: 1px solid #282B3D;
                border-left: 5px solid {self.stem_color};
                border-radius: 10px;
            }}
            QFrame[card="true"]:hover {{
                border-color: #383D54;
                border-left: 5px solid {self.stem_color};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)

        # 1. Stem Title & Badge
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        self.lbl_name = QLabel(self.stem_name.upper())
        self.lbl_name.setStyleSheet(f"""
            font-size: 14px;
            font-weight: 800;
            color: {self.stem_color};
            letter-spacing: 0.5px;
        """)
        
        self.lbl_duration = QLabel(format_duration(self.duration_sec))
        self.lbl_duration.setStyleSheet("font-size: 11px; color: #94A3B8; font-weight: 500;")

        title_box.addWidget(self.lbl_name)
        title_box.addWidget(self.lbl_duration)
        layout.addLayout(title_box, stretch=2)

        # 2. Solo Button
        self.btn_solo = QPushButton("S")
        self.btn_solo.setToolTip("Modo Solo: ouve apenas esta faixa")
        self.btn_solo.setFixedSize(36, 36)
        self.btn_solo.setCursor(Qt.PointingHandCursor)
        self.btn_solo.clicked.connect(self._toggle_solo)
        self._update_solo_style()
        layout.addWidget(self.btn_solo)

        # 3. Mute Button
        self.btn_mute = QPushButton("M")
        self.btn_mute.setToolTip("Modo Mute: silencia esta faixa")
        self.btn_mute.setFixedSize(36, 36)
        self.btn_mute.setCursor(Qt.PointingHandCursor)
        self.btn_mute.clicked.connect(self._toggle_mute)
        self._update_mute_style()
        layout.addWidget(self.btn_mute)

        # 4. Volume Control
        vol_box = QHBoxLayout()
        vol_box.setSpacing(8)

        lbl_vol_icon = QLabel("🔊")
        lbl_vol_icon.setStyleSheet("font-size: 12px; color: #94A3B8;")

        self.slider_vol = QSlider(Qt.Horizontal)
        self.slider_vol.setRange(0, 150)
        self.slider_vol.setValue(100)
        self.slider_vol.setFixedWidth(130)
        self.slider_vol.setCursor(Qt.PointingHandCursor)
        self.slider_vol.valueChanged.connect(self._on_volume_changed)

        self.lbl_vol_val = QLabel("100%")
        self.lbl_vol_val.setFixedWidth(40)
        self.lbl_vol_val.setStyleSheet("font-size: 11px; color: #F8FAFC; font-weight: 600;")

        vol_box.addWidget(lbl_vol_icon)
        vol_box.addWidget(self.slider_vol)
        vol_box.addWidget(self.lbl_vol_val)
        layout.addLayout(vol_box, stretch=3)

        # 5. Audition (Single Play) Button
        self.btn_audition = QPushButton("▶ Ouvir Solo")
        self.btn_audition.setToolTip("Ouvir esta faixa isoladamente")
        self.btn_audition.setCursor(Qt.PointingHandCursor)
        self.btn_audition.setStyleSheet("""
            QPushButton {
                background-color: #202436;
                border: 1px solid #323852;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2A3048;
                border-color: #8B5CF6;
                color: #FFFFFF;
            }
        """)
        self.btn_audition.clicked.connect(lambda: self.sig_audition_requested.emit(self.stem_name))
        layout.addWidget(self.btn_audition)

        # 6. Export WAV Button
        self.btn_export = QPushButton("Exportar WAV")
        self.btn_export.setToolTip("Exportar esta faixa em arquivo WAV de alta resolução")
        self.btn_export.setCursor(Qt.PointingHandCursor)
        self.btn_export.setStyleSheet("""
            QPushButton {
                background-color: #1A2E26;
                color: #34D399;
                border: 1px solid #059669;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #059669;
                color: #FFFFFF;
                border-color: #10B981;
            }
        """)
        self.btn_export.clicked.connect(lambda: self.sig_export_requested.emit(self.stem_name))
        layout.addWidget(self.btn_export)

    def _toggle_solo(self):
        self.is_solo = not self.is_solo
        self._update_solo_style()
        self.sig_solo_toggled.emit(self.stem_name, self.is_solo)

    def _update_solo_style(self):
        if self.is_solo:
            self.btn_solo.setStyleSheet("""
                QPushButton {
                    background-color: #F59E0B;
                    color: #000000;
                    border: 1px solid #FBBF24;
                    font-weight: 900;
                    border-radius: 6px;
                }
            """)
        else:
            self.btn_solo.setStyleSheet("""
                QPushButton {
                    background-color: #1F2232;
                    color: #94A3B8;
                    border: 1px solid #2F344B;
                    font-weight: 700;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    color: #F8FAFC;
                    border-color: #F59E0B;
                }
            """)

    def _toggle_mute(self):
        self.is_muted = not self.is_muted
        self._update_mute_style()
        self.sig_mute_toggled.emit(self.stem_name, self.is_muted)

    def _update_mute_style(self):
        if self.is_muted:
            self.btn_mute.setStyleSheet("""
                QPushButton {
                    background-color: #DC2626;
                    color: #FFFFFF;
                    border: 1px solid #EF4444;
                    font-weight: 900;
                    border-radius: 6px;
                }
            """)
        else:
            self.btn_mute.setStyleSheet("""
                QPushButton {
                    background-color: #1F2232;
                    color: #94A3B8;
                    border: 1px solid #2F344B;
                    font-weight: 700;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    color: #F8FAFC;
                    border-color: #EF4444;
                }
            """)

    def _on_volume_changed(self, value: int):
        self.volume = float(value) / 100.0
        self.lbl_vol_val.setText(f"{value}%")
        self.sig_volume_changed.emit(self.stem_name, self.volume)

    def reset_controls(self):
        """Reset solo, mute, and volume to default state."""
        self.is_solo = False
        self.is_muted = False
        self.volume = 1.0
        self._update_solo_style()
        self._update_mute_style()
        self.slider_vol.setValue(100)
