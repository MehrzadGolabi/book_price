import sys
import os
from datetime import datetime
import jdatetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QScrollArea, QWidget, QVBoxLayout,
                               QTabWidget, QFormLayout, QLineEdit, QComboBox,
                               QPushButton, QToolBar, QSpinBox, QDoubleSpinBox,
                               QLabel, QMessageBox, QHBoxLayout, QTableWidget, QHeaderView, QFileDialog, QCheckBox, QTableWidgetItem, QInputDialog, QDialog, QDialogButtonBox, QGroupBox,
                               QStackedWidget)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QAction, QFontDatabase, QShortcut, QKeySequence, QColor
import math
# Matplotlib imports
import matplotlib
matplotlib.use('QtAgg')
matplotlib.rcParams['font.family'] = ['Tahoma', 'Arial', 'DejaVu Sans']
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
# Farsi Text Handling
import arabic_reshaper
from bidi.algorithm import get_display
# ReportLab imports for PDF
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import cm
# Local modules
from config import get_db_config, DB_CONFIG
from db import BookDatabase
from pricing import (
    compute_cover_price,
    compute_net_revenue_per_copy,
    compute_break_even,
    compute_breakdown_pcts,
    compute_scenarios,
)
from calculator import CostCalculator
from paper_price_dialog import PaperPriceDialog
from print_layout_widget import PrintLayoutWidget


