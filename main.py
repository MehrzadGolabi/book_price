import sys
import os
from datetime import datetime
import jdatetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QScrollArea, QWidget, QVBoxLayout,
                               QTabWidget, QFormLayout, QLineEdit, QComboBox,
                               QPushButton, QToolBar, QSpinBox, QDoubleSpinBox, 
                               QLabel, QMessageBox, QHBoxLayout, QTableWidget, QHeaderView, QFileDialog, QCheckBox, QTableWidgetItem, QInputDialog, QDialog, QDialogButtonBox)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QAction, QFontDatabase, QShortcut, QKeySequence
import sqlite3
import configparser
# Matplotlib imports
import matplotlib
matplotlib.use('QtAgg')
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
def get_db_config():
    """Reads database config from config.ini."""
    # Default config
    default_config = {
        'filename': 'book_publishing.db'
    }

    # Determine the path of config.ini (same directory as the executable/script)
    if getattr(sys, 'frozen', False):
        # Running as a PyInstaller bundle
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))
    
    config_path = os.path.join(app_dir, 'config.ini')

    config = configparser.ConfigParser()
    if os.path.exists(config_path):
        config.read(config_path, encoding='utf-8')
        if 'database' in config:
            if 'filename' in config['database']:
                default_config['filename'] = config['database']['filename']

    return default_config

DELETE_PASSWORD = "admin"

DB_CONFIG = get_db_config()

