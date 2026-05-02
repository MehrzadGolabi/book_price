import sys
import os
from datetime import datetime
import jdatetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QScrollArea, QWidget, QVBoxLayout,
                               QTabWidget, QFormLayout, QLineEdit, QComboBox,
                               QPushButton, QToolBar, QSpinBox, QDoubleSpinBox, 
                               QLabel, QMessageBox, QHBoxLayout, QTableWidget, QHeaderView, QFileDialog, QCheckBox, QTableWidgetItem, QInputDialog)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QAction
import mysql.connector
# Matplotlib imports
import matplotlib
from numpy import dtype
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
import configparser

def get_db_config():
    """Reads database config from config.ini, falls back to hard‑coded defaults."""
    # Default config
    default_config = {
        'host': 'localhost',
        'user': 'book_admin',
        'password': 'book',
        'database': 'book_publishing',
        'charset': 'utf8mb4'
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
            for key in default_config.keys():
                if key in config['database']:
                    default_config[key] = config['database'][key]

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
            self.db_conn = mysql.connector.connect(**DB_CONFIG)
            self.cursor = self.db_conn.cursor(dictionary=True)
        except mysql.connector.Error as err:
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
        self.tab_defaults = QWidget()

        self.tabs.addTab(self.tab_project, "مدیریت پروژه‌ها")
        self.tabs.addTab(self.tab_details, "ورود اطلاعات و هزینه‌ها")
        self.tabs.addTab(self.tab_calc, "محاسبات نهایی")
        self.tabs.addTab(self.tab_report, "گزارش‌گیری (PDF)")
        self.tabs.addTab(self.tab_defaults, "مدیریت قیمت‌های پایه")

        self.setup_project_tab()
        self.setup_details_tab()
        self.setup_calc_tab()
        self.setup_report_tab()
        self.setup_default_costs_tab()

    def setup_project_tab(self):
        layout = QVBoxLayout()
        
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("جستجوی نام کتاب...")
        search_btn = QPushButton("جستجو")
        search_btn.clicked.connect(self.search_projects)           # ← connect search
        
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
        scroll_content.setLayoutDirection(Qt.RightToLeft)
        scroll_layout = QVBoxLayout(scroll_content)

        form_layout = QFormLayout()

        # Dictionaries to hold our UI inputs so we can read them later
        self.inputs = {}

        # Basic Info
        self.inputs['عنوان کتاب'] = QLineEdit()
        self.inputs['زیر عنوان کتاب'] = QLineEdit()
        
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
        
        for dtype in dynamic_types:
            combo = QComboBox()
            combo.setEditable(True) # Allows user to type new values!
            combo.setInsertPolicy(QComboBox.InsertAtBottom)
            self.populate_combo_from_db(combo, dtype)
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


    def populate_combo_from_db(self, combo_widget, category_name):
        # Fetch previously saved types for this specific category
        if self.db_conn:
            self.cursor.execute("SELECT item_value FROM categories WHERE category_name = %s", (category_name,))
            results = self.cursor.fetchall()
            for row in results:
                combo_widget.addItem(row['item_value'])

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

    def save_new_dynamic_types(self):
        # Checks all ComboBoxes. If text isn't in the list, save it to DB.
        for category, widget in self.inputs.items():
            if isinstance(widget, QComboBox) and widget.isEditable():
                current_text = widget.currentText()
                if current_text and widget.findText(current_text) == -1:
                    # It's a new entry, save to DB
                    try:
                        self.cursor.execute(
                            "INSERT IGNORE INTO categories (category_name, item_value) VALUES (%s, %s)", 
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
                        title = %s, subtitle = %s, creation_date = %s, qate = %s,
                        tiraj = %s, royalty_percent = %s, total_cost = %s, single_book_cost = %s
                    WHERE id = %s
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
                        noeh_kaghaz_matn = %s, noeh_chap_matn = %s, noeh_rang_matn = %s, noeh_zink_matn = %s,
                        noeh_kaghaz_jeld = %s, noeh_chap_jeld = %s, noeh_rang_jeld = %s, noeh_zink_jeld = %s,
                        hazineh_talif = %s, hazineh_tarjomeh = %s, hazineh_tasvir = %s, hazineh_virayesh = %s,
                        hazineh_tarahi_jeld = %s, hazineh_modiriat_atelieh = %s, hazineh_zink = %s,
                        hazineh_chap_matn = %s, hazineh_chap_jeld = %s, hazineh_kaghaz_matn = %s,
                        hazineh_kaghaz_jeld = %s, hazineh_rokesh_salfon = %s, hazineh_moghava_maghzi = %s,
                        hazineh_ghaleb_letterpress = %s, hazineh_ghaleb_diecut = %s, hazineh_khat_ta = %s,
                        hazineh_malzomat = %s, hazineh_jeldsazi = %s, hazineh_sahafi = %s,
                        hazineh_boresh_bastebandi = %s, hazineh_haml_naghl = %s, hazineh_montaj = %s
                    WHERE project_id = %s
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
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
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
                        %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
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

        except mysql.connector.Error as err:
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
            
    def write_farsi_text_right_aligned(self, canvas_obj, text, y_pos, font_size=12):
        """تابع کمکی برای نوشتن متن راست‌چین فارسی در PDF"""
        reshaped = arabic_reshaper.reshape(text)
        bidi_text = get_display(reshaped)
        canvas_obj.setFont('FarsiFont', font_size)
        # قرار دادن متن در سمت راست صفحه A4
        canvas_obj.drawRightString(A4[0] - 2*cm, y_pos, bidi_text)
        
    def generate_pdf(self):
        # بررسی وجود فایل فونت
        font_path = "tahoma.ttf"
        if not os.path.exists(font_path):
            QMessageBox.critical(self, "خطا", f"فایل فونت '{font_path}' در کنار برنامه پیدا نشد!\nلطفاً یک فونت فارسی را در پوشه برنامه قرار دهید.")
            return

        # دریافت مسیر ذخیره فایل از کاربر
        file_path, _ = QFileDialog.getSaveFileName(self, "ذخیره گزارش PDF", "", "PDF Files (*.pdf)")
        if not file_path:
            return # کاربر کنسل کرده است

        # ثبت فونت
        pdfmetrics.registerFont(TTFont('FarsiFont', font_path))
        
        c = canvas.Canvas(file_path, pagesize=A4)
        width, height = A4
        y = height - 2 * cm
        
        # تیتر اصلی
        title = f"گزارش برآورد هزینه چاپ کتاب: {self.inputs['عنوان کتاب'].text()}"
        self.write_farsi_text_right_aligned(c, title, y, font_size=18)
        y -= 1.5 * cm
        
        # 1. چاپ اطلاعات اصلی
        if self.chk_basic_info.isChecked():
            c.setLineWidth(1)
            c.line(2*cm, y, width - 2*cm, y)
            y -= 1 * cm
            self.write_farsi_text_right_aligned(c, "--- اطلاعات پایه ---", y, font_size=14)
            y -= 1 * cm
            for key in ['عنوان کتاب', 'زیر عنوان کتاب', 'تاریخ', 'قطع']:
                widget = self.inputs[key]
                val = widget.currentText() if isinstance(widget, QComboBox) else widget.text()
                if val:
                    self.write_farsi_text_right_aligned(c, f"{key}: {val}", y)
                    y -= 0.8 * cm
            
            # تیراژ
            self.write_farsi_text_right_aligned(c, f"تیراژ: {self.inputs['تیراژ'].value()}", y)
            y -= 1.2 * cm

        # 2. چاپ ویژگی‌های فنی
        if self.chk_features.isChecked():
            c.line(2*cm, y, width - 2*cm, y)
            y -= 1 * cm
            self.write_farsi_text_right_aligned(c, "--- ویژگی‌های فنی ---", y, font_size=14)
            y -= 1 * cm
            for key, widget in self.inputs.items():
                if isinstance(widget, QComboBox) and key != 'قطع':
                    val = widget.currentText()
                    if val:
                        self.write_farsi_text_right_aligned(c, f"{key}: {val}", y)
                        y -= 0.8 * cm
                        if y < 3*cm: # ایجاد صفحه جدید در صورت پر شدن
                            c.showPage()
                            y = height - 2*cm
            y -= 0.5 * cm

        # 3. چاپ ریز هزینه‌ها
        if self.chk_costs.isChecked():
            c.line(2*cm, y, width - 2*cm, y)
            y -= 1 * cm
            self.write_farsi_text_right_aligned(c, "--- ریز هزینه‌ها (تومان) ---", y, font_size=14)
            y -= 1 * cm
            
            for key, spin in self.cost_inputs.items():
                if spin.value() > 0:
                    self.write_farsi_text_right_aligned(c, f"{key}: {spin.value():,.0f}", y)
                    y -= 0.8 * cm
                    if y < 3*cm:
                        c.showPage()
                        y = height - 2*cm
                        
            y -= 0.5 * cm
            self.write_farsi_text_right_aligned(c, f"حق تالیف: {self.royalty_input.value()} %", y)
            y -= 1.5 * cm

        # نتایج نهایی در انتهای فایل
        c.line(2*cm, y, width - 2*cm, y)
        y -= 1 * cm
        self.write_farsi_text_right_aligned(c, f"جمع کل هزینه‌ها: {self.lbl_final_total.text()} تومان", y, font_size=16)
        y -= 1 * cm
        self.write_farsi_text_right_aligned(c, f"هزینه تمام شده هر جلد: {self.lbl_single_price.text()} تومان", y, font_size=16)

        c.save()
        QMessageBox.information(self, "موفقیت", "فایل PDF با موفقیت تولید و ذخیره شد.")

    def load_projects(self, filter_text=None):
        try:
            if filter_text:
                query = "SELECT id, title, creation_date, tiraj FROM projects WHERE title LIKE %s ORDER BY id DESC"
                self.cursor.execute(query, ('%' + filter_text + '%',))
            else:
                query = "SELECT id, title, creation_date, tiraj FROM projects ORDER BY id DESC"
                self.cursor.execute(query)
            
            results = self.cursor.fetchall()
            
            self.project_table.setRowCount(0)  # clear previous rows
            for row_idx, row_data in enumerate(results):
                self.project_table.insertRow(row_idx)
                self.project_table.setItem(row_idx, 0, QTableWidgetItem(str(row_data['id'])))
                self.project_table.setItem(row_idx, 1, QTableWidgetItem(row_data['title']))
                self.project_table.setItem(row_idx, 2, QTableWidgetItem(row_data['creation_date']))
                self.project_table.setItem(row_idx, 3, QTableWidgetItem(str(row_data['tiraj'])))
        except mysql.connector.Error as err:
            QMessageBox.warning(self, "خطا", f"بارگذاری پروژه‌ها با خطا مواجه شد:\n{err}")
    
    def search_projects(self):
        search_text = self.search_input.text().strip()
        self.load_projects(search_text if search_text else None)
        
    def open_project(self):
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
            self.cursor.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
            project = self.cursor.fetchone()
            if not project:
                QMessageBox.warning(self, "خطا", "پروژه‌ای با این شناسه یافت نشد.")
                return

            # Fetch detailed info
            self.cursor.execute("SELECT * FROM project_details WHERE project_id = %s", (project_id,))
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

        except mysql.connector.Error as err:
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
            self.cursor.execute("DELETE FROM project_details WHERE project_id = %s", (project_id,))
            # Delete main project
            self.cursor.execute("DELETE FROM projects WHERE id = %s", (project_id,))
            self.db_conn.commit()

            # 5. Refresh the project table
            self.load_projects()

            # 6. If the deleted project is currently loaded, clear the form
            if hasattr(self, 'current_project_id') and self.current_project_id == project_id:
                self.new_project()  # use the method we already created to reset fields

            QMessageBox.information(self, "موفقیت", "پروژه با موفقیت حذف شد.")

        except mysql.connector.Error as err:
            self.db_conn.rollback()
            QMessageBox.critical(self, "خطا", f"حذف پروژه با مشکل مواجه شد:\n{err}")
            
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
                "SELECT item_value FROM categories WHERE category_name = %s", (category_name,)
            )
            for row in self.cursor.fetchall():
                self.def_value_combo.addItem(row['item_value'])
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
            self.defaults_table.setRowCount(0)
            for i, row in enumerate(rows):
                self.defaults_table.insertRow(i)
                self.defaults_table.setItem(i, 0, QTableWidgetItem(row['category_name']))
                self.defaults_table.setItem(i, 1, QTableWidgetItem(row['item_value']))
                self.defaults_table.setItem(i, 2, QTableWidgetItem(row['target_cost_field']))
                cost_item = QTableWidgetItem(f"{row['default_cost']:,.2f}")
                cost_item.setTextAlignment(Qt.AlignCenter)
                self.defaults_table.setItem(i, 3, cost_item)
                # Store the id in the first cell's data for later use
                self.defaults_table.item(i, 0).setData(Qt.UserRole, row['id'])
        except mysql.connector.Error as err:
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
                "VALUES (%s, %s, %s, %s)",
                (cat, val, cost_field, cost)
            )
            self.db_conn.commit()
            self.load_default_costs_table()
            # also add the new item_value to the categories table if not present
            self.cursor.execute(
                "INSERT IGNORE INTO categories (category_name, item_value) VALUES (%s, %s)",
                (cat, val)
            )
            self.db_conn.commit()
            # refresh the value combo
            self.populate_default_value_combo(cat)
        except mysql.connector.Error as err:
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
                "UPDATE default_cost_mappings SET category_name=%s, item_value=%s, "
                "target_cost_field=%s, default_cost=%s WHERE id=%s",
                (cat, val, cost_field, cost, self.editing_default_id)
            )
            self.db_conn.commit()
            self.load_default_costs_table()
            self.populate_default_value_combo(cat)
            self.editing_default_id = None
        except mysql.connector.Error as err:
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
            self.cursor.execute("DELETE FROM default_cost_mappings WHERE id = %s", (mapping_id,))
            self.db_conn.commit()
            self.load_default_costs_table()
        except mysql.connector.Error as err:
            QMessageBox.critical(self, "خطا", f"حذف با خطا مواجه شد:\n{err}")
            
            
    def apply_default_cost(self, category_name, selected_text):
        """Looks up a default cost mapping and fills the target cost field."""
        if not selected_text or not self.db_conn:
            return
        try:
            self.cursor.execute(
                "SELECT target_cost_field, default_cost FROM default_cost_mappings "
                "WHERE category_name = %s AND item_value = %s",
                (category_name, selected_text)
            )
            mapping = self.cursor.fetchone()
            if mapping:
                cost_field = mapping['target_cost_field']
                cost_value = mapping['default_cost']
                if cost_field in self.cost_inputs:
                    self.cost_inputs[cost_field].setValue(cost_value)
        except mysql.connector.Error as err:
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
        for category, widget_key in category_map.items():
            widget = self.inputs[widget_key]
            selected_text = widget.currentText().strip()
            if not selected_text:
                continue
            try:
                self.cursor.execute(
                    "SELECT target_cost_field, default_cost FROM default_cost_mappings "
                    "WHERE category_name = %s AND item_value = %s",
                    (category, selected_text)
                )
                mapping = self.cursor.fetchone()
                if mapping:
                    cost_field = mapping['target_cost_field']
                    cost_value = mapping['default_cost']
                    if cost_field in self.cost_inputs:
                        self.cost_inputs[cost_field].setValue(cost_value)
                        updated_count += 1
            except mysql.connector.Error as err:
                print("Error importing default:", err)

        if updated_count > 0:
            QMessageBox.information(self, "موفقیت", f"{updated_count} قیمت پایه‌ای بارگذاری شد.")
        else:
            QMessageBox.information(self, "اطلاعات", "هیچ تطابقی یافت نشد.")
            
            
            
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Optional: Apply a clean stylesheet
    app.setStyleSheet("""
        QWidget { font-family: 'Tahoma', 'IRANSans', sans-serif; font-size: 14px; }
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { padding: 5px; }
        QSpinBox, QDoubleSpinBox { text-align: center; }
    """)

    window = BookCostCalculator()
    window.show()
    sys.exit(app.exec())