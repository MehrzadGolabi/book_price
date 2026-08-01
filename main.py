"""Application entry point. All real code lives in the ``bookcost`` package.

Accepts an optional path to an exported project file (.ketab) as the first
command-line argument — that's how the Windows file association opens
double-clicked exports.
"""

import os
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from bookcost.resources import resource_path
from bookcost.ui.main_window import BookCostCalculator
from bookcost.ui.utils import install_no_wheel_filter


def main():
    app = QApplication(sys.argv)
    install_no_wheel_filter(app)
    app.setStyle("Fusion")
    logo = resource_path("logo.png")
    if os.path.exists(logo):
        app.setWindowIcon(QIcon(logo))

    try:
        with open(resource_path("style.qss"), "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    except OSError:
        app.setStyleSheet("""
            QWidget { font-family: 'Tahoma', 'IRANSans', sans-serif; font-size: 14px; }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { padding: 5px; }
            QSpinBox, QDoubleSpinBox { text-align: center; }
        """)

    window = BookCostCalculator()
    window.show()

    # Double-clicked .ketab (or legacy .json) export: import it once the
    # event loop is running.
    if len(sys.argv) > 1:
        candidate = sys.argv[1]
        if os.path.isfile(candidate) and candidate.lower().endswith(('.ketab', '.json')):
            QTimer.singleShot(0, lambda: window.import_project_path(candidate))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
