"""Main window: assembles the tabs and coordinates cross-tab workflows
(calculate, save/load/delete project, PDF export, default price import).

Tabs never talk to each other directly — they expose signals and small state
APIs, and this class does the wiring.
"""

import os
import sys

import jdatetime
from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog, QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QTabWidget, QToolBar,
)

import re
import shutil

from bookcost.config import DB_CONFIG
from bookcost.core.calculator import CostCalculator
from bookcost.core.db import BookDatabase, is_valid_database_file
from bookcost.core.project_io import load_project_file, save_project_file
from bookcost.reporting.pdf_report import ReportData, build_pdf_report
from bookcost.resources import resource_path
from bookcost.ui.tabs.calc_tab import CalcTab
from bookcost.ui.tabs.defaults_tab import DefaultsTab
from bookcost.ui.tabs.details_tab import DetailsTab
from bookcost.ui.tabs.paper_calc_tab import PaperCalcTab
from bookcost.ui.tabs.pricing_tab import PricingTab
from bookcost.ui.tabs.projects_tab import ProjectsTab
from bookcost.ui.tabs.report_tab import ReportTab


class BookCostCalculator(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("نرم افزار محاسبه و مدیریت هزینه‌های چاپ کتاب")
        self.setGeometry(100, 100, 1100, 800)

        # VERY IMPORTANT: the entire application is Right-To-Left for Farsi
        self.setLayoutDirection(Qt.RightToLeft)

        self.db = BookDatabase(DB_CONFIG['filename'])
        try:
            self.db.connect()
        except Exception as err:
            QMessageBox.critical(
                self, "خطای دیتابیس",
                f"ارتباط با دیتابیس برقرار نشد.\nلطفاً فایل config.ini را بررسی کنید.\n\n{err}"
            )
            sys.exit(1)

        self.calculator = CostCalculator()
        self.current_project_id = None

        self._build_tabs()
        self._build_chrome()
        self._wire_signals()

    # ── Construction ───────────────────────────────────────────────────────

    def _build_tabs(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.projects_tab = ProjectsTab(self.db)
        self.details_tab = DetailsTab(self.db, self.calculator)
        self.pricing_tab = PricingTab()
        self.calc_tab = CalcTab()
        self.report_tab = ReportTab()
        self.paper_calc_tab = PaperCalcTab(self.db, self.calculator)
        self.defaults_tab = DefaultsTab(self.db)

        self.tabs.addTab(self.projects_tab,   "مدیریت پروژه‌ها")
        self.tabs.addTab(self.details_tab,    "ورود اطلاعات و هزینه‌ها")
        self.tabs.addTab(self.pricing_tab,    "قیمت‌گذاری و سودآوری")
        self.tabs.addTab(self.calc_tab,       "محاسبات نهایی")
        self.tabs.addTab(self.report_tab,     "گزارش‌گیری (PDF)")
        self.tabs.addTab(self.paper_calc_tab, "محاسبات پیش‌پردازش کاغذ")
        self.tabs.addTab(self.defaults_tab,   "مدیریت قیمت‌های پایه")

    def _build_chrome(self):
        file_menu = self.menuBar().addMenu("فایل")
        export_project_action = QAction("خروجی گرفتن از پروژه (JSON)...", self)
        export_project_action.triggered.connect(self.export_project_to_file)
        file_menu.addAction(export_project_action)
        import_project_action = QAction("وارد کردن پروژه (JSON)...", self)
        import_project_action.triggered.connect(self.import_project_from_file)
        file_menu.addAction(import_project_action)
        file_menu.addSeparator()
        backup_db_action = QAction("پشتیبان‌گیری از کل دیتابیس...", self)
        backup_db_action.triggered.connect(self.backup_database)
        file_menu.addAction(backup_db_action)
        restore_db_action = QAction("بازیابی دیتابیس از فایل پشتیبان...", self)
        restore_db_action.triggered.connect(self.restore_database)
        file_menu.addAction(restore_db_action)

        settings_menu = self.menuBar().addMenu("تنظیمات")
        paper_calc_menu_action = QAction("محاسبات پیش‌پردازش کاغذ", self)
        paper_calc_menu_action.triggered.connect(
            lambda: self.tabs.setCurrentWidget(self.paper_calc_tab))
        settings_menu.addAction(paper_calc_menu_action)
        defaults_menu_action = QAction("مدیریت قیمت‌های پایه", self)
        defaults_menu_action.triggered.connect(
            lambda: self.tabs.setCurrentWidget(self.defaults_tab))
        settings_menu.addAction(defaults_menu_action)

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

        self.status_project_label = QLabel("پروژه‌ای باز نشده است")
        self.status_save_label = QLabel("")
        self.statusBar().addWidget(self.status_project_label)
        self.statusBar().addPermanentWidget(self.status_save_label)

    def _wire_signals(self):
        self.projects_tab.open_requested.connect(self.load_project_by_id)
        self.projects_tab.new_requested.connect(self.new_project)

        self.details_tab.calculate_requested.connect(self.perform_calculations)

        self.pricing_tab.inputs_changed.connect(self.refresh_pricing_tab)

        self.report_tab.generate_requested.connect(self.generate_pdf)

        self.paper_calc_tab.defaults_exported.connect(self._on_defaults_exported)

        self.defaults_tab.zinc_prices_changed.connect(self._on_zinc_prices_changed)
        self.defaults_tab.cost_applied.connect(self.details_tab.set_cost_value)

        self.tabs.currentChanged.connect(self._on_tab_changed)

    # ── Cross-tab reactions ────────────────────────────────────────────────

    def _on_tab_changed(self, idx):
        if self.tabs.widget(idx) is self.details_tab:
            self.details_tab.refresh_zinc_price_labels()

    def _on_defaults_exported(self):
        self.defaults_tab.reload()
        self.tabs.setCurrentWidget(self.defaults_tab)

    def _on_zinc_prices_changed(self):
        self.details_tab.refresh_zinc_price_labels()
        self.details_tab.auto_calculate_costs()

    # ── Workflows ──────────────────────────────────────────────────────────

    def perform_calculations(self):
        tiraj = self.details_tab.tiraj()
        if tiraj == 0:
            QMessageBox.warning(self, "خطا", "تیراژ نمی‌تواند صفر باشد!")
            return

        cost_values = self.details_tab.cost_values()
        totals = self.calculator.compute_totals(
            cost_values,
            royalty_pct=self.details_tab.royalty_pct(),
            tiraj=tiraj,
        )

        self.details_tab.save_new_dynamic_types()
        self.calc_tab.set_totals(totals['total_cost'], totals['cost_per_book'])
        self.calc_tab.update_chart(cost_values)
        self.refresh_pricing_tab()
        self.tabs.setCurrentWidget(self.calc_tab)
        self.save_project_to_db()

    def refresh_pricing_tab(self):
        self.pricing_tab.refresh(
            total_cost=self.calc_tab.total_cost,
            single_cost=self.calc_tab.cost_per_book,
            tiraj=self.details_tab.tiraj(),
            royalty_pct=self.details_tab.royalty_pct(),
        )

    def save_project_to_db(self):
        title = self.details_tab.title()
        if not title:
            QMessageBox.warning(self, "خطا", "لطفاً حداقل عنوان کتاب را وارد کنید.")
            return

        p = self.details_tab.collect_project()
        p['total_cost'] = self.calc_tab.total_cost
        p['single_book_cost'] = self.calc_tab.cost_per_book

        d = self.details_tab.collect_details()
        d['pricing_multiplier'] = self.pricing_tab.multiplier()
        d['distribution_percent'] = self.pricing_tab.distribution_pct()

        try:
            if self.current_project_id is not None:
                self.db.update_project(self.current_project_id, p, d)
            else:
                self.current_project_id = self.db.insert_project(p, d)

            self.projects_tab.refresh()
            now = jdatetime.datetime.now().strftime("%H:%M:%S")
            self.status_project_label.setText(title)
            self.status_save_label.setText(f"آخرین ذخیره: {now}")
            QMessageBox.information(self, "موفقیت", "اطلاعات پروژه با موفقیت ذخیره شد!")
        except Exception as err:
            QMessageBox.critical(self, "خطای ذخیره‌سازی", f"مشکلی در ذخیره اطلاعات پیش آمد:\n{err}")

    def load_selected_project(self):
        selected = self.projects_tab.selected_project()
        if selected is None:
            QMessageBox.warning(self, "هشدار", "لطفاً ابتدا یک پروژه را از جدول انتخاب کنید.")
            return
        self.load_project_by_id(selected[0])

    def load_project_by_id(self, project_id):
        try:
            project = self.db.get_project(project_id)
            if not project:
                QMessageBox.warning(self, "خطا", "پروژه‌ای با این شناسه یافت نشد.")
                return
            details = self.db.get_project_details(project_id)

            self.details_tab.populate(project, details)
            if details:
                details = dict(details)
                self.pricing_tab.set_values(
                    multiplier=details.get('pricing_multiplier'),
                    distribution_pct=details.get('distribution_percent'),
                )

            self.current_project_id = project_id
            self.status_project_label.setText(project['title'])
            self.status_save_label.setText("")

            self.tabs.setCurrentWidget(self.details_tab)
            QMessageBox.information(self, "بارگذاری",
                                    "پروژه با موفقیت بارگذاری شد. پس از ویرایش می‌توانید ذخیره کنید.")
        except Exception as err:
            QMessageBox.critical(self, "خطا", f"بارگذاری پروژه با خطا مواجه شد:\n{err}")

    def new_project(self):
        self.current_project_id = None
        self.status_project_label.setText("پروژه جدید")
        self.status_save_label.setText("")

        self.details_tab.reset()
        self.pricing_tab.reset()
        self.calc_tab.reset()

        self.tabs.setCurrentWidget(self.details_tab)

    def delete_project(self):
        selected = self.projects_tab.selected_project()
        if selected is None:
            QMessageBox.warning(self, "هشدار", "لطفاً ابتدا یک پروژه را از جدول انتخاب کنید.")
            return
        project_id, project_title = selected

        password, ok = QInputDialog.getText(
            self, "تأیید حذف",
            f"برای حذف پروژه «{project_title}» لطفاً رمز عبور را وارد کنید:",
            QLineEdit.Password
        )
        if not ok or password != DB_CONFIG.get('delete_password', 'admin'):
            QMessageBox.critical(self, "خطا", "رمز عبور اشتباه است یا عملیات لغو شد.")
            return

        reply = QMessageBox.question(
            self, "تأیید نهایی",
            f"آیا از حذف کامل پروژه «{project_title}» اطمینان دارید؟",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        try:
            self.db.delete_project(project_id)
            self.projects_tab.refresh()
            if self.current_project_id == project_id:
                self.new_project()
            QMessageBox.information(self, "موفقیت", "پروژه با موفقیت حذف شد.")
        except Exception as err:
            QMessageBox.critical(self, "خطا", f"حذف پروژه با مشکل مواجه شد:\n{err}")

    def import_default_prices(self):
        """Fills cost fields from default mappings matching the selected type values."""
        items = self.details_tab.type_selections()
        if not items:
            QMessageBox.information(self, "اطلاعات", "هیچ تطابقی یافت نشد.")
            return
        try:
            mappings = self.db.get_default_costs_batch(items)
            updated_count = 0
            for mapping in mappings:
                cost_field = mapping['target_cost_field']
                if cost_field in self.details_tab.cost_inputs:
                    self.details_tab.set_cost_value(cost_field, mapping['default_cost'])
                    updated_count += 1
        except Exception as err:
            print("Error importing defaults:", err)
            return
        if updated_count > 0:
            QMessageBox.information(self, "موفقیت", f"{updated_count} قیمت پایه‌ای بارگذاری شد.")
        else:
            QMessageBox.information(self, "اطلاعات", "هیچ تطابقی یافت نشد.")

    # ── Project & database import/export ──────────────────────────────────

    def _project_id_for_export(self):
        """Selected row in the projects tab, else the currently open project."""
        selected = self.projects_tab.selected_project()
        if selected is not None:
            return selected[0]
        return self.current_project_id

    def export_project_to_file(self):
        project_id = self._project_id_for_export()
        if project_id is None:
            QMessageBox.warning(
                self, "هشدار",
                "ابتدا یک پروژه را از جدول انتخاب کنید یا پروژه‌ای را باز کنید.")
            return
        project = self.db.get_project(project_id)
        safe_title = re.sub(r'[\\/:*?"<>|]+', '_', project['title']).strip() or 'project'
        file_path, _ = QFileDialog.getSaveFileName(
            self, "خروجی گرفتن از پروژه", f"{safe_title}.json", "JSON Files (*.json)")
        if not file_path:
            return
        try:
            save_project_file(self.db, project_id, file_path)
        except Exception as err:
            QMessageBox.critical(self, "خطا", f"خروجی گرفتن با خطا مواجه شد:\n{err}")
            return
        QMessageBox.information(self, "موفقیت", f"پروژه «{project['title']}» ذخیره شد.")

    def import_project_from_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "وارد کردن پروژه", "", "JSON Files (*.json)")
        if not file_path:
            return
        try:
            new_id = load_project_file(self.db, file_path)
        except ValueError as err:
            QMessageBox.critical(self, "خطا", str(err))
            return
        except Exception as err:
            QMessageBox.critical(self, "خطا", f"وارد کردن پروژه با خطا مواجه شد:\n{err}")
            return
        self.projects_tab.refresh()
        self.details_tab.reload_categories()
        self.load_project_by_id(new_id)

    def backup_database(self):
        stamp = jdatetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
        docs = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        default_path = os.path.join(docs, f"پشتیبان_شهرقلم_{stamp}.db")
        file_path, _ = QFileDialog.getSaveFileName(
            self, "پشتیبان‌گیری از دیتابیس", default_path, "SQLite Database (*.db)")
        if not file_path:
            return
        try:
            self.db.backup_to(file_path)
            if not is_valid_database_file(file_path):
                raise RuntimeError("فایل پشتیبان پس از نوشتن قابل خواندن نیست")
        except Exception as err:
            QMessageBox.critical(self, "خطا", f"پشتیبان‌گیری با خطا مواجه شد:\n{err}")
            return
        QMessageBox.information(
            self, "موفقیت",
            f"پشتیبان‌گیری از دیتابیس انجام شد:\n{os.path.normpath(file_path)}")

    def restore_database(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "بازیابی دیتابیس", "", "SQLite Database (*.db)")
        if not file_path:
            return
        if not is_valid_database_file(file_path):
            QMessageBox.critical(
                self, "خطا",
                "این فایل یک پشتیبان معتبر دیتابیس این برنامه نیست.")
            return

        reply = QMessageBox.question(
            self, "تأیید بازیابی",
            "تمام اطلاعات فعلی با محتوای فایل پشتیبان جایگزین می‌شود.\n"
            "از دیتابیس فعلی به‌صورت خودکار نسخه پشتیبان تهیه خواهد شد.\n\n"
            "آیا ادامه می‌دهید؟",
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        db_path = DB_CONFIG['filename']
        stamp = jdatetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        auto_backup = f"{db_path}.pre-restore-{stamp}.bak"
        try:
            self.db.backup_to(auto_backup)
            self.db.close()
            shutil.copyfile(file_path, db_path)
            self.db.connect()
        except Exception as err:
            # Try to come back up on the old database
            try:
                if self.db._conn is None:
                    shutil.copyfile(auto_backup, db_path)
                    self.db.connect()
            except Exception:
                pass
            QMessageBox.critical(self, "خطا", f"بازیابی با خطا مواجه شد:\n{err}")
            return

        # Refresh everything that caches database content
        self.new_project()
        self.projects_tab.refresh()
        self.details_tab.reload_categories()
        self.details_tab.refresh_zinc_price_labels()
        self.defaults_tab.reload()
        self.defaults_tab.load_zinc_prices_table()
        self.paper_calc_tab.load_paper_calculations()
        QMessageBox.information(
            self, "موفقیت",
            f"دیتابیس بازیابی شد.\nنسخه قبلی در این مسیر نگه‌داری می‌شود:\n{auto_backup}")

    def generate_pdf(self):
        font_path = resource_path("tahoma.ttf")
        if not os.path.exists(font_path):
            QMessageBox.critical(
                self, "خطا",
                f"فایل فونت '{font_path}' پیدا نشد!\nلطفاً یک فونت فارسی را در پوشه برنامه قرار دهید.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "ذخیره گزارش PDF", "", "PDF Files (*.pdf)")
        if not file_path:
            return

        cost_values = self.details_tab.cost_values()
        cost_groups = [
            (group, [(f, cost_values[f]) for f in fields])
            for group, fields in CostCalculator.COST_GROUPS.items()
        ]

        data = ReportData(
            title=self.details_tab.title(),
            basic_info=self.details_tab.report_basic_info(),
            tiraj=self.details_tab.tiraj(),
            print_specs=self.details_tab.report_print_specs(),
            features=self.details_tab.report_features(),
            cost_groups=cost_groups,
            royalty_pct=self.details_tab.royalty_pct(),
            total_cost=self.calc_tab.total_cost,
            single_cost=self.calc_tab.cost_per_book,
            pricing_multiplier=self.pricing_tab.multiplier(),
            distribution_pct=self.pricing_tab.distribution_pct(),
            include_basic_info=self.report_tab.include_basic_info(),
            include_specs=self.report_tab.include_specs(),
            include_features=self.report_tab.include_features(),
            include_costs=self.report_tab.include_costs(),
            include_pricing=self.report_tab.include_pricing(),
            logo_path=resource_path("logo.png"),
        )

        try:
            build_pdf_report(file_path, font_path, data)
        except Exception as err:
            QMessageBox.critical(self, "خطا", f"تولید PDF با خطا مواجه شد:\n{err}")
            return
        QMessageBox.information(self, "موفقیت", "فایل PDF با موفقیت تولید و ذخیره شد.")
