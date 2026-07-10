"""PDF report tab: section checkboxes and the generate button.

The actual PDF rendering lives in bookcost.reporting.pdf_report; the main window
assembles the ReportData snapshot when generate_requested fires.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QLabel, QPushButton, QVBoxLayout, QWidget


class ReportTab(QWidget):
    generate_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("لطفاً بخش‌هایی که می‌خواهید در گزارش PDF چاپ شوند را انتخاب کنید:"))

        self.chk_basic_info = QCheckBox("اطلاعات اصلی (نام کتاب، تاریخ، تیراژ، ...)")
        self.chk_basic_info.setChecked(True)

        self.chk_features = QCheckBox("ویژگی‌های فنی و ظاهری (نوع کاغذ، چاپ و ...)")
        self.chk_features.setChecked(True)

        self.chk_costs = QCheckBox("ریز هزینه‌های پروژه")
        self.chk_costs.setChecked(True)

        layout.addWidget(self.chk_basic_info)
        layout.addWidget(self.chk_features)
        layout.addWidget(self.chk_costs)

        btn_pdf = QPushButton("تولید و ذخیره فایل PDF")
        btn_pdf.setStyleSheet("padding: 10px; font-weight: bold; background-color: #2c3e50; color: white;")
        btn_pdf.clicked.connect(self.generate_requested.emit)
        layout.addWidget(btn_pdf)

        layout.addStretch()

    def include_basic_info(self) -> bool:
        return self.chk_basic_info.isChecked()

    def include_features(self) -> bool:
        return self.chk_features.isChecked()

    def include_costs(self) -> bool:
        return self.chk_costs.isChecked()
