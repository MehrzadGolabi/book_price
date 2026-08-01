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
from bookcost.core.cost_model import (
    CALC_TYPE_ORDER, CALC_TYPE_LABELS, CalcType, CostContext, CostLine, resolve_total,
)
from bookcost.core.fields import (
    AUTO_COST_FIELDS, COST_FIELD_COLUMNS, DYNAMIC_TYPE_CATEGORIES,
    TYPE_FIELD_COLUMNS, default_calc_type,
)
from bookcost.ui.dialogs.defaults_dialog import DefaultsDialog
from bookcost.ui.dialogs.paper_price_dialog import PaperPriceDialog
from bookcost.ui.widgets.custom_cost_widget import CustomCostWidget
from bookcost.ui.widgets.paper_list_widget import PaperListWidget
from bookcost.ui.widgets.print_layout_widget import PrintLayoutWidget
from bookcost.ui.widgets.volumes_widget import VolumesWidget

# Type categories shown as free-text combos in section 1. Paper and zinc types
# are chosen in the merged smart paper/zinc section instead (their
# project_details columns are derived from that section at collect time), so
# only the print/color categories remain here.
VISIBLE_TYPE_CATEGORIES = ['نوع چاپ متن', 'نوع رنگ متن', 'نوع چاپ جلد', 'نوع رنگ جلد']

# Visualizer toggle button — filled = showing (default), outline = hidden
_VISUALIZER_ON_QSS = (
    "QPushButton { background-color: #1e293b; color: #f8fafc; padding: 6px 14px;"
    " border-radius: 6px; font-weight: 600; }"
    "QPushButton:hover { background-color: #334155; }"
)
_VISUALIZER_OFF_QSS = (
    "QPushButton { background-color: transparent; color: #1d4ed8; padding: 6px 14px;"
    " border: 1px solid #1d4ed8; border-radius: 6px; font-weight: 600; }"
    "QPushButton:hover { background-color: #eff6ff; }"
)


