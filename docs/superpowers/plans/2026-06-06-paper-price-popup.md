# Paper Price Calculator Popup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add inline paper price calculator dialogs to Tab 1 so users never need to leave the data entry tab to look up or calculate paper unit prices.

**Architecture:** A new `PaperPriceDialog(QDialog)` class is added to `main.py` before `BookCostCalculator`. Two "🧮 محاسبه" buttons are added next to the paper unit price spinboxes in Tab 1's calc group. Clicking either button opens the dialog, which shows the saved `paper_calculations` library and a three-formula calculator. On apply, the result is written directly into the target spinbox, triggering the existing `auto_calculate_costs()` chain.

**Tech Stack:** PySide6 (QDialog, QStackedWidget, QFormLayout, QTableWidget — all already imported), SQLite via existing `self.db_conn`.

---

### Task 1: Add `PaperPriceDialog` class to `main.py`

**Files:**
- Modify: `main.py` — insert new class at line 58 (just before `class BookCostCalculator`)

No new imports are needed: `QDialog`, `QStackedWidget`, `QGroupBox`, `QFormLayout`, `QTableWidget`, `QHeaderView`, `QLineEdit`, `QLabel`, `QPushButton`, `QHBoxLayout`, `QVBoxLayout`, `QDoubleSpinBox`, `QSpinBox`, `QWidget`, `QMessageBox`, `Qt` are all already imported on lines 5–10.

- [ ] **Step 1: Insert `PaperPriceDialog` class**

Open `main.py`. Locate line 58: `class BookCostCalculator(QMainWindow):`. Insert the following block **immediately before** that line (leave one blank line between the new class and `BookCostCalculator`):

