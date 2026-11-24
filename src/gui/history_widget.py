"""
Tela de Histórico de Projetos do SamukaLab.
Permite visualizar, abrir pastas e gerenciar músicas processadas anteriormente.
"""
import os
import subprocess
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from src.history.project_manager import ProjectHistoryManager
from src.gui.style import COLORS


class HistoryWidget(QWidget):
    """Visualizador e gerenciador de histórico de projetos."""

    sig_open_folder_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.history_mgr = ProjectHistoryManager()
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(16)

        # Header Row
        header_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        lbl_title = QLabel("Histórico de Projetos Processados")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #F1F2F4;")

        lbl_sub = QLabel("Acesse rapidamente as faixas e pastas de stems de separações anteriores")
        lbl_sub.setStyleSheet("font-size: 11px; color: #9DA3AD;")

        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_sub)
        header_row.addLayout(title_box)

        header_row.addStretch()

        self.btn_refresh = QPushButton("🔄 Atualizar")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.clicked.connect(self.refresh_list)

        self.btn_clear = QPushButton("🗑️ Limpar Histórico")
        self.btn_clear.setProperty("danger", "true")
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.clicked.connect(self._on_clear_clicked)

        header_row.addWidget(self.btn_refresh)
        header_row.addWidget(self.btn_clear)
        main_layout.addLayout(header_row)

        # Scroll area for history cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        self.container = QWidget()
        self.cards_layout = QVBoxLayout(self.container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(10)

        scroll.setWidget(self.container)
        main_layout.addWidget(scroll, stretch=1)

        self.refresh_list()

    def refresh_list(self):
        """Reconstrói a lista de registros do histórico."""
        for i in reversed(range(self.cards_layout.count())):
            item = self.cards_layout.takeAt(i)
            widget = item.widget() if item else None
            if widget:
                widget.deleteLater()

        entries = self.history_mgr.get_recent(limit=50)

        if not entries:
            lbl_empty = QLabel("Nenhum projeto registrado no histórico ainda.\nAs músicas processadas no estúdio aparecerão aqui automaticamente.")
            lbl_empty.setAlignment(Qt.AlignCenter)
            lbl_empty.setStyleSheet("color: #64748B; font-size: 13px; padding: 40px;")
            self.cards_layout.addWidget(lbl_empty)
            self.cards_layout.addStretch(1)
            return

        for entry in entries:
            card = self._create_entry_card(entry)
            self.cards_layout.addWidget(card)

        self.cards_layout.addStretch(1)

    def _create_entry_card(self, entry: dict) -> QFrame:
        card = QFrame()
        card.setProperty("card", "true")
        card.setStyleSheet(f"""
            QFrame[card="true"] {{
                background-color: {COLORS["surface"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 6px;
                padding: 12px;
            }}
            QFrame[card="true"]:hover {{
                border-color: {COLORS["accent"]};
            }}
        """)

        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(16)

        # Info Box
        info_box = QVBoxLayout()
        info_box.setSpacing(4)

        title_row = QHBoxLayout()
        lbl_title = QLabel(entry.get("title", "Sem título"))
        lbl_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #F1F2F4;")

        lbl_date = QLabel(entry.get("date_str", ""))
        lbl_date.setStyleSheet("font-size: 11px; color: #9DA3AD;")

        title_row.addWidget(lbl_title)
        title_row.addSpacing(10)
        title_row.addWidget(lbl_date)
        title_row.addStretch()
        info_box.addLayout(title_row)

        # Details row
        details_row = QHBoxLayout()
        details_row.setSpacing(12)

        dur_text = f"Duração: {entry.get('duration_s', 0):.1f}s"
        lbl_dur = QLabel(dur_text)
        lbl_dur.setStyleSheet("font-size: 11px; color: #9DA3AD;")

        model_text = f"Modelo: {entry.get('model_name', 'htdemucs')}"
        lbl_model = QLabel(model_text)
        lbl_model.setStyleSheet("font-size: 11px; color: #9DA3AD;")

        details_row.addWidget(lbl_dur)
        details_row.addWidget(lbl_model)

        if entry.get("has_drum_separation"):
            lbl_drum_badge = QLabel("🥁 Bateria Decomposta")
            lbl_drum_badge.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {COLORS['accent']}; background-color: #202329; border: 1px solid {COLORS['border']}; border-radius: 4px; padding: 2px 6px;")
            details_row.addWidget(lbl_drum_badge)

        details_row.addStretch()
        info_box.addLayout(details_row)

        layout.addLayout(info_box, stretch=1)

        # Action Buttons
        btn_box = QHBoxLayout()
        btn_box.setSpacing(8)

        output_dir = entry.get("output_dir", "")
        exists = os.path.exists(output_dir)

        btn_open = QPushButton("📁 Abrir Pasta")
        btn_open.setCursor(Qt.PointingHandCursor)
        btn_open.setEnabled(exists)
        btn_open.setStyleSheet(f"""
            QPushButton {{
                background-color: #202329;
                color: {COLORS['accent'] if exists else '#555A64'};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: 600;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: #2A303A;
                border-color: {COLORS['accent']};
            }}
        """)
        btn_open.clicked.connect(lambda _, path=output_dir: self._open_folder(path))

        btn_remove = QPushButton("✕")
        btn_remove.setToolTip("Remover do histórico")
        btn_remove.setCursor(Qt.PointingHandCursor)
        btn_remove.setFixedSize(28, 28)
        btn_remove.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #9DA3AD;
                border: 1px solid #363B44;
                border-radius: 4px;
            }
            QPushButton:hover {
                color: #EF4444;
                border-color: #EF4444;
            }
        """)
        btn_remove.clicked.connect(lambda _, eid=entry.get("id"): self._on_remove_entry(eid))

        btn_box.addWidget(btn_open)
        btn_box.addWidget(btn_remove)
        layout.addLayout(btn_box)

        return card

    def _open_folder(self, folder_path: str):
        if folder_path and os.path.exists(folder_path):
            try:
                subprocess.Popen(["xdg-open", folder_path])
            except Exception:
                pass

    def _on_remove_entry(self, entry_id: str):
        if entry_id:
            self.history_mgr.remove_entry(entry_id)
            self.refresh_list()

    def _on_clear_clicked(self):
        reply = QMessageBox.question(
            self,
            "Limpar Histórico",
            "Deseja realmente limpar todo o histórico de processamento?\n(Os arquivos no disco não serão apagados).",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.history_mgr.clear()
            self.refresh_list()
