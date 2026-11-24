"""Main Application Window for AI Audio Separation."""
import os
import subprocess
from typing import Dict, Optional, Any
import numpy as np
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QProgressBar, QScrollArea, QFrame,
    QFileDialog, QMessageBox, QCheckBox, QLineEdit, QTabWidget,
    QApplication, QGridLayout
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QIcon

from src.gui.style import MAIN_STYLESHEET, COLORS
from src.gui.drop_zone import DropZoneWidget
from src.gui.stem_widget import StemWidget
from src.gui.transport import TransportWidget
from src.separator.demucs_engine import DemucsEngine
from src.separator.pipeline_worker import UnifiedPipelineWorker
from src.downloader.youtube_downloader import YouTubeDownloader, InfoFetcherWorker
from src.audio.ffmpeg_converter import FFmpegService
from src.audio.player import MultiTrackPlayer
from src.audio.exporter import export_stem_to_wav, export_all_stems, sanitize_stem_slug
from src.utils.system_info import get_system_hardware_info
from src.utils.formatters import format_duration


class MainWindow(QMainWindow):
    """Primary Moises AI-inspired application window with YouTube & Local File support."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Moises AI — Separador de Áudio por IA")
        self.resize(1080, 820)
        self.setMinimumSize(880, 640)
        
        # Core state
        self.loaded_filepath: Optional[str] = None
        self.loaded_metadata: Optional[Dict[str, Any]] = None
        self.stems: Dict[str, np.ndarray] = {}
        self.stem_widgets: Dict[str, StemWidget] = {}
        self.stem_sample_rate: int = 44100
        self.current_output_folder: Optional[str] = None
        
        # Audio Player Engine
        self.player = MultiTrackPlayer(sample_rate=44100)
        self.pipeline_worker: Optional[UnifiedPipelineWorker] = None
        self.info_fetcher: Optional[InfoFetcherWorker] = None
        
        # Services & Inspection
        self.yt_downloader = YouTubeDownloader()
        self.ffmpeg_service = FFmpegService()
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

        # 2.3 Input Source Tabs (YouTube URL or Local File)
        self.input_tabs = self._create_input_source_tabs()
        self.content_layout.addWidget(self.input_tabs)

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
        
        lbl_sub = QLabel("Separação de Faixas Musicais (Stems) por Inteligência Artificial em Alta Resolução (Local & YouTube)")
        lbl_sub.setStyleSheet("font-size: 11px; color: #94A3B8;")
        
        title_box.addWidget(lbl_brand)
        title_box.addWidget(lbl_sub)
        layout.addLayout(title_box)

        layout.addStretch()

        # FFmpeg status indicator
        ffmpeg_ok = self.ffmpeg_service.is_available()
        ffmpeg_text = "✓ FFmpeg Ativo" if ffmpeg_ok else "✗ FFmpeg Ausente"
        lbl_ffmpeg = QLabel(ffmpeg_text)
        lbl_ffmpeg.setProperty("badge", "true")
        if not ffmpeg_ok:
            lbl_ffmpeg.setStyleSheet("background-color: #3B1B1B; color: #F87171; border: 1px solid #7F1D1D;")
        layout.addWidget(lbl_ffmpeg)

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

    def _create_input_source_tabs(self) -> QTabWidget:
        """Create tabs for switching between YouTube URL and Local Audio File."""
        tabs = QTabWidget()
        tabs.setCursor(Qt.PointingHandCursor)

        # Tab 1: YouTube Link
        yt_tab = self._create_youtube_tab()
        tabs.addTab(yt_tab, "🔗 Link do YouTube")

        # Tab 2: Local File
        local_tab = self._create_local_file_tab()
        tabs.addTab(local_tab, "📁 Arquivo Local")

        tabs.currentChanged.connect(self._on_input_tab_changed)
        return tabs

    def _create_youtube_tab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Instruction
        lbl_inst = QLabel("Cole o link do vídeo do YouTube para baixar e separar automaticamente:")
        lbl_inst.setStyleSheet("color: #F8FAFC; font-size: 13px; font-weight: 600;")
        layout.addWidget(lbl_inst)

        # Input row with Text Field, Paste and Validate Buttons
        input_row = QHBoxLayout()
        input_row.setSpacing(10)

        self.txt_youtube_url = QLineEdit()
        self.txt_youtube_url.setPlaceholderText("https://www.youtube.com/watch?v=... ou https://youtu.be/...")
        self.txt_youtube_url.textChanged.connect(self._on_youtube_url_text_changed)
        self.txt_youtube_url.returnPressed.connect(self._fetch_youtube_info)

        self.btn_paste_url = QPushButton("📋 Colar")
        self.btn_paste_url.setCursor(Qt.PointingHandCursor)
        self.btn_paste_url.clicked.connect(self._on_paste_url)

        self.btn_fetch_info = QPushButton("🔍 Validar Link")
        self.btn_fetch_info.setCursor(Qt.PointingHandCursor)
        self.btn_fetch_info.clicked.connect(self._fetch_youtube_info)

        input_row.addWidget(self.txt_youtube_url, stretch=4)
        input_row.addWidget(self.btn_paste_url)
        input_row.addWidget(self.btn_fetch_info)
        layout.addLayout(input_row)

        # YouTube Preview Card
        self.card_yt_preview = QFrame()
        self.card_yt_preview.setStyleSheet("""
            QFrame {
                background-color: #1A1D2C;
                border: 1px solid #2F344B;
                border-radius: 10px;
                padding: 12px;
            }
        """)
        self.card_yt_preview.setVisible(False)
        preview_layout = QVBoxLayout(self.card_yt_preview)
        preview_layout.setContentsMargins(14, 10, 14, 10)
        preview_layout.setSpacing(8)

        # Header preview
        prev_head = QHBoxLayout()
        self.lbl_yt_title = QLabel("Título do Vídeo")
        self.lbl_yt_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #38BDF8;")
        
        self.btn_clear_yt = QPushButton("Limpar")
        self.btn_clear_yt.setCursor(Qt.PointingHandCursor)
        self.btn_clear_yt.setStyleSheet("""
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
        self.btn_clear_yt.clicked.connect(self._clear_youtube_input)

        prev_head.addWidget(self.lbl_yt_title, stretch=1)
        prev_head.addWidget(self.btn_clear_yt)
        preview_layout.addLayout(prev_head)

        # Details row
        details_layout = QHBoxLayout()
        details_layout.setSpacing(20)

        self.lbl_yt_channel = QLabel("Canal: -")
        self.lbl_yt_channel.setStyleSheet("color: #94A3B8; font-size: 12px;")

        self.lbl_yt_duration = QLabel("Duração: -")
        self.lbl_yt_duration.setStyleSheet("color: #94A3B8; font-size: 12px;")

        self.lbl_yt_status = QLabel("✓ Pronto para download e separação")
        self.lbl_yt_status.setStyleSheet("color: #10B981; font-size: 12px; font-weight: 600;")

        details_layout.addWidget(self.lbl_yt_channel)
        details_layout.addWidget(self.lbl_yt_duration)
        details_layout.addStretch()
        details_layout.addWidget(self.lbl_yt_status)
        preview_layout.addLayout(details_layout)

        layout.addWidget(self.card_yt_preview)

        return container

    def _create_local_file_tab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        
        self.drop_zone = DropZoneWidget()
        self.drop_zone.sig_file_loaded.connect(self._on_file_loaded)
        self.drop_zone.sig_file_cleared.connect(self._on_file_cleared)
        layout.addWidget(self.drop_zone)
        
        return container

    def _create_processing_card(self) -> QFrame:
        card = QFrame()
        card.setProperty("card", "true")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        # 1. Pipeline Steps Flow Indicator
        steps_row = QHBoxLayout()
        steps_row.setSpacing(8)

        self.step_labels = []
        step_names = [
            ("step_dl", "1. Obtenção do Áudio"),
            ("step_ff", "2. Preparação (FFmpeg)"),
            ("step_ai", "3. Separação por IA"),
            ("step_done", "4. Concluído")
        ]
        for key, name in step_names:
            lbl = QLabel(name)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("""
                QLabel {
                    background-color: #1A1D2A;
                    color: #64748B;
                    border: 1px solid #282B3E;
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-size: 11px;
                    font-weight: 600;
                }
            """)
            steps_row.addWidget(lbl, stretch=1)
            self.step_labels.append(lbl)

        layout.addLayout(steps_row)

        # 2. Buttons row
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

        self.btn_open_folder = QPushButton("📁 Abrir Pasta de Resultados")
        self.btn_open_folder.setProperty("success", "true")
        self.btn_open_folder.setCursor(Qt.PointingHandCursor)
        self.btn_open_folder.setVisible(False)
        self.btn_open_folder.clicked.connect(self._on_open_output_folder)

        btn_row.addWidget(self.btn_separate)
        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_open_folder)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # 3. Progress bar and status
        self.progress_container = QWidget()
        self.progress_container.setVisible(False)
        p_layout = QVBoxLayout(self.progress_container)
        p_layout.setContentsMargins(0, 0, 0, 0)
        p_layout.setSpacing(6)

        status_row = QHBoxLayout()
        self.lbl_status = QLabel("Aguardando início...")
        self.lbl_status.setStyleSheet("color: #38BDF8; font-weight: 600; font-size: 12px;")

        self.lbl_dl_details = QLabel("")
        self.lbl_dl_details.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: 500;")

        status_row.addWidget(self.lbl_status)
        status_row.addStretch()
        status_row.addWidget(self.lbl_dl_details)
        p_layout.addLayout(status_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
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

    def _set_active_step_badge(self, active_index: int):
        """Update step visual indicators (0: Download, 1: FFmpeg, 2: Demucs, 3: Done)."""
        styles = {
            "idle": "background-color: #1A1D2A; color: #64748B; border: 1px solid #282B3E; border-radius: 6px; padding: 6px 12px; font-size: 11px; font-weight: 600;",
            "active": "background-color: #2D1B4E; color: #C4B5FD; border: 1px solid #8B5CF6; border-radius: 6px; padding: 6px 12px; font-size: 11px; font-weight: 700;",
            "done": "background-color: #064E3B; color: #6EE7B7; border: 1px solid #059669; border-radius: 6px; padding: 6px 12px; font-size: 11px; font-weight: 700;"
        }
        for idx, lbl in enumerate(self.step_labels):
            if idx < active_index:
                lbl.setStyleSheet(styles["done"])
            elif idx == active_index:
                lbl.setStyleSheet(styles["active"])
            else:
                lbl.setStyleSheet(styles["idle"])

    def _reset_step_badges(self):
        for lbl in self.step_labels:
            lbl.setStyleSheet("background-color: #1A1D2A; color: #64748B; border: 1px solid #282B3E; border-radius: 6px; padding: 6px 12px; font-size: 11px; font-weight: 600;")

    # =========================================================================
    # YouTube URL Handlers
    # =========================================================================
    def _on_paste_url(self):
        clipboard_text = QApplication.clipboard().text().strip()
        if clipboard_text:
            self.txt_youtube_url.setText(clipboard_text)
            self._fetch_youtube_info()

    def _on_youtube_url_text_changed(self, text: str):
        clean_text = text.strip()
        is_valid = self.yt_downloader.is_valid_url(clean_text)
        if self.input_tabs.currentIndex() == 0:
            self.btn_separate.setEnabled(is_valid)
        if not clean_text:
            self.card_yt_preview.setVisible(False)

    def _fetch_youtube_info(self):
        url = self.txt_youtube_url.text().strip()
        if not url:
            return
        if not self.yt_downloader.is_valid_url(url):
            QMessageBox.warning(
                self,
                "URL Inválida",
                "A URL inserida não corresponde a um link válido do YouTube.\n"
                "Exemplo suportado: https://www.youtube.com/watch?v=..."
            )
            return

        self.btn_fetch_info.setEnabled(False)
        self.btn_fetch_info.setText("Consultando...")

        # Worker assíncrono para não travar a GUI
        self.info_fetcher = InfoFetcherWorker(url, parent=self)
        self.info_fetcher.sig_info_ready.connect(self._on_youtube_info_ready)
        self.info_fetcher.sig_error.connect(self._on_youtube_info_error)
        self.info_fetcher.start()

    def _on_youtube_info_ready(self, info: dict):
        self.btn_fetch_info.setEnabled(True)
        self.btn_fetch_info.setText("🔍 Validar Link")

        self.lbl_yt_title.setText(info.get("title", "Título Desconhecido"))
        self.lbl_yt_channel.setText(f"Canal: {info.get('channel', 'Desconhecido')}")
        dur = info.get("duration", 0)
        self.lbl_yt_duration.setText(f"Duração: {format_duration(dur)}")
        self.lbl_yt_status.setText("✓ Vídeo validado e pronto para separação")
        self.card_yt_preview.setVisible(True)

        if self.input_tabs.currentIndex() == 0:
            self.btn_separate.setEnabled(True)

    def _on_youtube_info_error(self, err_msg: str):
        self.btn_fetch_info.setEnabled(True)
        self.btn_fetch_info.setText("🔍 Validar Link")
        QMessageBox.warning(
            self,
            "Não foi possível obter informações",
            f"Falha ao consultar informações do vídeo no YouTube:\n{err_msg}"
        )

    def _clear_youtube_input(self):
        self.txt_youtube_url.clear()
        self.card_yt_preview.setVisible(False)
        if self.input_tabs.currentIndex() == 0:
            self.btn_separate.setEnabled(False)

    def _on_input_tab_changed(self, index: int):
        if index == 0:  # YouTube tab
            url = self.txt_youtube_url.text().strip()
            self.btn_separate.setEnabled(self.yt_downloader.is_valid_url(url))
        else:  # Local file tab
            self.btn_separate.setEnabled(self.loaded_filepath is not None)

    # =========================================================================
    # Local File Handlers
    # =========================================================================
    def _on_model_changed(self, index: int):
        model_id = self.combo_model.currentData()
        if model_id in DemucsEngine.MODELS:
            self.lbl_model_desc.setText(DemucsEngine.MODELS[model_id]["description"])

    def _on_file_loaded(self, filepath: str, metadata: dict):
        self.loaded_filepath = filepath
        self.loaded_metadata = metadata
        self.input_tabs.setCurrentIndex(1)
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

    # =========================================================================
    # Pipeline Execution & Slots
    # =========================================================================
    def _start_separation(self):
        current_tab = self.input_tabs.currentIndex()

        if current_tab == 0:
            # YouTube URL Mode
            url = self.txt_youtube_url.text().strip()
            if not self.yt_downloader.is_valid_url(url):
                QMessageBox.warning(self, "Aviso", "Por favor, insira uma URL válida do YouTube antes de iniciar.")
                return
            mode = "url"
            source = url
        else:
            # Local File Mode
            if not self.loaded_filepath or not os.path.exists(self.loaded_filepath):
                QMessageBox.warning(self, "Aviso", "Por favor, selecione um arquivo de áudio válido antes de iniciar.")
                return
            mode = "file"
            source = self.loaded_filepath

        model_id = self.combo_model.currentData()

        # Update GUI controls state
        self.btn_separate.setEnabled(False)
        self.btn_cancel.setVisible(True)
        self.btn_cancel.setEnabled(True)
        self.btn_open_folder.setVisible(False)
        self.input_tabs.setEnabled(False)
        self.progress_container.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Preparando pipeline de separação de áudio...")
        self.lbl_dl_details.setText("")
        self._set_active_step_badge(0 if mode == "url" else 1)
        self.stems_card.setVisible(False)
        self.player.stop()

        # Instantiate unified pipeline worker
        self.pipeline_worker = UnifiedPipelineWorker(
            mode=mode,
            source=source,
            output_base_dir="output",
            model_name=model_id,
            device_name=self.hw_info["device"],
            shifts=1,
            overlap=0.25,
            match_sample_rate=self.chk_match_sr.isChecked(),
            parent=self
        )
        self.pipeline_worker.sig_stage_changed.connect(self._on_worker_stage_changed)
        self.pipeline_worker.sig_progress.connect(self._on_worker_progress)
        self.pipeline_worker.sig_download_details.connect(self._on_download_details)
        self.pipeline_worker.sig_finished.connect(self._on_pipeline_finished)
        self.pipeline_worker.sig_error.connect(self._on_worker_error)
        self.pipeline_worker.sig_cancelled.connect(self._on_worker_cancelled)
        self.pipeline_worker.start()

    def _cancel_separation(self):
        if self.pipeline_worker and self.pipeline_worker.isRunning():
            self.lbl_status.setText("Cancelando processamento...")
            self.btn_cancel.setEnabled(False)
            self.pipeline_worker.cancel()

    def _on_worker_stage_changed(self, stage_id: str, stage_name: str):
        self.lbl_status.setText(stage_name)
        if stage_id == "download":
            self._set_active_step_badge(0)
        elif stage_id == "convert":
            self._set_active_step_badge(1)
            self.lbl_dl_details.setText("")
        elif stage_id == "separate":
            self._set_active_step_badge(2)
            self.lbl_dl_details.setText("")
        elif stage_id in ("organize", "done"):
            self._set_active_step_badge(3)
            self.lbl_dl_details.setText("")

    def _on_worker_progress(self, percent: int, message: str):
        self.progress_bar.setValue(percent)
        self.lbl_status.setText(message)

    def _on_download_details(self, details: dict):
        speed = details.get("speed_str", "")
        eta = details.get("eta_str", "")
        if speed:
            self.lbl_dl_details.setText(f"Velocidade: {speed} | ETA: {eta}")

    def _on_worker_finished(self, stems_dict: Dict[str, np.ndarray], sample_rate: int, metadata: dict, output_folder: Optional[str] = None):
        """Método de retrocompatibilidade com a suíte de testes existente."""
        self._on_pipeline_finished(stems_dict, sample_rate, metadata, output_folder or os.path.abspath("output"))

    def _on_pipeline_finished(self, stems_dict: Dict[str, np.ndarray], sample_rate: int, metadata: dict, output_folder: str):
        self.stems = stems_dict
        self.stem_sample_rate = sample_rate
        self.loaded_metadata = metadata
        self.current_output_folder = output_folder

        self.btn_separate.setEnabled(True)
        self.btn_cancel.setVisible(False)
        self.btn_cancel.setEnabled(True)
        self.btn_open_folder.setVisible(True)
        self.input_tabs.setEnabled(True)
        self._set_active_step_badge(3)
        self.lbl_status.setText("Separação e organização concluídas com sucesso!")
        self.lbl_dl_details.setText(f"Salvo em: {os.path.basename(output_folder)}")

        # Load stems into synchronized playback engine
        self.player.load_stems(self.stems, sample_rate=sample_rate)
        self.transport.set_duration(self.player.duration_seconds)

        # Build stem rows in GUI
        self._populate_stems(self.stems, self.player.duration_seconds)
        self.stems_card.setVisible(True)

        # User feedback popup (apenas se a interface estiver interativa e visível)
        if self.isVisible() and os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            reply = QMessageBox.information(
                self,
                "Separação Concluída com Sucesso!",
                f"O áudio foi separado com sucesso por IA e salvo na pasta:\n\n{output_folder}\n\n"
                f"Deseja abrir a pasta agora para conferir as faixas?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._on_open_output_folder()

    def _on_worker_error(self, error_message: str):
        self.btn_separate.setEnabled(True)
        self.btn_cancel.setVisible(False)
        self.btn_cancel.setEnabled(True)
        self.input_tabs.setEnabled(True)
        self._reset_step_badges()
        self.lbl_status.setText("Falha no processamento.")
        self.lbl_dl_details.setText("")
        QMessageBox.critical(self, "Erro no Processamento", error_message)

    def _on_worker_cancelled(self):
        self.btn_separate.setEnabled(True)
        self.btn_cancel.setVisible(False)
        self.btn_cancel.setEnabled(True)
        self.input_tabs.setEnabled(True)
        self._reset_step_badges()
        self.lbl_status.setText("Processamento cancelado pelo usuário.")
        self.lbl_dl_details.setText("")

    def _on_open_output_folder(self):
        folder = self.current_output_folder
        if not folder or not os.path.exists(folder):
            folder = os.path.abspath("output")
        os.makedirs(folder, exist_ok=True)
        self._open_folder(folder)

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

    # =========================================================================
    # Stem Control Slots
    # =========================================================================
    def _on_stem_volume_changed(self, stem_name: str, volume: float):
        self.player.set_stem_volume(stem_name, volume)

    def _on_stem_mute_toggled(self, stem_name: str, is_muted: bool):
        self.player.set_stem_muted(stem_name, is_muted)

    def _on_stem_solo_toggled(self, stem_name: str, is_solo: bool):
        self.player.set_stem_solo(stem_name, is_solo)

    def _on_stem_audition_requested(self, stem_name: str):
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

    # =========================================================================
    # Playback Transport Slots
    # =========================================================================
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
        """Clean up audio streams and workers on window close."""
        self.playback_timer.stop()
        if self.player:
            self.player.stop()
        if self.pipeline_worker and self.pipeline_worker.isRunning():
            self.pipeline_worker.cancel()
            self.pipeline_worker.wait(2000)
        if self.info_fetcher and self.info_fetcher.isRunning():
            self.info_fetcher.wait(1000)
        event.accept()
