"""
Identidade Visual e Folha de Estilos Oficial do SAMUKALAB.
Design moderno, escuro e minimalista inspirado em DAWs profissionais (REAPER, Ableton Live, FL Studio).
Paleta Oficial:
- Fundo principal: #15171B
- Fundo secundário: #202329
- Superfícies: #292D34
- Texto principal: #F1F2F4
- Texto secundário: #9DA3AD
- Destaque: #B6E36A
- Sucesso: #10B981
- Avisos: #F59E0B
- Erros: #EF4444
"""

COLORS = {
    "bg_main": "#15171B",
    "bg_secondary": "#202329",
    "surface": "#292D34",
    "surface_hover": "#323740",
    "border": "#363B44",
    "border_focus": "#B6E36A",
    "text_primary": "#F1F2F4",
    "text_secondary": "#9DA3AD",
    "accent": "#B6E36A",
    "accent_hover": "#9ECE55",
    "success": "#10B981",
    "warning": "#F59E0B",
    "danger": "#EF4444",

    # Stems colors (DAW style)
    "stem_vocals": "#38BDF8",       # Sky blue
    "stem_drums": "#F59E0B",        # Amber
    "stem_bass": "#A855F7",         # Purple
    "stem_other": "#B6E36A",        # Lime
    "stem_guitar": "#FB923C",       # Orange
    "stem_piano": "#2DD4BF",        # Teal
    "stem_kick": "#EF4444",         # Red kick
    "stem_snare": "#FBBF24",        # Yellow snare
    "stem_hihat": "#A3E635",        # Light lime
    "stem_cymbals": "#67E8F9",      # Light cyan
    "stem_toms": "#C084FC",         # Light purple
}


def get_stem_color(stem_name: str) -> str:
    """Retorna cor de destaque no mixer baseada no instrumento."""
    s = stem_name.lower()
    if "kick" in s or "bumbo" in s:
        return COLORS["stem_kick"]
    elif "snare" in s or "caixa" in s:
        return COLORS["stem_snare"]
    elif "hi-hat" in s or "chimbal" in s:
        return COLORS["stem_hihat"]
    elif "cymbal" in s or "prato" in s:
        return COLORS["stem_cymbals"]
    elif "tom" in s:
        return COLORS["stem_toms"]
    elif "vocal" in s or "voz" in s:
        return COLORS["stem_vocals"]
    elif "drum" in s or "bater" in s:
        return COLORS["stem_drums"]
    elif "bass" in s or "baixo" in s:
        return COLORS["stem_bass"]
    elif "guitar" in s or "viol" in s:
        return COLORS["stem_guitar"]
    elif "piano" in s or "teclado" in s:
        return COLORS["stem_piano"]
    return COLORS["stem_other"]