```python
class PaperPriceDialog(QDialog):
    def __init__(self, db_conn, target, parent=None):
        super().__init__(parent)
        self.db_conn = db_conn
        self.target = target          # "matn" or "jeld"
        self.result_value = 0.0
        self.setLayoutDirection(Qt.RightToLeft)
        title = "کاغذ متن" if target == "matn" else "کاغذ جلد"
        self.setWindowTitle(f"🧮 محاسبه قیمت واحد {title}")
        self.setMinimumWidth(500)
        self._setup_ui()
        self._load_library()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # ── Library section ──────────────────────────────────────────────
        lib_group = QGroupBox("📚 انتخاب از کتابخانه ذخیره‌شده")
        lib_layout = QVBoxLayout()

        self.lib_table = QTableWidget(0, 4)
        self.lib_table.setHorizontalHeaderLabels(["ID", "نام کاغذ", "فرمول", "قیمت واحد"])
        self.lib_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.lib_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.lib_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.lib_table.setMaximumHeight(150)
        lib_layout.addWidget(self.lib_table)

        self.empty_lib_label = QLabel("هنوز محاسبه‌ای ذخیره نشده")
        self.empty_lib_label.setAlignment(Qt.AlignCenter)
        self.empty_lib_label.setStyleSheet("color: gray;")
        self.empty_lib_label.hide()
        lib_layout.addWidget(self.empty_lib_label)

        use_saved_btn = QPushButton("✓ استفاده از ردیف انتخابی")
        use_saved_btn.setStyleSheet("background-color: #2a6496; color: white;")
        use_saved_btn.clicked.connect(self._apply_from_library)
        lib_layout.addWidget(use_saved_btn)

        lib_group.setLayout(lib_layout)
        main_layout.addWidget(lib_group)

        # ── Separator ────────────────────────────────────────────────────
        sep = QLabel("— یا محاسبه جدید —")
        sep.setAlignment(Qt.AlignCenter)
        sep.setStyleSheet("color: gray; font-size: 11px;")
        main_layout.addWidget(sep)

        # ── Calculator section ────────────────────────────────────────────
        calc_group = QGroupBox("🔢 محاسبه قیمت جدید")
        calc_vbox = QVBoxLayout()

        self.formula_combo = QComboBox()
        self.formula_combo.addItems([
            "ابعاد، وزن و قیمت (هر واحد)",
            "قیمت هر بند و تعداد در بند",
            "دستی"
        ])
        self.formula_combo.currentIndexChanged.connect(self._update_formula_page)
        calc_vbox.addWidget(self.formula_combo)

        self.stacked = QStackedWidget()

        # Page 0 — dimensions × weight × price
        page0 = QWidget()
        f0 = QFormLayout(page0)
        self.dlg_weight_spin = QDoubleSpinBox(); self.dlg_weight_spin.setMaximum(999999)
        self.dlg_height_spin = QDoubleSpinBox(); self.dlg_height_spin.setMaximum(999999)
        self.dlg_length_spin = QDoubleSpinBox(); self.dlg_length_spin.setMaximum(999999)
        self.dlg_price1_spin = QDoubleSpinBox()
        self.dlg_price1_spin.setMaximum(9999999999.99)
        self.dlg_price1_spin.setGroupSeparatorShown(True)
        f0.addRow("وزن (گرم):", self.dlg_weight_spin)
        f0.addRow("ارتفاع (سانتی‌متر):", self.dlg_height_spin)
        f0.addRow("طول (سانتی‌متر):", self.dlg_length_spin)
        f0.addRow("قیمت (هر ۱۰۰۰ برگ):", self.dlg_price1_spin)
        self.stacked.addWidget(page0)

        # Page 1 — bundle price
        page1 = QWidget()
        f1 = QFormLayout(page1)
        self.dlg_count_spin = QSpinBox(); self.dlg_count_spin.setMaximum(999999)
        self.dlg_price2_spin = QDoubleSpinBox()
        self.dlg_price2_spin.setMaximum(9999999999.99)
        self.dlg_price2_spin.setGroupSeparatorShown(True)
        f1.addRow("تعداد در بند:", self.dlg_count_spin)
        f1.addRow("قیمت هر بند:", self.dlg_price2_spin)
        self.stacked.addWidget(page1)

        # Page 2 — manual
        page2 = QWidget()
        f2 = QFormLayout(page2)
        self.dlg_manual_spin = QDoubleSpinBox()
        self.dlg_manual_spin.setMaximum(9999999999.99)
        self.dlg_manual_spin.setGroupSeparatorShown(True)
        f2.addRow("قیمت واحد (مستقیم):", self.dlg_manual_spin)
        self.stacked.addWidget(page2)

        calc_vbox.addWidget(self.stacked)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("نام کاغذ برای ذخیره در کتابخانه (اختیاری)")
        calc_vbox.addWidget(self.name_input)

        self.result_label = QLabel("قیمت واحد: ۰")
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setStyleSheet(
            "background-color: #1a2a1a; border: 1px solid #2d5a27;"
            "color: #4caf50; font-size: 16px; font-weight: bold;"
            "padding: 8px; border-radius: 4px;"
        )
        calc_vbox.addWidget(self.result_label)
        calc_group.setLayout(calc_vbox)
        main_layout.addWidget(calc_group)

        # ── Footer ────────────────────────────────────────────────────────
        footer = QHBoxLayout()
        apply_btn = QPushButton("✓ اعمال در فیلد")
        apply_btn.setStyleSheet("background-color: #27ae60; color: white; padding: 6px 18px;")
        apply_btn.clicked.connect(self._apply_calculated)
        cancel_btn = QPushButton("انصراف")
        cancel_btn.clicked.connect(self.reject)
        footer.addWidget(apply_btn)
        footer.addWidget(cancel_btn)
        main_layout.addLayout(footer)

        # Live calculation signals
        for w in [self.dlg_weight_spin, self.dlg_height_spin, self.dlg_length_spin,
                  self.dlg_price1_spin, self.dlg_price2_spin, self.dlg_manual_spin]:
            w.valueChanged.connect(self._live_calculate)
        self.dlg_count_spin.valueChanged.connect(self._live_calculate)

    def _update_formula_page(self):
        self.stacked.setCurrentIndex(self.formula_combo.currentIndex())
        self._live_calculate()

    def _compute(self):
        idx = self.formula_combo.currentIndex()
        if idx == 0:
            h = self.dlg_height_spin.value()
            l = self.dlg_length_spin.value()
            w = self.dlg_weight_spin.value()
            p = self.dlg_price1_spin.value()
            if h > 0 and l > 0 and w > 0:
                return ((h * l) * w / 10000) * (p / 1000)
        elif idx == 1:
            count = self.dlg_count_spin.value()
            p = self.dlg_price2_spin.value()
            if count > 0:
                return p / count
        else:
            return self.dlg_manual_spin.value()
        return 0.0

    def _live_calculate(self):
        self.result_value = self._compute()
        self.result_label.setText(f"قیمت واحد: {self.result_value:,.2f} تومان")

    def _load_library(self):
        try:
            cursor = self.db_conn.cursor()
            cursor.execute(
                "SELECT id, paper_type, formula_type, unit_price "
                "FROM paper_calculations ORDER BY id DESC"
            )
            rows = cursor.fetchall()
        except Exception:
            rows = []

        self.lib_table.setRowCount(0)
        if not rows:
            self.lib_table.hide()
            self.empty_lib_label.show()
            return

        self.lib_table.show()
        self.empty_lib_label.hide()
        for row in rows:
            r = self.lib_table.rowCount()
            self.lib_table.insertRow(r)
            self.lib_table.setItem(r, 0, QTableWidgetItem(str(row['id'])))
            self.lib_table.setItem(r, 1, QTableWidgetItem(row['paper_type']))
            self.lib_table.setItem(r, 2, QTableWidgetItem(row['formula_type']))
            self.lib_table.setItem(r, 3, QTableWidgetItem(f"{row['unit_price']:,.2f}"))
        self.lib_table.hideColumn(0)

    def _apply_from_library(self):
        row = self.lib_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "توجه", "لطفاً یک ردیف را انتخاب کنید.")
            return
        text = self.lib_table.item(row, 3).text().replace(",", "")
        self.result_value = float(text)
        self.accept()

    def _apply_calculated(self):
        self.result_value = self._compute()
        if self.result_value <= 0:
            QMessageBox.warning(self, "خطا", "قیمت محاسبه‌شده معتبر نیست.")
            return
        name = self.name_input.text().strip()
        if name:
            self._save_to_library(name)
        self.accept()

    def _save_to_library(self, name):
        idx = self.formula_combo.currentIndex()
        formulas = [
            "ابعاد، وزن و قیمت (هر واحد)",
            "قیمت هر بند و تعداد در بند",
            "دستی"
        ]
        w = self.dlg_weight_spin.value() if idx == 0 else 0
        h = self.dlg_height_spin.value() if idx == 0 else 0
        l = self.dlg_length_spin.value() if idx == 0 else 0
        count = self.dlg_count_spin.value() if idx == 1 else 0
        prices = [self.dlg_price1_spin.value(), self.dlg_price2_spin.value(), self.dlg_manual_spin.value()]
        try:
            cursor = self.db_conn.cursor()
            cursor.execute(
                "INSERT INTO paper_calculations "
                "(paper_type, formula_type, weight, height, length, bundle_count, bundle_weight, price, unit_price) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (name, formulas[idx], w, h, l, count, 0, prices[idx], self.result_value)
            )
            self.db_conn.commit()
            if hasattr(self.parent(), 'load_paper_calculations'):
                self.parent().load_paper_calculations()
        except Exception as e:
            QMessageBox.warning(self, "خطا", f"ذخیره‌سازی با خطا مواجه شد:\n{e}")
```