class BookCostCalculator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("نرم افزار محاسبه و مدیریت هزینه‌های چاپ کتاب")
        self.setGeometry(100, 100, 1100, 800)
        
        # VERY IMPORTANT: Set the entire application to Right-To-Left for Farsi
        self.setLayoutDirection(Qt.RightToLeft)
        
        self.db_conn = None
        self.connect_db()

        self.init_ui()

    def connect_db(self):
            try:
                self.db_conn = sqlite3.connect(DB_CONFIG['filename'])
                self.db_conn.row_factory = sqlite3.Row
                self.cursor = self.db_conn.cursor()

                # Create ALL necessary tables for the standalone SQLite app
                self.cursor.executescript("""
                    CREATE TABLE IF NOT EXISTS categories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        category_name TEXT NOT NULL,
                        item_value TEXT NOT NULL,
                        UNIQUE(category_name, item_value)
                    );

                    CREATE TABLE IF NOT EXISTS paper_calculations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        paper_type TEXT NOT NULL,
                        formula_type TEXT NOT NULL,
                        weight REAL,
                        height REAL,
                        length REAL,
                        bundle_count INTEGER,
                        bundle_weight REAL,
                        price REAL,
                        unit_price REAL
                    );

                    CREATE TABLE IF NOT EXISTS projects (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        subtitle TEXT,
                        creation_date DATE NOT NULL,
                        qate TEXT,
                        tiraj INTEGER NOT NULL,
                        royalty_percent REAL,
                        total_cost REAL,
                        single_book_cost REAL
                    );

                    CREATE TABLE IF NOT EXISTS project_details (
                        project_id INTEGER PRIMARY KEY,
                        noeh_kaghaz_matn TEXT,
                        noeh_chap_matn TEXT,
                        noeh_rang_matn TEXT,
                        noeh_zink_matn TEXT,
                        noeh_kaghaz_jeld TEXT,
                        noeh_chap_jeld TEXT,
                        noeh_rang_jeld TEXT,
                        noeh_zink_jeld TEXT,
                        hazineh_talif REAL DEFAULT 0,
                        hazineh_tarjomeh REAL DEFAULT 0,
                        hazineh_tasvir REAL DEFAULT 0,
                        hazineh_virayesh REAL DEFAULT 0,
                        hazineh_tarahi_jeld REAL DEFAULT 0,
                        hazineh_modiriat_atelieh REAL DEFAULT 0,
                        hazineh_zink REAL DEFAULT 0,
                        hazineh_chap_matn REAL DEFAULT 0,
                        hazineh_chap_jeld REAL DEFAULT 0,
                        hazineh_kaghaz_matn REAL DEFAULT 0,
                        hazineh_kaghaz_jeld REAL DEFAULT 0,
                        hazineh_rokesh_salfon REAL DEFAULT 0,
                        hazineh_moghava_maghzi REAL DEFAULT 0,
                        hazineh_ghaleb_letterpress REAL DEFAULT 0,
                        hazineh_ghaleb_diecut REAL DEFAULT 0,
                        hazineh_khat_ta REAL DEFAULT 0,
                        hazineh_malzomat REAL DEFAULT 0,
                        hazineh_jeldsazi REAL DEFAULT 0,
                        hazineh_sahafi REAL DEFAULT 0,
                        hazineh_boresh_bastebandi REAL DEFAULT 0,
                        hazineh_haml_naghl REAL DEFAULT 0,
                        hazineh_montaj REAL DEFAULT 0,
                        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS default_cost_mappings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        category_name TEXT NOT NULL,
                        item_value TEXT NOT NULL,
                        target_cost_field TEXT NOT NULL,
                        default_cost REAL NOT NULL
                    );
                """)
                self.db_conn.commit()
            except sqlite3.Error as err:
                QMessageBox.critical(
                    self, "خطای دیتابیس",
                    f"ارتباط با دیتابیس برقرار نشد.\nلطفاً فایل config.ini را بررسی کنید.\n\n{err}"
                )
                sys.exit(1)


    def init_ui(self):
        # 1. Setup Toolbar
        toolbar = QToolBar("نوار ابزار اصلی")
        self.addToolBar(toolbar)
        
        save_action = QAction("ذخیره پروژه", self)
        save_action.triggered.connect(self.save_project_to_db)
        
        exit_action = QAction("خروج", self)
        exit_action.triggered.connect(self.close)
        
        open_action = QAction("بازکردن پروژه", self)
        open_action.triggered.connect(self.load_selected_project)
        toolbar.addAction(open_action)
        
        delete_action = QAction("حذف پروژه", self)
        delete_action.triggered.connect(self.delete_project)
        toolbar.addAction(delete_action)
        
        import_defaults_action = QAction("دریافت قیمت‌های پایه", self)
        import_defaults_action.triggered.connect(self.import_default_prices)
        toolbar.addAction(import_defaults_action)
        
        toolbar.addAction(save_action)
        toolbar.addAction(exit_action)

        # 2. Setup Tabs
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Create Tab Widgets
        self.tab_project = QWidget()
        self.tab_details = QWidget()
        self.tab_calc = QWidget()
        self.tab_report = QWidget()
        self.tab_paper_calc = QWidget()
        self.tab_defaults = QWidget()

        self.tabs.addTab(self.tab_project, "مدیریت پروژه‌ها")
        self.tabs.addTab(self.tab_details, "ورود اطلاعات و هزینه‌ها")
        self.tabs.addTab(self.tab_calc, "محاسبات نهایی")
        self.tabs.addTab(self.tab_report, "گزارش‌گیری (PDF)")
        self.tabs.addTab(self.tab_paper_calc, "محاسبات پیش‌پردازش کاغذ")
        self.tabs.addTab(self.tab_defaults, "مدیریت قیمت‌های پایه")

        self.setup_project_tab()
        self.setup_details_tab()
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
        
        new_project_btn = QPushButton("ایجاد پروژه جدید")
        new_project_btn.clicked.connect(self.new_project)   # was: lambda: self.tabs.setCurrentIndex(1)
        
        layout.addLayout(search_layout)
        layout.addWidget(self.project_table)
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

        # Dictionaries to hold our UI inputs so we can read them later
        self.inputs = {}

        # Basic Info
        self.inputs['عنوان کتاب'] = QLineEdit()
        self.inputs['عنوان کتاب'].setPlaceholderText("عنوان کتاب را وارد کنید")
        self.inputs['زیر عنوان کتاب'] = QLineEdit()
        self.inputs['زیر عنوان کتاب'].setPlaceholderText("(اختیاری)")
        
        # Auto-generating Date (Persian/Jalali)
        self.inputs['تاریخ'] = QLineEdit()
        
        # دریافت تاریخ امروز به صورت شمسی و تبدیل آن به رشته
        today_jalali = jdatetime.date.today()
        self.inputs['تاریخ'].setText(today_jalali.strftime("%1400-%m-%d").replace("1400", str(today_jalali.year))) 
        # یا به سادگی:
        self.inputs['تاریخ'].setText(today_jalali.strftime("%Y/%m/%d"))
        
        self.inputs['تاریخ'].setReadOnly(True) # کاربر نباید به صورت دستی آن را تغییر دهد

        self.inputs['قطع'] = QComboBox()
        self.inputs['قطع'].addItems(["جیبی", "رقعی", "وزیری", "خشتی", "رحلی کوچک", "رحلی بزرگ", "بیاضی بزرگ", "سلطانی"])
        
        self.inputs['تیراژ'] = QSpinBox()
        self.inputs['تیراژ'].setMaximum(100000)

        # Dynamic "نوع" (Type) Categories
        dynamic_types = ["نوع کاغذ متن", "نوع چاپ متن", "نوع رنگ متن", "نوع زینک متن", 
                         "نوع کاغذ جلد", "نوع چاپ جلد", "نوع رنگ جلد", "نوع زینک جلد"]
        
        # Pre-fetch all categories from db to avoid N+1 queries
        category_items = {dtype: [] for dtype in dynamic_types}
        if self.db_conn:
            try:
                self.cursor.execute("SELECT category_name, item_value FROM categories")
                for row in self.cursor.fetchall():
                    if row['category_name'] in category_items:
                        category_items[row['category_name']].append(row['item_value'])
            except Exception as e:
                print("Error pre-fetching categories:", e)

        for dtype in dynamic_types:
            combo = QComboBox()
            combo.setEditable(True) # Allows user to type new values!
            combo.setInsertPolicy(QComboBox.InsertAtBottom)
            combo.addItems(category_items[dtype])
            self.inputs[dtype] = combo

        # Costs (هزینه)
        cost_types = [
            "هزینه تالیف", "هزینه ترجمه", "هزینه تصویرگری", "هزینه ویرایش", 
            "هزینه طراحی جلد", "هزینه مديريت آتليه", "هزینه زینک", "هزینه چاپ متن", 
            "هزینه چاپ جلد", "هزینه کاغذ متن", "هزینه کاغذ جلد", "هزینه روکش سلفون", 
            "هزینه مقوای مغذی", "هزینه قالب لترپرس", "هزینه قالب دايكات", "هزینه خط تا", 
            "هزینه ملزومات", "هزینه جلدسازی", "هزینه صحافی", "هزینه برش و بسته‌بندی", 
            "هزینه حمل و نقل", "هزینه مونتاژ"
        ]

        self.cost_inputs = {}
        for ctype in cost_types:
            spin = QDoubleSpinBox()
            spin.setMaximum(9999999999.99) # Handle large currency values
            spin.setGroupSeparatorShown(True) # Adds commas to large numbers
            spin.setDecimals(0)
            spin.lineEdit().setAlignment(Qt.AlignCenter) 
            self.cost_inputs[ctype] = spin
            
        self.royalty_input = QDoubleSpinBox()
        self.royalty_input.setSuffix(" %")
        self.royalty_input.setMaximum(100.0)
        self.royalty_input.setDecimals(0)
        self.royalty_input.lineEdit().setAlignment(Qt.AlignCenter)

        # Add to form layout
        form_layout.addRow("عنوان کتاب:", self.inputs['عنوان کتاب'])
        form_layout.addRow("تاریخ:", self.inputs['تاریخ'])
        form_layout.addRow("تیراژ:", self.inputs['تیراژ'])
        form_layout.addRow("---", QLabel("--- ویژگی‌ها ---"))
        for k, v in self.inputs.items():
            if k not in ['عنوان کتاب', 'تاریخ', 'تیراژ'] and isinstance(v, QComboBox):
                form_layout.addRow(k + ":", v)
                
        form_layout.addRow("---", QLabel("--- هزینه‌ها (تومان) ---"))
        for k, v in self.cost_inputs.items():
            form_layout.addRow(k + ":", v)
            
        form_layout.addRow("حق تالیف درصدی:", self.royalty_input)

        calc_btn = QPushButton("ثبت اطلاعات و انجام محاسبات")
        calc_btn.clicked.connect(self.perform_calculations)
        
        scroll_layout.addLayout(form_layout)
        scroll_layout.addWidget(calc_btn)
        scroll_area.setWidget(scroll_content)
        main_layout = QVBoxLayout(self.tab_details)
        main_layout.addWidget(scroll_area)


    def perform_calculations(self):
        # 1. Sum all costs
        total_costs = sum([spin.value() for spin in self.cost_inputs.values()])
        
        # 2. Apply royalty percentage
        royalty_percent = self.royalty_input.value()
        final_price = total_costs * (1 + (royalty_percent / 100))
        
        # 3. Divide by Tiraj (Print Run)
        tiraj = self.inputs['تیراژ'].value()
        if tiraj == 0:
            QMessageBox.warning(self, "خطا", "تیراژ نمی‌تواند صفر باشد!")
            return
            
        single_book_price = final_price / tiraj

        # 4. Save new "Types" to Database if user typed them in
        self.save_new_dynamic_types()

        # Update the Calculation Tab UI
        self.lbl_final_total.setText(f"{final_price:,.0f}")
        self.lbl_single_price.setText(f"{single_book_price:,.0f}")
        
        # Update the chart
        self.update_chart()
        
        # Switch to calculation tab
        self.tabs.setCurrentIndex(2)
        
        #save the project to the database
        self.save_project_to_db()

    def save_new_dynamic_types(self):
        # Checks all ComboBoxes. If text isn't in the list, save it to DB.
        for category, widget in self.inputs.items():
            if isinstance(widget, QComboBox) and widget.isEditable():
                current_text = widget.currentText()
                if current_text and widget.findText(current_text) == -1:
                    # It's a new entry, save to DB
                    try:
                        self.cursor.execute(
                            "INSERT OR IGNORE INTO categories (category_name, item_value) VALUES (?, ?)",
                            (category, current_text)
                        )
                        self.db_conn.commit()
                        widget.addItem(current_text) # Add to current dropdown
                    except Exception as e:
                        print("Error saving category:", e)

    def setup_calc_tab(self):
            layout = QVBoxLayout()
            
            # بخش نمایش قیمت‌ها
            prices_layout = QFormLayout()
            self.lbl_final_total = QLabel("0")
            self.lbl_single_price = QLabel("0")
            self.lbl_final_total.setStyleSheet("font-size: 24px; font-weight: bold; color: darkred;")
            self.lbl_single_price.setStyleSheet("font-size: 24px; font-weight: bold; color: darkgreen;")
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

        try:
            # 1. Check if we are updating an existing project
            if hasattr(self, 'current_project_id') and self.current_project_id is not None:
                # --- UPDATE existing project ---
                query_projects = """
                    UPDATE projects SET
                        title = ?, subtitle = ?, creation_date = ?, qate = ?,
                        tiraj = ?, royalty_percent = ?, total_cost = ?, single_book_cost = ?
                    WHERE id = ?
                """
                val_projects = (
                    title,
                    get_val('زیر عنوان کتاب'),
                    get_val('تاریخ'),
                    get_val('قطع'),
                    get_val('تیراژ'),
                    self.royalty_input.value(),
                    total_cost,
                    single_cost,
                    self.current_project_id
                )
                self.cursor.execute(query_projects, val_projects)

                # Update project_details
                query_details = """
                    UPDATE project_details SET
                        noeh_kaghaz_matn = ?, noeh_chap_matn = ?, noeh_rang_matn = ?, noeh_zink_matn = ?,
                        noeh_kaghaz_jeld = ?, noeh_chap_jeld = ?, noeh_rang_jeld = ?, noeh_zink_jeld = ?,
                        hazineh_talif = ?, hazineh_tarjomeh = ?, hazineh_tasvir = ?, hazineh_virayesh = ?,
                        hazineh_tarahi_jeld = ?, hazineh_modiriat_atelieh = ?, hazineh_zink = ?,
                        hazineh_chap_matn = ?, hazineh_chap_jeld = ?, hazineh_kaghaz_matn = ?,
                        hazineh_kaghaz_jeld = ?, hazineh_rokesh_salfon = ?, hazineh_moghava_maghzi = ?,
                        hazineh_ghaleb_letterpress = ?, hazineh_ghaleb_diecut = ?, hazineh_khat_ta = ?,
                        hazineh_malzomat = ?, hazineh_jeldsazi = ?, hazineh_sahafi = ?,
                        hazineh_boresh_bastebandi = ?, hazineh_haml_naghl = ?, hazineh_montaj = ?
                    WHERE project_id = ?
                """
                val_details = (
                    get_val('نوع کاغذ متن'), get_val('نوع چاپ متن'), get_val('نوع رنگ متن'), get_val('نوع زینک متن'),
                    get_val('نوع کاغذ جلد'), get_val('نوع چاپ جلد'), get_val('نوع رنگ جلد'), get_val('نوع زینک جلد'),
                    self.cost_inputs['هزینه تالیف'].value(), self.cost_inputs['هزینه ترجمه'].value(),
                    self.cost_inputs['هزینه تصویرگری'].value(), self.cost_inputs['هزینه ویرایش'].value(),
                    self.cost_inputs['هزینه طراحی جلد'].value(), self.cost_inputs['هزینه مديريت آتليه'].value(),
                    self.cost_inputs['هزینه زینک'].value(), self.cost_inputs['هزینه چاپ متن'].value(),
                    self.cost_inputs['هزینه چاپ جلد'].value(), self.cost_inputs['هزینه کاغذ متن'].value(),
                    self.cost_inputs['هزینه کاغذ جلد'].value(), self.cost_inputs['هزینه روکش سلفون'].value(),
                    self.cost_inputs['هزینه مقوای مغذی'].value(), self.cost_inputs['هزینه قالب لترپرس'].value(),
                    self.cost_inputs['هزینه قالب دايكات'].value(), self.cost_inputs['هزینه خط تا'].value(),
                    self.cost_inputs['هزینه ملزومات'].value(), self.cost_inputs['هزینه جلدسازی'].value(),
                    self.cost_inputs['هزینه صحافی'].value(), self.cost_inputs['هزینه برش و بسته‌بندی'].value(),
                    self.cost_inputs['هزینه حمل و نقل'].value(), self.cost_inputs['هزینه مونتاژ'].value(),
                    self.current_project_id
                )
                self.cursor.execute(query_details, val_details)

            else:
                # --- INSERT new project ---
                query_projects = """
                    INSERT INTO projects 
                    (title, subtitle, creation_date, qate, tiraj, royalty_percent, total_cost, single_book_cost)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """
                val_projects = (
                    title,
                    get_val('زیر عنوان کتاب'),
                    get_val('تاریخ'),
                    get_val('قطع'),
                    get_val('تیراژ'),
                    self.royalty_input.value(),
                    total_cost,
                    single_cost
                )
                self.cursor.execute(query_projects, val_projects)
                project_id = self.cursor.lastrowid

                # Insert project_details
                query_details = """
                    INSERT INTO project_details (
                        project_id, noeh_kaghaz_matn, noeh_chap_matn, noeh_rang_matn, noeh_zink_matn,
                        noeh_kaghaz_jeld, noeh_chap_jeld, noeh_rang_jeld, noeh_zink_jeld,
                        hazineh_talif, hazineh_tarjomeh, hazineh_tasvir, hazineh_virayesh,
                        hazineh_tarahi_jeld, hazineh_modiriat_atelieh, hazineh_zink, hazineh_chap_matn,
                        hazineh_chap_jeld, hazineh_kaghaz_matn, hazineh_kaghaz_jeld, hazineh_rokesh_salfon,
                        hazineh_moghava_maghzi, hazineh_ghaleb_letterpress, hazineh_ghaleb_diecut,
                        hazineh_khat_ta, hazineh_malzomat, hazineh_jeldsazi, hazineh_sahafi,
                        hazineh_boresh_bastebandi, hazineh_haml_naghl, hazineh_montaj
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                """
                val_details = (
                    project_id,
                    get_val('نوع کاغذ متن'), get_val('نوع چاپ متن'), get_val('نوع رنگ متن'), get_val('نوع زینک متن'),
                    get_val('نوع کاغذ جلد'), get_val('نوع چاپ جلد'), get_val('نوع رنگ جلد'), get_val('نوع زینک جلد'),
                    self.cost_inputs['هزینه تالیف'].value(), self.cost_inputs['هزینه ترجمه'].value(),
                    self.cost_inputs['هزینه تصویرگری'].value(), self.cost_inputs['هزینه ویرایش'].value(),
                    self.cost_inputs['هزینه طراحی جلد'].value(), self.cost_inputs['هزینه مديريت آتليه'].value(),
                    self.cost_inputs['هزینه زینک'].value(), self.cost_inputs['هزینه چاپ متن'].value(),
                    self.cost_inputs['هزینه چاپ جلد'].value(), self.cost_inputs['هزینه کاغذ متن'].value(),
                    self.cost_inputs['هزینه کاغذ جلد'].value(), self.cost_inputs['هزینه روکش سلفون'].value(),
                    self.cost_inputs['هزینه مقوای مغذی'].value(), self.cost_inputs['هزینه قالب لترپرس'].value(),
                    self.cost_inputs['هزینه قالب دايكات'].value(), self.cost_inputs['هزینه خط تا'].value(),
                    self.cost_inputs['هزینه ملزومات'].value(), self.cost_inputs['هزینه جلدسازی'].value(),
                    self.cost_inputs['هزینه صحافی'].value(), self.cost_inputs['هزینه برش و بسته‌بندی'].value(),
                    self.cost_inputs['هزینه حمل و نقل'].value(), self.cost_inputs['هزینه مونتاژ'].value()
                )
                self.cursor.execute(query_details, val_details)

                # Store the new ID so subsequent saves update it
                self.current_project_id = project_id

            # Commit and refresh project list
            self.db_conn.commit()
            self.load_projects()  # reload the table to show changes
            QMessageBox.information(self, "موفقیت", "اطلاعات پروژه با موفقیت ذخیره شد!")

        except sqlite3.Error as err:
            self.db_conn.rollback()
            QMessageBox.critical(self, "خطای ذخیره‌سازی", f"مشکلی در ذخیره اطلاعات پیش آمد:\n{err}")
        
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
            if filter_text:
                query = "SELECT id, title, creation_date, tiraj FROM projects WHERE title LIKE ? ORDER BY id DESC"
                self.cursor.execute(query, ('%' + filter_text + '%',))
            else:
                query = "SELECT id, title, creation_date, tiraj FROM projects ORDER BY id DESC"
                self.cursor.execute(query)
            
            results = self.cursor.fetchall()
            
            self.project_table.setUpdatesEnabled(False)
            self.project_table.setRowCount(len(results))
            for row_idx, row_data in enumerate(results):
                self.project_table.setItem(row_idx, 0, QTableWidgetItem(str(row_data['id'])))
                self.project_table.setItem(row_idx, 1, QTableWidgetItem(row_data['title']))
                self.project_table.setItem(row_idx, 2, QTableWidgetItem(row_data['creation_date']))
                self.project_table.setItem(row_idx, 3, QTableWidgetItem(str(row_data['tiraj'])))
            self.project_table.setUpdatesEnabled(True)
        except sqlite3.Error as err:
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
            # Fetch main project info
            self.cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
            project = self.cursor.fetchone()
            if not project:
                QMessageBox.warning(self, "خطا", "پروژه‌ای با این شناسه یافت نشد.")
                return

            # Fetch detailed info
            self.cursor.execute("SELECT * FROM project_details WHERE project_id = ?", (project_id,))
            details = self.cursor.fetchone()

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
                    'هزینه مونتاژ': 'hazineh_montaj'
                }
                for persian_key, col_name in cost_mapping.items():
                    if col_name in details and details[col_name] is not None:
                        self.cost_inputs[persian_key].setValue(float(details[col_name]))

            # Store the project ID for possible update later
            self.current_project_id = project_id

            self.tabs.setCurrentIndex(1)  # Switch to details tab
            QMessageBox.information(self, "بارگذاری", "پروژه با موفقیت بارگذاری شد. پس از ویرایش می‌توانید ذخیره کنید.")

        except sqlite3.Error as err:
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
        # Reset the current project ID
        self.current_project_id = None

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

        # Clear costs
        for spin in self.cost_inputs.values():
            spin.setValue(0.0)

        self.royalty_input.setValue(0.0)

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
        if not ok or password != DELETE_PASSWORD:
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
            # Delete details first (if no ON DELETE CASCADE)
            self.cursor.execute("DELETE FROM project_details WHERE project_id = ?", (project_id,))
            # Delete main project
            self.cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            self.db_conn.commit()

            # 5. Refresh the project table
            self.load_projects()

            # 6. If the deleted project is currently loaded, clear the form
            if hasattr(self, 'current_project_id') and self.current_project_id == project_id:
                self.new_project()  # use the method we already created to reset fields

            QMessageBox.information(self, "موفقیت", "پروژه با موفقیت حذف شد.")

        except sqlite3.Error as err:
            self.db_conn.rollback()
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
        form.addRow("قیمت / قیمت بند (تومان):", self.paper_price_spin)

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
        elif formula == "قیمت هر بند و تعداد در بند":
            self.paper_weight_spin.setEnabled(False)
            self.paper_height_spin.setEnabled(False)
            self.paper_length_spin.setEnabled(False)
            self.paper_bundle_count_spin.setEnabled(True)
            self.paper_bundle_weight_spin.setEnabled(True)
            self.paper_price_spin.setEnabled(True)
        else: # دستی
            self.paper_weight_spin.setEnabled(False)
            self.paper_height_spin.setEnabled(False)
            self.paper_length_spin.setEnabled(False)
            self.paper_bundle_count_spin.setEnabled(False)
            self.paper_bundle_weight_spin.setEnabled(False)
            self.paper_price_spin.setEnabled(True)

    def calculate_paper_unit_price(self):
        formula = self.paper_formula_combo.currentText()
        price = self.paper_price_spin.value()
        unit_price = 0

        if formula == "ابعاد، وزن و قیمت (هر واحد)":
            height = self.paper_height_spin.value()
            length = self.paper_length_spin.value()
            weight = self.paper_weight_spin.value()
            if height > 0 and length > 0 and weight > 0:
                unit_price = ((height * length) * weight / 10000) * (price / 1000)
        elif formula == "قیمت هر بند و تعداد در بند":
            count = self.paper_bundle_count_spin.value()
            if count > 0:
                unit_price = price / count
        else: # دستی
            unit_price = price

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
            if hasattr(self, 'editing_paper_calc_id') and self.editing_paper_calc_id is not None:
                self.cursor.execute("""
                    UPDATE paper_calculations
                    SET paper_type=?, formula_type=?, weight=?, height=?, length=?,
                        bundle_count=?, bundle_weight=?, price=?, unit_price=?
                    WHERE id=?
                """, (paper_type, formula, weight, height, length, bundle_count, bundle_weight, price, unit_price, self.editing_paper_calc_id))
            else:
                self.cursor.execute("""
                    INSERT INTO paper_calculations
                    (paper_type, formula_type, weight, height, length, bundle_count, bundle_weight, price, unit_price)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (paper_type, formula, weight, height, length, bundle_count, bundle_weight, price, unit_price))

            self.db_conn.commit()
            self.load_paper_calculations()
            self.editing_paper_calc_id = None
        except sqlite3.Error as err:
            QMessageBox.critical(self, "خطا", f"ذخیره محاسبه با خطا مواجه شد:\n{err}")

    def load_paper_calculations(self):
        try:
            self.cursor.execute("SELECT * FROM paper_calculations ORDER BY id DESC")
            rows = self.cursor.fetchall()
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
        except sqlite3.Error as err:
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
                self.cursor.execute("DELETE FROM paper_calculations WHERE id=?", (calc_id,))
                self.db_conn.commit()
                self.load_paper_calculations()
                self.editing_paper_calc_id = None
            except sqlite3.Error as err:
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
                # Check if it already exists
                self.cursor.execute("SELECT id FROM default_cost_mappings WHERE category_name=? AND item_value=?", (cat, val))
                existing = self.cursor.fetchone()

                if existing:
                    self.cursor.execute("UPDATE default_cost_mappings SET target_cost_field=?, default_cost=? WHERE id=?",
                                        (field, unit_price, existing['id']))
                else:
                    self.cursor.execute("INSERT INTO default_cost_mappings (category_name, item_value, target_cost_field, default_cost) VALUES (?, ?, ?, ?)",
                                        (cat, val, field, unit_price))

                # Add to categories if needed
                self.cursor.execute("INSERT OR IGNORE INTO categories (category_name, item_value) VALUES (?, ?)", (cat, val))

                self.db_conn.commit()
                self.load_default_costs_table()
                self.populate_default_value_combo(self.def_cat_combo.currentText())
                QMessageBox.information(self, "موفقیت", "انتقال به قیمت‌های پایه با موفقیت انجام شد.")
                self.tabs.setCurrentIndex(5) # Switch to defaults tab
            except sqlite3.Error as err:
                QMessageBox.critical(self, "خطا", f"انتقال با خطا مواجه شد:\n{err}")

    def setup_default_costs_tab(self):
        layout = QVBoxLayout()

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
        self.def_cost_field_combo.addItems(list(self.cost_inputs.keys()))
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

    def populate_default_value_combo(self, category_name):
        """Fills the value combo with existing items from the chosen category."""
        self.def_value_combo.clear()
        if not self.db_conn:
            return
        try:
            self.cursor.execute(
                "SELECT item_value FROM categories WHERE category_name = ?", (category_name,)
            )
            items = [row['item_value'] for row in self.cursor.fetchall()]
            self.def_value_combo.addItems(items)
        except Exception as e:
            print("Error populating value combo:", e)

    def load_default_costs_table(self):
        """Reloads the table showing all default cost mappings."""
        try:
            self.cursor.execute(
                "SELECT id, category_name, item_value, target_cost_field, default_cost "
                "FROM default_cost_mappings ORDER BY category_name, item_value"
            )
            rows = self.cursor.fetchall()
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
        except sqlite3.Error as err:
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
            self.cursor.execute(
                "INSERT INTO default_cost_mappings (category_name, item_value, target_cost_field, default_cost) "
                "VALUES (?, ?, ?, ?)",
                (cat, val, cost_field, cost)
            )
            self.db_conn.commit()
            self.load_default_costs_table()
            # also add the new item_value to the categories table if not present
            self.cursor.execute(
                "INSERT OR IGNORE INTO categories (category_name, item_value) VALUES (?, ?)",
                (cat, val)
            )
            self.db_conn.commit()
            # refresh the value combo
            self.populate_default_value_combo(cat)
        except sqlite3.Error as err:
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
            self.cursor.execute(
                "UPDATE default_cost_mappings SET category_name=?, item_value=?, "
                "target_cost_field=?, default_cost=? WHERE id=?",
                (cat, val, cost_field, cost, self.editing_default_id)
            )
            self.db_conn.commit()
            self.load_default_costs_table()
            self.populate_default_value_combo(cat)
            self.editing_default_id = None
        except sqlite3.Error as err:
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
            self.cursor.execute("DELETE FROM default_cost_mappings WHERE id = ?", (mapping_id,))
            self.db_conn.commit()
            self.load_default_costs_table()
        except sqlite3.Error as err:
            QMessageBox.critical(self, "خطا", f"حذف با خطا مواجه شد:\n{err}")
            
            
    def apply_default_cost(self, category_name, selected_text):
        """Looks up a default cost mapping and fills the target cost field."""
        if not selected_text or not self.db_conn:
            return
        try:
            self.cursor.execute(
                "SELECT target_cost_field, default_cost FROM default_cost_mappings "
                "WHERE category_name = ? AND item_value = ?",
                (category_name, selected_text)
            )
            mapping = self.cursor.fetchone()
            if mapping:
                cost_field = mapping['target_cost_field']
                cost_value = mapping['default_cost']
                if cost_field in self.cost_inputs:
                    self.cost_inputs[cost_field].setValue(cost_value)
        except sqlite3.Error as err:
            print("Error applying default cost:", err)
            
            
    def import_default_prices(self):
        """Loops through all dynamic combos, reads their current text, and fills the associated default cost if a mapping exists."""
        if not self.db_conn:
            return

        # Map from Persian category name to widget key
        category_map = {
            'نوع کاغذ متن': 'نوع کاغذ متن',
            'نوع چاپ متن': 'نوع چاپ متن',
            'نوع رنگ متن': 'نوع رنگ متن',
            'نوع زینک متن': 'نوع زینک متن',
            'نوع کاغذ جلد': 'نوع کاغذ جلد',
            'نوع چاپ جلد': 'نوع چاپ جلد',
            'نوع رنگ جلد': 'نوع رنگ جلد',
            'نوع زینک جلد': 'نوع زینک جلد'
        }

        updated_count = 0

        # ⚡ Bolt Optimization: Batch queries to avoid N+1 problem inside loop
        # Instead of 8 individual SELECT queries, we collect requirements and
        # run a single database call, improving UI responsiveness.
        query_conditions = []
        query_params = []
        requested_items = [] # Keep track to verify what we asked for

        for category, widget_key in category_map.items():
            widget = self.inputs[widget_key]
            selected_text = widget.currentText().strip()
            if not selected_text:
                continue

            query_conditions.append("(category_name = ? AND item_value = ?)")
            query_params.extend([category, selected_text])
            requested_items.append((category, selected_text))

        if query_conditions:
            try:
                query = f"""
                    SELECT category_name, item_value, target_cost_field, default_cost
                    FROM default_cost_mappings
                    WHERE {' OR '.join(query_conditions)}
                """
                self.cursor.execute(query, tuple(query_params))
                mappings = self.cursor.fetchall()

                # Apply results
                for mapping in mappings:
                    cost_field = mapping['target_cost_field']
                    cost_value = mapping['default_cost']
                    if cost_field in self.cost_inputs:
                        self.cost_inputs[cost_field].setValue(cost_value)
                        updated_count += 1

            except sqlite3.Error as err:
                print("Error importing default:", err)

        if updated_count > 0:
            QMessageBox.information(self, "موفقیت", f"{updated_count} قیمت پایه‌ای بارگذاری شد.")
        else:
            QMessageBox.information(self, "اطلاعات", "هیچ تطابقی یافت نشد.")
            
            
            
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