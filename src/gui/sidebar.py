"""
Componente de Menu Lateral (Sidebar) do SamukaLab.
Permite alternância rápida e elegante entre o Estúdio de Separação, Histórico e Configurações.
"""
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget
from PySide6.QtCore import Qt, Signal
from src.gui.style import COLORS


class SidebarWidget(QFrame):
    """Menu lateral de navegação estilo DAW profissional."""

    sig_page_changed = Signal(int)  # 0: Estúdio, 1: Histórico, 2: Configurações

    def __init__(self, hardware_info: dict, parent=None):
        super().__init__(parent)
        self.hw_info = hardware_info
        self.current_index = 0
        self.buttons = []

        self.setFixedWidth(220)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["bg_secondary"]};
                border-right: 1px solid {COLORS["border"]};
            }}
        """)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 20)
        layout.setSpacing(16)

        # 1. Brand Logo & Title
        brand_box = QVBoxLayout()
        brand_box.setSpacing(2)

        lbl_logo = QLabel("SAMUKALAB")
        lbl_logo.setStyleSheet(f"""
            font-size: 18px;
            font-weight: 900;
            color: {COLORS["accent"]};
            letter-spacing: 2px;
        """)

        lbl_sub = QLabel("AUDIO DSP & AI WORKSTATION")
        lbl_sub.setStyleSheet(f"""
            font-size: 9px;
            font-weight: 700;
            color: {COLORS["text_secondary"]};
            letter-spacing: 1px;
        """)

        brand_box.addWidget(lbl_logo)
        brand_box.addWidget(lbl_sub)
        layout.addLayout(brand_box)

        layout.addSpacing(16)

        # 2. Navigation Section Label
        lbl_nav = QLabel("NAVEGAÇÃO")
        lbl_nav.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {COLORS['text_secondary']}; letter-spacing: 1px;")
        layout.addWidget(lbl_nav)

        # 3. Navigation Buttons
        nav_items = [
            ("🎛️  Estúdio de Separação", 0),
            ("🕒  Histórico de Projetos", 1),
            ("⚙️  Configurações", 2),
        ]

        for text, idx in nav_items:
            btn = QPushButton(text)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, index=idx: self.set_active_page(index))
            layout.addWidget(btn)
            self.buttons.append(btn)

        self._update_button_styles()

        layout.addStretch(1)

        # 4. Hardware Footer Badge
        hw_box = QFrame()
        hw_box.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["surface"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 6px;
                padding: 10px;
            }}
        """)
        hw_layout = QVBoxLayout(hw_box)
        hw_layout.setContentsMargins(8, 8, 8, 8)
        hw_layout.setSpacing(4)

        device_title = "⚡ GPU NVIDIA (CUDA)" if self.hw_info.get("cuda_available") else "💻 CPU MULTI-CORE"
        lbl_dev = QLabel(device_title)
        lbl_dev.setStyleSheet(f"font-size: 10px; font-weight: 800; color: {COLORS['accent']};")

        dev_desc = self.hw_info.get("device_name", "CPU")
        if self.hw_info.get("ram_available_gb", 0) > 0:
            dev_desc += f"\nRAM: {self.hw_info['ram_available_gb']:.1f} GB livre"

        lbl_desc = QLabel(dev_desc)
        lbl_desc.setStyleSheet(f"font-size: 10px; color: {COLORS['text_secondary']};")

        hw_layout.addWidget(lbl_dev)
        hw_layout.addWidget(lbl_desc)
        layout.addWidget(hw_box)

    def set_active_page(self, index: int):
        self.current_index = index
        self._update_button_styles()
        self.sig_page_changed.emit(index)

    def _update_button_styles(self):
        for idx, btn in enumerate(self.buttons):
            if idx == self.current_index:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {COLORS["surface"]};
                        color: {COLORS["accent"]};
                        border: 1px solid {COLORS["border"]};
                        border-left: 4px solid {COLORS["accent"]};
                        border-radius: 6px;
                        padding: 10px 14px;
                        text-align: left;
                        font-weight: 700;
                        font-size: 12px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: {COLORS["text_secondary"]};
                        border: 1px solid transparent;
                        border-radius: 6px;
                        padding: 10px 14px;
                        text-align: left;
                        font-weight: 600;
                        font-size: 12px;
                    }}
                    QPushButton:hover {{
                        background-color: {COLORS["surface"]};
                        color: {COLORS["text_primary"]};
                        border-color: {COLORS["border"]};
                    }}
                """)