- [ ] **Step 2: Run the app to verify the class loads without errors**

```bash
cd /home/mg/book_price && source .venv/bin/activate && python -c "from main import PaperPriceDialog; print('OK')"
```

Expected output: `OK`

If you see an `ImportError` or `NameError`, check that the class was inserted before `class BookCostCalculator` and that no indentation errors were introduced.

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add PaperPriceDialog class with library and calculator"
```

---

### Task 2: Wire "🧮 محاسبه" buttons into Tab 1

**Files:**
- Modify: `main.py:389` — replace `addRow` for matn paper unit price
- Modify: `main.py:411` — replace `addRow` for jeld paper unit price
- Add method `open_paper_price_dialog` to `BookCostCalculator`

- [ ] **Step 1: Replace the matn paper unit price row**

In `setup_data_entry_tab`, find this line (around line 389):
```python
            calc_layout.addRow("قیمت واحد هر ورق کاغذ متن:", self.unit_price_paper_matn_spin)
```

Replace it with:
```python
            matn_price_row = QWidget()
            matn_price_layout = QHBoxLayout(matn_price_row)
            matn_price_layout.setContentsMargins(0, 0, 0, 0)
            matn_price_layout.addWidget(self.unit_price_paper_matn_spin)
            btn_calc_matn = QPushButton("🧮 محاسبه")
            btn_calc_matn.setStyleSheet("background-color: #2a6496; color: white; padding: 4px 10px;")
            btn_calc_matn.clicked.connect(lambda: self.open_paper_price_dialog("matn"))
            matn_price_layout.addWidget(btn_calc_matn)
            calc_layout.addRow("قیمت واحد هر ورق کاغذ متن:", matn_price_row)
