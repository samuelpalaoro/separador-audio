"""
Tela de Configurações Globais do SamukaLab.
Permite configurar pastas de saída, aceleração de hardware, parâmetros DSP e preferências de exportação.
"""
import os
import shutil
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QFileDialog, QComboBox, QCheckBox, QLineEdit, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from src.config.settings import SettingsManager
from src.security.temp_manager import SafeTempManager
from src.gui.style import COLORS


class SettingsWidget(QWidget):
    """Painel de configurações e preferências da estação SamukaLab."""

    sig_settings_saved = Signal()

    def __init__(self, hardware_info: dict, parent=None):
        super().__init__(parent)
        self.hw_info = hardware_info
        self.settings_mgr = SettingsManager()
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(20)

        # Header
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        lbl_title = QLabel("Configurações do SamukaLab")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #F1F2F4;")
        lbl_sub = QLabel("Personalize os parâmetros de processamento, diretórios de trabalho e aceleração de hardware")
        lbl_sub.setStyleSheet("font-size: 11px; color: #9DA3AD;")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_sub)
        main_layout.addLayout(title_box)

        # 1. Output Directory Card
        card_dir = self._create_card("Diretório de Exportação Padrão")
        card_dir_layout = QVBoxLayout(card_dir)
        card_dir_layout.setContentsMargins(16, 14, 16, 14)
        card_dir_layout.setSpacing(10)

        dir_row = QHBoxLayout()
        self.txt_output_dir = QLineEdit(self.settings_mgr.get_output_dir())
        self.txt_output_dir.setReadOnly(True)
        self.btn_browse_dir = QPushButton("Selecionar Pasta...")
        self.btn_browse_dir.setCursor(Qt.PointingHandCursor)
        self.btn_browse_dir.clicked.connect(self._browse_output_dir)

        dir_row.addWidget(self.txt_output_dir, stretch=1)
        dir_row.addWidget(self.btn_browse_dir)
        card_dir_layout.addLayout(dir_row)
        main_layout.addWidget(card_dir)

        # 2. Audio & DSP Settings Card
        card_audio = self._create_card("Qualidade de Áudio e Formatos de Exportação")
        card_audio_layout = QVBoxLayout(card_audio)
        card_audio_layout.setContentsMargins(16, 14, 16, 14)
        card_audio_layout.setSpacing(12)

        opts_row = QHBoxLayout()
        opts_row.setSpacing(24)

        # Bit depth
        bit_box = QVBoxLayout()
        lbl_bit = QLabel("Resolução WAV padrão:")
        lbl_bit.setStyleSheet("color: #9DA3AD; font-size: 11px; font-weight: 600;")
        self.combo_bit_depth = QComboBox()
        self.combo_bit_depth.addItem("24-bit PCM (Profissional - Alta Resolução)", "PCM_24")
        self.combo_bit_depth.addItem("16-bit PCM (Padrão CD Áudio)", "PCM_16")
        self.combo_bit_depth.addItem("32-bit Float (Precisão Máxima de Ponto Flutuante)", "FLOAT")
        
        current_bit = self.settings_mgr.get("wav_bit_depth", "PCM_24")
        idx = self.combo_bit_depth.findData(current_bit)
        if idx >= 0:
            self.combo_bit_depth.setCurrentIndex(idx)
        bit_box.addWidget(lbl_bit)
        bit_box.addWidget(self.combo_bit_depth)
        opts_row.addLayout(bit_box, stretch=1)

        # Format
        fmt_box = QVBoxLayout()
        lbl_fmt = QLabel("Formato de Exportação:")
        lbl_fmt.setStyleSheet("color: #9DA3AD; font-size: 11px; font-weight: 600;")
        self.combo_format = QComboBox()
        self.combo_format.addItem("WAV (.wav) — Sem Compressão", "WAV")
        self.combo_format.addItem("FLAC (.flac) — Lossless Comprimido", "FLAC")
        fmt_box.addWidget(lbl_fmt)
        fmt_box.addWidget(self.combo_format)
        opts_row.addLayout(fmt_box, stretch=1)

        card_audio_layout.addLayout(opts_row)

        # Checkboxes
        self.chk_match_sr = QCheckBox("Preservar taxa de amostragem original (Sinc Interpolação para 48k/96k)")
        self.chk_match_sr.setChecked(self.settings_mgr.get("match_sample_rate", True))
        card_audio_layout.addWidget(self.chk_match_sr)

        self.chk_drum_sep = QCheckBox("Ativar Decomposição Experimental de Bateria (Kick, Snare, Hi-Hats, Cymbals, Toms)")
        self.chk_drum_sep.setChecked(self.settings_mgr.get("experimental_drum_separation", True))
        card_audio_layout.addWidget(self.chk_drum_sep)

        main_layout.addWidget(card_audio)

        # 3. Hardware & Acceleration Card
        card_hw = self._create_card("Aceleração de Hardware e Desempenho")
        card_hw_layout = QVBoxLayout(card_hw)
        card_hw_layout.setContentsMargins(16, 14, 16, 14)
        card_hw_layout.setSpacing(10)

        hw_row = QHBoxLayout()
        lbl_dev = QLabel("Dispositivo de Processamento:")
        lbl_dev.setStyleSheet("color: #9DA3AD; font-size: 11px; font-weight: 600;")
        self.combo_device = QComboBox()
        self.combo_device.addItem("Detecção Automática (GPU recomendada se disponível)", "auto")
        if self.hw_info.get("cuda_available"):
            self.combo_device.addItem(f"Forçar GPU NVIDIA ({self.hw_info['device_name']})", "cuda")
        self.combo_device.addItem(f"Forçar Processador CPU ({self.hw_info.get('cpu_count', 1)} Cores)", "cpu")
        
        dev_cur = self.settings_mgr.get("device_preference", "auto")
        idx_dev = self.combo_device.findData(dev_cur)
        if idx_dev >= 0:
            self.combo_device.setCurrentIndex(idx_dev)

        hw_row.addWidget(lbl_dev)
        hw_row.addWidget(self.combo_device, stretch=1)
        card_hw_layout.addLayout(hw_row)

        lbl_hw_note = QLabel(f"Hardware detectado: {self.hw_info.get('device_name', 'CPU')} | {self.hw_info.get('ram_total_gb', 0)} GB RAM Total")
        lbl_hw_note.setStyleSheet("color: #64748B; font-size: 11px; font-style: italic;")
        card_hw_layout.addWidget(lbl_hw_note)

        main_layout.addWidget(card_hw)

        # 4. Storage & Temporary Cache Card
        card_storage = self._create_card("Armazenamento Temporário e Privacidade")
        card_storage_layout = QVBoxLayout(card_storage)
        card_storage_layout.setContentsMargins(16, 14, 16, 14)
        card_storage_layout.setSpacing(10)

        lbl_storage_desc = QLabel(
            "O SamukaLab opera com isolamento rigoroso: músicas e stems não são salvos automaticamente "
            "em diretórios permanentes. Todo o processamento ocorre em cache temporário protegido e na memória RAM, "
            "sendo gravado no disco somente sob sua solicitação explícita de exportação."
        )
        lbl_storage_desc.setWordWrap(True)
        lbl_storage_desc.setStyleSheet("color: #9DA3AD; font-size: 11px; line-height: 1.4;")
        card_storage_layout.addWidget(lbl_storage_desc)

        cache_row = QHBoxLayout()
        temp_mgr = SafeTempManager()
        size_bytes = temp_mgr.get_total_temp_size_bytes()
        self.lbl_cache_size = QLabel(f"Espaço temporário utilizado: {size_bytes / (1024 * 1024):.1f} MB")
        self.lbl_cache_size.setStyleSheet("color: #F1F2F4; font-size: 11px; font-weight: 600;")

        self.btn_clean_cache = QPushButton("🧹 Limpar Cache Temporário")
        self.btn_clean_cache.setCursor(Qt.PointingHandCursor)
        self.btn_clean_cache.clicked.connect(self._clean_temporary_cache)

        cache_row.addWidget(self.lbl_cache_size, stretch=1)
        cache_row.addWidget(self.btn_clean_cache)
        card_storage_layout.addLayout(cache_row)

        main_layout.addWidget(card_storage)

        main_layout.addStretch(1)

        # Bottom Save Button Row
        btn_row = QHBoxLayout()
        self.btn_save = QPushButton("💾 Salvar Configurações")
        self.btn_save.setProperty("primary", "true")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.clicked.connect(self._save_settings)

        self.lbl_save_status = QLabel("")
        self.lbl_save_status.setStyleSheet("color: #10B981; font-weight: 600; font-size: 12px;")

        btn_row.addWidget(self.btn_save)
        btn_row.addSpacing(12)
        btn_row.addWidget(self.lbl_save_status)
        btn_row.addStretch()
        main_layout.addLayout(btn_row)

    def _create_card(self, title: str) -> QFrame:
        card = QFrame()
        card.setProperty("card", "true")
        card.setStyleSheet(f"""
            QFrame[card="true"] {{
                background-color: {COLORS["surface"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 8px;
            }}
        """)
        return card

    def _browse_output_dir(self):
        cur = self.txt_output_dir.text()
        chosen = QFileDialog.getExistingDirectory(self, "Selecionar Diretório de Exportação", cur)
        if chosen:
            self.txt_output_dir.setText(chosen)

    def _save_settings(self):
        out_dir = self.txt_output_dir.text().strip()
        bit_depth = self.combo_bit_depth.currentData()
        fmt = self.combo_format.currentData()
        match_sr = self.chk_match_sr.isChecked()
        drum_sep = self.chk_drum_sep.isChecked()
        device_pref = self.combo_device.currentData()

        self.settings_mgr.set("output_dir", out_dir)
        self.settings_mgr.set("wav_bit_depth", bit_depth)
        self.settings_mgr.set("export_format", fmt)
        self.settings_mgr.set("match_sample_rate", match_sr)
        self.settings_mgr.set("experimental_drum_separation", drum_sep)
        self.settings_mgr.set("device_preference", device_pref)

        self.lbl_save_status.setText("✓ Configurações salvas com sucesso!")
        self.sig_settings_saved.emit()

    def _clean_temporary_cache(self):
        cleaned = SafeTempManager().cleanup_orphaned_temporaries(max_age_seconds=0)
        size_bytes = SafeTempManager().get_total_temp_size_bytes()
        self.lbl_cache_size.setText(f"Espaço temporário utilizado: {size_bytes / (1024 * 1024):.1f} MB")
        QMessageBox.information(
            self,
            "Limpeza de Cache Concluída",
            f"Limpeza segura concluída.\n{cleaned} sessões/arquivos temporários foram liberados com sucesso."
        )