class DetailsTab(QWidget):
    calculate_requested = Signal()

    def __init__(self, db, calculator: CostCalculator, parent=None):
        super().__init__(parent)
        self.db = db
        self.calculator = calculator
        self.inputs = {}
        self.cost_inputs = {}
        self.cost_input_rows = {}
        self.cost_row_labels = {}
        self.cost_calc_combos = {}   # field name → calc-type combo (item 6)
        self.cost_group_boxes = {}
        self._build_ui()
        self._connect_signals()
        self.refresh_zinc_price_labels()
        self._update_zinc_size_labels()
        self._on_qate_changed()
        self._refresh_layout_widget()
        self._update_paper_readouts()
        self._update_running_subtotal()
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
        self.cost_row_labels[field_name] = label
        spin = QDoubleSpinBox()
        spin.setMaximum(9_999_999_999.99)
        spin.setGroupSeparatorShown(True)
        spin.setDecimals(0)
        spin.lineEdit().setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        layout.addWidget(spin)
        if readonly:
            spin.setReadOnly(True)
            spin.setProperty("autoField", True)   # green "computed" tint via QSS
            spin.setToolTip("این مقدار به‌صورت خودکار محاسبه می‌شود (هزینه کل).")
        else:
            spin.valueChanged.connect(self._on_cost_line_changed)
            # Per-field calculation type (item 6)
            calc_combo = QComboBox()
            for ct in CALC_TYPE_ORDER:
                calc_combo.addItem(CALC_TYPE_LABELS[ct], ct.value)
            idx = calc_combo.findData(default_calc_type(field_name))
            calc_combo.setCurrentIndex(max(0, idx))
            calc_combo.setToolTip("نحوهٔ محاسبهٔ این هزینه در جمع کل.")
            calc_combo.currentIndexChanged.connect(self._on_cost_line_changed)
            self.cost_calc_combos[field_name] = calc_combo
            layout.addWidget(calc_combo)
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

        # ── Multi-volume project (all volumes in one project) ─────────────
        self.series_chk = QCheckBox("پروژهٔ چند جلدی (همهٔ جلدها با هم محاسبه می‌شوند)")
        form_layout.addRow("", self.series_chk)

        series_widget = QWidget()
        series_layout = QVBoxLayout(series_widget)
        series_layout.setContentsMargins(16, 0, 0, 0)
        name_row = QHBoxLayout()
        name_row.setContentsMargins(0, 0, 0, 0)
        name_row.addWidget(QLabel("نام سری:"))
        self.series_name_input = QLineEdit()
        self.series_name_input.setPlaceholderText("نام سری (مثلاً: دانشنامه کودک)")
        name_row.addWidget(self.series_name_input, 1)
        series_layout.addLayout(name_row)
        self.volumes_widget = VolumesWidget(forms_estimator=self._estimate_volume_forms)
        series_layout.addWidget(self.volumes_widget)
        series_hint = QLabel(
            "همهٔ جلدها با هم چاپ و محاسبه می‌شوند. تعداد کل فرم‌ها و کاغذ از مجموع "
            "جلدها به‌دست می‌آید؛ هزینه‌ها را می‌توانید «ثابت (کل پروژه)» یا «به ازای هر جلد» بگیرید."
        )
        series_hint.setWordWrap(True)
        series_hint.setStyleSheet("color: #b45309; font-size: 12px;")
        series_layout.addWidget(series_hint)
        self.series_widget = series_widget
        self.series_widget.setVisible(False)
        form_layout.addRow(self.series_widget)

        form_layout.addRow("تیراژ:", self.inputs['تیراژ'])
        form_layout.addRow("قطع کتاب:", self.inputs['قطع'])
        form_layout.addRow("", self.lbl_optimal_paper)
        form_layout.addRow("تعداد صفحات کتاب:", self.total_pages_spin)

        # ── Paper size selector (always visible) ──────────────────────────
        self.paper_size_combo = QComboBox()
        self.paper_size_combo.addItems(["70×100", "60×90", "50×70"])
        form_layout.addRow("اندازه کاغذ خریداری:", self.paper_size_combo)

        # Cut-in-half toggle + actual press size (item 8)
        cut_row = QWidget()
        cut_row_layout = QHBoxLayout(cut_row)
        cut_row_layout.setContentsMargins(0, 0, 0, 0)
        self.cut_half_chk = QCheckBox("کاغذ نصف می‌شود (برش)")
        self.cut_half_chk.setToolTip(
            "کاغذ خریداری‌شده پیش از چاپ نصف می‌شود (مثلاً ۱۰۰×۷۰ به ۵۰×۷۰)؛ "
            "در نتیجه از هر ورق خریداری دو ورق چاپی به‌دست می‌آید.")
        self.lbl_actual_print_size = QLabel("—")
        self.lbl_actual_print_size.setStyleSheet("color: #1d4ed8; font-weight: bold;")
        cut_row_layout.addWidget(self.cut_half_chk)
        cut_row_layout.addStretch()
        cut_row_layout.addWidget(QLabel("اندازه واقعی چاپ:"))
        cut_row_layout.addWidget(self.lbl_actual_print_size)
        form_layout.addRow("", cut_row)

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
        self._form_layout = form_layout   # for setRowVisible (hides label+field)

        # ── Orientation result label ──────────────────────────────────────
        self.orientation_label = QLabel("")
        self.orientation_label.setWordWrap(True)
        self.orientation_label.setStyleSheet("color: #1d4ed8;")
        form_layout.addRow("جهت بهینه:", self.orientation_label)

        # ── Dynamic type categories (print/color only) ────────────────────
        # Paper (نوع کاغذ متن/جلد) and zinc (نوع زینک متن/جلد) types were here
        # too but duplicated the smart paper/zinc section and didn't affect
        # totals; they're removed and derived from that section instead.
        for dtype in VISIBLE_TYPE_CATEGORIES:
            combo = QComboBox()
            combo.setEditable(True)
            combo.setInsertPolicy(QComboBox.InsertAtBottom)
            try:
                combo.addItems(self.db.get_categories(dtype))
            except Exception as e:
                print("Error pre-fetching categories:", e)
            combo.setCurrentIndex(-1)
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

        # ── Custom cost lines + subfields (item 11) ───────────────────────
        grp_custom = QGroupBox("⑥ هزینه‌های سفارشی و زیرمجموعه‌ها")
        grp_custom_layout = QVBoxLayout(grp_custom)
        self.custom_cost_widget = CustomCostWidget(
            parent_options_provider=self._builtin_field_names)
        self.custom_cost_widget.changed.connect(self._on_cost_line_changed)
        grp_custom_layout.addWidget(self.custom_cost_widget)
        form_layout.addRow(grp_custom)
        self.cost_group_boxes["هزینه‌های سفارشی"] = grp_custom

        self.royalty_input = QDoubleSpinBox()
        self.royalty_input.setSuffix(" ٪")
        self.royalty_input.setMaximum(100.0)
        self.royalty_input.setDecimals(0)
        form_layout.addRow("حق تالیف درصدی:", self.royalty_input)

        self.tarjomeh_input = QDoubleSpinBox()
        self.tarjomeh_input.setSuffix(" ٪")
        self.tarjomeh_input.setMaximum(100.0)
        self.tarjomeh_input.setDecimals(0)
        self.tarjomeh_input.setToolTip(
            "هزینه ترجمه به‌صورت درصدی از جمع هزینه‌ها — مانند حق تالیف درصدی. "
            "اگر مبلغ ثابت ترجمه را در «هزینه ترجمه» وارد کرده‌اید این را صفر بگذارید.")
        form_layout.addRow("حق ترجمه درصدی:", self.tarjomeh_input)

        calc_btn = QPushButton("ثبت اطلاعات و انجام محاسبات نهایی")
        calc_btn.setStyleSheet("padding: 10px; font-weight: bold; background-color: #27ae60; color: white;")
        calc_btn.clicked.connect(lambda *_: self.calculate_requested.emit())

        scroll_layout.addLayout(form_layout)
        scroll_layout.addWidget(calc_btn)
        scroll_area.setWidget(scroll_content)

        # Sticky running subtotal — always visible below the scrolling form
        self.lbl_running_total = QLabel("جمع هزینه‌ها: ۰ تومان")
        self.lbl_running_total.setLayoutDirection(Qt.RightToLeft)
        self.lbl_running_total.setAlignment(Qt.AlignCenter)
        self.lbl_running_total.setStyleSheet(
            "background-color: #1e293b; color: #ffffff; font-weight: bold;"
            "font-size: 15px; padding: 10px; border-top: 2px solid #2563eb;")

        # Toggle for the print-layout visualizer — kept outside the scroll
        # area so it's always reachable, not buried after scrolling down.
        toggle_row = QHBoxLayout()
        toggle_row.setContentsMargins(8, 6, 8, 6)
        self.toggle_visualizer_btn = QPushButton("🖼 پنهان‌کردن نمایشگر")
        self.toggle_visualizer_btn.setCheckable(True)
        self.toggle_visualizer_btn.setChecked(True)
        self.toggle_visualizer_btn.setStyleSheet(_VISUALIZER_ON_QSS)
        self.toggle_visualizer_btn.setToolTip(
            "نمایشگر ابعاد و صفحه‌آرایی را پنهان یا نمایان می‌کند؛ با پنهان کردن آن "
            "بخش محاسبات کل عرض صفحه را در اختیار می‌گیرد.")
        self.toggle_visualizer_btn.toggled.connect(self._on_toggle_visualizer)
        toggle_row.addWidget(self.toggle_visualizer_btn)
        toggle_row.addStretch()

        left_col = QVBoxLayout()
        left_col.setContentsMargins(0, 0, 0, 0)
        left_col.setSpacing(0)
        left_col.addLayout(toggle_row)
        left_col.addWidget(scroll_area)
        left_col.addWidget(self.lbl_running_total)

        self.layout_widget = PrintLayoutWidget()
        self.layout_widget.setFixedWidth(320)

        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        self.setLayoutDirection(Qt.LeftToRight)
        outer_layout.addLayout(left_col)
        outer_layout.addWidget(self.layout_widget)

    def _on_toggle_visualizer(self, checked: bool):
        self.layout_widget.setVisible(checked)
        self.toggle_visualizer_btn.setText(
            "🖼 پنهان‌کردن نمایشگر" if checked else "🖼 نمایش نمایشگر")
        self.toggle_visualizer_btn.setStyleSheet(
            _VISUALIZER_ON_QSS if checked else _VISUALIZER_OFF_QSS)

    def _build_precalc_group(self) -> QGroupBox:
        self.calc_group = QGroupBox("② پیش از چاپ — محاسبات هوشمند کاغذ و زینک")
        calc_layout = QFormLayout()
        self._precalc_layout = calc_layout
        defaults_btn = QPushButton("🏷 مدیریت قیمت‌های پایه و زینک‌ها...")
        defaults_btn.setStyleSheet("padding: 3px 8px; color: #2a6496; background: transparent; border: 1px solid #2a6496; border-radius: 4px;")
        defaults_btn.clicked.connect(self.open_defaults_dialog)
        calc_layout.addRow("", defaults_btn)

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
        self.unit_price_paper_matn_spin.setToolTip(
            "قیمت هر ورق کاغذ متن (از پنجره محاسبه درج می‌شود، ولی همیشه قابل ویرایش و بازنویسی دستی است).")

        self.form_matn_spin.setToolTip(
            "به‌صورت خودکار پیشنهاد می‌شود اما همیشه قابل ویرایش است.")
        calc_layout.addRow("تعداد فرم متن (خودکار — قابل ویرایش):", self.form_matn_spin)
        calc_layout.addRow("", self.double_sided_matn_chk)
        calc_layout.addRow("تعداد رنگ متن:", self.color_matn_combo)
        zinc_matn_row = QWidget()
        zinc_matn_layout = QHBoxLayout(zinc_matn_row)
        zinc_matn_layout.setContentsMargins(0, 0, 0, 0)
        zinc_matn_layout.addWidget(self.zinc_size_matn_combo, 1)
        self.lbl_zinc_matn_size = QLabel("—")
        self.lbl_zinc_matn_size.setStyleSheet("color: #475569;")
        zinc_matn_layout.addWidget(self.lbl_zinc_matn_size)
        calc_layout.addRow("ابعاد زینک متن:", zinc_matn_row)
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
        self._matn_price_row = matn_price_row
        calc_layout.addRow("قیمت واحد هر ورق کاغذ متن:", matn_price_row)

        self.papers_matn_list = PaperListWidget(
            "نوع کاغذ متن (مثلاً تحریر ۸۰)",
            items_provider=lambda: self._paper_combo_items('نوع کاغذ متن'),
            price_lookup=self.db.get_latest_paper_price,
            dims_lookup=self.db.get_paper_dims,
            default_forms=self.form_matn_spin.value,
            default_price=self.unit_price_paper_matn_spin.value,
            calc_callback=lambda spin: self.open_paper_price_dialog_for_spin("matn", spin),
        )
        calc_layout.addRow("چند نوع کاغذ متن:", self.papers_matn_list)

        # Cover (jeld) setup
        self.form_jeld_spin = QSpinBox()
        self.form_jeld_spin.setMaximum(1000)
        self.form_jeld_spin.setToolTip("همیشه قابل ویرایش است (بازنویسی دستی مجاز).")
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
        self.unit_price_paper_jeld_spin.setToolTip(
            "قیمت هر ورق کاغذ جلد (از پنجره محاسبه درج می‌شود، ولی همیشه قابل ویرایش و بازنویسی دستی است).")

        calc_layout.addRow("تعداد فرم جلد (قابل ویرایش):", self.form_jeld_spin)
        calc_layout.addRow("", self.double_sided_jeld_chk)
        calc_layout.addRow("تعداد رنگ جلد:", self.color_jeld_combo)
        zinc_jeld_row = QWidget()
        zinc_jeld_layout = QHBoxLayout(zinc_jeld_row)
        zinc_jeld_layout.setContentsMargins(0, 0, 0, 0)
        zinc_jeld_layout.addWidget(self.zinc_size_jeld_combo, 1)
        self.lbl_zinc_jeld_size = QLabel("—")
        self.lbl_zinc_jeld_size.setStyleSheet("color: #475569;")
        zinc_jeld_layout.addWidget(self.lbl_zinc_jeld_size)
        calc_layout.addRow("ابعاد زینک جلد:", zinc_jeld_row)
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
        self._jeld_price_row = jeld_price_row
        calc_layout.addRow("قیمت واحد هر ورق کاغذ جلد:", jeld_price_row)

        self.papers_jeld_list = PaperListWidget(
            "نوع کاغذ جلد (مثلاً گلاسه ۱۳۵)",
            items_provider=lambda: self._paper_combo_items('نوع کاغذ جلد'),
            price_lookup=self.db.get_latest_paper_price,
            dims_lookup=self.db.get_paper_dims,
            default_forms=self.form_jeld_spin.value,
            default_price=self.unit_price_paper_jeld_spin.value,
            calc_callback=lambda spin: self.open_paper_price_dialog_for_spin("jeld", spin),
        )
        calc_layout.addRow("چند نوع کاغذ جلد:", self.papers_jeld_list)

        self.waste_percent_spin = QDoubleSpinBox()
        self.waste_percent_spin.setRange(0, 50)
        self.waste_percent_spin.setDecimals(1)
        self.waste_percent_spin.setValue(5.0)
        self.waste_percent_spin.setSuffix(" ٪")
        calc_layout.addRow("ضایعات کاغذ:", self.waste_percent_spin)

        # Total paper usage readout (item 12)
        self.lbl_paper_usage = QLabel("—")
        self.lbl_paper_usage.setWordWrap(True)
        self.lbl_paper_usage.setStyleSheet(
            "color: #0f172a; background:#eff6ff; border:1px solid #bfdbfe;"
            "border-radius:6px; padding:8px; font-weight:bold;")
        calc_layout.addRow("مصرف کاغذ پروژه:", self.lbl_paper_usage)

        self.calc_group.setLayout(calc_layout)
        return self.calc_group

    def _connect_signals(self):
        self.inputs['قطع'].currentIndexChanged.connect(self._on_qate_changed)
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
        self.series_chk.toggled.connect(self._on_series_toggled)
        self.volumes_widget.changed.connect(self._on_volumes_changed)
        self.papers_matn_list.changed.connect(self._on_papers_changed)
        self.papers_jeld_list.changed.connect(self._on_papers_changed)
        self.color_matn_combo.currentIndexChanged.connect(self.auto_calculate_costs)
        self.color_jeld_combo.currentIndexChanged.connect(self.auto_calculate_costs)
        self.zinc_size_matn_combo.currentIndexChanged.connect(self.refresh_zinc_price_labels)
        self.zinc_size_matn_combo.currentIndexChanged.connect(self._update_zinc_size_labels)
        self.zinc_size_matn_combo.currentIndexChanged.connect(self.auto_calculate_costs)
        self.zinc_size_jeld_combo.currentIndexChanged.connect(self.refresh_zinc_price_labels)
        self.zinc_size_jeld_combo.currentIndexChanged.connect(self._update_zinc_size_labels)
        self.zinc_size_jeld_combo.currentIndexChanged.connect(self.auto_calculate_costs)
        self.cut_half_chk.toggled.connect(self._update_paper_readouts)
        self.cut_half_chk.toggled.connect(self._refresh_layout_widget)
        self.paper_size_combo.currentIndexChanged.connect(self._update_paper_readouts)
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
        self.form_matn_spin.valueChanged.connect(self._refresh_layout_widget)
        self.form_jeld_spin.valueChanged.connect(self._refresh_layout_widget)
        self.papers_matn_list.changed.connect(self._refresh_layout_widget)
        self.papers_jeld_list.changed.connect(self._refresh_layout_widget)

    # ── Live behaviors ─────────────────────────────────────────────────────

    def _paper_combo_items(self, category: str) -> list:
        """Type-category values plus saved paper-library names, deduplicated."""
        items = []
        try:
            items.extend(self.db.get_categories(category))
            for name in self.db.get_paper_type_names():
                if name not in items:
                    items.append(name)
        except Exception as e:
            print("Error loading paper combo items:", e)
        return items

    def autofill_paper_prices(self) -> int:
        """Fills all multi-paper rows from the paper library; returns count."""
        return (self.papers_matn_list.autofill_prices()
                + self.papers_jeld_list.autofill_prices())

    def _set_aggregate_readonly(self, ro: bool):
        """In multi-volume mode the page/form totals are derived from the
        volume rows, so lock the aggregate spinboxes and hide the per-book
        optimal-paper hint (the per-volume rows drive it)."""
        for spin in (self.total_pages_spin, self.form_matn_spin, self.form_jeld_spin):
            spin.setReadOnly(ro)
            spin.setProperty("autoField", ro)
            spin.style().unpolish(spin)
            spin.style().polish(spin)
        tip = "در حالت چند جلدی از مجموع جلدها محاسبه می‌شود."
        self.total_pages_spin.setToolTip(tip if ro else "")
        self.form_matn_spin.setToolTip(
            tip if ro else "به‌صورت خودکار پیشنهاد می‌شود اما همیشه قابل ویرایش است.")
        self.form_jeld_spin.setToolTip(tip if ro else "همیشه قابل ویرایش است (بازنویسی دستی مجاز).")
        self._form_layout.setRowVisible(self.lbl_optimal_paper, not ro)

    def _on_series_toggled(self, checked: bool):
        self.series_widget.setVisible(checked)
        self._set_aggregate_readonly(checked)
        label = self.cost_row_labels.get('هزینه چاپ جلد')
        if label:
            label.setText("هزینه چاپ جلد (کل سری):" if checked else "هزینه چاپ جلد:")
        if checked and not self.volumes_widget.entries():
            self.volumes_widget.add_row(pages=self.total_pages_spin.value(),
                                        forms_matn=self.form_matn_spin.value(),
                                        forms_jeld=self.form_jeld_spin.value() or 1)
        self._on_volumes_changed()

    def _estimate_volume_forms(self, pages: int):
        """(forms_matn, forms_jeld) suggested for a volume with `pages` pages,
        using the current qate/paper layout. Cover defaults to 1 form."""
        layout = self.calculator.suggest_layout(
            self.inputs['قطع'].currentText(), pages,
            book_w=self.book_width_spin.value(), book_h=self.book_height_spin.value(),
            paper_size_str=self.paper_size_combo.currentText().replace('×', 'x'))
        if not layout or pages <= 0:
            return None
        mult = 2 if self.double_sided_matn_chk.isChecked() else 1
        return (layout['sheets_per_book'] * mult, 1)

    def _on_volumes_changed(self):
        """Sync the aggregate page/form spinboxes to the volume sums so the
        shared paper/zinc machinery keeps working, then recompute."""
        if self.series_chk.isChecked():
            t = self.volumes_widget.totals()
            for spin, val in ((self.total_pages_spin, t['pages']),
                              (self.form_matn_spin, t['forms_matn']),
                              (self.form_jeld_spin, t['forms_jeld'])):
                spin.blockSignals(True)
                spin.setValue(int(val))
                spin.blockSignals(False)
        self.auto_calculate_costs()

    def _on_papers_changed(self):
        """Multi-paper mode drives the unit-price fields from the list, but form
        counts always stay editable (item 5) — they're synced to the list total
        so the displayed value is right, yet the user can override afterward."""
        matn_multi = bool(self.papers_matn_list.entries())
        jeld_multi = bool(self.papers_jeld_list.entries())
        # When a section uses the multi-paper list, the single unit-price row is
        # redundant — hide it (label + field + محاسبه) instead of leaving a
        # greyed dead control.
        self._precalc_layout.setRowVisible(self._matn_price_row, not matn_multi)
        self._precalc_layout.setRowVisible(self._jeld_price_row, not jeld_multi)

        # Sync form spinboxes to the multi-paper totals (still editable)
        if matn_multi:
            total = sum(e['form_count'] for e in self.papers_matn_list.entries())
            self.form_matn_spin.blockSignals(True)
            self.form_matn_spin.setValue(int(total))
            self.form_matn_spin.blockSignals(False)
        if jeld_multi:
            total = sum(e['form_count'] for e in self.papers_jeld_list.entries())
            self.form_jeld_spin.blockSignals(True)
            self.form_jeld_spin.setValue(int(total))
            self.form_jeld_spin.blockSignals(False)
        self.auto_calculate_costs()

    def _update_zinc_size_labels(self):
        self.lbl_zinc_matn_size.setText(
            self.calculator.zinc_size_label(self.zinc_size_matn_combo.currentText()) or '—')
        self.lbl_zinc_jeld_size.setText(
            self.calculator.zinc_size_label(self.zinc_size_jeld_combo.currentText()) or '—')

    def _update_paper_readouts(self):
        """Actual print size (item 8) + total bought-paper usage (item 12)."""
        cut = self.cut_half_chk.isChecked()
        self.lbl_actual_print_size.setText(
            self.calculator.actual_print_size(self.paper_size_combo.currentText(), cut))

        tiraj = self.inputs['تیراژ'].value()
        waste = self.waste_percent_spin.value()
        # Total bought sheets depends on the TOTAL print forms (which track the
        # page count and volumes), not on how the paper types split them. The
        # form spinboxes already hold the project-wide totals — in multi-volume
        # mode they're the sum across volumes, so no extra ×volumes factor.
        form_matn = self.form_matn_spin.value()
        form_jeld = self.form_jeld_spin.value()
        sides_matn = 2 if self.double_sided_matn_chk.isChecked() else 1
        sides_jeld = 2 if self.double_sided_jeld_chk.isChecked() else 1

        bought_matn = self.calculator.bought_paper_count(form_matn, sides_matn, tiraj, waste, cut)
        bought_jeld = self.calculator.bought_paper_count(form_jeld, sides_jeld, tiraj, waste, cut)
        total = bought_matn + bought_jeld
        if tiraj <= 0 or (form_matn <= 0 and form_jeld <= 0):
            self.lbl_paper_usage.setText("برای محاسبه، تیراژ و تعداد فرم را وارد کنید.")
            return
        cut_note = " (با احتساب برش به نصف)" if cut else ""
        self.lbl_paper_usage.setText(
            f"کل کاغذ خریداری: {total:,.0f} برگ{cut_note}  —  "
            f"متن: {bought_matn:,.0f} برگ · جلد: {bought_jeld:,.0f} برگ")

    def series_info(self) -> dict:
        """{'series_name', 'volume_no', 'series_volumes'} — Nones when off.
        series_volumes is the number of volume rows in multi-volume mode."""
        if not self.series_chk.isChecked():
            return {'series_name': None, 'volume_no': None, 'series_volumes': 1}
        return {
            'series_name': self.series_name_input.text().strip() or None,
            'volume_no': None,
            'series_volumes': self.series_volumes(),
        }

    def series_volumes(self) -> int:
        if not self.series_chk.isChecked():
            return 1
        return max(1, self.volumes_widget.totals()['count'])

    def volumes(self) -> list:
        """Per-volume rows for persistence (empty for single-volume projects)."""
        return self.volumes_widget.entries() if self.series_chk.isChecked() else []

    def set_volumes(self, rows: list):
        self.volumes_widget.set_entries(rows or [])

    def _builtin_field_names(self) -> list:
        """Built-in cost field names offered as parents for subfields."""
        return [f for fields in CostCalculator.COST_GROUPS.values() for f in fields]

    def _on_cost_line_changed(self, *args):
        """A cost amount, calc-type combo, or custom line changed — refresh the
        live running subtotal. The final total (with percentages) is still
        computed on the calculate button."""
        self._update_running_subtotal()

    def _update_running_subtotal(self):
        ctx = CostContext(tiraj=self.tiraj(), total_forms=self.total_forms(),
                          volume_count=self.series_volumes())
        lines = [
            CostLine(key=d['field_key'], display_name=d['display_name'],
                     amount=d['amount'], calc_type=CalcType.coerce(d['calc_type']),
                     parent_key=d['parent_key'], is_custom=bool(d['is_custom']))
            for d in self.build_cost_lines()
        ]
        base = resolve_total(lines, ctx)
        self.lbl_running_total.setText(f"جمع هزینه‌ها (پیش از درصدها): {base:,.0f} تومان")

    def total_forms(self) -> int:
        """Total print forms across the project (text + cover) — summed across
        volumes in multi-volume mode, else the two spinboxes."""
        if self.series_chk.isChecked():
            t = self.volumes_widget.totals()
            return int(t['forms_matn'] + t['forms_jeld'])
        return int(self.form_matn_spin.value() + self.form_jeld_spin.value())

    def build_cost_lines(self) -> list:
        """Every cost as a dict for the unified model + persistence:
        {field_key, display_name, parent_key, amount, calc_type, is_custom}."""
        lines = []
        for fields in CostCalculator.COST_GROUPS.values():
            for f in fields:
                spin = self.cost_inputs.get(f)
                if spin is None:
                    continue
                if f in AUTO_COST_FIELDS:
                    calc = 'fixed'
                else:
                    combo = self.cost_calc_combos.get(f)
                    calc = combo.currentData() if combo else default_calc_type(f)
                lines.append({'field_key': f, 'display_name': f, 'parent_key': None,
                              'amount': spin.value(), 'calc_type': calc, 'is_custom': 0})
        for i, e in enumerate(self.custom_cost_widget.entries()):
            lines.append({'field_key': f'custom_{i}', 'display_name': e['display_name'],
                          'parent_key': e['parent_key'], 'amount': e['amount'],
                          'calc_type': e['calc_type'] or 'fixed', 'is_custom': 1})
        return lines

    def populate_cost_lines(self, lines: list):
        """Restore per-field calc types and custom rows from saved cost lines."""
        customs = []
        for l in lines:
            if l.get('is_custom'):
                customs.append(l)
                continue
            combo = self.cost_calc_combos.get(l.get('field_key'))
            if combo:
                idx = combo.findData(l.get('calc_type') or 'fixed')
                if idx >= 0:
                    combo.setCurrentIndex(idx)
        self.custom_cost_widget.set_entries(customs)

    def papers(self) -> list:
        """All multi-paper entries tagged with their section for persistence."""
        out = []
        for e in self.papers_matn_list.entries():
            out.append({**e, 'section': 'matn'})
        for e in self.papers_jeld_list.entries():
            out.append({**e, 'section': 'jeld'})
        return out

    def set_papers(self, rows: list):
        self.papers_matn_list.set_entries([r for r in rows if r.get('section') == 'matn'])
        self.papers_jeld_list.set_entries([r for r in rows if r.get('section') == 'jeld'])

    def refresh_zinc_price_labels(self):
        for label, combo in [
            (self.zinc_price_matn_label, self.zinc_size_matn_combo),
            (self.zinc_price_jeld_label, self.zinc_size_jeld_combo),
        ]:
            price = self.db.get_zinc_price(combo.currentText())
            if price > 0:
                label.setText(f"{price:,.0f} تومان")
                label.setStyleSheet("color: #15803d;")
            else:
                label.setText("⚠ قیمت تنظیم نشده")
                label.setStyleSheet("color: #b91c1c;")

    def auto_calculate_costs(self, *args):
        color_counts = {0: 1, 1: 2, 2: 4}
        papers_matn = self.papers_matn_list.entries()
        papers_jeld = self.papers_jeld_list.entries()
        # Zinc is per printed form: with multi-paper the form total comes
        # from the paper list, otherwise from the single form spinboxes.
        form_matn = (sum(e['form_count'] for e in papers_matn)
                     if papers_matn else self.form_matn_spin.value())
        form_jeld = (sum(e['form_count'] for e in papers_jeld)
                     if papers_jeld else self.form_jeld_spin.value())
        results = self.calculator.compute_auto_costs(
            form_matn=form_matn,
            sides_matn=2 if self.double_sided_matn_chk.isChecked() else 1,
            form_jeld=form_jeld,
            sides_jeld=2 if self.double_sided_jeld_chk.isChecked() else 1,
            tiraj=self.inputs['تیراژ'].value(),
            waste_pct=self.waste_percent_spin.value(),
            unit_price_matn=self.unit_price_paper_matn_spin.value(),
            unit_price_jeld=self.unit_price_paper_jeld_spin.value(),
            text_colors=color_counts.get(self.color_matn_combo.currentIndex(), 4),
            cover_colors=color_counts.get(self.color_jeld_combo.currentIndex(), 4),
            zinc_price_matn=self.db.get_zinc_price(self.zinc_size_matn_combo.currentText()),
            zinc_price_jeld=self.db.get_zinc_price(self.zinc_size_jeld_combo.currentText()),
            papers_matn=papers_matn,
            papers_jeld=papers_jeld,
            series_volumes=self.series_volumes(),
        )
        for field, value in results.items():
            self.cost_inputs[field].setValue(value)
        self._update_paper_readouts()
        self._update_running_subtotal()

    def open_paper_price_dialog_for_spin(self, target: str, price_spin):
        dlg = PaperPriceDialog(self.db, target, current_price=price_spin.value(), parent=self)
        dlg.setAttribute(Qt.WA_DeleteOnClose)
        if dlg.exec() == QDialog.Accepted:
            price_spin.setValue(dlg.result_value)

    def open_paper_price_dialog(self, target: str):
        price_spin = (self.unit_price_paper_matn_spin
                      if target == "matn"
                      else self.unit_price_paper_jeld_spin)
        self.open_paper_price_dialog_for_spin(target, price_spin)

    def open_defaults_dialog(self):
        dlg = DefaultsDialog(self.db, parent=self)
        dlg.exec()
        self.refresh_zinc_price_labels()
        self._update_zinc_size_labels()
        self.auto_calculate_costs()

    def _on_qate_changed(self):
        qate = self.inputs['قطع'].currentText()
        layout = self.calculator.suggest_layout(
            qate, self.total_pages_spin.value(),
            book_w=self.book_width_spin.value(),
            book_h=self.book_height_spin.value(),
            paper_size_str=self.paper_size_combo.currentText().replace('×', 'x'),
        )
        if layout:
            if layout['paper_size']:
                self.paper_size_combo.setCurrentText(layout['paper_size'])
            if layout['zinc']:
                self.zinc_size_matn_combo.setCurrentText(layout['zinc'])
        self.suggest_optimal_layout()

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
            self._form_layout.setRowVisible(self.book_dims_row_widget, False)
            self._form_layout.setRowVisible(self.orientation_label, False)
            self.lbl_optimal_paper.setText("کاغذ بهینه: - | ورق مصرفی هر جلد: -")
            return

        self._form_layout.setRowVisible(self.book_dims_row_widget, layout['is_custom'])
        self._form_layout.setRowVisible(self.orientation_label, layout['is_custom'])

        self.orientation_label.setText(layout['orientation_label'] or '')

        if layout['is_custom'] and layout['default_dims'] and layout['default_dims'][0] is not None:
            if self.book_width_spin.value() == self.book_width_spin.minimum():
                self.book_width_spin.setValue(layout['default_dims'][0])
                self.book_height_spin.setValue(layout['default_dims'][1])

        # In multi-volume mode the per-volume rows drive the form totals, so
        # don't overwrite the aggregate here.
        if not self.series_chk.isChecked():
            multiplier = 2 if self.double_sided_matn_chk.isChecked() else 1
            self.form_matn_spin.setValue(layout['sheets_per_book'] * multiplier)
        self.lbl_optimal_paper.setText(
            f"کاغذ بهینه: {layout['paper_size']} | ورق مصرفی هر جلد: {layout['sheets_per_book']}"
        )

    def _refresh_layout_widget(self):
        qate = self.inputs['قطع'].currentText()
        specs = CostCalculator.OPTIMAL_SPECS.get(qate, {})

        cut = self.cut_half_chk.isChecked()
        actual_str = self.calculator.actual_print_size(
            self.paper_size_combo.currentText(), cut)
        paper_w, paper_h = self.calculator.parse_size(actual_str)
        if paper_w <= 0 or paper_h <= 0:
            return

        if specs.get('pages_per_sheet') is None and self.book_dims_row_widget.isVisibleTo(self):
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
            cut_in_half=cut,
            papers_matn=self.papers_matn_list.entries(),
            papers_jeld=self.papers_jeld_list.entries(),
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
            group_fields = CostCalculator.COST_GROUPS.get(group_name)
            if group_fields is None:
                group_box.setVisible(True)   # custom group is always available
                continue
            any_visible = (visible_fields is None) or any(
                f in visible_fields for f in group_fields
            )
            group_box.setVisible(any_visible)

    def reload_categories(self):
        """Re-reads the dynamic type combos from the database (e.g. after a
        restore or an import added new type values)."""
        for dtype in VISIBLE_TYPE_CATEGORIES:
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
        self.papers_matn_list.refresh_items()
        self.papers_jeld_list.refresh_items()

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

    def _derived_type_values(self) -> dict:
        """Paper/zinc type-column values derived from the merged smart section
        (those free-text combos were removed from section 1)."""
        matn_papers = self.papers_matn_list.entries()
        jeld_papers = self.papers_jeld_list.entries()
        return {
            'نوع کاغذ متن': (matn_papers[0]['paper_type'] if matn_papers else ''),
            'نوع کاغذ جلد': (jeld_papers[0]['paper_type'] if jeld_papers else ''),
            'نوع زینک متن': self.zinc_size_matn_combo.currentText(),
            'نوع زینک جلد': self.zinc_size_jeld_combo.currentText(),
        }

    def type_selections(self) -> list:
        """[(category, current text)] for the visible print/color type combos
        (used for default-price matching)."""
        items = []
        for category in VISIBLE_TYPE_CATEGORIES:
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
        info = self.series_info()
        if info['series_name'] or (info['series_volumes'] or 1) > 1:
            rows.append(("سری", f"{info['series_name'] or '—'} — {info['series_volumes']} جلد"))
        return rows

    def report_features(self) -> list:
        rows = [(key, self.inputs[key].currentText()) for key in VISIBLE_TYPE_CATEGORIES]
        derived = self._derived_type_values()
        for key in ('نوع کاغذ متن', 'نوع کاغذ جلد', 'نوع زینک متن', 'نوع زینک جلد'):
            if derived.get(key):
                rows.append((key, derived[key]))
        return rows

    def report_print_specs(self) -> list:
        """[(label, value)] snapshot of the pre-press setup for the PDF report."""
        yes_no = lambda checked: "بله" if checked else "خیر"
        specs = [
            ("تعداد صفحات کتاب", f"{self.total_pages_spin.value():,}"),
            ("اندازه کاغذ خریداری", self.paper_size_combo.currentText()),
            ("اندازه واقعی چاپ",
             self.calculator.actual_print_size(self.paper_size_combo.currentText(),
                                               self.cut_half_chk.isChecked())),
            ("تعداد فرم متن", f"{self.form_matn_spin.value():,}"),
            ("چاپ دورو متن", yes_no(self.double_sided_matn_chk.isChecked())),
            ("تعداد رنگ متن", self.color_matn_combo.currentText()),
            ("ابعاد زینک متن", self.zinc_size_matn_combo.currentText()),
            ("تعداد فرم جلد", f"{self.form_jeld_spin.value():,}"),
            ("چاپ دورو جلد", yes_no(self.double_sided_jeld_chk.isChecked())),
            ("تعداد رنگ جلد", self.color_jeld_combo.currentText()),
            ("ابعاد زینک جلد", self.zinc_size_jeld_combo.currentText()),
            ("ضایعات کاغذ", f"{self.waste_percent_spin.value():g} ٪"),
        ]
        # Paper pricing: either the multi-paper lists or the single prices
        papers_matn = self.papers_matn_list.entries()
        papers_jeld = self.papers_jeld_list.entries()
        if papers_matn:
            for i, e in enumerate(papers_matn, 1):
                name = e['paper_type'] or f"کاغذ {i}"
                specs.append((f"کاغذ متن {i} ({name})",
                              f"{e['form_count']:g} فرم × {e['unit_price']:,.0f} تومان"))
        else:
            specs.append(("قیمت واحد کاغذ متن",
                          f"{self.unit_price_paper_matn_spin.value():,.0f} تومان"))
        if papers_jeld:
            for i, e in enumerate(papers_jeld, 1):
                name = e['paper_type'] or f"کاغذ {i}"
                specs.append((f"کاغذ جلد {i} ({name})",
                              f"{e['form_count']:g} فرم × {e['unit_price']:,.0f} تومان"))
        else:
            specs.append(("قیمت واحد کاغذ جلد",
                          f"{self.unit_price_paper_jeld_spin.value():,.0f} تومان"))
        if self.series_chk.isChecked():
            t = self.volumes_widget.totals()
            specs.append(("پروژهٔ چند جلدی",
                          f"{t['count']} جلد — مجموع {t['pages']:,} صفحه، "
                          f"{t['forms_matn'] + t['forms_jeld']:,} فرم"))
        if self.book_dims_row_widget.isVisibleTo(self):
            specs.insert(1, ("ابعاد کتاب",
                             f"{self.book_width_spin.value():g}×{self.book_height_spin.value():g} cm"))
        if self.orientation_label.text():
            specs.insert(2, ("جهت بهینه", self.orientation_label.text()))
        return specs

    # ── Persistence mapping ────────────────────────────────────────────────

    def tarjomeh_pct(self) -> float:
        return self.tarjomeh_input.value()

    def collect_project(self) -> dict:
        """Row for the ``projects`` table (totals are added by the main window)."""
        return {
            'title': self.title(),
            'subtitle': self.inputs['زیر عنوان کتاب'].text(),
            'creation_date': self.inputs['تاریخ'].text(),
            'qate': self.inputs['قطع'].currentText(),
            'tiraj': self.tiraj(),
            'royalty_percent': self.royalty_pct(),
            **self.series_info(),
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
            # isVisibleTo: true whenever the row is shown for this trim size,
            # regardless of whether the details tab is the current tab
            'book_width': self.book_width_spin.value() if self.book_dims_row_widget.isVisibleTo(self) else None,
            'book_height': self.book_height_spin.value() if self.book_dims_row_widget.isVisibleTo(self) else None,
            'paper_size': self.paper_size_combo.currentText().replace('×', 'x'),
            'orientation': self.orientation_label.text() or None,
            'pages_per_sheet': self.form_matn_spin.value(),
            'total_pages': self.total_pages_spin.value(),
            'book_type_preset': self.book_type_combo.currentText(),
            'tarjomeh_percent': self.tarjomeh_pct(),
            'paper_cut_half': int(self.cut_half_chk.isChecked()),
        }
        derived = self._derived_type_values()
        for category, col in TYPE_FIELD_COLUMNS.items():
            if category in self.inputs:
                d[col] = self.inputs[category].currentText()
            else:
                d[col] = derived.get(category, '')
        for field, col in COST_FIELD_COLUMNS.items():
            d[col] = self.cost_inputs[field].value()
        return d

    def populate(self, project, details, papers: list = None, volumes: list = None):
        """Fills the form from a projects row + optional details/papers/volumes."""
        project = dict(project)
        self.inputs['عنوان کتاب'].setText(project['title'])
        self.inputs['زیر عنوان کتاب'].setText(project['subtitle'] if project['subtitle'] else '')
        self.inputs['تاریخ'].setText(project['creation_date'])
        self.inputs['قطع'].setCurrentText(project['qate'] if project['qate'] else '')
        self.inputs['تیراژ'].setValue(int(float(project['tiraj'] or 0)))
        self.royalty_input.setValue(float(project['royalty_percent'] or 0.0))

        is_series = bool(volumes) or bool(project.get('series_name')) \
            or (project.get('series_volumes') or 1) > 1
        self.series_chk.blockSignals(True)
        self.series_chk.setChecked(is_series)
        self.series_chk.blockSignals(False)
        self.series_widget.setVisible(is_series)
        self._set_aggregate_readonly(is_series)
        if is_series:
            self.series_name_input.setText(project.get('series_name') or '')
            self.volumes_widget.blockSignals(True)
            self.set_volumes(volumes or [])
            self.volumes_widget.blockSignals(False)

        self.set_papers(papers or [])

        if not details:
            return
        details = dict(details)

        if details.get('tarjomeh_percent') is not None:
            self.tarjomeh_input.setValue(float(details['tarjomeh_percent']))
        self.cut_half_chk.setChecked(bool(details.get('paper_cut_half')))

        for category, col in TYPE_FIELD_COLUMNS.items():
            # Only the visible print/color combos still exist; paper/zinc types
            # are derived from the smart section, not restored here.
            if category in self.inputs and details.get(col):
                self.inputs[category].setCurrentText(details[col])

        color_indices = {1: 0, 2: 1, 4: 2}
        if details.get('form_matn') is not None:
            self.form_matn_spin.setValue(int(float(details['form_matn'])))
        if details.get('is_double_sided_matn') is not None:
            self.double_sided_matn_chk.setChecked(bool(details['is_double_sided_matn']))
        if details.get('color_count_matn') is not None:
            self.color_matn_combo.setCurrentIndex(color_indices.get(details['color_count_matn'], 2))
        if details.get('zinc_size_matn'):
            self.zinc_size_matn_combo.setCurrentText(details['zinc_size_matn'])
        if details.get('unit_price_paper_matn') is not None:
            self.unit_price_paper_matn_spin.setValue(float(details['unit_price_paper_matn']))

        if details.get('form_jeld') is not None:
            self.form_jeld_spin.setValue(int(float(details['form_jeld'])))
        if details.get('is_double_sided_jeld') is not None:
            self.double_sided_jeld_chk.setChecked(bool(details['is_double_sided_jeld']))
        if details.get('color_count_jeld') is not None:
            self.color_jeld_combo.setCurrentIndex(color_indices.get(details['color_count_jeld'], 2))
        if details.get('zinc_size_jeld'):
            self.zinc_size_jeld_combo.setCurrentText(details['zinc_size_jeld'])
        if details.get('unit_price_paper_jeld') is not None:
            self.unit_price_paper_jeld_spin.setValue(float(details['unit_price_paper_jeld']))

        if details.get('waste_percent') is not None:
            self.waste_percent_spin.setValue(float(details['waste_percent']))
        else:
            self.waste_percent_spin.setValue(5.0)

        if details.get('total_pages') is not None:
            self.total_pages_spin.setValue(int(float(details['total_pages'] or 0)))

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
        self._update_running_subtotal()

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
        self.tarjomeh_input.setValue(0.0)
        self.series_chk.setChecked(False)
        self.series_widget.setVisible(False)
        self._set_aggregate_readonly(False)
        self.series_name_input.clear()
        self.volumes_widget.clear()
        self.cut_half_chk.setChecked(False)
        self.papers_matn_list.clear()
        self.papers_jeld_list.clear()
        self.custom_cost_widget.clear()
        for f, combo in self.cost_calc_combos.items():
            idx = combo.findData(default_calc_type(f))
            combo.setCurrentIndex(max(0, idx))
        self._on_papers_changed()
        self._update_paper_readouts()

        self.book_type_combo.blockSignals(True)
        self.book_type_combo.setCurrentText("شومیز ساده")
        self.book_type_combo.blockSignals(False)
        self._apply_preset("شومیز ساده", zero_hidden=False)
