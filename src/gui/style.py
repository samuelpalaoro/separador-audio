"""Modern Moises AI-inspired dark theme stylesheet and color palette."""

COLORS = {
    "bg_main": "#0D0E15",
    "bg_card": "#151722",
    "bg_card_hover": "#1C1F2E",
    "bg_input": "#1B1D2A",
    "border": "#282B3D",
    "border_focus": "#7C3AED",
    "text_primary": "#F8FAFC",
    "text_secondary": "#94A3B8",
    "text_muted": "#64748B",
    
    # Accent colors
    "accent_primary": "#8B5CF6",       # Purple
    "accent_primary_hover": "#7C3AED",
    "accent_success": "#10B981",       # Emerald
    "accent_warning": "#F59E0B",       # Amber
    "accent_danger": "#EF4444",        # Red
    
    # Stem individual colors (Moises style)
    "stem_vocals": "#00D2FF",          # Cyan
    "stem_drums": "#FF7A00",           # Orange
    "stem_bass": "#A855F7",            # Purple
    "stem_other": "#10B981",           # Green
    "stem_guitar": "#F59E0B",          # Amber
    "stem_piano": "#06B6D4",           # Teal
}

def get_stem_color(stem_name: str) -> str:
    """Return specific accent color for stem name."""
    s = stem_name.lower()
    if "vocal" in s or "voz" in s:
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


MAIN_STYLESHEET = """
/* Base Application Style */
QMainWindow, QDialog {
    background-color: #0D0E15;
    color: #F8FAFC;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QWidget {
    color: #F8FAFC;
    outline: none;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #151722;
    width: 8px;
    border-radius: 4px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #33384D;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #8B5CF6;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    border: none;
    background: #151722;
    height: 8px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: #33384D;
    min-width: 20px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover {
    background: #8B5CF6;
}

/* Cards & Frames */
QFrame[card="true"] {
    background-color: #151722;
    border: 1px solid #282B3D;
    border-radius: 12px;
}

QFrame[card="true"]:hover {
    border-color: #383D54;
}

/* Buttons */
QPushButton {
    background-color: #1F2232;
    color: #F8FAFC;
    border: 1px solid #2F344B;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #292E42;
    border-color: #8B5CF6;
}

QPushButton:pressed {
    background-color: #191C2A;
}

QPushButton:disabled {
    background-color: #151722;
    color: #555A70;
    border-color: #202330;
}

/* Primary Action Button */
QPushButton[primary="true"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8B5CF6, stop:1 #6D28D9);
    border: 1px solid #9061F9;
    color: #FFFFFF;
    border-radius: 10px;
    padding: 12px 24px;
    font-size: 14px;
    font-weight: 700;
}

QPushButton[primary="true"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9D6EFF, stop:1 #7C3AED);
    border-color: #A78BFA;
}

QPushButton[primary="true"]:pressed {
    background: #5B21B6;
}

QPushButton[primary="true"]:disabled {
    background: #2D2545;
    border-color: #383057;
    color: #6B6484;
}

/* Danger Button (Cancel) */
QPushButton[danger="true"] {
    background-color: #2D151B;
    color: #FCA5A5;
    border: 1px solid #7F1D1D;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton[danger="true"]:hover {
    background-color: #451A22;
    border-color: #EF4444;
    color: #FFFFFF;
}

/* ComboBox */
QComboBox {
    background-color: #181A26;
    border: 1px solid #2B2F44;
    border-radius: 8px;
    padding: 8px 14px;
    color: #F8FAFC;
    font-weight: 500;
}

QComboBox:hover {
    border-color: #8B5CF6;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 25px;
    border-left: none;
}

QComboBox QAbstractItemView {
    background-color: #181A26;
    border: 1px solid #32374E;
    color: #F8FAFC;
    selection-background-color: #7C3AED;
    selection-color: #FFFFFF;
    border-radius: 8px;
    padding: 4px;
}

/* Sliders */
QSlider::groove:horizontal {
    border: none;
    height: 6px;
    background: #232738;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: #8B5CF6;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #F8FAFC;
    border: 2px solid #8B5CF6;
    width: 14px;
    margin-top: -4px;
    margin-bottom: -4px;
    border-radius: 7px;
}

QSlider::handle:horizontal:hover {
    background: #FFFFFF;
    border-color: #A78BFA;
    transform: scale(1.1);
}

/* Progress Bar */
QProgressBar {
    background-color: #191B28;
    border: 1px solid #2B2F43;
    border-radius: 8px;
    height: 18px;
    text-align: center;
    color: #FFFFFF;
    font-weight: 700;
    font-size: 11px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8B5CF6, stop:1 #06B6D4);
    border-radius: 7px;
}

/* Labels */
QLabel {
    color: #F8FAFC;
}

QLabel[secondary="true"] {
    color: #94A3B8;
    font-size: 12px;
}

QLabel[badge="true"] {
    background-color: #1E2130;
    border: 1px solid #32374F;
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
}
"""
