"""Editor for the volumes of a multi-volume project (item 1).

Each row holds one volume: name, page count, and its text/cover print-form
counts. Forms are auto-suggested from the page count via an estimator callback
but stay editable. The details tab sums these across volumes to drive the
shared paper/zinc/print machinery and to set the volume count.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)


class VolumesWidget(QWidget):
    changed = Signal()

    def __init__(self, forms_estimator=None, parent=None):
        super().__init__(parent)
        # forms_estimator(pages) -> (forms_matn, forms_jeld) or None
        self._estimator = forms_estimator
        self._rows = []   # (row_widget, name_edit, pages_spin, fm_spin, fj_spin)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        for text, stretch in (("نام جلد", 3), ("صفحات", 2), ("فرم متن", 2),
                              ("فرم جلد", 2), ("", 0)):
            lbl = QLabel(text)
            lbl.setStyleSheet("color:#475569; font-size:12px;")
            header.addWidget(lbl, stretch)
        layout.addLayout(header)

        self._rows_box = QVBoxLayout()
        self._rows_box.setSpacing(2)
        layout.addLayout(self._rows_box)

        add_btn = QPushButton("+ افزودن جلد")
        add_btn.setStyleSheet(
            "padding: 3px 8px; color: #1d4ed8; background: transparent;"
            "border: 1px dashed #1d4ed8;")
        add_btn.clicked.connect(lambda: (self.add_row(), self.changed.emit()))
        row = QHBoxLayout()
        row.addWidget(add_btn)
        row.addStretch()
        layout.addLayout(row)

    def add_row(self, name='', pages=0, forms_matn=0, forms_jeld=0):
        row_widget = QWidget()
        h = QHBoxLayout(row_widget)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)

        name_edit = QLineEdit(name)
        name_edit.setPlaceholderText(f"جلد {len(self._rows) + 1}")

        pages_spin = QSpinBox()
        pages_spin.setMaximum(5000)
        pages_spin.setValue(int(pages))
        pages_spin.setAlignment(Qt.AlignCenter)

        fm_spin = QSpinBox()
        fm_spin.setMaximum(1000)
        fm_spin.setValue(int(forms_matn))
        fm_spin.setAlignment(Qt.AlignCenter)

        fj_spin = QSpinBox()
        fj_spin.setMaximum(1000)
        fj_spin.setValue(int(forms_jeld))
        fj_spin.setAlignment(Qt.AlignCenter)

        remove_btn = QPushButton("✕")
        remove_btn.setFixedWidth(28)
        remove_btn.setStyleSheet("color: #b91c1c; background: transparent;")

        h.addWidget(name_edit, 3)
        h.addWidget(pages_spin, 2)
        h.addWidget(fm_spin, 2)
        h.addWidget(fj_spin, 2)
        h.addWidget(remove_btn)

        entry = (row_widget, name_edit, pages_spin, fm_spin, fj_spin)
        remove_btn.clicked.connect(lambda: self._remove(entry))
        name_edit.textChanged.connect(lambda _t: self.changed.emit())
        pages_spin.valueChanged.connect(lambda _v, e=entry: self._on_pages(e))
        fm_spin.valueChanged.connect(lambda _v: self.changed.emit())
        fj_spin.valueChanged.connect(lambda _v: self.changed.emit())

        self._rows.append(entry)
        self._rows_box.addWidget(row_widget)

    def _on_pages(self, entry):
        """Auto-suggest this volume's forms from its page count (editable)."""
        _, _, pages_spin, fm_spin, fj_spin = entry
        if self._estimator:
            est = self._estimator(pages_spin.value())
            if est:
                fm, fj = est
                fm_spin.blockSignals(True); fm_spin.setValue(int(fm)); fm_spin.blockSignals(False)
                if fj:
                    fj_spin.blockSignals(True); fj_spin.setValue(int(fj)); fj_spin.blockSignals(False)
        self.changed.emit()

    def _remove(self, entry):
        if entry in self._rows:
            self._rows.remove(entry)
            entry[0].setParent(None)
            entry[0].deleteLater()
            self.changed.emit()

    # ── State ─────────────────────────────────────────────────────────────

    def entries(self) -> list:
        """[{'volume_no','name','pages','forms_matn','forms_jeld'}] in order."""
        out = []
        for i, (_, name_edit, pages_spin, fm_spin, fj_spin) in enumerate(self._rows, 1):
            out.append({
                'volume_no': i,
                'name': name_edit.text().strip(),
                'pages': pages_spin.value(),
                'forms_matn': fm_spin.value(),
                'forms_jeld': fj_spin.value(),
            })
        return out

    def totals(self) -> dict:
        rows = self.entries()
        return {
            'pages': sum(r['pages'] for r in rows),
            'forms_matn': sum(r['forms_matn'] for r in rows),
            'forms_jeld': sum(r['forms_jeld'] for r in rows),
            'count': len(rows),
        }

    def set_entries(self, rows: list):
        self.clear()
        for r in rows:
            self.add_row(r.get('name') or '', r.get('pages') or 0,
                         r.get('forms_matn') or 0, r.get('forms_jeld') or 0)
        self.changed.emit()

    def clear(self):
        while self._rows:
            entry = self._rows.pop()
            entry[0].setParent(None)
            entry[0].deleteLater()
