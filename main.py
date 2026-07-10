"""Application entry point. All real code lives in the ``bookcost`` package."""

import sys

from PySide6.QtWidgets import QApplication

from bookcost.resources import resource_path
from bookcost.ui.main_window import BookCostCalculator


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

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
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
