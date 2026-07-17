"""Editable list of paper types for one section (متن or جلد).

Each row: paper type (editable combo fed by the type categories and the saved
paper-price library), number of forms, unit price per sheet. When the list has
rows, it replaces the single-paper form/price inputs in the cost calculation.

Conveniences wired by the details tab through callables:
- ``items_provider``  → combo items (categories + paper library names)
- ``price_lookup``    → auto-fills the unit price when a known paper is picked
- ``dims_lookup``     → sheet size per paper, used for the mixed-size warning
- ``default_forms``   → suggested total forms; a new row is prefilled with the
  remaining forms so the rows sum to the project's computed form count
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QPushButton, QSpinBox,
    QVBoxLayout, QWidget,
)


class PaperListWidget(QWidget):
    changed = Signal()

    def __init__(self, placeholder: str, items_provider=None, price_lookup=None,
                 dims_lookup=None, default_forms=None, parent=None):
        super().__init__(parent)
        self._placeholder = placeholder
        self._items_provider = items_provider
        self._price_lookup = price_lookup
        self._dims_lookup = dims_lookup
        self._default_forms = default_forms
        self._rows = []            # list of (row_widget, type_combo, forms_spin, price_spin)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._rows_box = QVBoxLayout()
        self._rows_box.setSpacing(2)
        layout.addLayout(self._rows_box)

        self._warning = QLabel("")
        self._warning.setWordWrap(True)
        self._warning.setStyleSheet("color: #b45309; font-size: 12px;")
        self._warning.setVisible(False)
        layout.addWidget(self._warning)

        add_btn = QPushButton("+ افزودن نوع کاغذ")
        add_btn.setStyleSheet("padding: 3px 8px; color: #1d4ed8; background: transparent; border: 1px dashed #1d4ed8;")
        add_btn.clicked.connect(self._add_row_interactive)
        row = QHBoxLayout()
        row.addWidget(add_btn)
        row.addStretch()
        layout.addLayout(row)

    # ── Rows ──────────────────────────────────────────────────────────────

    def _combo_items(self) -> list:
        return list(self._items_provider()) if self._items_provider else []

    def _add_row_interactive(self):
        """Button click: prefill forms with what's left of the suggested total."""
        form_count = 0
        if self._default_forms:
            total = self._default_forms() or 0
            used = sum(f.value() for _, _, f, _ in self._rows)
            form_count = max(0, total - used)
        self.add_row(form_count=form_count)
        self.changed.emit()

    def add_row(self, paper_type: str = '', form_count: float = 0, unit_price: float = 0.0):
        row_widget = QWidget()
        h = QHBoxLayout(row_widget)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)

        type_combo = QComboBox()
        type_combo.setEditable(True)
        type_combo.setInsertPolicy(QComboBox.NoInsert)
        type_combo.addItems(self._combo_items())
        type_combo.setCurrentIndex(-1)
        type_combo.lineEdit().setPlaceholderText(self._placeholder)
        if paper_type:
            type_combo.setCurrentText(paper_type)

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
        remove_btn.setStyleSheet("color: #b91c1c; background: transparent;")

        h.addWidget(type_combo, 3)
        h.addWidget(forms_spin, 2)
        h.addWidget(QLabel("قیمت:"))
        h.addWidget(price_spin, 3)
        h.addWidget(remove_btn)

        entry = (row_widget, type_combo, forms_spin, price_spin)
        remove_btn.clicked.connect(lambda: self._remove(entry))
        type_combo.currentTextChanged.connect(lambda _t, e=entry: self._on_type_changed(e))
        forms_spin.valueChanged.connect(lambda _v: self.changed.emit())
        price_spin.valueChanged.connect(lambda _v: self.changed.emit())

        self._rows.append(entry)
        self._rows_box.addWidget(row_widget)

    def _on_type_changed(self, entry):
        _, type_combo, _, price_spin = entry
        if self._price_lookup:
            price = self._price_lookup(type_combo.currentText().strip())
            if price:
                price_spin.setValue(price)
        self._update_warning()
        self.changed.emit()

    def _remove(self, entry):
        if entry in self._rows:
            self._rows.remove(entry)
            entry[0].setParent(None)
            entry[0].deleteLater()
            self._update_warning()
            self.changed.emit()

    # ── Conveniences ──────────────────────────────────────────────────────

    def autofill_prices(self) -> int:
        """Fills every row's unit price from the paper library; returns how
        many rows got a price."""
        if not self._price_lookup:
            return 0
        filled = 0
        for _, type_combo, _, price_spin in self._rows:
            price = self._price_lookup(type_combo.currentText().strip())
            if price:
                price_spin.setValue(price)
                filled += 1
        if filled:
            self.changed.emit()
        return filled

    def refresh_items(self):
        """Re-reads combo items (new categories / library entries)."""
        items = self._combo_items()
        for _, type_combo, _, _ in self._rows:
            current = type_combo.currentText()
            type_combo.blockSignals(True)
            type_combo.clear()
            type_combo.addItems(items)
            type_combo.setCurrentText(current)
            type_combo.blockSignals(False)

    def _update_warning(self):
        """Warns when the chosen papers have different sheet sizes — they
        can't share one imposition/form layout."""
        if not self._dims_lookup:
            return
        sizes = {}
        for _, type_combo, _, _ in self._rows:
            name = type_combo.currentText().strip()
            dims = self._dims_lookup(name) if name else None
            if dims:
                sizes[f"{dims[0]:g}×{dims[1]:g}"] = True
        if len(sizes) > 1:
            self._warning.setText(
                "⚠ اندازه کاغذهای انتخابی متفاوت است (" + "، ".join(sizes)
                + ") — این کاغذها روی یک فرم مشترک چاپ نمی‌شوند؛ تعداد فرم هر کاغذ را بازبینی کنید.")
            self._warning.setVisible(True)
        else:
            self._warning.setVisible(False)

    # ── State ─────────────────────────────────────────────────────────────

    def entries(self) -> list:
        """Non-empty rows as [{'paper_type', 'form_count', 'unit_price'}]."""
        out = []
        for _, type_combo, forms_spin, price_spin in self._rows:
            if (forms_spin.value() > 0 or price_spin.value() > 0
                    or type_combo.currentText().strip()):
                out.append({
                    'paper_type': type_combo.currentText().strip(),
                    'form_count': forms_spin.value(),
                    'unit_price': price_spin.value(),
                })
        return out

    def set_entries(self, entries: list):
        self.clear()
        for e in entries:
            self.add_row(e.get('paper_type') or '', e.get('form_count') or 0,
                         e.get('unit_price') or 0)
        self._update_warning()
        self.changed.emit()

    def clear(self):
        while self._rows:
            entry = self._rows.pop()
            entry[0].setParent(None)
            entry[0].deleteLater()
        self._warning.setVisible(False)
