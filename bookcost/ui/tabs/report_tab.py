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
        self.chk_specs = QCheckBox("مشخصات چاپ (فرم‌ها، رنگ، زینک، اندازه کاغذ، ...)")
        self.chk_features = QCheckBox("ویژگی‌های فنی و ظاهری (نوع کاغذ، چاپ و ...)")
        self.chk_costs = QCheckBox("ریز هزینه‌های پروژه (گروه‌بندی‌شده با جمع هر بخش)")
        self.chk_pricing = QCheckBox("قیمت‌گذاری و سودآوری (قیمت پشت جلد، نقطه سر به سر، ...)")

        for chk in (self.chk_basic_info, self.chk_specs, self.chk_features,
                    self.chk_costs, self.chk_pricing):
            chk.setChecked(True)
            layout.addWidget(chk)

        btn_pdf = QPushButton("تولید و ذخیره فایل PDF")
        btn_pdf.setStyleSheet("padding: 10px; font-weight: bold; background-color: #2c3e50; color: white;")
        btn_pdf.clicked.connect(lambda *_: self.generate_requested.emit())
        layout.addWidget(btn_pdf)

        layout.addStretch()

    def include_basic_info(self) -> bool:
        return self.chk_basic_info.isChecked()

    def include_specs(self) -> bool:
        return self.chk_specs.isChecked()

    def include_features(self) -> bool:
        return self.chk_features.isChecked()

    def include_costs(self) -> bool:
        return self.chk_costs.isChecked()

    def include_pricing(self) -> bool:
        return self.chk_pricing.isChecked()
