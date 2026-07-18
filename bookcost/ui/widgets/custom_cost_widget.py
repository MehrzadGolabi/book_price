"""Editable list of custom cost lines (item 11).

Each row: a free name, an optional parent (marks it a sub-line of a built-in
field, e.g. «خدمات» under «هزینه قالب لترپرس»), an amount, and a calculation
type (fixed / per-tiraj / per-form / per-volume). Rows can be added and
removed. The details tab folds these into the unified cost-line list.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QWidget,
)

from bookcost.core.cost_model import CALC_TYPE_ORDER, CALC_TYPE_LABELS, CalcType

_NO_PARENT = "— (هزینه مستقل)"


class CustomCostWidget(QWidget):
    changed = Signal()

    def __init__(self, parent_options_provider=None, parent=None):
        super().__init__(parent)
        self._parent_options = parent_options_provider or (lambda: [])
        self._rows = []   # (row_widget, name_edit, parent_combo, amount_spin, calc_combo)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self._rows_box = QVBoxLayout()
        self._rows_box.setSpacing(2)
        layout.addLayout(self._rows_box)

        add_btn = QPushButton("+ افزودن هزینه سفارشی / زیرمجموعه")
        add_btn.setStyleSheet(
            "padding: 4px 10px; color: #1d4ed8; background: transparent;"
            "border: 1px dashed #1d4ed8;")
        add_btn.clicked.connect(lambda: (self.add_row(), self.changed.emit()))
        row = QHBoxLayout()
        row.addWidget(add_btn)
        row.addStretch()
        layout.addLayout(row)

    def add_row(self, name='', parent_key=None, amount=0.0, calc_type='fixed'):
        row_widget = QWidget()
        h = QHBoxLayout(row_widget)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)

        name_edit = QLineEdit(name)
        name_edit.setPlaceholderText("نام هزینه")

        parent_combo = QComboBox()
        parent_combo.addItem(_NO_PARENT, None)
        for opt in self._parent_options():
            parent_combo.addItem(opt, opt)
        if parent_key:
            idx = parent_combo.findData(parent_key)
            if idx < 0:
                parent_combo.addItem(parent_key, parent_key)
                idx = parent_combo.findData(parent_key)
            parent_combo.setCurrentIndex(idx)

        amount_spin = QDoubleSpinBox()
        amount_spin.setMaximum(9_999_999_999.99)
        amount_spin.setDecimals(0)
        amount_spin.setGroupSeparatorShown(True)
        amount_spin.setValue(amount)
        amount_spin.setAlignment(Qt.AlignCenter)

        calc_combo = QComboBox()
        for ct in CALC_TYPE_ORDER:
            calc_combo.addItem(CALC_TYPE_LABELS[ct], ct.value)
        idx = calc_combo.findData(CalcType.coerce(calc_type).value)
        calc_combo.setCurrentIndex(max(0, idx))

        remove_btn = QPushButton("✕")
        remove_btn.setFixedWidth(28)
        remove_btn.setStyleSheet("color: #b91c1c; background: transparent;")

        h.addWidget(name_edit, 3)
        h.addWidget(QLabel("زیرمجموعهٔ:"))
        h.addWidget(parent_combo, 2)
        h.addWidget(amount_spin, 2)
        h.addWidget(calc_combo, 2)
        h.addWidget(remove_btn)

        entry = (row_widget, name_edit, parent_combo, amount_spin, calc_combo)
        remove_btn.clicked.connect(lambda: self._remove(entry))
        name_edit.textChanged.connect(lambda _t: self.changed.emit())
        amount_spin.valueChanged.connect(lambda _v: self.changed.emit())
        calc_combo.currentIndexChanged.connect(lambda _i: self.changed.emit())
        parent_combo.currentIndexChanged.connect(lambda _i: self.changed.emit())

        self._rows.append(entry)
        self._rows_box.addWidget(row_widget)

    def _remove(self, entry):
        if entry in self._rows:
            self._rows.remove(entry)
            entry[0].setParent(None)
            entry[0].deleteLater()
            self.changed.emit()

    def entries(self) -> list:
        """[{'display_name','parent_key','amount','calc_type'}] for named rows."""
        out = []
        for _, name_edit, parent_combo, amount_spin, calc_combo in self._rows:
            name = name_edit.text().strip()
            if not name:
                continue
            out.append({
                'display_name': name,
                'parent_key': parent_combo.currentData(),
                'amount': amount_spin.value(),
                'calc_type': calc_combo.currentData(),
            })
        return out

    def set_entries(self, rows: list):
        self.clear()
        for r in rows:
            self.add_row(r.get('display_name') or '', r.get('parent_key'),
                         r.get('amount') or 0, r.get('calc_type') or 'fixed')
        self.changed.emit()

    def clear(self):
        while self._rows:
            entry = self._rows.pop()
            entry[0].setParent(None)
            entry[0].deleteLater()
