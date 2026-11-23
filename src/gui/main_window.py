"""Main Application Window for AI Audio Separation."""
import os
import subprocess
from typing import Dict, Optional, Any
import numpy as np
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QProgressBar, QScrollArea, QFrame,
    QFileDialog, QMessageBox, QCheckBox
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QIcon

from src.gui.style import MAIN_STYLESHEET, COLORS
from src.gui.drop_zone import DropZoneWidget
from src.gui.stem_widget import StemWidget
from src.gui.transport import TransportWidget
from src.separator.demucs_engine import DemucsEngine
from src.separator.worker import SeparationWorker
from src.audio.player import MultiTrackPlayer
from src.audio.exporter import export_stem_to_wav, export_all_stems, sanitize_stem_slug
from src.utils.system_info import get_system_hardware_info
from src.utils.formatters import format_duration


class MainWindow(QMainWindow):
    """Primary Moises AI-inspired application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Moises AI — Separador de Áudio por IA")
        self.resize(1050, 780)
        self.setMinimumSize(850, 600)
        
        # Core state
        self.loaded_filepath: Optional[str] = None
        self.loaded_metadata: Optional[Dict[str, Any]] = None
        self.stems: Dict[str, np.ndarray] = {}
        self.stem_widgets: Dict[str, StemWidget] = {}
        self.stem_sample_rate: int = 44100
        
        # Audio Player Engine
        self.player = MultiTrackPlayer(sample_rate=44100)
        self.worker: Optional[SeparationWorker] = None
        
        # Hardware inspection
        self.hw_info = get_system_hardware_info()

        # GUI Timer for thread-safe playback position polling
        self.playback_timer = QTimer(self)
        self.playback_timer.setInterval(40)  # ~25 FPS smooth timeline
        self.playback_timer.timeout.connect(self._on_playback_tick)

        self._init_ui()
        self.setStyleSheet(MAIN_STYLESHEET)

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Header Bar
        header = self._create_header()
        root_layout.addWidget(header)

        # 2. Main Scroll Area for Content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        content_container = QWidget()
        self.content_layout = QVBoxLayout(content_container)
        self.content_layout.setContentsMargins(28, 20, 28, 20)
        self.content_layout.setSpacing(20)

        # 2.1 Hardware banner (if low RAM or CPU warning)
        if self.hw_info.get("warning"):
            banner = self._create_hardware_banner(self.hw_info["warning"])
            self.content_layout.addWidget(banner)

        # 2.2 Model & Settings Card
        settings_card = self._create_settings_card()
        self.content_layout.addWidget(settings_card)

        # 2.3 Audio Import Area (DropZone)
        self.drop_zone = DropZoneWidget()
        self.drop_zone.sig_file_loaded.connect(self._on_file_loaded)
        self.drop_zone.sig_file_cleared.connect(self._on_file_cleared)
        self.content_layout.addWidget(self.drop_zone)

        # 2.4 Processing Action Panel
        self.processing_card = self._create_processing_card()
        self.content_layout.addWidget(self.processing_card)

        # 2.5 Separated Stems Container
        self.stems_card = self._create_stems_container()
        self.stems_card.setVisible(False)
        self.content_layout.addWidget(self.stems_card)

        self.content_layout.addStretch(1)
        scroll.setWidget(content_container)
        root_layout.addWidget(scroll, stretch=1)

        # 3. Bottom Master Transport Bar
        self.transport = TransportWidget()
        self.transport.sig_play_clicked.connect(self._on_transport_play)
        self.transport.sig_pause_clicked.connect(self._on_transport_pause)
        self.transport.sig_stop_clicked.connect(self._on_transport_stop)
        self.transport.sig_seek_requested.connect(self._on_transport_seek)
        self.transport.sig_master_volume_changed.connect(self._on_master_volume_changed)
        self.transport.sig_export_all_requested.connect(self._on_export_all_requested)
        root_layout.addWidget(self.transport)

    def _create_header(self) -> QWidget:
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #12141F;
                border-bottom: 1px solid #282B3E;
                padding: 12px 28px;
            }
        """)
        layout = QHBoxLayout(header_frame)
        layout.setContentsMargins(10, 8, 10, 8)

        # App Title & Subtitle
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        
        lbl_brand = QLabel("MOISES AI — SEPARADOR DE ÁUDIO")
        lbl_brand.setStyleSheet("font-size: 16px; font-weight: 800; color: #8B5CF6; letter-spacing: 1px;")
        
        lbl_sub = QLabel("Separação de Faixas Musicais (Stems) por Inteligência Artificial em Alta Resolução")
        lbl_sub.setStyleSheet("font-size: 11px; color: #94A3B8;")
        
        title_box.addWidget(lbl_brand)
        title_box.addWidget(lbl_sub)
        layout.addLayout(title_box)

        layout.addStretch()

        # Hardware Badge
        hw_text = f"⚡ {self.hw_info['device_name']}" if self.hw_info["cuda_available"] else f"💻 CPU ({self.hw_info['cpu_count']} cores)"
        if self.hw_info["ram_available_gb"] > 0:
            hw_text += f" | {self.hw_info['ram_available_gb']:.1f} GB RAM Livre"

        lbl_hw = QLabel(hw_text)
        lbl_hw.setProperty("badge", "true")
        layout.addWidget(lbl_hw)

        return header_frame

    def _create_hardware_banner(self, text: str) -> QWidget:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #241A12;
                border: 1px solid #B45309;
                border-radius: 8px;
                padding: 10px 16px;
            }
        """)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(8, 4, 8, 4)
        
        icon = QLabel("⚠️")
        icon.setStyleSheet("font-size: 14px;")
        
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #FDE68A; font-size: 12px; font-weight: 500;")
        
        layout.addWidget(icon)
        layout.addWidget(lbl)
        layout.addStretch()
        return card

    def _create_settings_card(self) -> QFrame:
        card = QFrame()
        card.setProperty("card", "true")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Title
        lbl_title = QLabel("Configurações do Modelo de IA")
        lbl_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #F8FAFC;")
        layout.addWidget(lbl_title)

        # Options layout
        options_layout = QHBoxLayout()
        options_layout.setSpacing(20)

        # Model Selector
        model_box = QVBoxLayout()
        lbl_model = QLabel("Modelo de Separação:")
        lbl_model.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 600;")
        
        self.combo_model = QComboBox()
        for model_id, name, desc in DemucsEngine.get_model_choices():
            self.combo_model.addItem(name, model_id)
        self.combo_model.currentIndexChanged.connect(self._on_model_changed)
        
        model_box.addWidget(lbl_model)
        model_box.addWidget(self.combo_model)
        options_layout.addLayout(model_box, stretch=2)

        # Fidelity options
        fidelity_box = QVBoxLayout()
        lbl_fidelity = QLabel("Qualidade e Resolução:")
        lbl_fidelity.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 600;")

        self.chk_match_sr = QCheckBox("Preservar Sample Rate original ao exportar (Sinc)")
        self.chk_match_sr.setChecked(True)
        self.chk_match_sr.setToolTip(
            "Se o arquivo original estiver em 48kHz ou 96kHz, reconstrói as faixas separadas na taxa original usando interpolação sinc."
        )
        self.chk_match_sr.setStyleSheet("color: #E2E8F0; font-size: 12px;")

        fidelity_box.addWidget(lbl_fidelity)
        fidelity_box.addWidget(self.chk_match_sr)
        options_layout.addLayout(fidelity_box, stretch=2)

        layout.addLayout(options_layout)

        # Description label
        self.lbl_model_desc = QLabel(DemucsEngine.MODELS["htdemucs"]["description"])
        self.lbl_model_desc.setStyleSheet("color: #94A3B8; font-size: 11px; font-style: italic;")
        layout.addWidget(self.lbl_model_desc)

        return card

    def _create_processing_card(self) -> QFrame:
        card = QFrame()
        card.setProperty("card", "true")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.btn_separate = QPushButton("⚡ Separar Áudio com IA")
        self.btn_separate.setProperty("primary", "true")
        self.btn_separate.setCursor(Qt.PointingHandCursor)
        self.btn_separate.setEnabled(False)
        self.btn_separate.clicked.connect(self._start_separation)

        self.btn_cancel = QPushButton("✕ Cancelar Processamento")
        self.btn_cancel.setProperty("danger", "true")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self._cancel_separation)

        btn_row.addWidget(self.btn_separate)
        btn_row.addWidget(self.btn_cancel)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Progress bar and status
        self.progress_container = QWidget()
        self.progress_container.setVisible(False)
        p_layout = QVBoxLayout(self.progress_container)
        p_layout.setContentsMargins(0, 0, 0, 0)
        p_layout.setSpacing(6)

        self.lbl_status = QLabel("Aguardando início...")
        self.lbl_status.setStyleSheet("color: #38BDF8; font-weight: 600; font-size: 12px;")

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        p_layout.addWidget(self.lbl_status)
        p_layout.addWidget(self.progress_bar)

        layout.addWidget(self.progress_container)

        return card

    def _create_stems_container(self) -> QFrame:
        card = QFrame()
        card.setProperty("card", "true")
        self.stems_card_layout = QVBoxLayout(card)
        self.stems_card_layout.setContentsMargins(20, 16, 20, 16)
        self.stems_card_layout.setSpacing(12)

        lbl_title = QLabel("Faixas Separadas (Stems)")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #F8FAFC;")
        self.stems_card_layout.addWidget(lbl_title)

        self.stems_rows_layout = QVBoxLayout()
        self.stems_rows_layout.setSpacing(10)
        self.stems_card_layout.addLayout(self.stems_rows_layout)

        return card

    # Event Handlers
    def _on_model_changed(self, index: int):
        model_id = self.combo_model.currentData()
        if model_id in DemucsEngine.MODELS:
            self.lbl_model_desc.setText(DemucsEngine.MODELS[model_id]["description"])

    def _on_file_loaded(self, filepath: str, metadata: dict):
        self.loaded_filepath = filepath
        self.loaded_metadata = metadata
        self.btn_separate.setEnabled(True)
        self.stems_card.setVisible(False)
        self.stems.clear()
        self.stem_widgets.clear()
        self.player.stop()
        self.transport.set_duration(0.0)

    def _on_file_cleared(self):
        self.loaded_filepath = None
        self.loaded_metadata = None
        self.btn_separate.setEnabled(False)
        self.stems_card.setVisible(False)
        self.stems.clear()
        self.stem_widgets.clear()
        self.player.stop()
        self.transport.set_duration(0.0)

    def _start_separation(self):
        if not self.loaded_filepath or not os.path.exists(self.loaded_filepath):
            QMessageBox.warning(self, "Aviso", "Por favor, selecione um arquivo WAV válido antes de iniciar.")
            return

        model_id = self.combo_model.currentData()
        
        self.btn_separate.setEnabled(False)
        self.btn_cancel.setVisible(True)
        self.progress_container.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Preparando separação por inteligência artificial...")
        self.stems_card.setVisible(False)
        self.player.stop()

        self.worker = SeparationWorker(
            filepath=self.loaded_filepath,
            model_name=model_id,
            device_name=self.hw_info["device"],
            shifts=1,
            overlap=0.25,
            parent=self
        )
        self.worker.sig_progress.connect(self._on_worker_progress)
        self.worker.sig_finished.connect(self._on_worker_finished)
        self.worker.sig_error.connect(self._on_worker_error)
        self.worker.sig_cancelled.connect(self._on_worker_cancelled)
        self.worker.start()

    def _cancel_separation(self):
        if self.worker and self.worker.isRunning():
            self.lbl_status.setText("Cancelando processamento...")
            self.btn_cancel.setEnabled(False)
            self.worker.cancel()

    def _on_worker_progress(self, percent: int, message: str):
        self.progress_bar.setValue(percent)
        self.lbl_status.setText(message)

    def _on_worker_finished(self, stems_dict: Dict[str, np.ndarray], sample_rate: int, metadata: dict):
        self.stems = stems_dict
        self.stem_sample_rate = sample_rate
        self.btn_separate.setEnabled(True)
        self.btn_cancel.setVisible(False)
        self.btn_cancel.setEnabled(True)
        self.lbl_status.setText("Separação concluída com sucesso!")
        
        # Load into synchronized player
        self.player.load_stems(self.stems, sample_rate=sample_rate)
        self.transport.set_duration(self.player.duration_seconds)

        # Build stem rows in GUI
        self._populate_stems(self.stems, self.player.duration_seconds)
        self.stems_card.setVisible(True)

    def _on_worker_error(self, error_message: str):
        self.btn_separate.setEnabled(True)
        self.btn_cancel.setVisible(False)
        self.btn_cancel.setEnabled(True)
        self.lbl_status.setText("Falha no processamento.")
        QMessageBox.critical(self, "Erro na Separação", error_message)

    def _on_worker_cancelled(self):
        self.btn_separate.setEnabled(True)
        self.btn_cancel.setVisible(False)
        self.btn_cancel.setEnabled(True)
        self.lbl_status.setText("Processamento cancelado pelo usuário.")

    def _populate_stems(self, stems_dict: Dict[str, np.ndarray], duration_sec: float):
        # Clear existing rows safely
        for i in reversed(range(self.stems_rows_layout.count())):
            item = self.stems_rows_layout.takeAt(i)
            widget = item.widget() if item else None
            if widget:
                widget.deleteLater()
        self.stem_widgets.clear()

        for stem_name in stems_dict.keys():
            widget = StemWidget(stem_name, duration_sec, self)
            widget.sig_volume_changed.connect(self._on_stem_volume_changed)
            widget.sig_mute_toggled.connect(self._on_stem_mute_toggled)
            widget.sig_solo_toggled.connect(self._on_stem_solo_toggled)
            widget.sig_audition_requested.connect(self._on_stem_audition_requested)
            widget.sig_export_requested.connect(self._on_stem_export_requested)
            
            self.stem_widgets[stem_name] = widget
            self.stems_rows_layout.addWidget(widget)

    # Stem Control Slots
    def _on_stem_volume_changed(self, stem_name: str, volume: float):
        self.player.set_stem_volume(stem_name, volume)

    def _on_stem_mute_toggled(self, stem_name: str, is_muted: bool):
        self.player.set_stem_muted(stem_name, is_muted)

    def _on_stem_solo_toggled(self, stem_name: str, is_solo: bool):
        self.player.set_stem_solo(stem_name, is_solo)

    def _on_stem_audition_requested(self, stem_name: str):
        """Audition (solo preview) this stem and start playback."""
        if stem_name in self.stem_widgets and self.stem_widgets[stem_name].is_solo and self.player.is_playing:
            self._on_transport_pause()
            return

        for name, widget in self.stem_widgets.items():
            if name == stem_name:
                widget.is_solo = True
                widget._update_solo_style()
                self.player.set_stem_solo(name, True)
            else:
                widget.is_solo = False
                widget._update_solo_style()
                self.player.set_stem_solo(name, False)
        
        self.player.play()
        self.playback_timer.start()
        self.transport.set_playing_state(True)

    def _on_stem_export_requested(self, stem_name: str):
        """Export single stem to lossless WAV."""
        if stem_name not in self.stems:
            return

        stem_slug = sanitize_stem_slug(stem_name)
        base_name = os.path.splitext(self.loaded_metadata["filename"])[0] if self.loaded_metadata else "audio"
        default_filename = f"{base_name}_{stem_slug}.wav"

        out_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Exportar Faixa {stem_name} em WAV",
            default_filename,
            "Arquivos WAV (*.wav)"
        )

        if not out_path:
            return

        try:
            match_sr = self.chk_match_sr.isChecked()
            export_stem_to_wav(
                stem_audio=self.stems[stem_name],
                stem_sample_rate=self.stem_sample_rate,
                output_path=out_path,
                original_metadata=self.loaded_metadata,
                match_original_sample_rate=match_sr
            )
            
            reply = QMessageBox.information(
                self,
                "Exportação Concluída",
                f"Faixa exportada com sucesso em alta resolução:\n{out_path}\n\nDeseja abrir a pasta?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._open_folder(os.path.dirname(out_path))

        except Exception as e:
            QMessageBox.critical(self, "Erro na Exportação", f"Falha ao exportar a faixa:\n{str(e)}")

    def _on_export_all_requested(self):
        """Export all separated stems into a selected directory."""
        if not self.stems:
            return

        output_dir = QFileDialog.getExistingDirectory(
            self,
            "Selecione a Pasta para Exportar Todas as Faixas",
            ""
        )
        if not output_dir:
            return

        base_name = os.path.splitext(self.loaded_metadata["filename"])[0] if self.loaded_metadata else "faixas"
        match_sr = self.chk_match_sr.isChecked()

        try:
            exported = export_all_stems(
                stems=self.stems,
                stem_sample_rate=self.stem_sample_rate,
                output_directory=output_dir,
                base_name=base_name,
                original_metadata=self.loaded_metadata,
                match_original_sample_rate=match_sr
            )

            file_list_str = "\n".join([f"• {os.path.basename(p)}" for p in exported])
            reply = QMessageBox.information(
                self,
                "Exportação Concluída",
                f"{len(exported)} faixas exportadas com sucesso em alta fidelidade WAV para:\n{output_dir}\n\n{file_list_str}\n\nDeseja abrir a pasta?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._open_folder(output_dir)

        except Exception as e:
            QMessageBox.critical(self, "Erro na Exportação", f"Falha ao exportar faixas:\n{str(e)}")

    def _open_folder(self, folder_path: str):
        try:
            subprocess.Popen(["xdg-open", folder_path])
        except Exception:
            pass

    # Playback Transport Slots
    def _on_transport_play(self):
        try:
            self.player.play()
            self.playback_timer.start()
        except Exception as e:
            QMessageBox.critical(self, "Erro no Dispositivo de Áudio", str(e))
            self.transport.set_playing_state(False)

    def _on_transport_pause(self):
        self.player.pause()
        self.playback_timer.stop()

    def _on_transport_stop(self):
        self.player.stop()
        self.playback_timer.stop()

    def _on_transport_seek(self, fraction: float):
        self.player.seek_normalized(fraction)

    def _on_master_volume_changed(self, volume: float):
        self.player.set_master_volume(volume)

    def _on_playback_tick(self):
        if not self.player.is_playing:
            self.playback_timer.stop()
            self.transport.set_playing_state(False)
            self.transport.update_position(
                self.player.current_time_seconds,
                self.player.duration_seconds
            )
            return
        self.transport.update_position(
            self.player.current_time_seconds,
            self.player.duration_seconds
        )

    def closeEvent(self, event):
        """Clean up audio streams and worker on window close."""
        self.playback_timer.stop()
        if self.player:
            self.player.stop()
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(2000)
        event.accept()
