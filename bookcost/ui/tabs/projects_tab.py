"""Project list tab: search, open, create."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)


class ProjectsTab(QWidget):
    open_requested = Signal(int)   # project id
    new_requested = Signal()

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("جستجوی نام کتاب...")
        search_btn = QPushButton("جستجو")
        search_btn.clicked.connect(self._search)
        self.search_input.returnPressed.connect(self._search)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_btn)

        self.project_table = QTableWidget(0, 5)
        self.project_table.setHorizontalHeaderLabels(["شناسه", "عنوان کتاب", "سری", "تاریخ", "تیراژ"])
        self.project_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.project_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.project_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.project_table.doubleClicked.connect(self._open_row)

        empty_widget = QWidget()
        empty_layout = QVBoxLayout(empty_widget)
        empty_layout.setAlignment(Qt.AlignCenter)
        empty_lbl = QLabel("هیچ پروژه‌ای یافت نشد\n\nبرای شروع، یک پروژه جدید ایجاد کنید.")
        empty_lbl.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(empty_lbl)

        self.project_stack = QStackedWidget()
        self.project_stack.addWidget(empty_widget)        # index 0: empty state
        self.project_stack.addWidget(self.project_table)  # index 1: table

        new_project_btn = QPushButton("ایجاد پروژه جدید")
        new_project_btn.clicked.connect(self.new_requested.emit)

        layout.addLayout(search_layout)
        layout.addWidget(self.project_stack)
        layout.addWidget(new_project_btn)

    def refresh(self, filter_text=None):
        try:
            results = self.db.get_projects(filter_text or '')
            self.project_table.setUpdatesEnabled(False)
            self.project_table.setRowCount(len(results))
            for row_idx, row_data in enumerate(results):
                row = dict(row_data)
                if row.get('series_name') or (row.get('series_volumes') or 1) > 1:
                    series_txt = (f"{row.get('series_name') or '—'} — "
                                  f"جلد {row.get('volume_no') or '?'} از {row.get('series_volumes') or '?'}")
                else:
                    series_txt = ""
                series_item = QTableWidgetItem(series_txt)
                if series_txt:
                    series_item.setForeground(QColor('#64b5f6'))
                self.project_table.setItem(row_idx, 0, QTableWidgetItem(str(row['id'])))
                self.project_table.setItem(row_idx, 1, QTableWidgetItem(row['title']))
                self.project_table.setItem(row_idx, 2, series_item)
                self.project_table.setItem(row_idx, 3, QTableWidgetItem(row['creation_date']))
                self.project_table.setItem(row_idx, 4, QTableWidgetItem(str(row['tiraj'])))
            self.project_table.setUpdatesEnabled(True)
            self.project_stack.setCurrentIndex(1 if results else 0)
        except Exception as err:
            QMessageBox.warning(self, "خطا", f"بارگذاری پروژه‌ها با خطا مواجه شد:\n{err}")

    def selected_project(self):
        """Returns (project_id, title) of the selected row, or None."""
        row = self.project_table.currentRow()
        if row < 0:
            return None
        id_item = self.project_table.item(row, 0)
        if not id_item:
            return None
        return int(id_item.text()), self.project_table.item(row, 1).text()

    def _search(self):
        text = self.search_input.text().strip()
        self.refresh(text if text else None)

    def _open_row(self, index):
        id_item = self.project_table.item(index.row(), 0)
        if id_item:
            self.open_requested.emit(int(id_item.text()))
