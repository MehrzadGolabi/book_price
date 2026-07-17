"""Default cost mappings tab: zinc prices plus (category, value) → cost-field defaults."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from bookcost.core.calculator import CostCalculator
from bookcost.core.fields import (
    AUTO_COST_FIELDS, CATEGORY_TARGET_FIELDS, GENERAL_CATEGORY,
)

_ZINC_SIZES = ["زینک 2 ورقی", "زینک 2.5 ورقی", "زینک 3.5 ورقی", "زینک 4.5 ورقی", "زینک GTO"]

_GENERAL_LABEL = "هزینه عمومی (مستقل از نوع)"


class DefaultsTab(QWidget):
    zinc_prices_changed = Signal()
    # A default mapping matched the selected type value: (cost_field, value)
    cost_applied = Signal(str, float)
    # User asked to manage paper prices → main window opens the paper library
    paper_library_requested = Signal()

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.editing_default_id = None
        self._build_ui()
        self._on_category_changed()
        self.load_default_costs_table()
        self.load_zinc_prices_table()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ── Zinc Prices Group ──────────────────────────────────────────────
        zinc_group = QGroupBox("قیمت زینک‌ها")
        zinc_layout = QVBoxLayout()
        self.zinc_prices_table = QTableWidget(5, 3)
        self.zinc_prices_table.setHorizontalHeaderLabels(["اندازه زینک", "قیمت واحد (تومان)", ""])
        self.zinc_prices_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.zinc_prices_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.zinc_prices_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.zinc_prices_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.zinc_prices_table.verticalHeader().setVisible(False)
        zinc_layout.addWidget(self.zinc_prices_table)
        zinc_group.setLayout(zinc_layout)
        layout.addWidget(zinc_group)

        # ── Mapping Form Group ─────────────────────────────────────────────
        self.mapping_form_group = QGroupBox("افزودن قیمت پایه جدید")
        form_outer = QVBoxLayout()

        # Papers are priced in the paper library, not here
        paper_hint_row = QHBoxLayout()
        paper_hint = QLabel(
            "قیمت انواع کاغذ اینجا تعریف نمی‌شود — قیمت واحد هر کاغذ در «کتابخانه کاغذ» "
            "نگه‌داری و به‌طور خودکار در پروژه‌ها بارگذاری می‌شود. قیمت زینک‌ها نیز در جدول بالا است.")
        paper_hint.setWordWrap(True)
        paper_hint.setStyleSheet("color: #64b5f6; font-size: 12px;")
        paper_lib_btn = QPushButton("کتابخانه کاغذ ←")
        paper_lib_btn.setStyleSheet("padding: 4px 10px; color: #64b5f6; background: transparent; border: 1px solid #64b5f6;")
        paper_lib_btn.clicked.connect(self.paper_library_requested.emit)
        paper_hint_row.addWidget(paper_hint, 1)
        paper_hint_row.addWidget(paper_lib_btn)
        form_outer.addLayout(paper_hint_row)

        self._form = form = QFormLayout()

        self.def_cat_combo = QComboBox()
        self.def_cat_combo.setEditable(False)
        self.def_cat_combo.addItems([_GENERAL_LABEL] + list(CATEGORY_TARGET_FIELDS))
        self.def_cat_combo.currentIndexChanged.connect(self._on_category_changed)
        form.addRow("دسته‌بندی:", self.def_cat_combo)

        self.def_value_combo = QComboBox()
        self.def_value_combo.setEditable(True)
        self.def_value_combo.setInsertPolicy(QComboBox.InsertAtBottom)
        self.def_value_combo.currentTextChanged.connect(
            lambda text: self.apply_default_cost(self._current_category(), text)
        )
        self._value_label = QLabel("مقدار (نوع):")
        form.addRow(self._value_label, self.def_value_combo)

        self.def_cost_field_combo = QComboBox()
        form.addRow("فیلد هزینه هدف:", self.def_cost_field_combo)

        self.def_cost_spin = QDoubleSpinBox()
        self.def_cost_spin.setMaximum(9999999999.99)
        self.def_cost_spin.setGroupSeparatorShown(True)
        self.def_cost_spin.setDecimals(0)
        self.def_cost_spin.lineEdit().setAlignment(Qt.AlignCenter)
        form.addRow("قیمت پیش‌فرض:", self.def_cost_spin)

        form_outer.addLayout(form)

        btn_layout = QHBoxLayout()
        self._default_add_btn = QPushButton("افزودن")
        self._default_add_btn.setStyleSheet(
            "QPushButton { background-color: #27ae60; color: white; padding: 6px 16px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #219a52; }"
        )
        self._default_add_btn.clicked.connect(self.add_default_cost_mapping)

        self._default_save_btn = QPushButton("ذخیره ویرایش")
        self._default_save_btn.setStyleSheet(
            "QPushButton { background-color: #2a6496; color: white; padding: 6px 16px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #1f4f78; }"
        )
        self._default_save_btn.clicked.connect(self.edit_default_cost_mapping)
        self._default_save_btn.setVisible(False)

        self._default_cancel_btn = QPushButton("انصراف")
        self._default_cancel_btn.setStyleSheet(
            "QPushButton { background-color: #6c757d; color: white; padding: 6px 16px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #565e64; }"
        )
        self._default_cancel_btn.clicked.connect(self._reset_default_form)
        self._default_cancel_btn.setVisible(False)

        delete_btn = QPushButton("حذف")
        delete_btn.setStyleSheet(
            "QPushButton { background-color: #c0392b; color: white; padding: 6px 16px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #a93226; }"
        )
        delete_btn.clicked.connect(self.delete_default_cost_mapping)

        btn_layout.addWidget(self._default_add_btn)
        btn_layout.addWidget(self._default_save_btn)
        btn_layout.addWidget(self._default_cancel_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(delete_btn)

        form_outer.addLayout(btn_layout)
        self.mapping_form_group.setLayout(form_outer)
        layout.addWidget(self.mapping_form_group)

        # ── Saved Mappings Table Group ─────────────────────────────────────
        table_group = QGroupBox("ردیف‌های ذخیره‌شده")
        table_layout = QVBoxLayout()

        self.defaults_table = QTableWidget(0, 4)
        self.defaults_table.setHorizontalHeaderLabels(["دسته‌بندی", "مقدار", "فیلد هزینه", "قیمت پیش‌فرض"])
        self.defaults_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.defaults_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.defaults_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.defaults_table.doubleClicked.connect(self.load_selected_default_for_edit)
        table_layout.addWidget(self.defaults_table)

        hint_label = QLabel("برای ویرایش، روی ردیف دابل‌کلیک کنید")
        hint_label.setAlignment(Qt.AlignCenter)
        hint_label.setStyleSheet("color: #64748b; font-size: 11px;")
        table_layout.addWidget(hint_label)

        table_group.setLayout(table_layout)
        layout.addWidget(table_group)

    # ── Zinc prices ────────────────────────────────────────────────────────

    def load_zinc_prices_table(self):
        self.zinc_prices_table.setRowCount(len(_ZINC_SIZES))
        for i, zs in enumerate(_ZINC_SIZES):
            name_item = QTableWidgetItem(zs)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.zinc_prices_table.setItem(i, 0, name_item)
            spin = QDoubleSpinBox()
            spin.setMaximum(9999999999.99)
            spin.setGroupSeparatorShown(True)
            spin.setDecimals(0)
            spin.setValue(self.db.get_zinc_price(zs))
            self.zinc_prices_table.setCellWidget(i, 1, spin)
            save_btn = QPushButton("ذخیره")
            save_btn.setStyleSheet("background-color: #2a6496; color: white; padding: 2px 8px; font-size: 11px;")
            save_btn.clicked.connect(lambda checked, row=i, size=zs: self.save_zinc_price(row, size))
            self.zinc_prices_table.setCellWidget(i, 2, save_btn)

    def save_zinc_price(self, row, zinc_size):
        spin = self.zinc_prices_table.cellWidget(row, 1)
        if spin is None:
            return
        try:
            self.db.save_zinc_price(zinc_size, spin.value())
            self.zinc_prices_changed.emit()
            QMessageBox.information(self, "ذخیره شد", f"قیمت {zinc_size} ذخیره شد.")
        except Exception as err:
            QMessageBox.critical(self, "خطا", f"ذخیره قیمت زینک با خطا مواجه شد:\n{err}")

    # ── Default cost mappings ──────────────────────────────────────────────

    @staticmethod
    def _all_manual_fields() -> list:
        all_fields = [f for fields in CostCalculator.COST_GROUPS.values() for f in fields]
        return [f for f in all_fields if f not in AUTO_COST_FIELDS]

    def _current_category(self) -> str:
        """Stored category name for the current selection ('عمومی' for general)."""
        text = self.def_cat_combo.currentText()
        return GENERAL_CATEGORY if text == _GENERAL_LABEL else text

    def _on_category_changed(self, *args):
        """General mode hides the value row and opens up all manual cost
        fields; a type category shows its values and constrains the target."""
        category = self._current_category()
        is_general = category == GENERAL_CATEGORY
        self._value_label.setVisible(not is_general)
        self.def_value_combo.setVisible(not is_general)

        self.def_cost_field_combo.blockSignals(True)
        self.def_cost_field_combo.clear()
        if is_general:
            self.def_cost_field_combo.addItems(self._all_manual_fields())
            self.def_cost_field_combo.setEnabled(True)
        else:
            allowed = CATEGORY_TARGET_FIELDS.get(category, [])
            self.def_cost_field_combo.addItems(allowed)
            self.def_cost_field_combo.setEnabled(len(allowed) > 1)
        self.def_cost_field_combo.blockSignals(False)

        if not is_general:
            self.populate_default_value_combo(category)

    def populate_default_value_combo(self, category_name):
        """Fills the value combo with existing items from the chosen category."""
        self.def_value_combo.clear()
        try:
            self.def_value_combo.addItems(self.db.get_categories(category_name))
        except Exception as e:
            print("Error populating value combo:", e)

    def load_default_costs_table(self):
        """Reloads the table showing all default cost mappings."""
        try:
            rows = self.db.get_default_cost_mappings()
            self.defaults_table.setUpdatesEnabled(False)
            self.defaults_table.setRowCount(len(rows))
            for i, row in enumerate(rows):
                is_general = row['category_name'] == GENERAL_CATEGORY
                self.defaults_table.setItem(i, 0, QTableWidgetItem(row['category_name']))
                self.defaults_table.setItem(
                    i, 1, QTableWidgetItem('—' if is_general else row['item_value']))
                self.defaults_table.setItem(i, 2, QTableWidgetItem(row['target_cost_field']))
                cost_item = QTableWidgetItem(f"{row['default_cost']:,.2f}")
                cost_item.setTextAlignment(Qt.AlignCenter)
                self.defaults_table.setItem(i, 3, cost_item)
                self.defaults_table.item(i, 0).setData(Qt.UserRole, row['id'])
            self.defaults_table.setUpdatesEnabled(True)
        except Exception as err:
            QMessageBox.warning(self, "خطا", f"بارگذاری قیمت‌های پایه با خطا مواجه شد:\n{err}")

    def reload(self):
        """Refresh after external changes (import, restore, ...)."""
        self.load_default_costs_table()
        self._on_category_changed()

    def _reset_default_form(self):
        self.def_cost_spin.setValue(0)
        self.editing_default_id = None
        self.mapping_form_group.setTitle("افزودن قیمت پایه جدید")
        self._default_add_btn.setVisible(True)
        self._default_save_btn.setVisible(False)
        self._default_cancel_btn.setVisible(False)

    def add_default_cost_mapping(self):
        cat = self._current_category()
        field = self.def_cost_field_combo.currentText()
        if cat == GENERAL_CATEGORY:
            # keyed by the field itself so upserts stay unique per field
            val = field
        else:
            val = self.def_value_combo.currentText().strip()
            if not val:
                QMessageBox.warning(self, "خطا", "مقدار نوع نمی‌تواند خالی باشد.")
                return
        try:
            self.db.upsert_default_mapping(cat, val, field, self.def_cost_spin.value())
            if cat != GENERAL_CATEGORY:
                self.db.save_category(cat, val)
            self.load_default_costs_table()
            self._on_category_changed()
            self._reset_default_form()
        except Exception as err:
            QMessageBox.critical(self, "خطا", f"افزودن قیمت پایه با خطا مواجه شد:\n{err}")

    def load_selected_default_for_edit(self):
        row = self.defaults_table.currentRow()
        if row < 0:
            return
        id_item = self.defaults_table.item(row, 0)
        mapping_id = id_item.data(Qt.UserRole)
        cat = self.defaults_table.item(row, 0).text()
        val = self.defaults_table.item(row, 1).text()
        field = self.defaults_table.item(row, 2).text()
        cost_text = self.defaults_table.item(row, 3).text().replace(',', '')
        try:
            cost = float(cost_text)
        except ValueError:
            cost = 0.0

        if cat == GENERAL_CATEGORY or cat == _GENERAL_LABEL:
            self.def_cat_combo.setCurrentText(_GENERAL_LABEL)
        elif cat in CATEGORY_TARGET_FIELDS:
            self.def_cat_combo.setCurrentText(cat)
            self.def_value_combo.setCurrentText(val)
        else:
            # Legacy row (paper/zinc type categories from older versions)
            QMessageBox.information(
                self, "ردیف قدیمی",
                "این ردیف از نسخه‌های قبلی است و دیگر قابل ویرایش نیست.\n"
                "قیمت کاغذها در «کتابخانه کاغذ» و قیمت زینک‌ها در جدول بالای همین صفحه "
                "مدیریت می‌شود. در صورت عدم نیاز می‌توانید این ردیف را حذف کنید.")
            return
        self._on_category_changed()
        if self.def_cost_field_combo.findText(field) == -1:
            self.def_cost_field_combo.addItem(field)   # legacy pairing — keep editable
        self.def_cost_field_combo.setCurrentText(field)
        self.def_cost_spin.setValue(cost)
        self.editing_default_id = mapping_id
        self.mapping_form_group.setTitle("ویرایش قیمت پایه")
        self._default_add_btn.setVisible(False)
        self._default_save_btn.setVisible(True)
        self._default_cancel_btn.setVisible(True)

    def edit_default_cost_mapping(self):
        if self.editing_default_id is None:
            QMessageBox.warning(self, "خطا", "ابتدا یک ردیف را با دابل کلیک انتخاب کنید.")
            return
        cat = self._current_category()
        field = self.def_cost_field_combo.currentText()
        val = field if cat == GENERAL_CATEGORY else self.def_value_combo.currentText().strip()
        try:
            self.db.update_default_mapping(self.editing_default_id, cat, val,
                                           field, self.def_cost_spin.value())
            self.load_default_costs_table()
            self._on_category_changed()
            self._reset_default_form()
        except Exception as err:
            QMessageBox.critical(self, "خطا", f"ویرایش با خطا مواجه شد:\n{err}")

    def delete_default_cost_mapping(self):
        row = self.defaults_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "خطا", "لطفاً یک ردیف را انتخاب کنید.")
            return
        mapping_id = self.defaults_table.item(row, 0).data(Qt.UserRole)
        reply = QMessageBox.question(self, "تأیید حذف", "آیا از حذف این قیمت پایه اطمینان دارید؟",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        try:
            self.db.delete_default_mapping(mapping_id)
            self.load_default_costs_table()
        except Exception as err:
            QMessageBox.critical(self, "خطا", f"حذف با خطا مواجه شد:\n{err}")

    def apply_default_cost(self, category_name, selected_text):
        """Looks up a default cost mapping and notifies listeners to fill the field."""
        if not selected_text:
            return
        try:
            mapping = self.db.get_default_cost(category_name, selected_text)
            if mapping:
                self.cost_applied.emit(mapping['target_cost_field'], mapping['default_cost'])
        except Exception as err:
            print("Error applying default cost:", err)
