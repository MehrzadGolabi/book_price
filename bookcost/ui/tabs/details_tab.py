"""Details tab: all project inputs — basic info, dynamic types, smart paper/zinc
pre-press calculations, and the grouped cost fields.

Persistence mapping to/from the ``project_details`` row goes through
``collect_project()`` / ``collect_details()`` / ``populate()`` so the main
window never reaches into individual widgets.
"""

import jdatetime
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSpinBox,
    QVBoxLayout, QWidget,
)

from bookcost.core.calculator import CostCalculator
from bookcost.core.fields import (
    AUTO_COST_FIELDS, COST_FIELD_COLUMNS, DYNAMIC_TYPE_CATEGORIES, TYPE_FIELD_COLUMNS,
)
from bookcost.ui.dialogs.paper_price_dialog import PaperPriceDialog
from bookcost.ui.widgets.print_layout_widget import PrintLayoutWidget


class DetailsTab(QWidget):
    calculate_requested = Signal()

    def __init__(self, db, calculator: CostCalculator, parent=None):
        super().__init__(parent)
        self.db = db
        self.calculator = calculator
        self.inputs = {}
        self.cost_inputs = {}
        self.cost_input_rows = {}
        self.cost_group_boxes = {}
        self._build_ui()
        self._connect_signals()
        self.refresh_zinc_price_labels()
        self.suggest_optimal_layout()
        self._refresh_layout_widget()
        # Apply default preset without zeroing (fields are already zero)
        self._apply_preset("شومیز ساده", zero_hidden=False)

    # ── UI construction ────────────────────────────────────────────────────

    def _make_cost_row(self, field_name: str, readonly: bool = False) -> QWidget:
        """Creates a labeled row widget for a cost field and registers it."""
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(4, 1, 4, 1)
        layout.setSpacing(8)
        label = QLabel(field_name + ":")
        label.setMinimumWidth(200)
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        spin = QDoubleSpinBox()
        spin.setMaximum(9_999_999_999.99)
        spin.setGroupSeparatorShown(True)
        spin.setDecimals(0)
        spin.lineEdit().setAlignment(Qt.AlignCenter)
        if readonly:
            spin.setReadOnly(True)
            spin.setStyleSheet("background-color: #1e2d1e; color: #4caf50;")
        layout.addWidget(label)
        layout.addWidget(spin)
        self.cost_inputs[field_name] = spin
        self.cost_input_rows[field_name] = row
        return row

    def _build_ui(self):
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setLayoutDirection(Qt.LeftToRight)

        scroll_content = QWidget()
        scroll_content.setObjectName("scroll_content")
        scroll_content.setLayoutDirection(Qt.RightToLeft)
        scroll_layout = QVBoxLayout(scroll_content)

        form_layout = QFormLayout()

        # ── Preset selector ───────────────────────────────────────────────
        self.book_type_combo = QComboBox()
        self.book_type_combo.addItems(list(CostCalculator.BOOK_TYPE_PRESETS.keys()))
        self.book_type_combo.setCurrentText("شومیز ساده")
        form_layout.addRow("نوع کتاب:", self.book_type_combo)

        # ── Basic info ────────────────────────────────────────────────────
        self.inputs['عنوان کتاب'] = QLineEdit()
        self.inputs['عنوان کتاب'].setPlaceholderText("عنوان کتاب را وارد کنید")

        self.inputs['زیر عنوان کتاب'] = QLineEdit()
        self.inputs['زیر عنوان کتاب'].setPlaceholderText("(اختیاری)")

        self.inputs['تاریخ'] = QLineEdit()
        self.inputs['تاریخ'].setText(jdatetime.date.today().strftime("%Y/%m/%d"))
        self.inputs['تاریخ'].setReadOnly(True)

        self.inputs['تیراژ'] = QSpinBox()
        self.inputs['تیراژ'].setMaximum(100000)
        self.inputs['تیراژ'].setGroupSeparatorShown(True)

        self.inputs['قطع'] = QComboBox()
        self.inputs['قطع'].addItems(list(CostCalculator.OPTIMAL_SPECS.keys()))

        self.lbl_optimal_paper = QLabel("کاغذ بهینه: - | ورق مصرفی هر جلد: -")
        self.lbl_optimal_paper.setObjectName("lbl_optimal_paper")

        self.total_pages_spin = QSpinBox()
        self.total_pages_spin.setMaximum(5000)
        self.total_pages_spin.setSuffix(" صفحه")
        self.total_pages_spin.setAlignment(Qt.AlignCenter)

        form_layout.addRow("عنوان کتاب:", self.inputs['عنوان کتاب'])
        form_layout.addRow("زیر عنوان:", self.inputs['زیر عنوان کتاب'])
        form_layout.addRow("تاریخ:", self.inputs['تاریخ'])
        form_layout.addRow("تیراژ:", self.inputs['تیراژ'])
        form_layout.addRow("قطع کتاب:", self.inputs['قطع'])
        form_layout.addRow("", self.lbl_optimal_paper)
        form_layout.addRow("تعداد صفحات کتاب:", self.total_pages_spin)

        # ── Paper size selector (always visible) ──────────────────────────
        self.paper_size_combo = QComboBox()
        self.paper_size_combo.addItems(["70×100", "60×90", "50×70"])
        form_layout.addRow("اندازه کاغذ چاپ:", self.paper_size_combo)

        # ── Custom book dimensions (hidden for standard formats) ──────────
        dims_widget = QWidget()
        dims_layout = QHBoxLayout(dims_widget)
        dims_layout.setContentsMargins(0, 0, 0, 0)
        self.book_width_spin = QDoubleSpinBox()
        self.book_width_spin.setRange(5, 60)
        self.book_width_spin.setDecimals(1)
        self.book_width_spin.setSuffix(" cm")
        self.book_height_spin = QDoubleSpinBox()
        self.book_height_spin.setRange(5, 100)
        self.book_height_spin.setDecimals(1)
        self.book_height_spin.setSuffix(" cm")
        dims_layout.addWidget(QLabel("عرض:"))
        dims_layout.addWidget(self.book_width_spin)
        dims_layout.addWidget(QLabel("  ارتفاع:"))
        dims_layout.addWidget(self.book_height_spin)
        self.book_dims_row_widget = dims_widget
        form_layout.addRow("ابعاد کتاب:", self.book_dims_row_widget)

        # ── Orientation result label ──────────────────────────────────────
        self.orientation_label = QLabel("")
        self.orientation_label.setWordWrap(True)
        self.orientation_label.setStyleSheet("color: #64b5f6;")
        form_layout.addRow("جهت بهینه:", self.orientation_label)

        # ── Dynamic type categories ───────────────────────────────────────
        category_items = {dtype: [] for dtype in DYNAMIC_TYPE_CATEGORIES}
        try:
            for dtype in DYNAMIC_TYPE_CATEGORIES:
                category_items[dtype] = self.db.get_categories(dtype)
        except Exception as e:
            print("Error pre-fetching categories:", e)

        for dtype in DYNAMIC_TYPE_CATEGORIES:
            combo = QComboBox()
            combo.setEditable(True)
            combo.setInsertPolicy(QComboBox.InsertAtBottom)
            combo.addItems(category_items[dtype])
            self.inputs[dtype] = combo
            form_layout.addRow(dtype + ":", combo)

        # ── Group ①: خلاقیت و تحریریه ─────────────────────────────────────
        grp1 = QGroupBox("① خلاقیت و تحریریه")
        grp1_layout = QVBoxLayout(grp1)
        grp1_layout.setSpacing(2)
        for fname in CostCalculator.COST_GROUPS["خلاقیت و تحریریه"]:
            grp1_layout.addWidget(self._make_cost_row(fname))
        form_layout.addRow(grp1)
        self.cost_group_boxes["خلاقیت و تحریریه"] = grp1

        # ── Group ②: پیش از چاپ — smart paper & zinc calculations ─────────
        form_layout.addRow(self._build_precalc_group())

        # ── Group ③: چاپ و مواد ───────────────────────────────────────────
        grp3 = QGroupBox("③ چاپ و مواد")
        grp3_layout = QVBoxLayout(grp3)
        grp3_layout.setSpacing(2)
        for fname in CostCalculator.COST_GROUPS["چاپ و مواد"]:
            grp3_layout.addWidget(self._make_cost_row(fname, readonly=fname in AUTO_COST_FIELDS))
        form_layout.addRow(grp3)
        self.cost_group_boxes["چاپ و مواد"] = grp3

        # ── Group ④: تکمیل و صحافی ────────────────────────────────────────
        grp4 = QGroupBox("④ تکمیل و صحافی")
        grp4_layout = QVBoxLayout(grp4)
        grp4_layout.setSpacing(2)
        for fname in CostCalculator.COST_GROUPS["تکمیل و صحافی"]:
            grp4_layout.addWidget(self._make_cost_row(fname))
        form_layout.addRow(grp4)
        self.cost_group_boxes["تکمیل و صحافی"] = grp4

        # ── Group ⑤: اداری و مجوزها ───────────────────────────────────────
        grp5 = QGroupBox("⑤ اداری و مجوزها")
        grp5_layout = QVBoxLayout(grp5)
        grp5_layout.setSpacing(2)
        for fname in CostCalculator.COST_GROUPS["اداری و مجوزها"]:
            grp5_layout.addWidget(self._make_cost_row(fname))
        form_layout.addRow(grp5)
        self.cost_group_boxes["اداری و مجوزها"] = grp5

        self.royalty_input = QDoubleSpinBox()
        self.royalty_input.setSuffix(" %")
        self.royalty_input.setMaximum(100.0)
        self.royalty_input.setDecimals(0)
        form_layout.addRow("حق تالیف درصدی:", self.royalty_input)

        calc_btn = QPushButton("ثبت اطلاعات و انجام محاسبات نهایی")
        calc_btn.setStyleSheet("padding: 10px; font-weight: bold; background-color: #27ae60; color: white;")
        calc_btn.clicked.connect(self.calculate_requested.emit)

        scroll_layout.addLayout(form_layout)
        scroll_layout.addWidget(calc_btn)
        scroll_area.setWidget(scroll_content)

        self.layout_widget = PrintLayoutWidget()
        self.layout_widget.setFixedWidth(320)

        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        self.setLayoutDirection(Qt.LeftToRight)
        outer_layout.addWidget(scroll_area)
        outer_layout.addWidget(self.layout_widget)

    def _build_precalc_group(self) -> QGroupBox:
        self.calc_group = QGroupBox("② پیش از چاپ — محاسبات هوشمند کاغذ و زینک")
        calc_layout = QFormLayout()

        # Text block (matn) setup
        self.form_matn_spin = QSpinBox()
        self.form_matn_spin.setMaximum(1000)
        self.double_sided_matn_chk = QCheckBox("چاپ دورو (متن)")
        self.double_sided_matn_chk.setChecked(True)

        self.color_matn_combo = QComboBox()
        self.color_matn_combo.addItems(["تک رنگ (1)", "دو رنگ (2)", "چهار رنگ (4)"])

        self.zinc_size_matn_combo = QComboBox()
        self.zinc_size_matn_combo.addItems(["زینک 4.5 ورقی", "زینک 3.5 ورقی", "زینک 2.5 ورقی", "زینک 2 ورقی", "زینک GTO"])

        self.unit_price_paper_matn_spin = QDoubleSpinBox()
        self.unit_price_paper_matn_spin.setMaximum(9999999999.99)
        self.unit_price_paper_matn_spin.setGroupSeparatorShown(True)

        calc_layout.addRow("تعداد فرم متن (خودکار):", self.form_matn_spin)
        calc_layout.addRow("", self.double_sided_matn_chk)
        calc_layout.addRow("تعداد رنگ متن:", self.color_matn_combo)
        calc_layout.addRow("ابعاد زینک متن:", self.zinc_size_matn_combo)
        self.zinc_price_matn_label = QLabel("—")
        self.zinc_price_matn_label.setAlignment(Qt.AlignCenter)
        calc_layout.addRow("قیمت واحد زینک متن:", self.zinc_price_matn_label)
        matn_price_row = QWidget()
        matn_price_layout = QHBoxLayout(matn_price_row)
        matn_price_layout.setContentsMargins(0, 0, 0, 0)
        matn_price_layout.addWidget(self.unit_price_paper_matn_spin)
        btn_calc_matn = QPushButton("🧮 محاسبه")
        btn_calc_matn.setStyleSheet("background-color: #2a6496; color: white; padding: 4px 10px;")
        btn_calc_matn.clicked.connect(lambda: self.open_paper_price_dialog("matn"))
        matn_price_layout.addWidget(btn_calc_matn)
        calc_layout.addRow("قیمت واحد هر ورق کاغذ متن:", matn_price_row)

        # Cover (jeld) setup
        self.form_jeld_spin = QSpinBox()
        self.double_sided_jeld_chk = QCheckBox("چاپ دورو (جلد)")
        self.double_sided_jeld_chk.setChecked(False)

        self.color_jeld_combo = QComboBox()
        self.color_jeld_combo.addItems(["تک رنگ (1)", "دو رنگ (2)", "چهار رنگ (4)"])
        self.color_jeld_combo.setCurrentIndex(2)

        self.zinc_size_jeld_combo = QComboBox()
        self.zinc_size_jeld_combo.addItems(["زینک 4.5 ورقی", "زینک 3.5 ورقی", "زینک 2.5 ورقی", "زینک 2 ورقی", "زینک GTO"])

        self.unit_price_paper_jeld_spin = QDoubleSpinBox()
        self.unit_price_paper_jeld_spin.setMaximum(9999999999.99)
        self.unit_price_paper_jeld_spin.setGroupSeparatorShown(True)

        calc_layout.addRow("تعداد فرم جلد:", self.form_jeld_spin)
        calc_layout.addRow("", self.double_sided_jeld_chk)
        calc_layout.addRow("تعداد رنگ جلد:", self.color_jeld_combo)
        calc_layout.addRow("ابعاد زینک جلد:", self.zinc_size_jeld_combo)
        self.zinc_price_jeld_label = QLabel("—")
        self.zinc_price_jeld_label.setAlignment(Qt.AlignCenter)
        calc_layout.addRow("قیمت واحد زینک جلد:", self.zinc_price_jeld_label)
        jeld_price_row = QWidget()
        jeld_price_layout = QHBoxLayout(jeld_price_row)
        jeld_price_layout.setContentsMargins(0, 0, 0, 0)
        jeld_price_layout.addWidget(self.unit_price_paper_jeld_spin)
        btn_calc_jeld = QPushButton("🧮 محاسبه")
        btn_calc_jeld.setStyleSheet("background-color: #2a6496; color: white; padding: 4px 10px;")
        btn_calc_jeld.clicked.connect(lambda: self.open_paper_price_dialog("jeld"))
        jeld_price_layout.addWidget(btn_calc_jeld)
        calc_layout.addRow("قیمت واحد هر ورق کاغذ جلد:", jeld_price_row)

        self.waste_percent_spin = QDoubleSpinBox()
        self.waste_percent_spin.setRange(0, 50)
        self.waste_percent_spin.setDecimals(1)
        self.waste_percent_spin.setValue(5.0)
        self.waste_percent_spin.setSuffix(" %")
        calc_layout.addRow("ضایعات کاغذ:", self.waste_percent_spin)

        self.calc_group.setLayout(calc_layout)
        return self.calc_group

    def _connect_signals(self):
        self.inputs['قطع'].currentIndexChanged.connect(self.suggest_optimal_layout)
        self.total_pages_spin.valueChanged.connect(self.suggest_optimal_layout)
        self.double_sided_matn_chk.toggled.connect(self.suggest_optimal_layout)
        self.book_type_combo.currentTextChanged.connect(
            lambda name: self._apply_preset(name, zero_hidden=True)
        )

        for w in [self.form_matn_spin, self.unit_price_paper_matn_spin,
                  self.form_jeld_spin, self.unit_price_paper_jeld_spin,
                  self.inputs['تیراژ'], self.waste_percent_spin]:
            w.valueChanged.connect(self.auto_calculate_costs)

        self.double_sided_matn_chk.toggled.connect(self.auto_calculate_costs)
        self.double_sided_jeld_chk.toggled.connect(self.auto_calculate_costs)
        self.color_matn_combo.currentIndexChanged.connect(self.auto_calculate_costs)
        self.color_jeld_combo.currentIndexChanged.connect(self.auto_calculate_costs)
        self.zinc_size_matn_combo.currentIndexChanged.connect(self.refresh_zinc_price_labels)
        self.zinc_size_matn_combo.currentIndexChanged.connect(self.auto_calculate_costs)
        self.zinc_size_jeld_combo.currentIndexChanged.connect(self.refresh_zinc_price_labels)
        self.zinc_size_jeld_combo.currentIndexChanged.connect(self.auto_calculate_costs)
        self.book_width_spin.valueChanged.connect(self.suggest_optimal_layout)
        self.book_height_spin.valueChanged.connect(self.suggest_optimal_layout)
        self.paper_size_combo.currentIndexChanged.connect(self.suggest_optimal_layout)
        self.inputs['قطع'].currentIndexChanged.connect(self._refresh_layout_widget)
        self.total_pages_spin.valueChanged.connect(self._refresh_layout_widget)
        self.paper_size_combo.currentIndexChanged.connect(self._refresh_layout_widget)
        self.zinc_size_matn_combo.currentIndexChanged.connect(self._refresh_layout_widget)
        self.zinc_size_jeld_combo.currentIndexChanged.connect(self._refresh_layout_widget)
        self.book_width_spin.valueChanged.connect(self._refresh_layout_widget)
        self.book_height_spin.valueChanged.connect(self._refresh_layout_widget)

    # ── Live behaviors ─────────────────────────────────────────────────────

    def refresh_zinc_price_labels(self):
        for label, combo in [
            (self.zinc_price_matn_label, self.zinc_size_matn_combo),
            (self.zinc_price_jeld_label, self.zinc_size_jeld_combo),
        ]:
            price = self.db.get_zinc_price(combo.currentText())
            if price > 0:
                label.setText(f"{price:,.0f} تومان")
                label.setStyleSheet("color: #4caf50;")
            else:
                label.setText("⚠ قیمت تنظیم نشده")
                label.setStyleSheet("color: #e57373;")

    def auto_calculate_costs(self, *args):
        color_counts = {0: 1, 1: 2, 2: 4}
        results = self.calculator.compute_auto_costs(
            form_matn=self.form_matn_spin.value(),
            sides_matn=2 if self.double_sided_matn_chk.isChecked() else 1,
            form_jeld=self.form_jeld_spin.value(),
            sides_jeld=2 if self.double_sided_jeld_chk.isChecked() else 1,
            tiraj=self.inputs['تیراژ'].value(),
            waste_pct=self.waste_percent_spin.value(),
            unit_price_matn=self.unit_price_paper_matn_spin.value(),
            unit_price_jeld=self.unit_price_paper_jeld_spin.value(),
            text_colors=color_counts.get(self.color_matn_combo.currentIndex(), 4),
            cover_colors=color_counts.get(self.color_jeld_combo.currentIndex(), 4),
            zinc_price_matn=self.db.get_zinc_price(self.zinc_size_matn_combo.currentText()),
            zinc_price_jeld=self.db.get_zinc_price(self.zinc_size_jeld_combo.currentText()),
        )
        for field, value in results.items():
            self.cost_inputs[field].setValue(value)

    def open_paper_price_dialog(self, target):
        dlg = PaperPriceDialog(self.db, target, parent=self)
        dlg.setAttribute(Qt.WA_DeleteOnClose)
        if dlg.exec() == QDialog.Accepted:
            if target == "matn":
                self.unit_price_paper_matn_spin.setValue(dlg.result_value)
            else:
                self.unit_price_paper_jeld_spin.setValue(dlg.result_value)

    def suggest_optimal_layout(self):
        qate = self.inputs['قطع'].currentText()
        total_pages = self.total_pages_spin.value()

        layout = self.calculator.suggest_layout(
            qate, total_pages,
            book_w=self.book_width_spin.value(),
            book_h=self.book_height_spin.value(),
            paper_size_str=self.paper_size_combo.currentText().replace('×', 'x'),
        )

        if layout is None or total_pages == 0:
            self.book_dims_row_widget.setVisible(False)
            self.orientation_label.setVisible(False)
            self.lbl_optimal_paper.setText("کاغذ بهینه: - | ورق مصرفی هر جلد: -")
            return

        self.book_dims_row_widget.setVisible(layout['is_custom'])
        self.orientation_label.setVisible(layout['is_custom'])

        self.paper_size_combo.setCurrentText(layout['paper_size'])
        if layout['zinc']:
            self.zinc_size_matn_combo.setCurrentText(layout['zinc'])

        self.orientation_label.setText(layout['orientation_label'] or '')

        if layout['is_custom'] and layout['default_dims'] and layout['default_dims'][0] is not None:
            if self.book_width_spin.value() == self.book_width_spin.minimum():
                self.book_width_spin.setValue(layout['default_dims'][0])
                self.book_height_spin.setValue(layout['default_dims'][1])

        multiplier = 2 if self.double_sided_matn_chk.isChecked() else 1
        self.form_matn_spin.setValue(layout['sheets_per_book'] * multiplier)
        self.lbl_optimal_paper.setText(
            f"کاغذ بهینه: {layout['paper_size']} | ورق مصرفی هر جلد: {layout['sheets_per_book']}"
        )

    def _refresh_layout_widget(self):
        qate = self.inputs['قطع'].currentText()
        specs = CostCalculator.OPTIMAL_SPECS.get(qate, {})

        paper_str = self.paper_size_combo.currentText().replace('×', 'x')
        try:
            paper_w, paper_h = map(float, paper_str.split('x'))
        except ValueError:
            return

        if specs.get('pages_per_sheet') is None and self.book_dims_row_widget.isVisible():
            book_w = self.book_width_spin.value()
            book_h = self.book_height_spin.value()
        else:
            dims = CostCalculator.BOOK_PAGE_DIMS.get(qate, (None, None))
            book_w = dims[0] if dims[0] else paper_w / 4
            book_h = dims[1] if dims[1] else paper_h / 4

        total_pages = self.total_pages_spin.value()
        if total_pages == 0:
            pages_per_sheet = 0
        elif specs.get('pages_per_sheet') is not None:
            pages_per_sheet = specs['pages_per_sheet']
        elif book_w > 0 and book_h > 0:
            _, pages_per_sheet = self.calculator.compute_optimal_orientation(
                book_w, book_h, paper_w, paper_h
            )
        else:
            pages_per_sheet = 0

        self.layout_widget.update_layout(
            paper_w, paper_h,
            book_w, book_h,
            pages_per_sheet,
            self.zinc_size_matn_combo.currentText(),
            self.zinc_size_jeld_combo.currentText(),
        )

    def _apply_preset(self, preset_name: str, zero_hidden: bool = True):
        visible_fields = CostCalculator.BOOK_TYPE_PRESETS.get(preset_name)  # None = show all
        all_fields = [f for fields in CostCalculator.COST_GROUPS.values() for f in fields]

        for field_name in all_fields:
            row = self.cost_input_rows.get(field_name)
            if row is None:
                continue
            should_show = (visible_fields is None) or (field_name in visible_fields)
            row.setVisible(should_show)
            if not should_show and zero_hidden:
                spin = self.cost_inputs.get(field_name)
                if spin and not spin.isReadOnly():
                    spin.setValue(0.0)

        for group_name, group_box in self.cost_group_boxes.items():
            group_fields = CostCalculator.COST_GROUPS[group_name]
            any_visible = (visible_fields is None) or any(
                f in visible_fields for f in group_fields
            )
            group_box.setVisible(any_visible)

    def reload_categories(self):
        """Re-reads the dynamic type combos from the database (e.g. after a
        restore or an import added new type values)."""
        for dtype in DYNAMIC_TYPE_CATEGORIES:
            combo = self.inputs[dtype]
            current = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            try:
                combo.addItems(self.db.get_categories(dtype))
            except Exception as e:
                print("Error reloading categories:", e)
            combo.setCurrentText(current)
            combo.blockSignals(False)

    def save_new_dynamic_types(self):
        """Persists any type combo text that isn't in its list yet."""
        for category, widget in self.inputs.items():
            if isinstance(widget, QComboBox) and widget.isEditable():
                current_text = widget.currentText()
                if current_text and widget.findText(current_text) == -1:
                    try:
                        self.db.save_category(category, current_text)
                        widget.addItem(current_text)
                    except Exception as e:
                        print("Error saving category:", e)

    # ── State accessors used by the main window ────────────────────────────

    def title(self) -> str:
        return self.inputs['عنوان کتاب'].text().strip()

    def tiraj(self) -> int:
        return self.inputs['تیراژ'].value()

    def royalty_pct(self) -> float:
        return self.royalty_input.value()

    def cost_values(self) -> dict:
        return {name: spin.value() for name, spin in self.cost_inputs.items()}

    def set_cost_value(self, field: str, value: float):
        if field in self.cost_inputs:
            self.cost_inputs[field].setValue(value)

    def type_selections(self) -> list:
        """[(category, current text)] for all non-empty dynamic type combos."""
        items = []
        for category in DYNAMIC_TYPE_CATEGORIES:
            text = self.inputs[category].currentText().strip()
            if text:
                items.append((category, text))
        return items

    def report_basic_info(self) -> list:
        rows = []
        for key in ['عنوان کتاب', 'زیر عنوان کتاب', 'تاریخ', 'قطع']:
            widget = self.inputs[key]
            val = widget.currentText() if isinstance(widget, QComboBox) else widget.text()
            rows.append((key, val))
        return rows

    def report_features(self) -> list:
        return [(key, self.inputs[key].currentText()) for key in DYNAMIC_TYPE_CATEGORIES]

    def report_print_specs(self) -> list:
        """[(label, value)] snapshot of the pre-press setup for the PDF report."""
        yes_no = lambda checked: "بله" if checked else "خیر"
        specs = [
            ("تعداد صفحات کتاب", f"{self.total_pages_spin.value():,}"),
            ("اندازه کاغذ چاپ", self.paper_size_combo.currentText()),
            ("تعداد فرم متن", f"{self.form_matn_spin.value():,}"),
            ("چاپ دورو متن", yes_no(self.double_sided_matn_chk.isChecked())),
            ("تعداد رنگ متن", self.color_matn_combo.currentText()),
            ("ابعاد زینک متن", self.zinc_size_matn_combo.currentText()),
            ("تعداد فرم جلد", f"{self.form_jeld_spin.value():,}"),
            ("چاپ دورو جلد", yes_no(self.double_sided_jeld_chk.isChecked())),
            ("تعداد رنگ جلد", self.color_jeld_combo.currentText()),
            ("ابعاد زینک جلد", self.zinc_size_jeld_combo.currentText()),
            ("ضایعات کاغذ", f"{self.waste_percent_spin.value():g} ٪"),
            ("قیمت واحد کاغذ متن", f"{self.unit_price_paper_matn_spin.value():,.0f} تومان"),
            ("قیمت واحد کاغذ جلد", f"{self.unit_price_paper_jeld_spin.value():,.0f} تومان"),
        ]
        if self.book_dims_row_widget.isVisible():
            specs.insert(1, ("ابعاد کتاب",
                             f"{self.book_width_spin.value():g}×{self.book_height_spin.value():g} cm"))
        if self.orientation_label.text():
            specs.insert(2, ("جهت بهینه", self.orientation_label.text()))
        return specs

    # ── Persistence mapping ────────────────────────────────────────────────

    def collect_project(self) -> dict:
        """Row for the ``projects`` table (totals are added by the main window)."""
        return {
            'title': self.title(),
            'subtitle': self.inputs['زیر عنوان کتاب'].text(),
            'creation_date': self.inputs['تاریخ'].text(),
            'qate': self.inputs['قطع'].currentText(),
            'tiraj': self.tiraj(),
            'royalty_percent': self.royalty_pct(),
        }

    def collect_details(self) -> dict:
        """Row for ``project_details`` (pricing tab columns added by the main window)."""
        color_counts = {0: 1, 1: 2, 2: 4}
        d = {
            'form_matn': self.form_matn_spin.value(),
            'is_double_sided_matn': int(self.double_sided_matn_chk.isChecked()),
            'color_count_matn': color_counts.get(self.color_matn_combo.currentIndex(), 4),
            'zinc_size_matn': self.zinc_size_matn_combo.currentText(),
            'form_jeld': self.form_jeld_spin.value(),
            'is_double_sided_jeld': int(self.double_sided_jeld_chk.isChecked()),
            'color_count_jeld': color_counts.get(self.color_jeld_combo.currentIndex(), 4),
            'zinc_size_jeld': self.zinc_size_jeld_combo.currentText(),
            'unit_price_paper_matn': self.unit_price_paper_matn_spin.value(),
            'unit_price_paper_jeld': self.unit_price_paper_jeld_spin.value(),
            'unit_price_zinc': 0,
            'waste_percent': self.waste_percent_spin.value(),
            'book_width': self.book_width_spin.value() if self.book_dims_row_widget.isVisible() else None,
            'book_height': self.book_height_spin.value() if self.book_dims_row_widget.isVisible() else None,
            'paper_size': self.paper_size_combo.currentText().replace('×', 'x'),
            'orientation': self.orientation_label.text() or None,
            'pages_per_sheet': self.form_matn_spin.value(),
            'total_pages': self.total_pages_spin.value(),
            'book_type_preset': self.book_type_combo.currentText(),
        }
        for category, col in TYPE_FIELD_COLUMNS.items():
            d[col] = self.inputs[category].currentText()
        for field, col in COST_FIELD_COLUMNS.items():
            d[col] = self.cost_inputs[field].value()
        return d

    def populate(self, project, details):
        """Fills the form from a projects row + optional project_details row."""
        self.inputs['عنوان کتاب'].setText(project['title'])
        self.inputs['زیر عنوان کتاب'].setText(project['subtitle'] if project['subtitle'] else '')
        self.inputs['تاریخ'].setText(project['creation_date'])
        self.inputs['قطع'].setCurrentText(project['qate'] if project['qate'] else '')
        self.inputs['تیراژ'].setValue(project['tiraj'])
        self.royalty_input.setValue(project['royalty_percent'])

        if not details:
            return
        details = dict(details)

        for category, col in TYPE_FIELD_COLUMNS.items():
            if details.get(col):
                self.inputs[category].setCurrentText(details[col])

        color_indices = {1: 0, 2: 1, 4: 2}
        if details.get('form_matn') is not None:
            self.form_matn_spin.setValue(details['form_matn'])
        if details.get('is_double_sided_matn') is not None:
            self.double_sided_matn_chk.setChecked(bool(details['is_double_sided_matn']))
        if details.get('color_count_matn') is not None:
            self.color_matn_combo.setCurrentIndex(color_indices.get(details['color_count_matn'], 2))
        if details.get('zinc_size_matn'):
            self.zinc_size_matn_combo.setCurrentText(details['zinc_size_matn'])
        if details.get('unit_price_paper_matn') is not None:
            self.unit_price_paper_matn_spin.setValue(details['unit_price_paper_matn'])

        if details.get('form_jeld') is not None:
            self.form_jeld_spin.setValue(details['form_jeld'])
        if details.get('is_double_sided_jeld') is not None:
            self.double_sided_jeld_chk.setChecked(bool(details['is_double_sided_jeld']))
        if details.get('color_count_jeld') is not None:
            self.color_jeld_combo.setCurrentIndex(color_indices.get(details['color_count_jeld'], 2))
        if details.get('zinc_size_jeld'):
            self.zinc_size_jeld_combo.setCurrentText(details['zinc_size_jeld'])
        if details.get('unit_price_paper_jeld') is not None:
            self.unit_price_paper_jeld_spin.setValue(details['unit_price_paper_jeld'])

        if details.get('waste_percent') is not None:
            self.waste_percent_spin.setValue(float(details['waste_percent']))
        else:
            self.waste_percent_spin.setValue(5.0)

        if details.get('total_pages') is not None:
            self.total_pages_spin.setValue(details['total_pages'] or 0)

        if details.get('book_width') is not None:
            self.book_width_spin.setValue(float(details['book_width']))
        if details.get('book_height') is not None:
            self.book_height_spin.setValue(float(details['book_height']))
        if details.get('paper_size'):
            self.paper_size_combo.setCurrentText(details['paper_size'].replace("x", "×"))

        for field, col in COST_FIELD_COLUMNS.items():
            if details.get(col) is not None:
                self.cost_inputs[field].setValue(float(details[col]))

        # Restore preset — block signals to avoid zeroing loaded values
        preset = details.get('book_type_preset') or 'شومیز ساده'
        self.book_type_combo.blockSignals(True)
        self.book_type_combo.setCurrentText(preset)
        self.book_type_combo.blockSignals(False)
        self._apply_preset(preset, zero_hidden=False)

    def reset(self):
        """Clears the form for a new project."""
        self.inputs['عنوان کتاب'].clear()
        self.inputs['زیر عنوان کتاب'].clear()
        self.inputs['تاریخ'].setText(jdatetime.date.today().strftime("%Y/%m/%d"))
        self.inputs['قطع'].setCurrentIndex(0)
        self.inputs['تیراژ'].setValue(0)

        for key, widget in self.inputs.items():
            if isinstance(widget, QComboBox) and key != 'قطع':
                widget.setCurrentIndex(-1)

        self.form_matn_spin.setValue(0)
        self.double_sided_matn_chk.setChecked(True)
        self.color_matn_combo.setCurrentIndex(0)
        self.zinc_size_matn_combo.setCurrentIndex(0)
        self.unit_price_paper_matn_spin.setValue(0.0)
        self.form_jeld_spin.setValue(0)
        self.double_sided_jeld_chk.setChecked(False)
        self.color_jeld_combo.setCurrentIndex(2)
        self.zinc_size_jeld_combo.setCurrentIndex(0)
        self.unit_price_paper_jeld_spin.setValue(0.0)
        self.waste_percent_spin.setValue(5.0)
        self.book_width_spin.setValue(self.book_width_spin.minimum())
        self.book_height_spin.setValue(self.book_height_spin.minimum())
        self.paper_size_combo.setCurrentIndex(0)
        self.orientation_label.setText("")
        self.total_pages_spin.setValue(0)

        for spin in self.cost_inputs.values():
            spin.setValue(0.0)

        self.royalty_input.setValue(0.0)

        self.book_type_combo.blockSignals(True)
        self.book_type_combo.setCurrentText("شومیز ساده")
        self.book_type_combo.blockSignals(False)
        self._apply_preset("شومیز ساده", zero_hidden=False)
