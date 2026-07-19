"""Paper pre-calculation tab: compute a paper unit price via 3 formulas and
keep a saved library of calculations (paper_calculations table)."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)


class PaperCalcTab(QWidget):

    def __init__(self, db, calculator, parent=None):
        super().__init__(parent)
        self.db = db
        self.calculator = calculator
        self.editing_paper_calc_id = None
        self._all_calcs = []
        self._build_ui()
        self.update_paper_inputs_visibility()
        self.load_paper_calculations()

    # ── Quick-select cascade (item 7) ──────────────────────────────────────

    @staticmethod
    def _size_str(row) -> str:
        h, l = row['height'] or 0, row['length'] or 0
        return f"{h:g}×{l:g}" if (h or l) else "—"

    @staticmethod
    def _gramaj_str(row) -> str:
        return f"{int(row['weight'] or 0)}"

    @staticmethod
    def _bundle_str(row) -> str:
        return f"{int(row['bundle_count'] or 0)}"

    def _build_quick_select(self) -> QGroupBox:
        grp = QGroupBox("📚 انتخاب سریع از کتابخانه (بر اساس محاسبات ذخیره‌شده)")
        gl = QFormLayout(grp)
        gl.setVerticalSpacing(10)
        self.q_type = QComboBox()
        self.q_size = QComboBox()
        self.q_gramaj = QComboBox()
        self.q_bundle = QComboBox()
        self._q_combos = [self.q_type, self.q_size, self.q_gramaj, self.q_bundle]
        gl.addRow("نوع کاغذ:", self.q_type)
        gl.addRow("اندازه (ارتفاع×طول):", self.q_size)
        gl.addRow("گراماژ:", self.q_gramaj)
        gl.addRow("تعداد بند:", self.q_bundle)
        self.q_hint = QLabel("یک ترکیب را انتخاب کنید تا قیمت واحد آن بارگذاری شود.")
        self.q_hint.setWordWrap(True)
        self.q_hint.setStyleSheet("color:#475569;")
        gl.addRow("", self.q_hint)
        use_btn = QPushButton("بارگذاری در فرم و محاسبه")
        use_btn.setStyleSheet(_PRIMARY_BTN_QSS)
        use_btn.clicked.connect(self._apply_quick_select)
        gl.addRow("", use_btn)
        self.q_type.currentIndexChanged.connect(lambda: self._refresh_cascade(1))
        self.q_size.currentIndexChanged.connect(lambda: self._refresh_cascade(2))
        self.q_gramaj.currentIndexChanged.connect(lambda: self._refresh_cascade(3))
        self.q_bundle.currentIndexChanged.connect(self._update_quick_hint)
        return grp

    def _q_val(self, combo) -> str | None:
        return combo.currentData()   # None means "any"

    def _rows_matching(self, upto: int) -> list:
        """Saved rows matching the first `upto` cascade selections (any = None)."""
        sel = [self._q_val(c) for c in self._q_combos]
        keyfns = [lambda r: r['paper_type'], self._size_str, self._gramaj_str, self._bundle_str]
        out = []
        for r in self._all_calcs:
            if all(sel[i] is None or keyfns[i](r) == sel[i] for i in range(upto)):
                out.append(r)
        return out

    def _fill_combo(self, combo, values):
        prev = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("— همه —", None)
        for v in values:
            combo.addItem(v, v)
        idx = combo.findData(prev)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def _refresh_quick_options(self):
        """Rebuild the whole cascade from the saved-calc list."""
        types = sorted({r['paper_type'] for r in self._all_calcs if r['paper_type']})
        self._fill_combo(self.q_type, types)
        self._refresh_cascade(1)

    def _refresh_cascade(self, level: int):
        if level <= 1:
            sizes = sorted({self._size_str(r) for r in self._rows_matching(1)})
            self._fill_combo(self.q_size, sizes)
        if level <= 2:
            gramaj = sorted({self._gramaj_str(r) for r in self._rows_matching(2)},
                            key=lambda s: int(s))
            self._fill_combo(self.q_gramaj, gramaj)
        if level <= 3:
            bundles = sorted({self._bundle_str(r) for r in self._rows_matching(3)},
                             key=lambda s: int(s))
            self._fill_combo(self.q_bundle, bundles)
        self._update_quick_hint()

    def _update_quick_hint(self):
        rows = self._rows_matching(4)
        if not self._all_calcs:
            self.q_hint.setText("کتابخانه خالی است — ابتدا یک محاسبه ذخیره کنید.")
        elif rows:
            self.q_hint.setText(
                f"{len(rows)} مورد منطبق — قیمت واحد: {rows[0]['unit_price']:,.0f} تومان")
        else:
            self.q_hint.setText("موردی با این ترکیب یافت نشد.")

    def _apply_quick_select(self):
        rows = self._rows_matching(4)
        if not rows:
            QMessageBox.information(self, "اطلاعات", "موردی با این ترکیب در کتابخانه یافت نشد.")
            return
        self._load_calc_row(rows[0])       # newest match (list is id DESC)

    # ── UI construction ─────────────────────────────────────────────────────

    def _wide_spin(self, cls):
        """A QSpinBox/QDoubleSpinBox exempted from the app-wide 220px cap —
        this tab's two-column grid has real room, and cramped fields were the
        original complaint."""
        w = cls()
        w.setObjectName("paperCalcField")
        return w

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # The single-column fields (wide, per the redesign) make this a tall
        # form — scroll it instead of forcing the whole window to grow past
        # its normal size. The library table stays outside the scroll area,
        # always visible, and gets whatever vertical space is left over.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 8)
        scroll_layout.setSpacing(12)
        scroll_layout.addWidget(self._build_quick_select())
        scroll_layout.addWidget(self._build_manual_entry())
        scroll.setWidget(scroll_content)

        outer.addWidget(scroll)
        outer.addWidget(self._build_library_table(), 1)

    def _build_manual_entry(self) -> QGroupBox:
        manual_group = QGroupBox("🧮 ورود دستی / محاسبه")
        outer = QVBoxLayout(manual_group)

        # One field per row, same as the quick-select group above it — that
        # gives each box the full row width instead of splitting it in two.
        form = QFormLayout()
        form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.paper_type_combo = QComboBox()
        self.paper_type_combo.setEditable(True)
        self.paper_type_combo.setInsertPolicy(QComboBox.InsertAtBottom)
        self.paper_type_combo.addItems([
            "ایندربرد", "گلاسه", "بالک", "پشت طوسی", "تحریر", "مقوای مغزی"
        ])

        self.paper_formula_combo = QComboBox()
        self.paper_formula_combo.addItems([
            "ابعاد، وزن و قیمت (هر واحد)",
            "قیمت هر بند و تعداد در بند",
            "دستی"
        ])
        self.paper_formula_combo.currentTextChanged.connect(self.update_paper_inputs_visibility)

        self.paper_weight_spin = self._wide_spin(QDoubleSpinBox)
        self.paper_weight_spin.setRange(0, 2000)
        self.paper_weight_spin.setDecimals(0)
        self.paper_weight_spin.setSuffix(" گرم/مترمربع")
        self.paper_weight_spin.setToolTip(
            "گراماژ کاغذ: وزن یک مترمربع از کاغذ بر حسب گرم — مثلاً تحریر ۸۰ یعنی ۸۰ گرم/مترمربع.\n"
            "از این مقدار همراه با ابعاد ورق و قیمت هر کیلوگرم، قیمت یک ورق محاسبه می‌شود.")
        self._weight_label = QLabel("گراماژ کاغذ (وزن):")
        self._weight_label.setToolTip(self.paper_weight_spin.toolTip())

        self.paper_price_spin = self._wide_spin(QDoubleSpinBox)
        self.paper_price_spin.setMaximum(9999999999.99)
        self.paper_price_spin.setGroupSeparatorShown(True)
        self.paper_price_label = QLabel("قیمت / قیمت بند (تومان):")

        self.paper_height_spin = self._wide_spin(QDoubleSpinBox)
        self.paper_height_spin.setMaximum(999999)
        self.paper_height_spin.setSuffix(" سانتی‌متر")

        self.paper_length_spin = self._wide_spin(QDoubleSpinBox)
        self.paper_length_spin.setMaximum(999999)
        self.paper_length_spin.setSuffix(" سانتی‌متر")

        self.paper_bundle_count_spin = self._wide_spin(QSpinBox)
        self.paper_bundle_count_spin.setMaximum(999999)
        self.paper_bundle_count_spin.setSuffix(" برگ")

        self.paper_bundle_weight_spin = self._wide_spin(QDoubleSpinBox)
        self.paper_bundle_weight_spin.setMaximum(999999)
        self.paper_bundle_weight_spin.setSuffix(" کیلوگرم")
        self.paper_bundle_weight_spin.setToolTip(
            "وزن کل یک بند کاغذ (اختیاری، فقط برای ثبت در کتابخانه).")

        form.addRow("نوع کاغذ:", self.paper_type_combo)
        form.addRow("نحوه محاسبه:", self.paper_formula_combo)
        form.addRow(self._weight_label, self.paper_weight_spin)
        form.addRow(self.paper_price_label, self.paper_price_spin)
        form.addRow("ارتفاع:", self.paper_height_spin)
        form.addRow("طول:", self.paper_length_spin)
        form.addRow("تعداد در بند:", self.paper_bundle_count_spin)
        form.addRow("وزن بند:", self.paper_bundle_weight_spin)
        outer.addLayout(form)

        # Result banner — full width, semantic success color (matches the
        # cover-price banner in قیمت‌گذاری و سودآوری for a consistent look)
        result_row = QHBoxLayout()
        result_row.addWidget(QLabel("قیمت نهایی یک واحد:"))
        self.paper_unit_price_lbl = QLabel("0 تومان")
        self.paper_unit_price_lbl.setAlignment(Qt.AlignCenter)
        self.paper_unit_price_lbl.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #15803d;"
            "background-color: #f0fdf4; border: 1px solid #bbf7d0;"
            "padding: 10px; border-radius: 6px;")
        result_row.addWidget(self.paper_unit_price_lbl, 1)
        outer.addLayout(result_row)

        btn_layout = QHBoxLayout()
        calc_btn = QPushButton("محاسبه")
        calc_btn.setStyleSheet(_PRIMARY_BTN_QSS)
        calc_btn.clicked.connect(self.calculate_paper_unit_price)

        save_btn = QPushButton("ذخیره محاسبه")
        save_btn.setStyleSheet(_SUCCESS_BTN_QSS)
        save_btn.clicked.connect(self.save_paper_calculation)

        btn_layout.addWidget(calc_btn)
        btn_layout.addWidget(save_btn)
        btn_layout.addStretch()
        outer.addLayout(btn_layout)

        return manual_group

    def _build_library_table(self) -> QGroupBox:
        table_group = QGroupBox("🗂 کتابخانه محاسبات ذخیره‌شده")
        table_layout = QVBoxLayout(table_group)

        self.paper_calc_table = QTableWidget(0, 9)
        self.paper_calc_table.setHorizontalHeaderLabels([
            "ID", "نوع کاغذ", "نحوه محاسبه", "گراماژ", "اندازه (ارتفاع×طول)",
            "تعداد در بند", "وزن بند (kg)", "قیمت ورودی", "قیمت واحد (تومان)"
        ])
        header = self.paper_calc_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setMinimumSectionSize(90)
        self.paper_calc_table.verticalHeader().setVisible(False)
        self.paper_calc_table.verticalHeader().setDefaultSectionSize(34)
        self.paper_calc_table.setAlternatingRowColors(True)
        self.paper_calc_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.paper_calc_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.paper_calc_table.setMinimumHeight(240)
        self.paper_calc_table.doubleClicked.connect(self.load_selected_paper_calc)
        table_layout.addWidget(self.paper_calc_table, 1)

        table_footer = QHBoxLayout()
        hint_label = QLabel("برای ویرایش، روی ردیف دابل‌کلیک کنید")
        hint_label.setStyleSheet("color: #475569; font-size: 12px;")
        delete_btn = QPushButton("حذف ردیف انتخاب‌شده")
        delete_btn.setStyleSheet(_DANGER_BTN_QSS)
        delete_btn.clicked.connect(self.delete_paper_calculation)
        table_footer.addWidget(hint_label, 1)
        table_footer.addWidget(delete_btn)
        table_layout.addLayout(table_footer)

        return table_group

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
        self.paper_unit_price_lbl.setText(f"{unit_price:,.2f} تومان")
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

    @staticmethod
    def _dash_or(text: str, applicable: bool) -> str:
        return text if applicable else "—"

    def load_paper_calculations(self):
        try:
            rows = self.db.get_paper_calculations()
            self._all_calcs = [dict(r) for r in rows]
            self._refresh_quick_options()
            self.paper_calc_table.setUpdatesEnabled(False)
            self.paper_calc_table.setRowCount(len(rows))
            for row_idx, row in enumerate(rows):
                by_weight = row['formula_type'] == "ابعاد، وزن و قیمت (هر واحد)"
                by_bundle = row['formula_type'] == "قیمت هر بند و تعداد در بند"

                self.paper_calc_table.setItem(row_idx, 0, QTableWidgetItem(str(row['id'])))
                self.paper_calc_table.setItem(row_idx, 1, QTableWidgetItem(row['paper_type']))
                self.paper_calc_table.setItem(row_idx, 2, QTableWidgetItem(row['formula_type']))
                self.paper_calc_table.setItem(
                    row_idx, 3, QTableWidgetItem(self._dash_or(self._gramaj_str(row), by_weight)))
                self.paper_calc_table.setItem(
                    row_idx, 4, QTableWidgetItem(self._dash_or(self._size_str(row), by_weight)))
                self.paper_calc_table.setItem(
                    row_idx, 5, QTableWidgetItem(self._dash_or(self._bundle_str(row), by_bundle)))
                bundle_w = f"{row['bundle_weight']:g}" if row['bundle_weight'] else "0"
                self.paper_calc_table.setItem(
                    row_idx, 6, QTableWidgetItem(self._dash_or(bundle_w, by_bundle)))
                self.paper_calc_table.setItem(
                    row_idx, 7, QTableWidgetItem(f"{row['price']:,.2f}"))

                unit_item = QTableWidgetItem(f"{row['unit_price']:,.0f}")
                unit_item.setForeground(QColor('#15803d'))
                font = QFont()
                font.setBold(True)
                unit_item.setFont(font)
                self.paper_calc_table.setItem(row_idx, 8, unit_item)

                for col in range(1, 9):
                    self.paper_calc_table.item(row_idx, col).setTextAlignment(
                        Qt.AlignCenter)
            self.paper_calc_table.setUpdatesEnabled(True)
            self.paper_calc_table.hideColumn(0)  # Hide ID
        except Exception as err:
            QMessageBox.warning(self, "خطا", f"بارگذاری محاسبات با خطا مواجه شد:\n{err}")

    def _load_calc_row(self, r: dict):
        """Load a saved calculation (dict) into the manual form."""
        self.editing_paper_calc_id = r.get('id')
        self.paper_type_combo.setCurrentText(r.get('paper_type') or '')
        self.paper_formula_combo.setCurrentText(r.get('formula_type') or 'دستی')
        self.update_paper_inputs_visibility()
        self.paper_weight_spin.setValue(float(r.get('weight') or 0))
        self.paper_height_spin.setValue(float(r.get('height') or 0))
        self.paper_length_spin.setValue(float(r.get('length') or 0))
        self.paper_bundle_count_spin.setValue(int(r.get('bundle_count') or 0))
        self.paper_bundle_weight_spin.setValue(float(r.get('bundle_weight') or 0))
        self.paper_price_spin.setValue(float(r.get('price') or 0))
        self.paper_unit_price_lbl.setText(f"{float(r.get('unit_price') or 0):,.2f} تومان")

    def load_selected_paper_calc(self):
        row = self.paper_calc_table.currentRow()
        if row < 0:
            return
        calc_id = int(self.paper_calc_table.item(row, 0).text())
        match = next((r for r in self._all_calcs if r['id'] == calc_id), None)
        if match:
            self._load_calc_row(match)

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


# Semantic action-button styles, reused across this tab (mirrors the
# green/red/blue vocabulary already established elsewhere in the app)
_PRIMARY_BTN_QSS = (
    "QPushButton { background-color: #2563eb; color: white; padding: 8px 18px;"
    " border-radius: 6px; font-weight: 600; }"
    "QPushButton:hover { background-color: #1d4ed8; }"
)
_SUCCESS_BTN_QSS = (
    "QPushButton { background-color: #15803d; color: white; padding: 8px 18px;"
    " border-radius: 6px; font-weight: 600; }"
    "QPushButton:hover { background-color: #166534; }"
)
_DANGER_BTN_QSS = (
    "QPushButton { background-color: #c0392b; color: white; padding: 6px 16px;"
    " border-radius: 4px; }"
    "QPushButton:hover { background-color: #a93226; }"
)
