"""Global Transport and Timeline control bar."""
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QSlider, QWidget
)
from PySide6.QtCore import Qt, Signal
from src.utils.formatters import format_duration


class TransportWidget(QFrame):
    """
    Bottom control bar for synchronized multi-track playback, timeline scrubbing,
    and batch stems export.
    """
    sig_play_clicked = Signal()
    sig_pause_clicked = Signal()
    sig_stop_clicked = Signal()
    sig_seek_requested = Signal(float)          # normalized fraction (0.0 to 1.0)
    sig_master_volume_changed = Signal(float)   # 0.0 to 1.5
    sig_export_all_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_playing = False
        self.total_duration_sec = 0.0
        self.current_time_sec = 0.0
        self._user_is_seeking = False

        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QFrame {
                background-color: #12141F;
                border-top: 1px solid #282B3E;
                padding: 10px 20px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        # 1. Timeline scrubbing row
        timeline_layout = QHBoxLayout()
        timeline_layout.setSpacing(12)

        self.lbl_current_time = QLabel("00:00")
        self.lbl_current_time.setStyleSheet("font-size: 12px; font-weight: 700; color: #8B5CF6; font-family: monospace;")

        self.timeline_slider = QSlider(Qt.Horizontal)
        self.timeline_slider.setRange(0, 1000)
        self.timeline_slider.setValue(0)
        self.timeline_slider.setCursor(Qt.PointingHandCursor)
        self.timeline_slider.sliderPressed.connect(self._on_seek_pressed)
        self.timeline_slider.sliderReleased.connect(self._on_seek_released)
        self.timeline_slider.valueChanged.connect(self._on_seek_value_changed)

        self.lbl_total_time = QLabel("00:00")
        self.lbl_total_time.setStyleSheet("font-size: 12px; font-weight: 600; color: #94A3B8; font-family: monospace;")

        timeline_layout.addWidget(self.lbl_current_time)
        timeline_layout.addWidget(self.timeline_slider, stretch=1)
        timeline_layout.addWidget(self.lbl_total_time)
        layout.addLayout(timeline_layout)

        # 2. Main Controls row
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(16)

        # Left: Export All Stems button
        self.btn_export_all = QPushButton("💾 Exportar Todas as Faixas (WAV)")
        self.btn_export_all.setToolTip("Exportar todos os stems simultaneamente para uma pasta em WAV")
        self.btn_export_all.setCursor(Qt.PointingHandCursor)
        self.btn_export_all.setStyleSheet("""
            QPushButton {
                background-color: #1E293B;
                color: #38BDF8;
                border: 1px solid #0284C7;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0284C7;
                color: #FFFFFF;
            }
            QPushButton:disabled {
                background-color: #151722;
                color: #475569;
                border-color: #1E293B;
            }
        """)
        self.btn_export_all.clicked.connect(self.sig_export_all_requested.emit)
        self.btn_export_all.setEnabled(False)
        controls_layout.addWidget(self.btn_export_all)

        controls_layout.addStretch(1)

        # Center: Play/Pause and Stop buttons
        center_box = QHBoxLayout()
        center_box.setSpacing(12)

        self.btn_stop = QPushButton("⏹")
        self.btn_stop.setToolTip("Parar e voltar ao início")
        self.btn_stop.setFixedSize(40, 40)
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background-color: #1F2232;
                border: 1px solid #32374E;
                font-size: 16px;
                border-radius: 20px;
            }
            QPushButton:hover {
                background-color: #2D3349;
                border-color: #EF4444;
            }
        """)
        self.btn_stop.clicked.connect(self._on_stop_clicked)
        self.btn_stop.setEnabled(False)

        self.btn_play_pause = QPushButton("▶")
        self.btn_play_pause.setToolTip("Reproduzir / Pausar faixas sincronizadas")
        self.btn_play_pause.setFixedSize(48, 48)
        self.btn_play_pause.setCursor(Qt.PointingHandCursor)
        self.btn_play_pause.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8B5CF6, stop:1 #6D28D9);
                border: 1px solid #A78BFA;
                color: #FFFFFF;
                font-size: 20px;
                font-weight: 900;
                border-radius: 24px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9D6EFF, stop:1 #7C3AED);
            }
            QPushButton:disabled {
                background: #252839;
                border-color: #32374E;
                color: #4B526D;
            }
        """)
        self.btn_play_pause.clicked.connect(self._on_play_pause_clicked)
        self.btn_play_pause.setEnabled(False)

        center_box.addWidget(self.btn_stop)
        center_box.addWidget(self.btn_play_pause)
        controls_layout.addLayout(center_box)

        controls_layout.addStretch(1)

        # Right: Master volume
        vol_box = QHBoxLayout()
        vol_box.setSpacing(8)

        lbl_vol_title = QLabel("Master:")
        lbl_vol_title.setStyleSheet("font-size: 12px; color: #94A3B8; font-weight: 600;")

        self.slider_master_vol = QSlider(Qt.Horizontal)
        self.slider_master_vol.setRange(0, 150)
        self.slider_master_vol.setValue(100)
        self.slider_master_vol.setFixedWidth(100)
        self.slider_master_vol.setCursor(Qt.PointingHandCursor)
        self.slider_master_vol.valueChanged.connect(self._on_master_vol_changed)

        self.lbl_master_vol = QLabel("100%")
        self.lbl_master_vol.setFixedWidth(40)
        self.lbl_master_vol.setStyleSheet("font-size: 11px; color: #F8FAFC; font-weight: 700;")

        vol_box.addWidget(lbl_vol_title)
        vol_box.addWidget(self.slider_master_vol)
        vol_box.addWidget(self.lbl_master_vol)
        controls_layout.addLayout(vol_box)

        layout.addLayout(controls_layout)

    def set_duration(self, duration_sec: float):
        """Set song total duration in seconds."""
        self.total_duration_sec = max(0.0, duration_sec)
        self.lbl_total_time.setText(format_duration(self.total_duration_sec))
        self.lbl_current_time.setText("00:00")
        self.timeline_slider.setValue(0)
        enabled = self.total_duration_sec > 0
        self.btn_play_pause.setEnabled(enabled)
        self.btn_stop.setEnabled(enabled)
        self.btn_export_all.setEnabled(enabled)

    def update_position(self, current_sec: float, total_sec: float):
        """Update playback position from audio player callback."""
        if self._user_is_seeking:
            return
            
        self.current_time_sec = current_sec
        self.lbl_current_time.setText(format_duration(current_sec))
        
        if total_sec > 0:
            fraction = min(1.0, max(0.0, current_sec / total_sec))
            self.timeline_slider.blockSignals(True)
            self.timeline_slider.setValue(int(fraction * 1000))
            self.timeline_slider.blockSignals(False)

    def set_playing_state(self, is_playing: bool):
        """Update play/pause icon state."""
        self.is_playing = is_playing
        self.btn_play_pause.setText("⏸" if is_playing else "▶")

    def _on_play_pause_clicked(self):
        if self.is_playing:
            self.sig_pause_clicked.emit()
            self.set_playing_state(False)
        else:
            self.sig_play_clicked.emit()
            self.set_playing_state(True)

    def _on_stop_clicked(self):
        self.set_playing_state(False)
        self.lbl_current_time.setText("00:00")
        self.timeline_slider.setValue(0)
        self.sig_stop_clicked.emit()

    def _on_seek_pressed(self):
        self._user_is_seeking = True

    def _on_seek_released(self):
        self._user_is_seeking = False
        fraction = float(self.timeline_slider.value()) / 1000.0
        self.sig_seek_requested.emit(fraction)

    def _on_seek_value_changed(self, value: int):
        if self._user_is_seeking and self.total_duration_sec > 0:
            preview_sec = (float(value) / 1000.0) * self.total_duration_sec
            self.lbl_current_time.setText(format_duration(preview_sec))

    def _on_master_vol_changed(self, value: int):
        vol = float(value) / 100.0
        self.lbl_master_vol.setText(f"{value}%")
        self.sig_master_volume_changed.emit(vol)
