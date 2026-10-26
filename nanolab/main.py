# -*- coding: utf-8 -*-
"""NanoCode 电子实验室 —— 入口"""

from __future__ import annotations

import sys

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

DARK_QSS = """
QMainWindow, QWidget { background:#0f1319; color:#cbd5e1; }
QToolBar { background:#141a22; border-bottom:1px solid #263041; spacing:6px; padding:4px; }
QToolButton { color:#cbd5e1; padding:4px 8px; border-radius:6px; }
QToolButton:hover { background:#1e293b; }
QDockWidget { color:#cbd5e1; }
QDockWidget::title { background:#141a22; padding:6px; border-bottom:1px solid #263041; }
QComboBox, QLineEdit { background:#141a22; border:1px solid #263041; border-radius:6px;
    padding:4px 6px; color:#cbd5e1; }
QComboBox QAbstractItemView { background:#141a22; color:#cbd5e1; selection-background-color:#1d4ed8; }
QPushButton { background:#1b2430; border:1px solid #263041; border-radius:6px;
    padding:5px 10px; color:#cbd5e1; }
QPushButton:hover { background:#233041; }
QPushButton:checked { background:#1d4ed8; border-color:#3b82f6; color:#fff; }
QListWidget { background:#0b0f14; border:1px solid #263041; border-radius:6px; color:#cbd5e1; }
QListWidget::item { padding:5px 6px; border-bottom:1px solid #151c26; }
QListWidget::item:selected { background:#1d4ed8; }
QSlider::groove:horizontal { height:4px; background:#263041; border-radius:2px; }
QSlider::handle:horizontal { width:14px; margin:-6px 0; border-radius:7px; background:#22d3ee; }
QStatusBar { background:#141a22; color:#94a3b8; }
QScrollBar:vertical { background:#0b0f14; width:10px; }
QScrollBar::handle:vertical { background:#263041; border-radius:5px; min-height:20px; }
"""


FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
    r"C:\Windows\Fonts\Deng.ttf",
]


def load_font(app):
    """显式加载中文字体：不依赖系统字体回退，离屏/无字体环境也不出方框"""
    from PySide6.QtGui import QFont, QFontDatabase
    family = None
    for path in FONT_CANDIDATES:
        try:
            fid = QFontDatabase.addApplicationFont(path)
            if fid >= 0:
                fams = QFontDatabase.applicationFontFamilies(fid)
                if fams:
                    family = fams[0]
                    break
        except Exception:
            continue
    if family:
        f = QFont(family, 9)
        app.setFont(f)
    return family


def set_taskbar_identity():
    """让任务栏显示自己的图标，而不是 python 的图标（Windows 专有）"""
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "NanoCode.ElectronicsLab.v2")
    except Exception:
        pass


def app_icon(app):
    import os
    from PySide6.QtGui import QIcon
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name in ("app.ico", "icon.ico"):
        p = os.path.join(base, name)
        if os.path.exists(p):
            ic = QIcon(p)
            app.setWindowIcon(ic)
            return ic
    return None


def main():
    set_taskbar_identity()
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except Exception:
        pass
    app = QApplication(sys.argv)
    app.setApplicationName("NanoCode 电子实验室")
    app_icon(app)
    app.setStyle("Fusion")
    load_font(app)
    app.setStyleSheet(DARK_QSS)
    pal = app.palette()
    pal.setColor(QPalette.Window, QColor("#0f1319"))
    pal.setColor(QPalette.Base, QColor("#0b0f14"))
    pal.setColor(QPalette.Text, QColor("#cbd5e1"))
    pal.setColor(QPalette.WindowText, QColor("#cbd5e1"))
    app.setPalette(pal)

    from .ui.main_window import MainWindow
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
