"""A restrained dark stylesheet — modern and focused, not overloaded with
panels, decorative gradients, or constant animation. For accessibility,
colors keep sufficient contrast, and status is never signaled by color
alone: status text in this app always carries a word, never just a color.
"""

BACKGROUND = "#15171c"
SURFACE = "#1d2027"
SURFACE_RAISED = "#262a33"
BORDER = "#343944"
TEXT_PRIMARY = "#e8e9ec"
TEXT_SECONDARY = "#9aa0ac"
ACCENT = "#4f8cff"
ACCENT_HOVER = "#6ea0ff"
DANGER = "#e2574c"

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {BACKGROUND};
    color: {TEXT_PRIMARY};
    font-size: 13px;
}}

QMenuBar {{
    background-color: {SURFACE};
    color: {TEXT_PRIMARY};
    border-bottom: 1px solid {BORDER};
}}
QMenuBar::item:selected {{ background-color: {SURFACE_RAISED}; }}
QMenu {{ background-color: {SURFACE}; border: 1px solid {BORDER}; }}
QMenu::item:selected {{ background-color: {ACCENT}; color: #0a0a0a; }}

QToolBar {{
    background-color: {SURFACE};
    border: none;
    border-bottom: 1px solid {BORDER};
    spacing: 6px;
    padding: 6px;
}}

QDockWidget {{
    color: {TEXT_PRIMARY};
    titlebar-close-icon: none;
}}
QDockWidget::title {{
    background-color: {SURFACE};
    padding: 8px;
    border-bottom: 1px solid {BORDER};
}}

QPushButton {{
    background-color: {SURFACE_RAISED};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 12px;
    color: {TEXT_PRIMARY};
}}
QPushButton:hover {{ background-color: {BORDER}; }}
QPushButton:pressed {{ background-color: {ACCENT}; }}
QPushButton:disabled {{ color: {TEXT_SECONDARY}; }}
QPushButton#primaryAction {{
    background-color: {ACCENT};
    color: #0a0a0a;
    font-weight: 600;
    border: none;
}}
QPushButton#primaryAction:hover {{ background-color: {ACCENT_HOVER}; }}
QPushButton#primaryAction:disabled {{
    background-color: {SURFACE_RAISED}; color: {TEXT_SECONDARY};
}}

QLabel#sectionLabel {{
    color: {TEXT_SECONDARY};
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding-top: 10px;
}}

QSlider::groove:horizontal {{
    height: 4px;
    background: {BORDER};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{ background: {ACCENT_HOVER}; }}

QStatusBar {{
    background-color: {SURFACE};
    border-top: 1px solid {BORDER};
    color: {TEXT_SECONDARY};
}}

QComboBox, QSpinBox {{
    background-color: {SURFACE_RAISED};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 8px;
}}

QScrollArea {{ border: none; }}
"""
