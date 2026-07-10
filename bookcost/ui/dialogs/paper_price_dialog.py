from bookcost.core.db import BookDatabase
from PySide6.QtWidgets import (
    QDialog, QGroupBox, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTableWidget, QHeaderView, QTableWidgetItem,
    QPushButton, QComboBox, QStackedWidget, QWidget,
    QDoubleSpinBox, QSpinBox, QLineEdit, QLabel, QMessageBox,
)
from PySide6.QtCore import Qt


class PaperPriceDialog(QDialog):
    FORMULA_LABELS = (
        "ابعاد، وزن و قیمت (هر واحد)",
        "قیمت هر بند و تعداد در بند",
        "دستی"
    )

    def __init__(self, db: BookDatabase, target, parent=None):
        super().__init__(parent)
        self.db = db
        self.target = target          # "matn" or "jeld"
        self.result_value = 0.0
        self.setLayoutDirection(Qt.RightToLeft)
        title = "کاغذ متن" if target == "matn" else "کاغذ جلد"
        self.setWindowTitle(f"🧮 محاسبه قیمت واحد {title}")
        self.setMinimumWidth(500)
        self._setup_ui()
        self._load_library()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # ── Library section ──────────────────────────────────────────────
        lib_group = QGroupBox("📚 انتخاب از کتابخانه ذخیره‌شده")
        lib_layout = QVBoxLayout()

        self.lib_table = QTableWidget(0, 4)
        self.lib_table.setHorizontalHeaderLabels(["ID", "نام کاغذ", "فرمول", "قیمت واحد"])
        self.lib_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.lib_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.lib_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.lib_table.setMaximumHeight(150)
        lib_layout.addWidget(self.lib_table)

        self.empty_lib_label = QLabel("هنوز محاسبه‌ای ذخیره نشده")
        self.empty_lib_label.setAlignment(Qt.AlignCenter)
        self.empty_lib_label.setStyleSheet("color: gray;")
        self.empty_lib_label.hide()
        lib_layout.addWidget(self.empty_lib_label)

        use_saved_btn = QPushButton("✓ استفاده از ردیف انتخابی")
        use_saved_btn.setStyleSheet("background-color: #2a6496; color: white;")
        use_saved_btn.clicked.connect(self._apply_from_library)
        lib_layout.addWidget(use_saved_btn)

        lib_group.setLayout(lib_layout)
        main_layout.addWidget(lib_group)

        # ── Separator ────────────────────────────────────────────────────
        sep = QLabel("— یا محاسبه جدید —")
        sep.setAlignment(Qt.AlignCenter)
        sep.setStyleSheet("color: gray; font-size: 11px;")
        main_layout.addWidget(sep)

        # ── Calculator section ────────────────────────────────────────────
        calc_group = QGroupBox("🔢 محاسبه قیمت جدید")
        calc_vbox = QVBoxLayout()

        self.formula_combo = QComboBox()
        self.formula_combo.addItems(self.FORMULA_LABELS)
        self.formula_combo.currentIndexChanged.connect(self._update_formula_page)
        calc_vbox.addWidget(self.formula_combo)

        self.stacked = QStackedWidget()

        # Page 0 — dimensions × weight × price
        page0 = QWidget()
        f0 = QFormLayout(page0)
        self.dlg_weight_spin = QDoubleSpinBox(); self.dlg_weight_spin.setMaximum(999999)
        self.dlg_height_spin = QDoubleSpinBox(); self.dlg_height_spin.setMaximum(999999)
        self.dlg_length_spin = QDoubleSpinBox(); self.dlg_length_spin.setMaximum(999999)
        self.dlg_price1_spin = QDoubleSpinBox()
        self.dlg_price1_spin.setMaximum(9999999999.99)
        self.dlg_price1_spin.setGroupSeparatorShown(True)
        f0.addRow("وزن (گرم):", self.dlg_weight_spin)
        f0.addRow("ارتفاع (سانتی‌متر):", self.dlg_height_spin)
        f0.addRow("طول (سانتی‌متر):", self.dlg_length_spin)
        f0.addRow("قیمت کاغذ (هر کیلوگرم):", self.dlg_price1_spin)
        self.stacked.addWidget(page0)

        # Page 1 — bundle price
        page1 = QWidget()
        f1 = QFormLayout(page1)
        self.dlg_count_spin = QSpinBox(); self.dlg_count_spin.setMaximum(999999)
        self.dlg_price2_spin = QDoubleSpinBox()
        self.dlg_price2_spin.setMaximum(9999999999.99)
        self.dlg_price2_spin.setGroupSeparatorShown(True)
        f1.addRow("تعداد در بند:", self.dlg_count_spin)
        f1.addRow("قیمت هر بند:", self.dlg_price2_spin)
        self.stacked.addWidget(page1)

        # Page 2 — manual
        page2 = QWidget()
        f2 = QFormLayout(page2)
        self.dlg_manual_spin = QDoubleSpinBox()
        self.dlg_manual_spin.setMaximum(9999999999.99)
        self.dlg_manual_spin.setGroupSeparatorShown(True)
        f2.addRow("قیمت واحد (مستقیم):", self.dlg_manual_spin)
        self.stacked.addWidget(page2)

        calc_vbox.addWidget(self.stacked)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("نام کاغذ برای ذخیره در کتابخانه (اختیاری)")
        calc_vbox.addWidget(self.name_input)

        self.result_label = QLabel("قیمت واحد: 0.00 تومان")
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setStyleSheet(
            "background-color: #1a2a1a; border: 1px solid #2d5a27;"
            "color: #4caf50; font-size: 16px; font-weight: bold;"
            "padding: 8px; border-radius: 4px;"
        )
        calc_vbox.addWidget(self.result_label)
        calc_group.setLayout(calc_vbox)
        main_layout.addWidget(calc_group)

        # ── Footer ────────────────────────────────────────────────────────
        footer = QHBoxLayout()
        apply_btn = QPushButton("✓ اعمال در فیلد")
        apply_btn.setStyleSheet("background-color: #27ae60; color: white; padding: 6px 18px;")
        apply_btn.clicked.connect(self._apply_calculated)
        cancel_btn = QPushButton("انصراف")
        cancel_btn.clicked.connect(self.reject)
        footer.addWidget(apply_btn)
        footer.addWidget(cancel_btn)
        main_layout.addLayout(footer)

        # Live calculation signals
        for w in [self.dlg_weight_spin, self.dlg_height_spin, self.dlg_length_spin,
                  self.dlg_price1_spin, self.dlg_price2_spin, self.dlg_manual_spin]:
            w.valueChanged.connect(self._live_calculate)
        self.dlg_count_spin.valueChanged.connect(self._live_calculate)

    def _update_formula_page(self):
        self.stacked.setCurrentIndex(self.formula_combo.currentIndex())
        self._live_calculate()

    def _compute(self):
        idx = self.formula_combo.currentIndex()
        if idx == 0:
            h = self.dlg_height_spin.value()
            length = self.dlg_length_spin.value()
            w = self.dlg_weight_spin.value()
            p = self.dlg_price1_spin.value()
            if h > 0 and length > 0 and w > 0:
                return ((h * length) * w / 10000) * (p / 1000)
        elif idx == 1:
            count = self.dlg_count_spin.value()
            p = self.dlg_price2_spin.value()
            if count > 0:
                return p / count
        else:
            return self.dlg_manual_spin.value()
        return 0.0

    def _live_calculate(self):
        self.result_value = self._compute()
        self.result_label.setText(f"قیمت واحد: {self.result_value:,.2f} تومان")

    def _load_library(self):
        try:
            rows = self.db.get_paper_calculations()
        except Exception:
            rows = []

        self.lib_table.setRowCount(0)
        if not rows:
            self.lib_table.hide()
            self.empty_lib_label.show()
            return

        self.lib_table.show()
        self.empty_lib_label.hide()
        for row in rows:
            r = self.lib_table.rowCount()
            self.lib_table.insertRow(r)
            self.lib_table.setItem(r, 0, QTableWidgetItem(str(row['id'])))
            self.lib_table.setItem(r, 1, QTableWidgetItem(row['paper_type']))
            self.lib_table.setItem(r, 2, QTableWidgetItem(row['formula_type']))
            self.lib_table.setItem(r, 3, QTableWidgetItem(f"{row['unit_price']:,.2f}"))
        self.lib_table.hideColumn(0)

    def _apply_from_library(self):
        row = self.lib_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "توجه", "لطفاً یک ردیف را انتخاب کنید.")
            return
        item = self.lib_table.item(row, 3)
        if item is None:
            return
        self.result_value = float(item.text().replace(",", ""))
        self.accept()

    def _apply_calculated(self):
        self.result_value = self._compute()
        if self.result_value <= 0:
            QMessageBox.warning(self, "خطا", "قیمت محاسبه‌شده معتبر نیست.")
            return
        name = self.name_input.text().strip()
        if name:
            self._save_to_library(name)
        self.accept()

    def _save_to_library(self, name):
        idx = self.formula_combo.currentIndex()
        w = self.dlg_weight_spin.value() if idx == 0 else 0
        h = self.dlg_height_spin.value() if idx == 0 else 0
        length = self.dlg_length_spin.value() if idx == 0 else 0
        count = self.dlg_count_spin.value() if idx == 1 else 0
        prices = [self.dlg_price1_spin.value(), self.dlg_price2_spin.value(), self.dlg_manual_spin.value()]
        try:
            self.db.insert_paper_calculation({
                'paper_type': name, 'formula_type': self.FORMULA_LABELS[idx],
                'weight': w, 'height': h, 'length': length,
                'bundle_count': count, 'bundle_weight': 0,
                'price': prices[idx], 'unit_price': self.result_value,
            })
            if hasattr(self.parent(), 'load_paper_calculations'):
                self.parent().load_paper_calculations()
        except Exception as e:
            QMessageBox.warning(self, "خطا", f"ذخیره‌سازی با خطا مواجه شد:\n{e}")