```

- [ ] **Step 2: Replace the jeld paper unit price row**

In `setup_data_entry_tab`, find this line (around line 411):
```python
            calc_layout.addRow("قیمت واحد هر ورق کاغذ جلد:", self.unit_price_paper_jeld_spin)
```

Replace it with:
```python
            jeld_price_row = QWidget()
            jeld_price_layout = QHBoxLayout(jeld_price_row)
            jeld_price_layout.setContentsMargins(0, 0, 0, 0)
            jeld_price_layout.addWidget(self.unit_price_paper_jeld_spin)
            btn_calc_jeld = QPushButton("🧮 محاسبه")
            btn_calc_jeld.setStyleSheet("background-color: #2a6496; color: white; padding: 4px 10px;")
            btn_calc_jeld.clicked.connect(lambda: self.open_paper_price_dialog("jeld"))
            jeld_price_layout.addWidget(btn_calc_jeld)
            calc_layout.addRow("قیمت واحد هر ورق کاغذ جلد:", jeld_price_row)
```

- [ ] **Step 3: Add `open_paper_price_dialog` method to `BookCostCalculator`**

Find any convenient location inside `BookCostCalculator` (e.g., after `auto_calculate_costs` around line 510). Add this method:

```python
    def open_paper_price_dialog(self, target):
        dlg = PaperPriceDialog(self.db_conn, target, parent=self)
        if dlg.exec() == QDialog.Accepted:
            if target == "matn":
                self.unit_price_paper_matn_spin.setValue(dlg.result_value)
            else:
                self.unit_price_paper_jeld_spin.setValue(dlg.result_value)
```

- [ ] **Step 4: Run the app and verify end-to-end**

```bash
cd /home/mg/book_price && source .venv/bin/activate && python main.py
```

Manually verify the following:
1. Tab 1 → "محاسبات هوشمند کاغذ و زینک" → both paper unit price rows now show a blue "🧮 محاسبه" button
2. Click "🧮 محاسبه" next to **کاغذ متن** → dialog opens with title "محاسبه قیمت واحد کاغذ متن"
3. With empty library → "هنوز محاسبه‌ای ذخیره نشده" label is shown
4. Switch formula dropdown to "دستی" → stacked widget changes to manual input page
5. Enter a value in the manual field → result label updates live
6. Click "✓ اعمال در فیلد" → dialog closes, `unit_price_paper_matn_spin` updates, `هزینه کاغذ متن` auto-recalculates
7. Click "🧮 محاسبه" again → enter a name in the optional field, click Apply → row appears in library next time dialog opens
8. Open dialog again → click "✓ استفاده از ردیف انتخابی" on the saved row → price fills in
9. Click "🧮 محاسبه" next to **کاغذ جلد** → dialog opens with correct title "محاسبه قیمت واحد کاغذ جلد"
10. Tab 4 and Tab 5 still function normally (no regressions)

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "feat: wire paper price calculator buttons into Tab 1 data entry"
```

---

## Verification Summary

After both tasks are complete and committed, the full verification from the spec is satisfied:
- No tab switching needed to calculate paper unit prices
- Saved paper calculations are accessible from Tab 1 as a one-click library
- Fresh calculations auto-save to the library when a name is provided
- Tab 4 (Paper Preprocessing) and Tab 5 (Base Price Management) are untouched
- `auto_calculate_costs()` fires automatically after price is applied (via existing `valueChanged` connection)