class BookCostCalculator(QMainWindow):
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("نرم افزار محاسبه و مدیریت هزینه‌های چاپ کتاب")
        self.setGeometry(100, 100, 1100, 800)
        
        # VERY IMPORTANT: Set the entire application to Right-To-Left for Farsi
        self.setLayoutDirection(Qt.RightToLeft)
        
        self.db: BookDatabase = BookDatabase(DB_CONFIG['filename'])
        self.cost_inputs: dict = {}
        self.cost_input_rows: dict = {}
        self.cost_group_boxes: dict = {}
        try:
            self.db.connect()
        except Exception as err:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self, "خطای دیتابیس",
                f"ارتباط با دیتابیس برقرار نشد.\nلطفاً فایل config.ini را بررسی کنید.\n\n{err}"
            )
            sys.exit(1)

        self.calculator = CostCalculator()
        self.init_ui()

    def _make_cost_row(self, field_name: str, readonly: bool = False) -> 'QWidget':
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

    def init_ui(self):
        # 1. Setup Menu Bar (Settings menu for advanced tabs)
        settings_menu = self.menuBar().addMenu("تنظیمات")
        paper_calc_menu_action = QAction("محاسبات پیش‌پردازش کاغذ", self)
        paper_calc_menu_action.triggered.connect(lambda: self.tabs.setCurrentIndex(5))
        settings_menu.addAction(paper_calc_menu_action)
        defaults_menu_action = QAction("مدیریت قیمت‌های پایه", self)
        defaults_menu_action.triggered.connect(lambda: self.tabs.setCurrentIndex(6))
        settings_menu.addAction(defaults_menu_action)

        # 2. Setup Toolbar (Open → Save | Import | Delete → Exit)
        toolbar = QToolBar("نوار ابزار اصلی")
        self.addToolBar(toolbar)

        open_action = QAction("بازکردن پروژه", self)
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.triggered.connect(self.load_selected_project)
        toolbar.addAction(open_action)

        save_action = QAction("ذخیره پروژه", self)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.triggered.connect(self.save_project_to_db)
        toolbar.addAction(save_action)

        toolbar.addSeparator()

        import_defaults_action = QAction("دریافت قیمت‌های پایه", self)
        import_defaults_action.triggered.connect(self.import_default_prices)
        toolbar.addAction(import_defaults_action)

        toolbar.addSeparator()

        delete_action = QAction("حذف پروژه", self)
        delete_action.triggered.connect(self.delete_project)
        toolbar.addAction(delete_action)

        exit_action = QAction("خروج", self)
        exit_action.triggered.connect(self.close)
        toolbar.addAction(exit_action)

        # 3. Setup Status Bar
        self.status_project_label = QLabel("پروژه‌ای باز نشده است")
        self.status_save_label = QLabel("")
        self.statusBar().addWidget(self.status_project_label)
        self.statusBar().addPermanentWidget(self.status_save_label)

        # 4. Setup Tabs
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Create Tab Widgets
        self.tab_project = QWidget()
        self.tab_details = QWidget()
        self.tab_pricing = QWidget()
        self.tab_calc = QWidget()
        self.tab_report = QWidget()
        self.tab_paper_calc = QWidget()
        self.tab_defaults = QWidget()

        self.tabs.addTab(self.tab_project,    "مدیریت پروژه‌ها")
        self.tabs.addTab(self.tab_details,    "ورود اطلاعات و هزینه‌ها")
        self.tabs.addTab(self.tab_pricing,    "قیمت‌گذاری و سودآوری")
        self.tabs.addTab(self.tab_calc,       "محاسبات نهایی")
        self.tabs.addTab(self.tab_report,     "گزارش‌گیری (PDF)")
        self.tabs.addTab(self.tab_paper_calc, "محاسبات پیش‌پردازش کاغذ")
        self.tabs.addTab(self.tab_defaults,   "مدیریت قیمت‌های پایه")

        self.setup_project_tab()
        self.setup_details_tab()
        self.setup_pricing_tab()
        self.setup_calc_tab()
        self.setup_report_tab()
        self.setup_paper_calc_tab()
        self.setup_default_costs_tab()

    def setup_project_tab(self):
        layout = QVBoxLayout()
        
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("جستجوی نام کتاب...")
        search_btn = QPushButton("جستجو")
        search_btn.clicked.connect(self.search_projects)           # ← connect search
        self.search_input.returnPressed.connect(self.search_projects) # Palette: Search on Enter
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_btn)
        
        self.project_table = QTableWidget(0, 4)
        self.project_table.setHorizontalHeaderLabels(["شناسه", "عنوان کتاب", "تاریخ", "تیراژ"])
        self.project_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.project_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.project_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.project_table.doubleClicked.connect(self.open_project)  # ← open on double click
        
        # Empty state page
        empty_widget = QWidget()
        empty_layout = QVBoxLayout(empty_widget)
        empty_layout.setAlignment(Qt.AlignCenter)
        empty_lbl = QLabel("هیچ پروژه‌ای یافت نشد\n\nبرای شروع، یک پروژه جدید ایجاد کنید.")
        empty_lbl.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(empty_lbl)

        self.project_stack = QStackedWidget()
        self.project_stack.addWidget(empty_widget)      # index 0: empty
        self.project_stack.addWidget(self.project_table)  # index 1: table

        new_project_btn = QPushButton("ایجاد پروژه جدید")
        new_project_btn.clicked.connect(self.new_project)

        layout.addLayout(search_layout)
        layout.addWidget(self.project_stack)
        layout.addWidget(new_project_btn)
        self.tab_project.setLayout(layout)
        
        # Load all projects initially
        self.load_projects()

    def setup_details_tab(self):
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

            self.inputs = {}

            # --- Basic Info Section ---
            self.inputs['عنوان کتاب'] = QLineEdit()
            self.inputs['عنوان کتاب'].setPlaceholderText("عنوان کتاب را وارد کنید")
            
            self.inputs['زیر عنوان کتاب'] = QLineEdit()
            self.inputs['زیر عنوان کتاب'].setPlaceholderText("(اختیاری)")
            
            self.inputs['تاریخ'] = QLineEdit()
            today_jalali = jdatetime.date.today()
            self.inputs['تاریخ'].setText(today_jalali.strftime("%Y/%m/%d"))
            self.inputs['تاریخ'].setReadOnly(True)

            self.inputs['تیراژ'] = QSpinBox()
            self.inputs['تیراژ'].setMaximum(100000)
            self.inputs['تیراژ'].setGroupSeparatorShown(True)

            # --- Book Size and Auto-Calculator Inputs ---
            self.inputs['قطع'] = QComboBox()
            self.inputs['قطع'].addItems([
                "وزیری", "رقعی", "رحلی کوچک", "رحلی بزرگ", "جیبی", "خشتی",
                "مربع", "بزرگ‌قطع", "کوچک‌قطع", "سفارشی"
            ])
            
            # Label to display optimization feedback
            self.lbl_optimal_paper = QLabel("کاغذ بهینه: - | ورق مصرفی هر جلد: -")
            self.lbl_optimal_paper.setObjectName("lbl_optimal_paper")

            # New Input: Total Pages
            self.total_pages_spin = QSpinBox()
            self.total_pages_spin.setMaximum(5000)
            self.total_pages_spin.setSuffix(" صفحه")
            self.total_pages_spin.setAlignment(Qt.AlignCenter)

            # Adding to form
            form_layout.addRow("عنوان کتاب:", self.inputs['عنوان کتاب'])
            form_layout.addRow("زیر عنوان:", self.inputs['زیر عنوان کتاب'])
            form_layout.addRow("تاریخ:", self.inputs['تاریخ'])
            form_layout.addRow("تیراژ:", self.inputs['تیراژ'])
            form_layout.addRow("قطع کتاب:", self.inputs['قطع'])
            form_layout.addRow("", self.lbl_optimal_paper) # Info label
            form_layout.addRow("تعداد صفحات کتاب:", self.total_pages_spin)

            # ── Paper size selector (always visible) ──────────────────────
            self.paper_size_combo = QComboBox()
            self.paper_size_combo.addItems(["70×100", "60×90", "50×70"])
            form_layout.addRow("اندازه کاغذ چاپ:", self.paper_size_combo)

            # ── Custom book dimensions (hidden for standard formats) ───────
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

            # ── Orientation result label ───────────────────────────────────
            self.orientation_label = QLabel("")
            self.orientation_label.setWordWrap(True)
            self.orientation_label.setStyleSheet("color: #64b5f6;")
            form_layout.addRow("جهت بهینه:", self.orientation_label)

            # --- Dynamic Type Categories ---
            dynamic_types = ["نوع کاغذ متن", "نوع چاپ متن", "نوع رنگ متن", "نوع زینک متن", 
                            "نوع کاغذ جلد", "نوع چاپ جلد", "نوع رنگ جلد", "نوع زینک جلد"]
            
            category_items = {dtype: [] for dtype in dynamic_types}
            try:
                for dtype in dynamic_types:
                    category_items[dtype] = self.db.get_categories(dtype)
            except Exception as e:
                print("Error pre-fetching categories:", e)

            for dtype in dynamic_types:
                combo = QComboBox()
                combo.setEditable(True)
                combo.setInsertPolicy(QComboBox.InsertAtBottom)
                combo.addItems(category_items[dtype])
                self.inputs[dtype] = combo
                form_layout.addRow(dtype + ":", combo)

            # --- Base Paper & Zinc Calculations GroupBox ---
            self.calc_group = QGroupBox("② پیش از چاپ — محاسبات هوشمند کاغذ و زینک")
            calc_layout = QFormLayout()

            # Text Setup
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

            # Cover Setup
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

            # --- Detailed Cost Inputs (5 GroupBoxes) ---

            # ── Group ①: خلاقیت و تحریریه ─────────────────────────────────
            grp1 = QGroupBox("① خلاقیت و تحریریه")
            grp1_layout = QVBoxLayout(grp1)
            grp1_layout.setSpacing(2)
            for fname in CostCalculator.COST_GROUPS["خلاقیت و تحریریه"]:
                grp1_layout.addWidget(self._make_cost_row(fname))
            form_layout.addRow(grp1)
            self.cost_group_boxes["خلاقیت و تحریریه"] = grp1

            # ── Group ②: پیش از چاپ (existing calc_group) ──────────────────
            form_layout.addRow(self.calc_group)

            # ── Group ③: چاپ و مواد ───────────────────────────────────────
            grp3 = QGroupBox("③ چاپ و مواد")
            grp3_layout = QVBoxLayout(grp3)
            grp3_layout.setSpacing(2)
            readonly_auto = {"هزینه زینک", "هزینه کاغذ متن", "هزینه کاغذ جلد"}
            for fname in CostCalculator.COST_GROUPS["چاپ و مواد"]:
                grp3_layout.addWidget(self._make_cost_row(fname, readonly=fname in readonly_auto))
            form_layout.addRow(grp3)
            self.cost_group_boxes["چاپ و مواد"] = grp3

            # ── Group ④: تکمیل و صحافی ───────────────────────────────────
            grp4 = QGroupBox("④ تکمیل و صحافی")
            grp4_layout = QVBoxLayout(grp4)
            grp4_layout.setSpacing(2)
            for fname in CostCalculator.COST_GROUPS["تکمیل و صحافی"]:
                grp4_layout.addWidget(self._make_cost_row(fname))
            form_layout.addRow(grp4)
            self.cost_group_boxes["تکمیل و صحافی"] = grp4

            # ── Group ⑤: اداری و مجوزها ─────────────────────────────────
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
            calc_btn.clicked.connect(self.perform_calculations)
            
            scroll_layout.addLayout(form_layout)
            scroll_layout.addWidget(calc_btn)
            scroll_area.setWidget(scroll_content)
            
            self.layout_widget = PrintLayoutWidget()
            self.layout_widget.setFixedWidth(320)

            outer_layout = QHBoxLayout(self.tab_details)
            outer_layout.setContentsMargins(0, 0, 0, 0)
            outer_layout.setSpacing(0)
            self.tab_details.setLayoutDirection(Qt.LeftToRight)
            outer_layout.addWidget(scroll_area)
            outer_layout.addWidget(self.layout_widget)

            # --- Signal Connections for Intelligent Auto-Calc ---
            self.inputs['قطع'].currentIndexChanged.connect(self.suggest_optimal_layout)
            self.total_pages_spin.valueChanged.connect(self.suggest_optimal_layout)
            self.double_sided_matn_chk.toggled.connect(self.suggest_optimal_layout)
            self.book_type_combo.currentTextChanged.connect(
                lambda name: self._apply_preset(name, zero_hidden=True)
            )

            # Standard auto-calculation signals
            widgets_to_connect = [
                self.form_matn_spin, self.unit_price_paper_matn_spin,
                self.form_jeld_spin, self.unit_price_paper_jeld_spin,
                self.inputs['تیراژ'], self.waste_percent_spin
            ]
            for w in widgets_to_connect:
                w.valueChanged.connect(self.auto_calculate_costs)

            self.double_sided_matn_chk.toggled.connect(self.auto_calculate_costs)
            self.double_sided_jeld_chk.toggled.connect(self.auto_calculate_costs)
            self.color_matn_combo.currentIndexChanged.connect(self.auto_calculate_costs)
            self.color_jeld_combo.currentIndexChanged.connect(self.auto_calculate_costs)
            self.zinc_size_matn_combo.currentIndexChanged.connect(self._update_zinc_price_labels)
            self.zinc_size_matn_combo.currentIndexChanged.connect(self.auto_calculate_costs)
            self.zinc_size_jeld_combo.currentIndexChanged.connect(self._update_zinc_price_labels)
            self.zinc_size_jeld_combo.currentIndexChanged.connect(self.auto_calculate_costs)
            self.tabs.currentChanged.connect(lambda idx: self._update_zinc_price_labels() if idx == 1 else None)
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
            self._update_zinc_price_labels()
            self.suggest_optimal_layout()
            self._refresh_layout_widget()
            # Apply default preset without zeroing (fields are already zero)
            self._apply_preset("شومیز ساده", zero_hidden=False)

    def _get_zinc_price(self, zinc_size):
        return self.db.get_zinc_price(zinc_size)

    def _update_zinc_price_labels(self):
        for label, combo in [
            (self.zinc_price_matn_label, self.zinc_size_matn_combo),
            (self.zinc_price_jeld_label, self.zinc_size_jeld_combo),
        ]:
            price = self._get_zinc_price(combo.currentText())
            if price > 0:
                label.setText(f"{price:,.0f} تومان")
                label.setStyleSheet("color: #4caf50;")
            else:
                label.setText("⚠ قیمت تنظیم نشده")
                label.setStyleSheet("color: #e57373;")

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
            _, pages_per_sheet = self._compute_optimal_orientation(
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

    def load_zinc_prices_table(self):
        zinc_sizes = ["زینک 2 ورقی", "زینک 2.5 ورقی", "زینک 3.5 ورقی", "زینک 4.5 ورقی", "زینک GTO"]
        self.zinc_prices_table.setRowCount(len(zinc_sizes))
        for i, zs in enumerate(zinc_sizes):
            name_item = QTableWidgetItem(zs)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.zinc_prices_table.setItem(i, 0, name_item)
            price = self._get_zinc_price(zs)
            spin = QDoubleSpinBox()
            spin.setMaximum(9999999999.99)
            spin.setGroupSeparatorShown(True)
            spin.setDecimals(0)
            spin.setValue(price)
            self.zinc_prices_table.setCellWidget(i, 1, spin)
            save_btn = QPushButton("ذخیره")
            save_btn.setStyleSheet("background-color: #2a6496; color: white; padding: 2px 8px; font-size: 11px;")
            save_btn.clicked.connect(lambda checked, row=i, size=zs: self.save_zinc_price(row, size))
            self.zinc_prices_table.setCellWidget(i, 2, save_btn)

    def save_zinc_price(self, row, zinc_size):
        spin = self.zinc_prices_table.cellWidget(row, 1)
        if spin is None:
            return
        price = spin.value()
        try:
            self.db.save_zinc_price(zinc_size, price)
            self._update_zinc_price_labels()
            self.auto_calculate_costs()
            QMessageBox.information(self, "ذخیره شد", f"قیمت {zinc_size} ذخیره شد.")
        except Exception as err:
            QMessageBox.critical(self, "خطا", f"ذخیره قیمت زینک با خطا مواجه شد:\n{err}")

    def auto_calculate_costs(self, *args):
        text_colors = 1 if self.color_matn_combo.currentIndex() == 0 else (2 if self.color_matn_combo.currentIndex() == 1 else 4)
        cover_colors = 1 if self.color_jeld_combo.currentIndex() == 0 else (2 if self.color_jeld_combo.currentIndex() == 1 else 4)
        sides_matn = 2 if self.double_sided_matn_chk.isChecked() else 1
        sides_jeld = 2 if self.double_sided_jeld_chk.isChecked() else 1

        results = self.calculator.compute_auto_costs(
            form_matn=self.form_matn_spin.value(),
            sides_matn=sides_matn,
            form_jeld=self.form_jeld_spin.value(),
            sides_jeld=sides_jeld,
            tiraj=self.inputs['تیراژ'].value(),
            waste_pct=self.waste_percent_spin.value(),
            unit_price_matn=self.unit_price_paper_matn_spin.value(),
            unit_price_jeld=self.unit_price_paper_jeld_spin.value(),
            text_colors=text_colors,
            cover_colors=cover_colors,
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

    def perform_calculations(self):
        tiraj = self.inputs['تیراژ'].value()
        if tiraj == 0:
            QMessageBox.warning(self, "خطا", "تیراژ نمی‌تواند صفر باشد!")
            return

        cost_values = {k: s.value() for k, s in self.cost_inputs.items()}
        totals = self.calculator.compute_totals(
            cost_values,
            royalty_pct=self.royalty_input.value(),
            tiraj=tiraj,
        )
        final_price = totals['total_cost']
        single_book_price = totals['cost_per_book']

        self.save_new_dynamic_types()
        self.lbl_final_total.setText(f"{final_price:,.0f}")
        self.lbl_single_price.setText(f"{single_book_price:,.0f}")
        self.update_chart()
        self._refresh_pricing_tab()
        self.tabs.setCurrentIndex(3)
        self.save_project_to_db()

    def save_new_dynamic_types(self):
        # Checks all ComboBoxes. If text isn't in the list, save it to DB.
        for category, widget in self.inputs.items():
            if isinstance(widget, QComboBox) and widget.isEditable():
                current_text = widget.currentText()
                if current_text and widget.findText(current_text) == -1:
                    # It's a new entry, save to DB
                    try:
                        self.db.save_category(category, current_text)
                        widget.addItem(current_text) # Add to current dropdown
                    except Exception as e:
                        print("Error saving category:", e)

    def setup_calc_tab(self):
            layout = QVBoxLayout()
            
            # بخش نمایش قیمت‌ها
            prices_layout = QFormLayout()
            self.lbl_final_total = QLabel("0")
            self.lbl_single_price = QLabel("0")
            self.lbl_final_total.setObjectName("lbl_final_total")
            self.lbl_single_price.setObjectName("lbl_single_price")
            prices_layout.addRow("قیمت تمام شده کل (تومان):", self.lbl_final_total)
            prices_layout.addRow("قیمت تمام شده یک جلد کتاب (تومان):", self.lbl_single_price)
            layout.addLayout(prices_layout)
            
            # راه‌اندازی بوم نمودار (Canvas)
            self.figure = Figure(figsize=(6, 6))
            self.canvas = FigureCanvasQTAgg(self.figure)
            layout.addWidget(self.canvas)
            
            self.tab_calc.setLayout(layout)

    def update_chart(self):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        labels = []
        sizes = []
        
        # استخراج هزینه‌هایی که بیشتر از صفر هستند
        for name, spinbox in self.cost_inputs.items():
            val = spinbox.value()
            if val > 0:
                # اصلاح متن فارسی برای متپلات‌لیب
                reshaped_text = arabic_reshaper.reshape(name)
                bidi_text = get_display(reshaped_text)
                labels.append(bidi_text)
                sizes.append(val)
                
        if not sizes:
            ax.text(0.5, 0.5, "هیچ هزینه‌ای وارد نشده است", ha='center', va='center')
            self.canvas.draw()
            return

        # رسم نمودار دایره‌ای (Pie Chart)
        ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140)
        ax.axis('equal') # دایره را کامل گرد می‌کند
        
        # تنظیم فونت کلی چارت (اختیاری، اگر فونت سیستم ساپورت کند)
        self.figure.tight_layout()
        self.canvas.draw()
    def save_project_to_db(self):
        title = self.inputs['عنوان کتاب'].text().strip()
        if not title:
            QMessageBox.warning(self, "خطا", "لطفاً حداقل عنوان کتاب را وارد کنید.")
            return

        def get_val(key):
            widget = self.inputs.get(key)
            if isinstance(widget, QComboBox):
                return widget.currentText()
            elif hasattr(widget, 'text'):
                return widget.text()
            elif hasattr(widget, 'value'):
                return widget.value()
            return None

        try:
            total_cost = float(self.lbl_final_total.text().replace(',', ''))
            single_cost = float(self.lbl_single_price.text().replace(',', ''))
        except ValueError:
            total_cost = 0
            single_cost = 0

        p = {
            'title': title,
            'subtitle': get_val('زیر عنوان کتاب'),
            'creation_date': get_val('تاریخ'),
            'qate': get_val('قطع'),
            'tiraj': get_val('تیراژ'),
            'royalty_percent': self.royalty_input.value(),
            'total_cost': total_cost,
            'single_book_cost': single_cost,
        }

        d = {
            'noeh_kaghaz_matn': get_val('نوع کاغذ متن'),
            'noeh_chap_matn': get_val('نوع چاپ متن'),
            'noeh_rang_matn': get_val('نوع رنگ متن'),
            'noeh_zink_matn': get_val('نوع زینک متن'),
            'noeh_kaghaz_jeld': get_val('نوع کاغذ جلد'),
            'noeh_chap_jeld': get_val('نوع چاپ جلد'),
            'noeh_rang_jeld': get_val('نوع رنگ جلد'),
            'noeh_zink_jeld': get_val('نوع زینک جلد'),
            'form_matn': self.form_matn_spin.value(),
            'is_double_sided_matn': int(self.double_sided_matn_chk.isChecked()),
            'color_count_matn': 1 if self.color_matn_combo.currentIndex() == 0 else (2 if self.color_matn_combo.currentIndex() == 1 else 4),
            'zinc_size_matn': self.zinc_size_matn_combo.currentText(),
            'form_jeld': self.form_jeld_spin.value(),
            'is_double_sided_jeld': int(self.double_sided_jeld_chk.isChecked()),
            'color_count_jeld': 1 if self.color_jeld_combo.currentIndex() == 0 else (2 if self.color_jeld_combo.currentIndex() == 1 else 4),
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
            'hazineh_talif': self.cost_inputs['هزینه تالیف'].value(),
            'hazineh_tarjomeh': self.cost_inputs['هزینه ترجمه'].value(),
            'hazineh_tasvir': self.cost_inputs['هزینه تصویرگری'].value(),
            'hazineh_virayesh': self.cost_inputs['هزینه ویرایش'].value(),
            'hazineh_tarahi_jeld': self.cost_inputs['هزینه طراحی جلد'].value(),
            'hazineh_modiriat_atelieh': self.cost_inputs['هزینه مديريت آتليه'].value(),
            'hazineh_zink': self.cost_inputs['هزینه زینک'].value(),
            'hazineh_chap_matn': self.cost_inputs['هزینه چاپ متن'].value(),
            'hazineh_chap_jeld': self.cost_inputs['هزینه چاپ جلد'].value(),
            'hazineh_kaghaz_matn': self.cost_inputs['هزینه کاغذ متن'].value(),
            'hazineh_kaghaz_jeld': self.cost_inputs['هزینه کاغذ جلد'].value(),
            'hazineh_rokesh_salfon': self.cost_inputs['هزینه روکش سلفون'].value(),
            'hazineh_moghava_maghzi': self.cost_inputs['هزینه مقوای مغذی'].value(),
            'hazineh_ghaleb_letterpress': self.cost_inputs['هزینه قالب لترپرس'].value(),
            'hazineh_ghaleb_diecut': self.cost_inputs['هزینه قالب دايكات'].value(),
            'hazineh_khat_ta': self.cost_inputs['هزینه خط تا'].value(),
            'hazineh_malzomat': self.cost_inputs['هزینه ملزومات'].value(),
            'hazineh_jeldsazi': self.cost_inputs['هزینه جلدسازی'].value(),
            'hazineh_sahafi': self.cost_inputs['هزینه صحافی'].value(),
            'hazineh_boresh_bastebandi': self.cost_inputs['هزینه برش و بسته‌بندی'].value(),
            'hazineh_haml_naghl': self.cost_inputs['هزینه حمل و نقل'].value(),
            'hazineh_montaj': self.cost_inputs['هزینه مونتاژ'].value(),
            'hazineh_horoofchini': self.cost_inputs['هزینه حروفچینی و صفحه‌آرایی'].value(),
            'hazineh_mojawwez_ershad': self.cost_inputs['هزینه مجوز ارشاد'].value(),
            'hazineh_shabok': self.cost_inputs['هزینه ثبت شابک'].value(),
            'hazineh_talakoobi': self.cost_inputs['هزینه طلاکوبی'].value(),
            'hazineh_uv_mowzei': self.cost_inputs['هزینه UV موضعی'].value(),
            'hazineh_barjasteh': self.cost_inputs['هزینه برجسته‌کاری'].value(),
            'book_type_preset': self.book_type_combo.currentText(),
            'pricing_multiplier': self.pricing_multiplier_spin.value() if hasattr(self, 'pricing_multiplier_spin') else 2.5,
            'distribution_percent': self.distribution_spin.value() if hasattr(self, 'distribution_spin') else 35.0,
        }

        try:
            if hasattr(self, 'current_project_id') and self.current_project_id is not None:
                self.db.update_project(self.current_project_id, p, d)
            else:
                self.current_project_id = self.db.insert_project(p, d)

            self.load_projects()
            now = jdatetime.datetime.now().strftime("%H:%M:%S")
            self.status_project_label.setText(title)
            self.status_save_label.setText(f"آخرین ذخیره: {now}")
            QMessageBox.information(self, "موفقیت", "اطلاعات پروژه با موفقیت ذخیره شد!")
        except Exception as err:
            QMessageBox.critical(self, "خطای ذخیره‌سازی", f"مشکلی در ذخیره اطلاعات پیش آمد:\n{err}")
        
    def setup_pricing_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content.setLayoutDirection(Qt.RightToLeft)
        main_vbox = QVBoxLayout(content)
        main_vbox.setSpacing(12)

        # ── Part A: Suggested cover price ────────────────────────────────
        grp_a = QGroupBox("قیمت‌گذاری پیشنهادی")
        grp_a_form = QFormLayout(grp_a)

        self.pricing_multiplier_spin = QDoubleSpinBox()
        self.pricing_multiplier_spin.setRange(1.0, 5.0)
        self.pricing_multiplier_spin.setSingleStep(0.1)
        self.pricing_multiplier_spin.setDecimals(1)
        self.pricing_multiplier_spin.setValue(2.5)
        grp_a_form.addRow("ضریب قیمت‌گذاری:", self.pricing_multiplier_spin)

        self.lbl_cover_price = QLabel("—")
        self.lbl_cover_price.setAlignment(Qt.AlignCenter)
        self.lbl_cover_price.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: #4caf50;"
            "background-color: #1a2a1a; padding: 10px; border-radius: 6px;"
        )
        grp_a_form.addRow("قیمت پشت جلد پیشنهادی:", self.lbl_cover_price)

        breakdown_container = QWidget()
        self.breakdown_layout = QHBoxLayout(breakdown_container)
        self.breakdown_layout.setContentsMargins(0, 0, 0, 0)
        self.breakdown_layout.setSpacing(2)
        self._breakdown_frames = {}
        colors = {
            "production":   "#2196f3",
            "distribution": "#ff9800",
            "royalty":      "#9c27b0",
            "publisher":    "#4caf50",
        }
        labels_fa = {
            "production": "تولید", "distribution": "توزیع",
            "royalty": "حق تالیف", "publisher": "سود ناشر",
        }
        for key, color in colors.items():
            frame = QLabel(labels_fa[key])
            frame.setAlignment(Qt.AlignCenter)
            frame.setStyleSheet(
                f"background-color: {color}; color: white; font-size: 10px;"
                "border-radius: 3px; padding: 4px;"
            )
            frame.setMinimumHeight(32)
            self.breakdown_layout.addWidget(frame, 1)
            self._breakdown_frames[key] = frame
        grp_a_form.addRow("توزیع قیمت پشت جلد:", breakdown_container)

        self.distribution_spin = QDoubleSpinBox()
        self.distribution_spin.setRange(0, 70)
        self.distribution_spin.setSingleStep(1)
        self.distribution_spin.setDecimals(0)
        self.distribution_spin.setValue(35.0)
        self.distribution_spin.setSuffix(" %")
        grp_a_form.addRow("سهم کتابفروشی / توزیع:", self.distribution_spin)

        main_vbox.addWidget(grp_a)

        # ── Part B: Break-even ───────────────────────────────────────────
        grp_b = QGroupBox("نقطه سر به سر")
        grp_b_form = QFormLayout(grp_b)

        self.lbl_total_project_cost = QLabel("—")
        grp_b_form.addRow("هزینه کل پروژه:", self.lbl_total_project_cost)

        self.lbl_net_per_copy = QLabel("—")
        grp_b_form.addRow("درآمد خالص ناشر (هر جلد):", self.lbl_net_per_copy)

        self.lbl_break_even = QLabel("—")
        self.lbl_break_even.setStyleSheet("font-weight: bold; font-size: 14px;")
        grp_b_form.addRow("نقطه سر به سر:", self.lbl_break_even)

        self.lbl_profit_status = QLabel("—")
        self.lbl_profit_status.setWordWrap(True)
        grp_b_form.addRow("وضعیت تیراژ فعلی:", self.lbl_profit_status)

        main_vbox.addWidget(grp_b)

        # ── Part C: Scenario table ───────────────────────────────────────
        grp_c = QGroupBox("جدول سناریوها")
        grp_c_vbox = QVBoxLayout(grp_c)

        self.scenario_table = QTableWidget(4, 3)
        self.scenario_table.setHorizontalHeaderLabels(["×۲.۵", "×۳.۰", "×۳.۵"])
        self.scenario_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.scenario_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.scenario_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        grp_c_vbox.addWidget(self.scenario_table)

        main_vbox.addWidget(grp_c)
        main_vbox.addStretch()

        scroll.setWidget(content)
        pricing_outer = QVBoxLayout(self.tab_pricing)
        pricing_outer.setContentsMargins(0, 0, 0, 0)
        pricing_outer.addWidget(scroll)

        # Wire live updates
        self.pricing_multiplier_spin.valueChanged.connect(self._refresh_pricing_tab)
        self.distribution_spin.valueChanged.connect(self._refresh_pricing_tab)

    def _refresh_pricing_tab(self):
        try:
            total_cost = float(self.lbl_final_total.text().replace(',', ''))
            single_cost = float(self.lbl_single_price.text().replace(',', ''))
            tiraj = self.inputs['تیراژ'].value()
        except (ValueError, AttributeError):
            return
        if total_cost <= 0 or single_cost <= 0 or tiraj <= 0:
            return

        multiplier = self.pricing_multiplier_spin.value()
        dist_pct = self.distribution_spin.value()
        royalty_pct = self.royalty_input.value()

        cover_price = compute_cover_price(single_cost, multiplier)
        net_per_copy = compute_net_revenue_per_copy(cover_price, dist_pct, royalty_pct)
        break_even = compute_break_even(total_cost, net_per_copy)
        bd = compute_breakdown_pcts(cover_price, single_cost, dist_pct, royalty_pct)

        # Part A — cover price label and breakdown bar
        self.lbl_cover_price.setText(f"{cover_price:,.0f} تومان")
        labels_fa = {"production": "تولید", "distribution": "توزیع",
                     "royalty": "حق تالیف", "publisher": "سود ناشر"}
        for key, frame in self._breakdown_frames.items():
            pct = bd[f'{key}_pct']
            amount = bd[key]
            frame.setText(f"{labels_fa[key]}\n{pct:.1f}%")
            frame.setToolTip(f"{amount:,.0f} تومان")
            self.breakdown_layout.setStretchFactor(frame, max(1, int(pct)))

        # Part B — break-even analysis
        self.lbl_total_project_cost.setText(f"{total_cost:,.0f} تومان")
        self.lbl_net_per_copy.setText(f"{net_per_copy:,.0f} تومان")
        if break_even > 0:
            self.lbl_break_even.setText(f"{break_even:,} جلد")
            if tiraj >= break_even:
                profit = net_per_copy * tiraj - total_cost
                self.lbl_profit_status.setText(
                    f"✓ تیراژ {tiraj:,} جلد از نقطه سر به سر ({break_even:,}) عبور کرده | "
                    f"سود تخمینی فروش کامل: {profit:,.0f} تومان"
                )
                self.lbl_profit_status.setStyleSheet("color: #4caf50; font-weight: bold;")
            else:
                shortage = break_even - tiraj
                self.lbl_profit_status.setText(
                    f"✗ تیراژ {tiraj:,} جلد کمتر از نقطه سر به سر است | "
                    f"برای رسیدن به سر به سر {shortage:,} جلد بیشتر نیاز است"
                )
                self.lbl_profit_status.setStyleSheet("color: #e57373; font-weight: bold;")
        else:
            self.lbl_break_even.setText("قابل محاسبه نیست")
            self.lbl_profit_status.setText("درآمد خالص ناشر صفر یا منفی است")
            self.lbl_profit_status.setStyleSheet("color: #e57373;")

        # Part C — scenario table
        fixed_multipliers = [2.5, 3.0, 3.5]
        sales_pcts = [0.25, 0.5, 0.75, 1.0]
        rows_data = compute_scenarios(total_cost, single_cost, tiraj,
                                      dist_pct, royalty_pct, fixed_multipliers)
        row_labels = [f"{max(1, int(tiraj * p)):,} جلد ({int(p * 100)}٪)" for p in sales_pcts]
        self.scenario_table.setVerticalHeaderLabels(row_labels)

        for row_idx, pct in enumerate(sales_pcts):
            for col_idx, mult in enumerate(fixed_multipliers):
                sales_qty = max(1, int(tiraj * pct))
                entry = next((r for r in rows_data
                              if r['multiplier'] == mult and r['sales_qty'] == sales_qty), None)
                if entry is None:
                    continue
                profit = entry['net_profit']
                item = QTableWidgetItem(f"{profit:+,.0f} تومان")
                item.setTextAlignment(Qt.AlignCenter)
                if profit > 0:
                    item.setForeground(QColor('#4caf50'))
                elif profit < -0.10 * total_cost:
                    item.setForeground(QColor('#e57373'))
                else:
                    item.setForeground(QColor('#ffb74d'))
                if abs(mult - multiplier) < 0.01 and pct == 1.0:
                    item.setBackground(QColor('#1a2a1a'))
                self.scenario_table.setItem(row_idx, col_idx, item)

    def setup_report_tab(self):
            layout = QVBoxLayout()
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
            btn_pdf.clicked.connect(self.generate_pdf)
            layout.addWidget(btn_pdf)
            
            layout.addStretch() # هل دادن عناصر به سمت بالا
            self.tab_report.setLayout(layout)
            

    def write_farsi_text(self, canvas_obj, text, x_pos, y_pos, font_size=12, align='right', color=(0,0,0)):
            """Helper for advanced Farsi text alignment and coloring in PDF."""
            reshaped = arabic_reshaper.reshape(text)
            bidi_text = get_display(reshaped)
            canvas_obj.setFont('FarsiFont', font_size)
            canvas_obj.setFillColorRGB(*color)
            if align == 'right':
                canvas_obj.drawRightString(x_pos, y_pos, bidi_text)
            elif align == 'center':
                canvas_obj.drawCentredString(x_pos, y_pos, bidi_text)
            else:
                canvas_obj.drawString(x_pos, y_pos, bidi_text)

    def generate_pdf(self):
        font_path = "tahoma.ttf"
        if not os.path.exists(font_path):
            QMessageBox.critical(self, "خطا", f"فایل فونت '{font_path}' در کنار برنامه پیدا نشد!\nلطفاً یک فونت فارسی را در پوشه برنامه قرار دهید.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "ذخیره گزارش PDF", "", "PDF Files (*.pdf)")
        if not file_path:
            return

        pdfmetrics.registerFont(TTFont('FarsiFont', font_path))
        c = canvas.Canvas(file_path, pagesize=A4)
        width, height = A4
        margin = 2 * cm
        y = height - margin

        def check_page_break(current_y, needed_space=2*cm):
            """Creates a new page if the required space isn't available."""
            if current_y < margin + needed_space:
                c.showPage()
                return height - margin
            return current_y

        # ==========================================
        # 1. HEADER (Logo, Title, Date)
        # ==========================================
        
        # Logo placeholder (Top Left)
        logo_path = "logo.png" # Place a logo.png in the same folder to use it
        if os.path.exists(logo_path):
            c.drawImage(logo_path, margin, y - 2*cm, width=3*cm, height=3*cm, preserveAspectRatio=True)
        else:
            # Draw a dotted placeholder box if no logo is found
            c.setDash(3, 3)
            c.setStrokeColorRGB(0.5, 0.5, 0.5)
            c.rect(margin, y - 2*cm, 3*cm, 2.5*cm)
            self.write_farsi_text(c, "محل لوگوی ناشر", margin + 1.5*cm, y - 0.9*cm, font_size=10, align='center', color=(0.5, 0.5, 0.5))
            c.setDash() # Reset dash

        # Title (Top Right)
        self.write_farsi_text(c, "گزارش برآورد هزینه چاپ کتاب", width - margin, y - 0.5*cm, font_size=18, color=(0.1, 0.2, 0.4))
        self.write_farsi_text(c, self.inputs['عنوان کتاب'].text(), width - margin, y - 1.5*cm, font_size=14)

        # Date
        today = jdatetime.date.today().strftime("%Y/%m/%d")
        self.write_farsi_text(c, f"تاریخ گزارش: {today}", width - margin, y - 2.3*cm, font_size=10, color=(0.4, 0.4, 0.4))

        y -= 3.5 * cm

        # ==========================================
        # STRUCTURAL HELPERS
        # ==========================================
        
        def draw_section_header(title, current_y):
            current_y = check_page_break(current_y, 3*cm)
            c.setFillColorRGB(0.92, 0.94, 0.96) # Light blue-gray background for header
            c.rect(margin, current_y - 0.3*cm, width - 2*margin, 0.8*cm, fill=1, stroke=0)
            self.write_farsi_text(c, title, width - margin - 0.2*cm, current_y, font_size=12, color=(0.1, 0.2, 0.4))
            return current_y - 1 * cm

        def draw_row(key, value, current_y):
            current_y = check_page_break(current_y, 1*cm)
            
            # Dotted leader line between text
            c.setStrokeColorRGB(0.8, 0.8, 0.8)
            c.setDash(1, 4)
            c.line(margin + 4*cm, current_y + 0.1*cm, width - margin - 4*cm, current_y + 0.1*cm)
            c.setDash()

            # Key on Right, Value on Left
            self.write_farsi_text(c, key, width - margin, current_y, font_size=11)
            self.write_farsi_text(c, str(value), margin, current_y, font_size=11, align='left')
            return current_y - 0.8 * cm

        # ==========================================
        # 2. SECTIONS
        # ==========================================
        
        # Basic Info
        if self.chk_basic_info.isChecked():
            y = draw_section_header("اطلاعات پایه", y)
            for key in ['عنوان کتاب', 'زیر عنوان کتاب', 'تاریخ', 'قطع']:
                widget = self.inputs[key]
                val = widget.currentText() if isinstance(widget, QComboBox) else widget.text()
                if val:
                    y = draw_row(key, val, y)
            y = draw_row("تیراژ", str(self.inputs['تیراژ'].value()), y)
            y -= 0.5 * cm

        # Technical Features
        if self.chk_features.isChecked():
            y = draw_section_header("ویژگی‌های فنی", y)
            for key, widget in self.inputs.items():
                if isinstance(widget, QComboBox) and key != 'قطع':
                    val = widget.currentText()
                    if val:
                        y = draw_row(key, val, y)
            y -= 0.5 * cm

        # Costs
        if self.chk_costs.isChecked():
            y = draw_section_header("ریز هزینه‌ها (تومان)", y)
            for key, spin in self.cost_inputs.items():
                if spin.value() > 0:
                    y = draw_row(key, f"{spin.value():,.0f}", y)
            
            y = draw_row("حق تالیف", f"{self.royalty_input.value()} %", y)
            y -= 0.5 * cm

        # ==========================================
        # 3. TOTALS
        # ==========================================
        y = check_page_break(y, 4*cm)
        c.setStrokeColorRGB(0.1, 0.2, 0.4)
        c.setLineWidth(2)
        c.line(margin, y, width - margin, y)
        y -= 1 * cm

        self.write_farsi_text(c, "جمع کل هزینه‌ها:", width - margin, y, font_size=14, color=(0.6, 0.1, 0.1))
        self.write_farsi_text(c, f"{self.lbl_final_total.text()} تومان", margin, y, font_size=14, align='left', color=(0.6, 0.1, 0.1))
        y -= 1 * cm

        self.write_farsi_text(c, "هزینه تمام شده هر جلد:", width - margin, y, font_size=14, color=(0.1, 0.5, 0.1))
        self.write_farsi_text(c, f"{self.lbl_single_price.text()} تومان", margin, y, font_size=14, align='left', color=(0.1, 0.5, 0.1))

        # ==========================================
        # 4. SIGNATURE BLOCKS
        # ==========================================
        y -= 2 * cm
        y = check_page_break(y, 4*cm) # Guarantee space for signatures at the bottom

        c.setLineWidth(1)
        c.setStrokeColorRGB(0, 0, 0)
        
        # Right Signature (Publisher)
        c.line(width - margin - 5*cm, y, width - margin, y)
        self.write_farsi_text(c, "مهر و امضای ناشر", width - margin - 2.5*cm, y - 0.7*cm, font_size=11, align='center')

        # Left Signature (Client/Author)
        c.line(margin, y, margin + 5*cm, y)
        self.write_farsi_text(c, "امضای نویسنده / سفارش‌دهنده", margin + 2.5*cm, y - 0.7*cm, font_size=11, align='center')

        c.save()
        QMessageBox.information(self, "موفقیت", "فایل PDF با موفقیت تولید و ذخیره شد.")


    def load_projects(self, filter_text=None):
        try:
            results = self.db.get_projects(filter_text or '')
            self.project_table.setUpdatesEnabled(False)
            self.project_table.setRowCount(len(results))
            for row_idx, row_data in enumerate(results):
                self.project_table.setItem(row_idx, 0, QTableWidgetItem(str(row_data['id'])))
                self.project_table.setItem(row_idx, 1, QTableWidgetItem(row_data['title']))
                self.project_table.setItem(row_idx, 2, QTableWidgetItem(row_data['creation_date']))
                self.project_table.setItem(row_idx, 3, QTableWidgetItem(str(row_data['tiraj'])))
            self.project_table.setUpdatesEnabled(True)
            if hasattr(self, 'project_stack'):
                self.project_stack.setCurrentIndex(1 if results else 0)
        except Exception as err:
            QMessageBox.warning(self, "خطا", f"بارگذاری پروژه‌ها با خطا مواجه شد:\n{err}")
    
    def search_projects(self):
        search_text = self.search_input.text().strip()
        self.load_projects(search_text if search_text else None)
        
    def open_project(self, index):
        """Called when a row is double‑clicked."""
        row = index.row()
        project_id_item = self.project_table.item(row, 0)
        if not project_id_item:
            return
        project_id = int(project_id_item.text())
        self.load_project_by_id(project_id)
    
    def load_project_by_id(self, project_id):
        """Loads a project's data into the details tab given its ID."""
        try:
            project = self.db.get_project(project_id)
            if not project:
                QMessageBox.warning(self, "خطا", "پروژه‌ای با این شناسه یافت نشد.")
                return
            details = self.db.get_project_details(project_id)

            # Populate basic fields
            self.inputs['عنوان کتاب'].setText(project['title'])
            self.inputs['زیر عنوان کتاب'].setText(project['subtitle'] if project['subtitle'] else '')
            self.inputs['تاریخ'].setText(project['creation_date'])
            self.inputs['قطع'].setCurrentText(project['qate'] if project['qate'] else '')
            self.inputs['تیراژ'].setValue(project['tiraj'])
            self.royalty_input.setValue(project['royalty_percent'])

            # Populate dynamic types if details exist
            if details:
                type_mapping = {
                    'نوع کاغذ متن': 'noeh_kaghaz_matn',
                    'نوع چاپ متن': 'noeh_chap_matn',
                    'نوع رنگ متن': 'noeh_rang_matn',
                    'نوع زینک متن': 'noeh_zink_matn',
                    'نوع کاغذ جلد': 'noeh_kaghaz_jeld',
                    'نوع چاپ جلد': 'noeh_chap_jeld',
                    'نوع رنگ جلد': 'noeh_rang_jeld',
                    'نوع زینک جلد': 'noeh_zink_jeld'
                }
                for persian_key, col_name in type_mapping.items():
                    if col_name in details and details[col_name]:
                        self.inputs[persian_key].setCurrentText(details[col_name])

                # Populate base calculations
                if 'form_matn' in details and details['form_matn'] is not None:
                    self.form_matn_spin.setValue(details['form_matn'])
                if 'is_double_sided_matn' in details and details['is_double_sided_matn'] is not None:
                    self.double_sided_matn_chk.setChecked(bool(details['is_double_sided_matn']))
                if 'color_count_matn' in details and details['color_count_matn'] is not None:
                    color_matn = details['color_count_matn']
                    self.color_matn_combo.setCurrentIndex(0 if color_matn == 1 else (1 if color_matn == 2 else 2))
                if 'zinc_size_matn' in details and details['zinc_size_matn']:
                    self.zinc_size_matn_combo.setCurrentText(details['zinc_size_matn'])
                if 'unit_price_paper_matn' in details and details['unit_price_paper_matn'] is not None:
                    self.unit_price_paper_matn_spin.setValue(details['unit_price_paper_matn'])

                if 'form_jeld' in details and details['form_jeld'] is not None:
                    self.form_jeld_spin.setValue(details['form_jeld'])
                if 'is_double_sided_jeld' in details and details['is_double_sided_jeld'] is not None:
                    self.double_sided_jeld_chk.setChecked(bool(details['is_double_sided_jeld']))
                if 'color_count_jeld' in details and details['color_count_jeld'] is not None:
                    color_jeld = details['color_count_jeld']
                    self.color_jeld_combo.setCurrentIndex(0 if color_jeld == 1 else (1 if color_jeld == 2 else 2))
                if 'zinc_size_jeld' in details and details['zinc_size_jeld']:
                    self.zinc_size_jeld_combo.setCurrentText(details['zinc_size_jeld'])
                if 'unit_price_paper_jeld' in details and details['unit_price_paper_jeld'] is not None:
                    self.unit_price_paper_jeld_spin.setValue(details['unit_price_paper_jeld'])

                if 'waste_percent' in details and details['waste_percent'] is not None:
                    self.waste_percent_spin.setValue(float(details['waste_percent']))
                else:
                    self.waste_percent_spin.setValue(5.0)

                if 'total_pages' in details.keys() and details['total_pages'] is not None:
                    self.total_pages_spin.setValue(details['total_pages'] or 0)

                if 'book_width' in details and details['book_width'] is not None:
                    self.book_width_spin.setValue(float(details['book_width']))
                if 'book_height' in details and details['book_height'] is not None:
                    self.book_height_spin.setValue(float(details['book_height']))
                if 'paper_size' in details and details['paper_size']:
                    self.paper_size_combo.setCurrentText(details['paper_size'].replace("x", "×"))

                cost_mapping = {
                    'هزینه تالیف': 'hazineh_talif',
                    'هزینه ترجمه': 'hazineh_tarjomeh',
                    'هزینه تصویرگری': 'hazineh_tasvir',
                    'هزینه ویرایش': 'hazineh_virayesh',
                    'هزینه طراحی جلد': 'hazineh_tarahi_jeld',
                    'هزینه مديريت آتليه': 'hazineh_modiriat_atelieh',
                    'هزینه زینک': 'hazineh_zink',
                    'هزینه چاپ متن': 'hazineh_chap_matn',
                    'هزینه چاپ جلد': 'hazineh_chap_jeld',
                    'هزینه کاغذ متن': 'hazineh_kaghaz_matn',
                    'هزینه کاغذ جلد': 'hazineh_kaghaz_jeld',
                    'هزینه روکش سلفون': 'hazineh_rokesh_salfon',
                    'هزینه مقوای مغذی': 'hazineh_moghava_maghzi',
                    'هزینه قالب لترپرس': 'hazineh_ghaleb_letterpress',
                    'هزینه قالب دايكات': 'hazineh_ghaleb_diecut',
                    'هزینه خط تا': 'hazineh_khat_ta',
                    'هزینه ملزومات': 'hazineh_malzomat',
                    'هزینه جلدسازی': 'hazineh_jeldsazi',
                    'هزینه صحافی': 'hazineh_sahafi',
                    'هزینه برش و بسته‌بندی': 'hazineh_boresh_bastebandi',
                    'هزینه حمل و نقل': 'hazineh_haml_naghl',
                    'هزینه مونتاژ': 'hazineh_montaj',
                    'هزینه حروفچینی و صفحه‌آرایی': 'hazineh_horoofchini',
                    'هزینه مجوز ارشاد': 'hazineh_mojawwez_ershad',
                    'هزینه ثبت شابک': 'hazineh_shabok',
                    'هزینه طلاکوبی': 'hazineh_talakoobi',
                    'هزینه UV موضعی': 'hazineh_uv_mowzei',
                    'هزینه برجسته‌کاری': 'hazineh_barjasteh',
                }
                for persian_key, col_name in cost_mapping.items():
                    if col_name in details and details[col_name] is not None:
                        self.cost_inputs[persian_key].setValue(float(details[col_name]))

                # Restore preset — block signals to avoid zeroing loaded values
                preset = details['book_type_preset'] if 'book_type_preset' in details.keys() and details['book_type_preset'] else 'شومیز ساده'
                self.book_type_combo.blockSignals(True)
                self.book_type_combo.setCurrentText(preset)
                self.book_type_combo.blockSignals(False)
                self._apply_preset(preset, zero_hidden=False)

                # Restore pricing settings if Tab 3 is initialized
                if hasattr(self, 'pricing_multiplier_spin') and 'pricing_multiplier' in details.keys() and details['pricing_multiplier'] is not None:
                    self.pricing_multiplier_spin.setValue(float(details['pricing_multiplier']))
                if hasattr(self, 'distribution_spin') and 'distribution_percent' in details.keys() and details['distribution_percent'] is not None:
                    self.distribution_spin.setValue(float(details['distribution_percent']))

            # Store the project ID for possible update later
            self.current_project_id = project_id
            self.status_project_label.setText(project['title'])
            self.status_save_label.setText("")

            self.tabs.setCurrentIndex(1)  # Switch to details tab
            QMessageBox.information(self, "بارگذاری", "پروژه با موفقیت بارگذاری شد. پس از ویرایش می‌توانید ذخیره کنید.")

        except Exception as err:
            QMessageBox.critical(self, "خطا", f"بارگذاری پروژه با خطا مواجه شد:\n{err}")

    def load_selected_project(self):
        """Opens the project that is currently selected in the table."""
        current_row = self.project_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "هشدار", "لطفاً ابتدا یک پروژه را از جدول انتخاب کنید.")
            return
        project_id_item = self.project_table.item(current_row, 0)
        if not project_id_item:
            return
        project_id = int(project_id_item.text())
        self.load_project_by_id(project_id)
    
    def new_project(self):
        """Clears the details form and prepares for a new project."""
        self.current_project_id = None
        self.status_project_label.setText("پروژه جدید")
        self.status_save_label.setText("")

        # Clear basic fields
        self.inputs['عنوان کتاب'].clear()
        self.inputs['زیر عنوان کتاب'].clear()
        # Date will auto‑update when setup_details_tab is called, but we can set again:
        today_jalali = jdatetime.date.today()
        self.inputs['تاریخ'].setText(today_jalali.strftime("%Y/%m/%d"))
        self.inputs['قطع'].setCurrentIndex(0)
        self.inputs['تیراژ'].setValue(0)

        # Clear dynamic types (set to first item)
        for key, widget in self.inputs.items():
            if isinstance(widget, QComboBox) and key != 'قطع':
                widget.setCurrentIndex(-1)

        # Clear base calculations
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

        # Clear costs
        for spin in self.cost_inputs.values():
            spin.setValue(0.0)

        self.royalty_input.setValue(0.0)

        self.book_type_combo.blockSignals(True)
        self.book_type_combo.setCurrentText("شومیز ساده")
        self.book_type_combo.blockSignals(False)
        self._apply_preset("شومیز ساده", zero_hidden=False)
        if hasattr(self, 'pricing_multiplier_spin'):
            self.pricing_multiplier_spin.setValue(2.5)
        if hasattr(self, 'distribution_spin'):
            self.distribution_spin.setValue(35.0)

        # Clear calculation labels
        self.lbl_final_total.setText("0")
        self.lbl_single_price.setText("0")

        # Switch to details tab
        self.tabs.setCurrentIndex(1)
    
    def delete_project(self):
        """Deletes the selected project after password verification."""
        # 1. Check if a row is selected in the table
        current_row = self.project_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "هشدار", "لطفاً ابتدا یک پروژه را از جدول انتخاب کنید.")
            return

        project_id_item = self.project_table.item(current_row, 0)
        if not project_id_item:
            return
        project_id = int(project_id_item.text())
        project_title = self.project_table.item(current_row, 1).text()

        # 2. Ask for password
        password, ok = QInputDialog.getText(
            self, "تأیید حذف",
            f"برای حذف پروژه «{project_title}» لطفاً رمز عبور را وارد کنید:",
            QLineEdit.Password
        )
        if not ok or password != DB_CONFIG.get('delete_password', 'admin'):
            QMessageBox.critical(self, "خطا", "رمز عبور اشتباه است یا عملیات لغو شد.")
            return

        # 3. Confirm deletion
        reply = QMessageBox.question(
            self, "تأیید نهایی",
            f"آیا از حذف کامل پروژه «{project_title}» اطمینان دارید؟",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        # 4. Delete from database
        try:
            self.db.delete_project(project_id)

            # 5. Refresh the project table
            self.load_projects()

            # 6. If the deleted project is currently loaded, clear the form
            if hasattr(self, 'current_project_id') and self.current_project_id == project_id:
                self.new_project()  # use the method we already created to reset fields

            QMessageBox.information(self, "موفقیت", "پروژه با موفقیت حذف شد.")

        except Exception as err:
            QMessageBox.critical(self, "خطا", f"حذف پروژه با مشکل مواجه شد:\n{err}")
            
    def setup_paper_calc_tab(self):
        layout = QVBoxLayout()

        # Form layout for inputs
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

        # Table
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
        self.tab_paper_calc.setLayout(layout)

        self.update_paper_inputs_visibility()
        self.load_paper_calculations()

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
        formula_idx = self.paper_formula_combo.currentIndex()
        unit_price = self.calculator.compute_paper_unit_price(
            formula_idx=formula_idx,
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

        paper_type = self.paper_type_combo.currentText().strip()
        formula = self.paper_formula_combo.currentText()
        weight = self.paper_weight_spin.value() if self.paper_weight_spin.isEnabled() else 0
        height = self.paper_height_spin.value() if self.paper_height_spin.isEnabled() else 0
        length = self.paper_length_spin.value() if self.paper_length_spin.isEnabled() else 0
        bundle_count = self.paper_bundle_count_spin.value() if self.paper_bundle_count_spin.isEnabled() else 0
        bundle_weight = self.paper_bundle_weight_spin.value() if self.paper_bundle_weight_spin.isEnabled() else 0
        price = self.paper_price_spin.value()

        try:
            data = {
                'paper_type': paper_type, 'formula_type': formula,
                'weight': weight, 'height': height, 'length': length,
                'bundle_count': bundle_count, 'bundle_weight': bundle_weight,
                'price': price, 'unit_price': unit_price,
            }
            if hasattr(self, 'editing_paper_calc_id') and self.editing_paper_calc_id is not None:
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
            self.paper_calc_table.setRowCount(0)
            for row in rows:
                row_idx = self.paper_calc_table.rowCount()
                self.paper_calc_table.insertRow(row_idx)

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

            self.paper_calc_table.hideColumn(0) # Hide ID
        except Exception as err:
            QMessageBox.warning(self, "خطا", f"بارگذاری محاسبات با خطا مواجه شد:\n{err}")

    def load_selected_paper_calc(self):
        row = self.paper_calc_table.currentRow()
        if row < 0: return

        calc_id = int(self.paper_calc_table.item(row, 0).text())
        self.editing_paper_calc_id = calc_id

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
        unit_price_str = self.paper_calc_table.item(row, 9).text().replace(',', '')
        unit_price = float(unit_price_str)

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
                self.load_default_costs_table()
                self.populate_default_value_combo(self.def_cat_combo.currentText())
                QMessageBox.information(self, "موفقیت", "انتقال به قیمت‌های پایه با موفقیت انجام شد.")
                self.tabs.setCurrentIndex(6) # Switch to defaults tab
            except Exception as err:
                QMessageBox.critical(self, "خطا", f"انتقال با خطا مواجه شد:\n{err}")

    def setup_default_costs_tab(self):
        layout = QVBoxLayout()

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


        # Form to add / edit a mapping
        form = QFormLayout()

        self.def_cat_combo = QComboBox()
        self.def_cat_combo.setEditable(False)
        self.def_cat_combo.addItems([
            "نوع کاغذ متن", "نوع چاپ متن", "نوع رنگ متن", "نوع زینک متن",
            "نوع کاغذ جلد", "نوع چاپ جلد", "نوع رنگ جلد", "نوع زینک جلد"
        ])
        form.addRow("دسته‌بندی:", self.def_cat_combo)

        self.def_value_combo = QComboBox()
        self.def_value_combo.setEditable(True)   # allow entering new values
        self.def_value_combo.setInsertPolicy(QComboBox.InsertAtBottom)
        # Populate with existing items when category changes
        self.def_value_combo.currentTextChanged.connect(lambda text, cat=self.def_cat_combo.currentText(): self.apply_default_cost(cat, text))
        form.addRow("مقدار (نوع):", self.def_value_combo)

        self.def_cost_field_combo = QComboBox()
        # all cost field keys
        _readonly_auto = {"هزینه زینک", "هزینه کاغذ متن", "هزینه کاغذ جلد"}
        self.def_cost_field_combo.addItems(
            [k for k in self.cost_inputs.keys() if k not in _readonly_auto]
        )
        form.addRow("فیلد هزینه هدف:", self.def_cost_field_combo)

        self.def_cost_spin = QDoubleSpinBox()
        self.def_cost_spin.setMaximum(9999999999.99)
        self.def_cost_spin.setGroupSeparatorShown(True)
        self.def_cost_spin.setDecimals(0)
        self.def_cost_spin.lineEdit().setAlignment(Qt.AlignCenter)
        form.addRow("قیمت پیش‌فرض:", self.def_cost_spin)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("افزودن")
        add_btn.clicked.connect(self.add_default_cost_mapping)
        edit_btn = QPushButton("ویرایش")
        edit_btn.clicked.connect(self.edit_default_cost_mapping)
        delete_btn = QPushButton("حذف")
        delete_btn.clicked.connect(self.delete_default_cost_mapping)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(delete_btn)

        layout.addLayout(form)
        layout.addLayout(btn_layout)

        # Table showing all mappings
        self.defaults_table = QTableWidget(0, 4)
        self.defaults_table.setHorizontalHeaderLabels(["دسته‌بندی", "مقدار", "فیلد هزینه", "قیمت پیش‌فرض"])
        self.defaults_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.defaults_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.defaults_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.defaults_table.doubleClicked.connect(self.load_selected_default_for_edit)
        layout.addWidget(self.defaults_table)

        self.tab_defaults.setLayout(layout)

        # Initial load
        self.populate_default_value_combo(self.def_cat_combo.currentText())
        self.load_default_costs_table()
        self.load_zinc_prices_table()

    def populate_default_value_combo(self, category_name):
        """Fills the value combo with existing items from the chosen category."""
        self.def_value_combo.clear()
        try:
            items = self.db.get_categories(category_name)
            self.def_value_combo.addItems(items)
        except Exception as e:
            print("Error populating value combo:", e)

    def load_default_costs_table(self):
        """Reloads the table showing all default cost mappings."""
        try:
            rows = self.db.get_default_cost_mappings()
            self.defaults_table.setUpdatesEnabled(False)
            self.defaults_table.setRowCount(len(rows))
            for i, row in enumerate(rows):
                self.defaults_table.setItem(i, 0, QTableWidgetItem(row['category_name']))
                self.defaults_table.setItem(i, 1, QTableWidgetItem(row['item_value']))
                self.defaults_table.setItem(i, 2, QTableWidgetItem(row['target_cost_field']))
                cost_item = QTableWidgetItem(f"{row['default_cost']:,.2f}")
                cost_item.setTextAlignment(Qt.AlignCenter)
                self.defaults_table.setItem(i, 3, cost_item)
                # Store the id in the first cell's data for later use
                self.defaults_table.item(i, 0).setData(Qt.UserRole, row['id'])
            self.defaults_table.setUpdatesEnabled(True)
        except Exception as err:
            QMessageBox.warning(self, "خطا", f"بارگذاری قیمت‌های پایه با خطا مواجه شد:\n{err}")

    def add_default_cost_mapping(self):
        """Inserts a new mapping into the database."""
        cat = self.def_cat_combo.currentText()
        val = self.def_value_combo.currentText().strip()
        if not val:
            QMessageBox.warning(self, "خطا", "مقدار نوع نمی‌تواند خالی باشد.")
            return
        cost_field = self.def_cost_field_combo.currentText()
        cost = self.def_cost_spin.value()
        try:
            self.db.insert_default_mapping(cat, val, cost_field, cost)
            self.db.save_category(cat, val)
            self.load_default_costs_table()
            self.populate_default_value_combo(cat)
        except Exception as err:
            QMessageBox.critical(self, "خطا", f"افزودن قیمت پایه با خطا مواجه شد:\n{err}")

    def load_selected_default_for_edit(self):
        """When a table row is double‑clicked, fill the form above for editing."""
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

        self.def_cat_combo.setCurrentText(cat)
        self.def_value_combo.setCurrentText(val)
        self.def_cost_field_combo.setCurrentText(field)
        self.def_cost_spin.setValue(cost)
        # Store the editing id temporary
        self.editing_default_id = mapping_id

    def edit_default_cost_mapping(self):
        """Updates the mapping currently loaded in the form."""
        if not hasattr(self, 'editing_default_id') or self.editing_default_id is None:
            QMessageBox.warning(self, "خطا", "ابتدا یک ردیف را با دابل کلیک انتخاب کنید.")
            return
        cat = self.def_cat_combo.currentText()
        val = self.def_value_combo.currentText().strip()
        cost_field = self.def_cost_field_combo.currentText()
        cost = self.def_cost_spin.value()
        try:
            self.db.update_default_mapping(self.editing_default_id, cat, val, cost_field, cost)
            self.load_default_costs_table()
            self.populate_default_value_combo(cat)
            self.editing_default_id = None
        except Exception as err:
            QMessageBox.critical(self, "خطا", f"ویرایش با خطا مواجه شد:\n{err}")

    def delete_default_cost_mapping(self):
        """Deletes the mapping selected in the table."""
        row = self.defaults_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "خطا", "لطفاً یک ردیف را انتخاب کنید.")
            return
        id_item = self.defaults_table.item(row, 0)
        mapping_id = id_item.data(Qt.UserRole)
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
        """Looks up a default cost mapping and fills the target cost field."""
        if not selected_text:
            return
        try:
            mapping = self.db.get_default_cost(category_name, selected_text)
            if mapping:
                cost_field = mapping['target_cost_field']
                cost_value = mapping['default_cost']
                if cost_field in self.cost_inputs:
                    self.cost_inputs[cost_field].setValue(cost_value)
        except Exception as err:
            print("Error applying default cost:", err)
            
            
    def import_default_prices(self):
        """Loops through all dynamic combos, reads their current text, and fills the associated default cost if a mapping exists."""
        category_map = {
            'نوع کاغذ متن': 'نوع کاغذ متن',
            'نوع چاپ متن': 'نوع چاپ متن',
            'نوع رنگ متن': 'نوع رنگ متن',
            'نوع زینک متن': 'نوع زینک متن',
            'نوع کاغذ جلد': 'نوع کاغذ جلد',
            'نوع چاپ جلد': 'نوع چاپ جلد',
            'نوع رنگ جلد': 'نوع رنگ جلد',
            'نوع زینک جلد': 'نوع زینک جلد',
        }
        items = []
        for category, widget_key in category_map.items():
            text = self.inputs[widget_key].currentText().strip()
            if text:
                items.append((category, text))
        if not items:
            QMessageBox.information(self, "اطلاعات", "هیچ تطابقی یافت نشد.")
            return
        try:
            mappings = self.db.get_default_costs_batch(items)
            updated_count = 0
            for mapping in mappings:
                cost_field = mapping['target_cost_field']
                if cost_field in self.cost_inputs:
                    self.cost_inputs[cost_field].setValue(mapping['default_cost'])
                    updated_count += 1
        except Exception as err:
            print("Error importing defaults:", err)
            return
        if updated_count > 0:
            QMessageBox.information(self, "موفقیت", f"{updated_count} قیمت پایه‌ای بارگذاری شد.")
        else:
            QMessageBox.information(self, "اطلاعات", "هیچ تطابقی یافت نشد.")
    
    def suggest_optimal_layout(self):
        qate = self.inputs['قطع'].currentText()
        total_pages = self.total_pages_spin.value()

        paper_size_str = self.paper_size_combo.currentText().replace('×', 'x')
        book_w = self.book_width_spin.value()
        book_h = self.book_height_spin.value()

        layout = self.calculator.suggest_layout(
            qate, total_pages,
            book_w=book_w, book_h=book_h,
            paper_size_str=paper_size_str,
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

        if layout['orientation_label']:
            self.orientation_label.setText(layout['orientation_label'])
        else:
            self.orientation_label.setText('')

        if layout['is_custom'] and layout['default_dims'] and layout['default_dims'][0] is not None:
            if self.book_width_spin.value() == self.book_width_spin.minimum():
                self.book_width_spin.setValue(layout['default_dims'][0])
                self.book_height_spin.setValue(layout['default_dims'][1])

        multiplier = 2 if self.double_sided_matn_chk.isChecked() else 1
        self.form_matn_spin.setValue(layout['sheets_per_book'] * multiplier)
        self.lbl_optimal_paper.setText(
            f"کاغذ بهینه: {layout['paper_size']} | ورق مصرفی هر جلد: {layout['sheets_per_book']}"
        )
            
            
            
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    app.setStyle("Fusion")
    
    style_path = os.path.join(os.path.dirname(__file__), "style.qss")
    if os.path.exists(style_path):
        with open(style_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    else:
        app.setStyleSheet("""
            QWidget { font-family: 'Tahoma', 'IRANSans', sans-serif; font-size: 14px; }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { padding: 5px; }
            QSpinBox, QDoubleSpinBox { text-align: center; }
        """)

    window = BookCostCalculator()
    window.show()
    sys.exit(app.exec())