SAMUKALAB_STYLESHEET = """
/* Base Application Style */
QMainWindow, QDialog {
    background-color: #15171B;
    color: #F1F2F4;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QWidget {
    color: #F1F2F4;
    outline: none;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #15171B;
    width: 6px;
    border-radius: 3px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #363B44;
    min-height: 24px;
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover {
    background: #B6E36A;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    border: none;
    background: #15171B;
    height: 6px;
    border-radius: 3px;
}
QScrollBar::handle:horizontal {
    background: #363B44;
    min-width: 24px;
    border-radius: 3px;
}
QScrollBar::handle:horizontal:hover {
    background: #B6E36A;
}

/* Surfaces and Panels */
QFrame[card="true"] {
    background-color: #202329;
    border: 1px solid #292D34;
    border-radius: 8px;
}
QFrame[card="true"]:hover {
    border-color: #363B44;
}

/* Inputs */
QLineEdit {
    background-color: #15171B;
    border: 1px solid #363B44;
    border-radius: 6px;
    padding: 8px 12px;
    color: #F1F2F4;
    font-size: 13px;
    selection-background-color: #B6E36A;
    selection-color: #15171B;
}
QLineEdit:focus {
    border-color: #B6E36A;
}
QLineEdit:disabled {
    background-color: #1A1D23;
    color: #64748B;
    border-color: #262A32;
}

/* Buttons */
QPushButton {
    background-color: #292D34;
    color: #F1F2F4;
    border: 1px solid #363B44;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #323740;
    border-color: #4A515E;
}
QPushButton:pressed {
    background-color: #202329;
}
QPushButton:disabled {
    background-color: #1C1E24;
    color: #555A64;
    border-color: #252830;
}

/* Primary Action Button (SamukaLab Accent #B6E36A) */
QPushButton[primary="true"] {
    background-color: #B6E36A;
    color: #15171B;
    border: 1px solid #C4EC82;
    border-radius: 6px;
    padding: 10px 22px;
    font-size: 13px;
    font-weight: 700;
}
QPushButton[primary="true"]:hover {
    background-color: #C8F086;
    border-color: #D6F69E;
}
QPushButton[primary="true"]:pressed {
    background-color: #A2CF56;
}
QPushButton[primary="true"]:disabled {
    background-color: #262F1E;
    border-color: #34402A;
    color: #556644;
}

/* Danger Button */
QPushButton[danger="true"] {
    background-color: #2C181B;
    color: #F87171;
    border: 1px solid #5C2329;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
}
QPushButton[danger="true"]:hover {
    background-color: #3F1D22;
    border-color: #EF4444;
    color: #FFFFFF;
}

/* Success Button (Open Folder) */
QPushButton[success="true"] {
    background-color: #1C2B22;
    color: #6EE7B7;
    border: 1px solid #23543B;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 700;
}
QPushButton[success="true"]:hover {
    background-color: #233D2F;
    border-color: #10B981;
    color: #FFFFFF;
}

/* ComboBox */
QComboBox {
    background-color: #15171B;
    border: 1px solid #363B44;
    border-radius: 6px;
    padding: 6px 12px;
    color: #F1F2F4;
    font-weight: 500;
    font-size: 12px;
}
QComboBox:hover {
    border-color: #B6E36A;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left: none;
}
QComboBox QAbstractItemView {
    background-color: #202329;
    border: 1px solid #363B44;
    color: #F1F2F4;
    selection-background-color: #292D34;
    selection-color: #B6E36A;
    padding: 4px;
}

/* CheckBox */
QCheckBox {
    color: #F1F2F4;
    font-size: 12px;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #363B44;
    border-radius: 4px;
    background-color: #15171B;
}
QCheckBox::indicator:checked {
    background-color: #B6E36A;
    border-color: #B6E36A;
    image: none;
}
QCheckBox::indicator:hover {
    border-color: #B6E36A;
}

/* Progress Bar */
QProgressBar {
    background-color: #15171B;
    border: 1px solid #292D34;
    border-radius: 4px;
    height: 14px;
    text-align: center;
    color: #F1F2F4;
    font-weight: 700;
    font-size: 10px;
}
QProgressBar::chunk {
    background-color: #B6E36A;
    border-radius: 3px;
}

/* Sliders */
QSlider::groove:horizontal {
    border: none;
    height: 4px;
    background: #292D34;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: #B6E36A;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #F1F2F4;
    border: 1px solid #B6E36A;
    width: 12px;
    margin-top: -4px;
    margin-bottom: -4px;
    border-radius: 6px;
}
QSlider::handle:horizontal:hover {
    background: #B6E36A;
}

/* Badges */
QLabel[badge="true"] {
    background-color: #202329;
    border: 1px solid #292D34;
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
    color: #9DA3AD;
}

/* Tab Widget */
QTabWidget::pane {
    border: 1px solid #292D34;
    background-color: #202329;
    border-radius: 8px;
}
QTabBar::tab {
    background-color: #15171B;
    color: #9DA3AD;
    border: 1px solid #292D34;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 18px;
    font-weight: 600;
    font-size: 12px;
    margin-right: 4px;
}
QTabBar::tab:selected {
    background-color: #202329;
    color: #B6E36A;
    border-color: #292D34;
    border-bottom: 2px solid #202329;
}
QTabBar::tab:hover:!selected {
    background-color: #1C1E24;
    color: #F1F2F4;
}
"""

# Alias para compatibilidade legada
MAIN_STYLESHEET = SAMUKALAB_STYLESHEET
