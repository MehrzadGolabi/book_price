"""Editable list of paper types for one section (متن or جلد).

Each row: paper type name, number of forms printed on it, unit price per
sheet. When the list has rows, it replaces the single-paper form/price inputs
in the cost calculation (the details tab wires that logic).
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox,
    QVBoxLayout, QWidget,
)


class PaperListWidget(QWidget):
    changed = Signal()

    def __init__(self, placeholder: str, parent=None):
        super().__init__(parent)
        self._placeholder = placeholder
        self._rows = []            # list of (row_widget, type_edit, forms_spin, price_spin)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._rows_box = QVBoxLayout()
        self._rows_box.setSpacing(2)
        layout.addLayout(self._rows_box)

        add_btn = QPushButton("+ افزودن نوع کاغذ")
        add_btn.setStyleSheet("padding: 3px 8px; color: #64b5f6; background: transparent; border: 1px dashed #64b5f6;")
        add_btn.clicked.connect(lambda: (self.add_row(), self.changed.emit()))
        row = QHBoxLayout()
        row.addWidget(add_btn)
        row.addStretch()
        layout.addLayout(row)

    # ── Rows ──────────────────────────────────────────────────────────────

    def add_row(self, paper_type: str = '', form_count: float = 0, unit_price: float = 0.0):
        row_widget = QWidget()
        h = QHBoxLayout(row_widget)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)

        type_edit = QLineEdit(paper_type)
        type_edit.setPlaceholderText(self._placeholder)

        forms_spin = QSpinBox()
        forms_spin.setRange(0, 1000)
        forms_spin.setSuffix(" فرم")
        forms_spin.setValue(int(form_count))
        forms_spin.setAlignment(Qt.AlignCenter)

        price_spin = QDoubleSpinBox()
        price_spin.setMaximum(9_999_999_999.99)
        price_spin.setDecimals(0)
        price_spin.setGroupSeparatorShown(True)
        price_spin.setValue(unit_price)
        price_spin.setAlignment(Qt.AlignCenter)

        remove_btn = QPushButton("✕")
        remove_btn.setFixedWidth(28)
        remove_btn.setStyleSheet("color: #e57373; background: transparent;")

        h.addWidget(type_edit, 3)
        h.addWidget(forms_spin, 2)
        h.addWidget(QLabel("قیمت:"))
        h.addWidget(price_spin, 3)
        h.addWidget(remove_btn)

        entry = (row_widget, type_edit, forms_spin, price_spin)
        remove_btn.clicked.connect(lambda: self._remove(entry))
        forms_spin.valueChanged.connect(self.changed.emit)
        price_spin.valueChanged.connect(self.changed.emit)

        self._rows.append(entry)
        self._rows_box.addWidget(row_widget)

    def _remove(self, entry):
        if entry in self._rows:
            self._rows.remove(entry)
            entry[0].setParent(None)
            entry[0].deleteLater()
            self.changed.emit()

    # ── State ─────────────────────────────────────────────────────────────

    def entries(self) -> list:
        """Non-empty rows as [{'paper_type', 'form_count', 'unit_price'}]."""
        out = []
        for _, type_edit, forms_spin, price_spin in self._rows:
            if forms_spin.value() > 0 or price_spin.value() > 0 or type_edit.text().strip():
                out.append({
                    'paper_type': type_edit.text().strip(),
                    'form_count': forms_spin.value(),
                    'unit_price': price_spin.value(),
                })
        return out

    def set_entries(self, entries: list):
        self.clear()
        for e in entries:
            self.add_row(e.get('paper_type') or '', e.get('form_count') or 0,
                         e.get('unit_price') or 0)
        self.changed.emit()

    def clear(self):
        while self._rows:
            entry = self._rows.pop()
            entry[0].setParent(None)
            entry[0].deleteLater()
