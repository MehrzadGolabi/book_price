"""Paper pre-calculation tab: compute a paper unit price via 3 formulas and
keep a saved library of calculations (paper_calculations table)."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)


class PaperCalcTab(QWidget):
    # (category, item_value, target_cost_field, unit_price) exported to defaults
    defaults_exported = Signal()

    def __init__(self, db, calculator, parent=None):
        super().__init__(parent)
        self.db = db
        self.calculator = calculator
        self.editing_paper_calc_id = None
        self._build_ui()
        self.update_paper_inputs_visibility()
        self.load_paper_calculations()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.paper_type_combo = QComboBox()
        self.paper_type_combo.setEditable(True)
        self.paper_type_combo.setInsertPolicy(QComboBox.InsertAtBottom)
        self.paper_type_combo.addItems([
            "ایندربرد", "گلاسه", "بالک", "پشت طوسی", "تحریر", "مقوای مغزی"
        ])
        form.addRow("نوع کاغذ:", self.paper_type_combo)

        self.paper_formula_combo = QComboBox()
        self.paper_formula_combo.addItems([
            "ابعاد، وزن و قیمت (هر واحد)",
            "قیمت هر بند و تعداد در بند",
            "دستی"
        ])
        self.paper_formula_combo.currentTextChanged.connect(self.update_paper_inputs_visibility)
        form.addRow("نحوه محاسبه:", self.paper_formula_combo)

        self.paper_weight_spin = QDoubleSpinBox()
        self.paper_weight_spin.setMaximum(999999)
        form.addRow("وزن:", self.paper_weight_spin)

        self.paper_height_spin = QDoubleSpinBox()
        self.paper_height_spin.setMaximum(999999)
        form.addRow("ارتفاع (سانتی‌متر):", self.paper_height_spin)

        self.paper_length_spin = QDoubleSpinBox()
        self.paper_length_spin.setMaximum(999999)
        form.addRow("طول (سانتی‌متر):", self.paper_length_spin)

        self.paper_bundle_count_spin = QSpinBox()
        self.paper_bundle_count_spin.setMaximum(999999)
        form.addRow("تعداد در بند:", self.paper_bundle_count_spin)

        self.paper_bundle_weight_spin = QDoubleSpinBox()
        self.paper_bundle_weight_spin.setMaximum(999999)
        form.addRow("وزن در بند:", self.paper_bundle_weight_spin)

        self.paper_price_spin = QDoubleSpinBox()
        self.paper_price_spin.setMaximum(9999999999.99)
        self.paper_price_spin.setGroupSeparatorShown(True)
        self.paper_price_label = QLabel("قیمت / قیمت بند (تومان):")
        form.addRow(self.paper_price_label, self.paper_price_spin)

        self.paper_unit_price_lbl = QLabel("0")
        self.paper_unit_price_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: darkblue;")
        form.addRow("قیمت نهایی یک واحد:", self.paper_unit_price_lbl)

        btn_layout = QHBoxLayout()
        calc_btn = QPushButton("محاسبه")
        calc_btn.clicked.connect(self.calculate_paper_unit_price)

        save_btn = QPushButton("ذخیره محاسبه")
        save_btn.clicked.connect(self.save_paper_calculation)

        delete_btn = QPushButton("حذف ردیف")
        delete_btn.clicked.connect(self.delete_paper_calculation)

        export_btn = QPushButton("انتقال به مدیریت قیمت‌های پایه")
        export_btn.clicked.connect(self.export_paper_to_defaults)

        btn_layout.addWidget(calc_btn)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addWidget(export_btn)

        layout.addLayout(form)
        layout.addLayout(btn_layout)

        self.paper_calc_table = QTableWidget(0, 10)
        self.paper_calc_table.setHorizontalHeaderLabels([
            "ID", "نوع کاغذ", "نحوه محاسبه", "وزن", "ارتفاع", "طول",
            "تعداد در بند", "وزن در بند", "قیمت ورودی", "قیمت واحد"
        ])
        self.paper_calc_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.paper_calc_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.paper_calc_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.paper_calc_table.doubleClicked.connect(self.load_selected_paper_calc)

        layout.addWidget(self.paper_calc_table)

    def update_paper_inputs_visibility(self):
        formula = self.paper_formula_combo.currentText()
        if formula == "ابعاد، وزن و قیمت (هر واحد)":
            self.paper_weight_spin.setEnabled(True)
            self.paper_height_spin.setEnabled(True)
            self.paper_length_spin.setEnabled(True)
            self.paper_bundle_count_spin.setEnabled(False)
            self.paper_bundle_weight_spin.setEnabled(False)
            self.paper_price_spin.setEnabled(True)
            self.paper_price_label.setText("قیمت کاغذ (هر کیلوگرم):")
        elif formula == "قیمت هر بند و تعداد در بند":
            self.paper_weight_spin.setEnabled(False)
            self.paper_height_spin.setEnabled(False)
            self.paper_length_spin.setEnabled(False)
            self.paper_bundle_count_spin.setEnabled(True)
            self.paper_bundle_weight_spin.setEnabled(True)
            self.paper_price_spin.setEnabled(True)
            self.paper_price_label.setText("قیمت هر بند:")
        else:  # دستی
            self.paper_weight_spin.setEnabled(False)
            self.paper_height_spin.setEnabled(False)
            self.paper_length_spin.setEnabled(False)
            self.paper_bundle_count_spin.setEnabled(False)
            self.paper_bundle_weight_spin.setEnabled(False)
            self.paper_price_spin.setEnabled(True)
            self.paper_price_label.setText("قیمت واحد (مستقیم):")

    def calculate_paper_unit_price(self):
        unit_price = self.calculator.compute_paper_unit_price(
            formula_idx=self.paper_formula_combo.currentIndex(),
            height=self.paper_height_spin.value(),
            length=self.paper_length_spin.value(),
            weight=self.paper_weight_spin.value(),
            price=self.paper_price_spin.value(),
            count=self.paper_bundle_count_spin.value(),
        )
        self.paper_unit_price_lbl.setText(f"{unit_price:,.2f}")
        return unit_price

    def save_paper_calculation(self):
        unit_price = self.calculate_paper_unit_price()
        if unit_price <= 0:
            QMessageBox.warning(self, "خطا", "قیمت محاسبه شده نامعتبر است.")
            return

        data = {
            'paper_type': self.paper_type_combo.currentText().strip(),
            'formula_type': self.paper_formula_combo.currentText(),
            'weight': self.paper_weight_spin.value() if self.paper_weight_spin.isEnabled() else 0,
            'height': self.paper_height_spin.value() if self.paper_height_spin.isEnabled() else 0,
            'length': self.paper_length_spin.value() if self.paper_length_spin.isEnabled() else 0,
            'bundle_count': self.paper_bundle_count_spin.value() if self.paper_bundle_count_spin.isEnabled() else 0,
            'bundle_weight': self.paper_bundle_weight_spin.value() if self.paper_bundle_weight_spin.isEnabled() else 0,
            'price': self.paper_price_spin.value(),
            'unit_price': unit_price,
        }
        try:
            if self.editing_paper_calc_id is not None:
                self.db.update_paper_calculation(self.editing_paper_calc_id, data)
            else:
                self.db.insert_paper_calculation(data)
            self.load_paper_calculations()
            self.editing_paper_calc_id = None
        except Exception as err:
            QMessageBox.critical(self, "خطا", f"ذخیره محاسبه با خطا مواجه شد:\n{err}")

    def load_paper_calculations(self):
        try:
            rows = self.db.get_paper_calculations()
            self.paper_calc_table.setUpdatesEnabled(False)
            self.paper_calc_table.setRowCount(len(rows))
            for row_idx, row in enumerate(rows):
                self.paper_calc_table.setItem(row_idx, 0, QTableWidgetItem(str(row['id'])))
                self.paper_calc_table.setItem(row_idx, 1, QTableWidgetItem(row['paper_type']))
                self.paper_calc_table.setItem(row_idx, 2, QTableWidgetItem(row['formula_type']))
                self.paper_calc_table.setItem(row_idx, 3, QTableWidgetItem(str(row['weight'])))
                self.paper_calc_table.setItem(row_idx, 4, QTableWidgetItem(str(row['height'])))
                self.paper_calc_table.setItem(row_idx, 5, QTableWidgetItem(str(row['length'])))
                self.paper_calc_table.setItem(row_idx, 6, QTableWidgetItem(str(row['bundle_count'])))
                self.paper_calc_table.setItem(row_idx, 7, QTableWidgetItem(str(row['bundle_weight'])))
                self.paper_calc_table.setItem(row_idx, 8, QTableWidgetItem(f"{row['price']:,.2f}"))
                self.paper_calc_table.setItem(row_idx, 9, QTableWidgetItem(f"{row['unit_price']:,.2f}"))
            self.paper_calc_table.setUpdatesEnabled(True)
            self.paper_calc_table.hideColumn(0)  # Hide ID
        except Exception as err:
            QMessageBox.warning(self, "خطا", f"بارگذاری محاسبات با خطا مواجه شد:\n{err}")

    def load_selected_paper_calc(self):
        row = self.paper_calc_table.currentRow()
        if row < 0:
            return

        self.editing_paper_calc_id = int(self.paper_calc_table.item(row, 0).text())

        self.paper_type_combo.setCurrentText(self.paper_calc_table.item(row, 1).text())
        self.paper_formula_combo.setCurrentText(self.paper_calc_table.item(row, 2).text())

        self.paper_weight_spin.setValue(float(self.paper_calc_table.item(row, 3).text()))
        self.paper_height_spin.setValue(float(self.paper_calc_table.item(row, 4).text()))
        self.paper_length_spin.setValue(float(self.paper_calc_table.item(row, 5).text()))
        self.paper_bundle_count_spin.setValue(int(self.paper_calc_table.item(row, 6).text()))
        self.paper_bundle_weight_spin.setValue(float(self.paper_calc_table.item(row, 7).text()))

        price_text = self.paper_calc_table.item(row, 8).text().replace(',', '')
        self.paper_price_spin.setValue(float(price_text))

        unit_price_text = self.paper_calc_table.item(row, 9).text().replace(',', '')
        self.paper_unit_price_lbl.setText(f"{float(unit_price_text):,.2f}")

    def delete_paper_calculation(self):
        row = self.paper_calc_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "خطا", "لطفاً یک ردیف را انتخاب کنید.")
            return

        calc_id = int(self.paper_calc_table.item(row, 0).text())
        reply = QMessageBox.question(self, "تأیید حذف", "آیا از حذف این محاسبه اطمینان دارید؟",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                self.db.delete_paper_calculation(calc_id)
                self.load_paper_calculations()
                self.editing_paper_calc_id = None
            except Exception as err:
                QMessageBox.critical(self, "خطا", f"حذف با خطا مواجه شد:\n{err}")

    def export_paper_to_defaults(self):
        row = self.paper_calc_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "خطا", "لطفاً یک ردیف محاسبه شده را انتخاب کنید.")
            return

        paper_type = self.paper_calc_table.item(row, 1).text()
        unit_price = float(self.paper_calc_table.item(row, 9).text().replace(',', ''))

        dialog = QDialog(self)
        dialog.setWindowTitle("انتقال به قیمت‌های پایه")
        layout = QFormLayout(dialog)

        cat_combo = QComboBox()
        cat_combo.addItems(["نوع کاغذ متن", "نوع کاغذ جلد"])
        layout.addRow("دسته‌بندی (متن/جلد):", cat_combo)

        item_val_input = QLineEdit(paper_type)
        layout.addRow("مقدار (نام دقیق ویژگی):", item_val_input)

        cost_field_combo = QComboBox()
        cost_field_combo.addItems(["هزینه کاغذ متن", "هزینه کاغذ جلد"])
        layout.addRow("فیلد هزینه هدف:", cost_field_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec() == QDialog.Accepted:
            cat = cat_combo.currentText()
            val = item_val_input.text().strip()
            field = cost_field_combo.currentText()
            try:
                self.db.upsert_default_mapping(cat, val, field, unit_price)
                self.db.save_category(cat, val)
                QMessageBox.information(self, "موفقیت", "انتقال به قیمت‌های پایه با موفقیت انجام شد.")
                self.defaults_exported.emit()
            except Exception as err:
                QMessageBox.critical(self, "خطا", f"انتقال با خطا مواجه شد:\n{err}")
