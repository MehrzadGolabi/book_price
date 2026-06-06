# Calculation Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three calculation bugs (wrong formula label, zinc pricing ignored, no waste factor) and add custom book size support with automatic orientation optimization.

**Architecture:** All changes are in-place edits to `main.py` (single-file app). DB schema additions via `ALTER TABLE` at startup. No new files needed.

**Tech Stack:** PySide6, SQLite3, Python 3.x

---

## File Map

| File | Changes |
|------|---------|
| `main.py:313-403` | `connect_db()` — add `zinc_prices` table creation + `ALTER TABLE` for new `project_details` columns |
| `main.py:291-298` | `OPTIMAL_SPECS` — add 4 new entries (مربع, بزرگ‌قطع, کوچک‌قطع, سفارشی) |
| `main.py:521-728` | `setup_details_tab()` — add paper_size_combo, book dimension inputs, orientation label, waste_percent_spin; remove unit_price_zinc_spin; add zinc price lookup labels |
| `main.py:710-728` | Signal connections block — update/add connections for new widgets |
| `main.py:729-757` | `auto_calculate_costs()` — add waste factor and per-size zinc pricing |
| `main.py:866-1033` | `save_project_to_db()` — add new columns to INSERT/UPDATE queries |
| `main.py:1256-1358` | `load_project_by_id()` — restore new fields from DB |
| `main.py:1373-1417` | `new_project()` — reset new fields to defaults |
| `main.py:1473-1561` | `setup_paper_calc_tab()` — fix `paper_price_spin` label; store label ref as `self.paper_price_label` |
| `main.py:1563-1585` | `update_paper_inputs_visibility()` — update `self.paper_price_label` text per formula |
| `main.py:58-287` | `PaperPriceDialog._setup_ui()` — fix "قیمت (هر ۱۰۰۰ برگ):" label |
| `main.py:1766-1826` | `setup_default_costs_tab()` / new `setup_zinc_prices_section()` — prepend zinc price table to Tab 5 |
| `main.py:2040-2064` | `suggest_optimal_layout()` — handle `pages_per_sheet: None` for custom formats |
| `main.py` (new methods) | `_get_zinc_price()`, `_compute_optimal_orientation()`, `_update_zinc_price_labels()`, `load_zinc_prices_table()`, `save_zinc_price()` |

---

## Task 1: DB Schema — zinc_prices table + new project_details columns

**Files:**
- Modify: `main.py:313-403` (`connect_db`)

- [ ] **Step 1: Add `zinc_prices` table creation to `connect_db`**

In `connect_db`, the `executescript` block ends at the `default_cost_mappings` table definition (around line 395). Add the zinc_prices table inside that same `executescript` call, after `default_cost_mappings`:

```python
                    CREATE TABLE IF NOT EXISTS zinc_prices (
                        zinc_size TEXT PRIMARY KEY,
                        unit_price REAL DEFAULT 0
                    );
```

- [ ] **Step 2: Pre-populate zinc_prices with zero prices**

After `self.db_conn.commit()` (the commit after `executescript`), add:

```python
                zinc_sizes = [
                    "زینک 2 ورقی", "زینک 2.5 ورقی", "زینک 3.5 ورقی",
                    "زینک 4.5 ورقی", "زینک GTO"
                ]
                for zs in zinc_sizes:
                    self.cursor.execute(
                        "INSERT OR IGNORE INTO zinc_prices (zinc_size, unit_price) VALUES (?, 0)",
                        (zs,)
                    )
                self.db_conn.commit()
```

- [ ] **Step 3: Add new `project_details` columns via ALTER TABLE**

After the pre-populate block, add:

```python
                new_cols = [
                    ("waste_percent", "REAL DEFAULT 5"),
                    ("book_width", "REAL"),
                    ("book_height", "REAL"),
                    ("paper_size", "TEXT"),
                    ("orientation", "TEXT"),
                    ("pages_per_sheet", "INTEGER"),
                ]
                for col_name, col_def in new_cols:
                    try:
                        self.cursor.execute(
                            f"ALTER TABLE project_details ADD COLUMN {col_name} {col_def}"
                        )
                        self.db_conn.commit()
                    except sqlite3.OperationalError:
                        pass  # column already exists
```

- [ ] **Step 4: Verify by running the app**

```bash
cd /home/mg/book_price && source .venv/bin/activate && python -c "
import sqlite3
conn = sqlite3.connect('book_publishing.db')
c = conn.cursor()
c.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name='zinc_prices'\")
print('zinc_prices table:', c.fetchone())
c.execute('SELECT * FROM zinc_prices')
print('zinc rows:', c.fetchall())
c.execute('PRAGMA table_info(project_details)')
cols = [r[1] for r in c.fetchall()]
print('new cols present:', all(x in cols for x in ['waste_percent','book_width','book_height','paper_size','orientation','pages_per_sheet']))
conn.close()
"
```

Expected: `zinc_prices table: ('zinc_prices',)`, 5 zinc rows, `new cols present: True`

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "feat: add zinc_prices table and new project_details columns"
```

---

## Task 2: Formula 1 Label Fix

**Files:**
- Modify: `main.py:1473-1585` (`setup_paper_calc_tab`, `update_paper_inputs_visibility`)
- Modify: `main.py:124-136` (`PaperPriceDialog._setup_ui`)

The problem: The label for `paper_price_spin` (Tab 4) and `dlg_price1_spin` (dialog) says "per 1000 sheets" but Formula 1 expects a **per-kg** price.

- [ ] **Step 1: Store the Tab 4 price label as an instance variable**

In `setup_paper_calc_tab`, find line 1519:
```python
        form.addRow("قیمت / قیمت بند (تومان):", self.paper_price_spin)
```

Replace with:
```python
        self.paper_price_label = QLabel("قیمت / قیمت بند (تومان):")
        form.addRow(self.paper_price_label, self.paper_price_spin)
```

- [ ] **Step 2: Update `update_paper_inputs_visibility` to change the label**

Find the method `update_paper_inputs_visibility` at line ~1563. Replace its entire body with:

```python
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
```

- [ ] **Step 3: Fix the dialog label**

In `PaperPriceDialog._setup_ui`, find line 135:
```python
        f0.addRow("قیمت (هر ۱۰۰۰ برگ):", self.dlg_price1_spin)
```

Replace with:
```python
        f0.addRow("قیمت کاغذ (هر کیلوگرم):", self.dlg_price1_spin)
```

- [ ] **Step 4: Verify**

Run the app. Open Tab 4 (محاسبات پیش‌پردازش کاغذ). Select formula "ابعاد، وزن و قیمت" — label should read "قیمت کاغذ (هر کیلوگرم):". Switch to "قیمت هر بند" — label should read "قیمت هر بند:". Open the 🧮 dialog from Tab 1 — the first formula's price field label should say "قیمت کاغذ (هر کیلوگرم):".

```bash
cd /home/mg/book_price && source .venv/bin/activate && python main.py
```

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "fix: correct Formula 1 paper price label to 'per kg' in Tab 4 and dialog"
```

---

## Task 3: Waste Factor

**Files:**
- Modify: `main.py:596-728` (`setup_details_tab` — calc_group section)
- Modify: `main.py:729-757` (`auto_calculate_costs`)
- Modify: `main.py:866-1033` (`save_project_to_db`)
- Modify: `main.py:1256-1358` (`load_project_by_id`)
- Modify: `main.py:1373-1417` (`new_project`)

- [ ] **Step 1: Add waste_percent_spin widget to calc_group**

In `setup_details_tab`, find the line after the zinc spinbox is removed (which we'll do in Task 4). For now, add the waste spin immediately before `self.calc_group.setLayout(calc_layout)` at line ~665:

```python
            self.waste_percent_spin = QDoubleSpinBox()
            self.waste_percent_spin.setRange(0, 50)
            self.waste_percent_spin.setDecimals(1)
            self.waste_percent_spin.setValue(5.0)
            self.waste_percent_spin.setSuffix(" %")
            calc_layout.addRow("ضایعات کاغذ:", self.waste_percent_spin)
```

- [ ] **Step 2: Connect waste_percent_spin to auto_calculate_costs**

In the signal connections block (line ~716-728), the current list is:
```python
            widgets_to_connect = [
                self.form_matn_spin, self.unit_price_paper_matn_spin,
                self.form_jeld_spin, self.unit_price_paper_jeld_spin,
                self.unit_price_zinc_spin, self.inputs['تیراژ']
            ]
```

Add `self.waste_percent_spin` to that list:
```python
            widgets_to_connect = [
                self.form_matn_spin, self.unit_price_paper_matn_spin,
                self.form_jeld_spin, self.unit_price_paper_jeld_spin,
                self.inputs['تیراژ'], self.waste_percent_spin
            ]
```

(Note: `self.unit_price_zinc_spin` is removed in Task 4; do not include it here.)

- [ ] **Step 3: Update `auto_calculate_costs` to apply waste factor**

Replace the paper cost calculation in `auto_calculate_costs` (lines 744-751):

```python
        # Waste multiplier
        waste = 1 + self.waste_percent_spin.value() / 100

        # Paper Text
        total_paper_matn = (self.form_matn_spin.value() / sides_matn) * tiraj * waste
        calculated_paper_cost_matn = total_paper_matn * self.unit_price_paper_matn_spin.value()
        self.cost_inputs['هزینه کاغذ متن'].setValue(calculated_paper_cost_matn)

        # Paper Cover
        total_paper_jeld = (self.form_jeld_spin.value() / sides_jeld) * tiraj * waste
        calculated_paper_cost_jeld = total_paper_jeld * self.unit_price_paper_jeld_spin.value()
        self.cost_inputs['هزینه کاغذ جلد'].setValue(calculated_paper_cost_jeld)
```

- [ ] **Step 4: Add `waste_percent` to INSERT query in `save_project_to_db`**

In the INSERT branch (lines 975-1017), extend the column list and values tuple. Find:
```python
                query_details = """
                    INSERT INTO project_details (
                        project_id, noeh_kaghaz_matn, noeh_chap_matn, noeh_rang_matn, noeh_zink_matn,
                        noeh_kaghaz_jeld, noeh_chap_jeld, noeh_rang_jeld, noeh_zink_jeld,
                        form_matn, is_double_sided_matn, color_count_matn, zinc_size_matn,
                        form_jeld, is_double_sided_jeld, color_count_jeld, zinc_size_jeld,
                        unit_price_paper_matn, unit_price_paper_jeld, unit_price_zinc,
```

Add `waste_percent` after `unit_price_zinc`:
```python
                query_details = """
                    INSERT INTO project_details (
                        project_id, noeh_kaghaz_matn, noeh_chap_matn, noeh_rang_matn, noeh_zink_matn,
                        noeh_kaghaz_jeld, noeh_chap_jeld, noeh_rang_jeld, noeh_zink_jeld,
                        form_matn, is_double_sided_matn, color_count_matn, zinc_size_matn,
                        form_jeld, is_double_sided_jeld, color_count_jeld, zinc_size_jeld,
                        unit_price_paper_matn, unit_price_paper_jeld, unit_price_zinc, waste_percent,
```

Add `self.waste_percent_spin.value()` to the matching position in `val_details` after `self.unit_price_zinc_spin.value()` (or `0` after we replace the zinc spin in Task 4):

```python
                    self.unit_price_paper_matn_spin.value(), self.unit_price_paper_jeld_spin.value(), 0, self.waste_percent_spin.value(),
```

Do the same for the UPDATE branch — add `waste_percent = ?,` in the SET clause and `self.waste_percent_spin.value()` in the corresponding position in `val_details`.

In the UPDATE query (lines 913-951), find:
```python
                        unit_price_paper_matn = ?, unit_price_paper_jeld = ?, unit_price_zinc = ?,
```
Replace with:
```python
                        unit_price_paper_matn = ?, unit_price_paper_jeld = ?, unit_price_zinc = ?, waste_percent = ?,
```

And in the UPDATE `val_details`, find:
```python
                    self.unit_price_paper_matn_spin.value(), self.unit_price_paper_jeld_spin.value(), self.unit_price_zinc_spin.value(),
```
Replace with:
```python
                    self.unit_price_paper_matn_spin.value(), self.unit_price_paper_jeld_spin.value(), 0, self.waste_percent_spin.value(),
```

- [ ] **Step 5: Load `waste_percent` in `load_project_by_id`**

After the block that loads `unit_price_paper_jeld` and `unit_price_zinc` (around line 1319), add:

```python
                if 'waste_percent' in details and details['waste_percent'] is not None:
                    self.waste_percent_spin.setValue(float(details['waste_percent']))
                else:
                    self.waste_percent_spin.setValue(5.0)
```

- [ ] **Step 6: Reset `waste_percent` in `new_project`**

After `self.unit_price_paper_jeld_spin.setValue(0.0)` (line ~1403), add:
```python
        self.waste_percent_spin.setValue(5.0)
```

- [ ] **Step 7: Verify**

Run app, create a project with tiraj=1000, form_matn=16, double-sided, unit price = 1.0. With waste at 0%: هزینه کاغذ متن = 8000. With waste at 10%: هزینه کاغذ متن = 8800.

- [ ] **Step 8: Commit**

```bash
git add main.py
git commit -m "feat: add configurable waste factor to paper cost calculation (default 5%)"
```

---

## Task 4: Zinc Pricing Table (Tab 5) + Auto-Lookup (Tab 1)

**Files:**
- Modify: `main.py:596-728` (`setup_details_tab` — remove zinc spin, add lookup labels)
- Modify: `main.py:729-757` (`auto_calculate_costs` — new zinc formula)
- Modify: `main.py:1766-1826` (`setup_default_costs_tab` — prepend zinc group)
- Add new methods: `_get_zinc_price`, `_update_zinc_price_labels`, `load_zinc_prices_table`, `save_zinc_price`

### Part A — Remove `unit_price_zinc_spin`, add lookup labels in Tab 1

- [ ] **Step 1: Remove unit_price_zinc_spin from calc_group**

In `setup_details_tab`, find and delete these three lines (around line 660-663):
```python
            self.unit_price_zinc_spin = QDoubleSpinBox()
            self.unit_price_zinc_spin.setMaximum(9999999999.99)
            self.unit_price_zinc_spin.setGroupSeparatorShown(True)
            calc_layout.addRow("قیمت واحد هر زینک:", self.unit_price_zinc_spin)
```

- [ ] **Step 2: Add zinc price lookup label for متن after zinc_size_matn_combo row**

After `calc_layout.addRow("ابعاد زینک متن:", self.zinc_size_matn_combo)` (line ~619), add:

```python
            self.zinc_price_matn_label = QLabel("—")
            self.zinc_price_matn_label.setAlignment(Qt.AlignCenter)
            calc_layout.addRow("قیمت واحد زینک متن:", self.zinc_price_matn_label)
```

- [ ] **Step 3: Add zinc price lookup label for جلد after zinc_size_jeld_combo row**

After `calc_layout.addRow("ابعاد زینک جلد:", self.zinc_size_jeld_combo)` (line ~649), add:

```python
            self.zinc_price_jeld_label = QLabel("—")
            self.zinc_price_jeld_label.setAlignment(Qt.AlignCenter)
            calc_layout.addRow("قیمت واحد زینک جلد:", self.zinc_price_jeld_label)
```

- [ ] **Step 4: Add `_get_zinc_price` helper method**

Add this method to `BookCostCalculator`, before `auto_calculate_costs`:

```python
    def _get_zinc_price(self, zinc_size):
        try:
            self.cursor.execute(
                "SELECT unit_price FROM zinc_prices WHERE zinc_size = ?", (zinc_size,)
            )
            row = self.cursor.fetchone()
            return row['unit_price'] if row else 0.0
        except sqlite3.Error:
            return 0.0
```

- [ ] **Step 5: Add `_update_zinc_price_labels` method**

Add this method after `_get_zinc_price`:

```python
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
```

- [ ] **Step 6: Connect zinc combos to `_update_zinc_price_labels` and `auto_calculate_costs`**

In the signal connections block (lines ~724-728), add after the existing color combo connections:

```python
            self.zinc_size_matn_combo.currentIndexChanged.connect(self._update_zinc_price_labels)
            self.zinc_size_matn_combo.currentIndexChanged.connect(self.auto_calculate_costs)
            self.zinc_size_jeld_combo.currentIndexChanged.connect(self._update_zinc_price_labels)
            self.zinc_size_jeld_combo.currentIndexChanged.connect(self.auto_calculate_costs)
```

Also call `self._update_zinc_price_labels()` at the very end of `setup_details_tab` (after the signal connections) to initialize the labels on startup.

- [ ] **Step 7: Update zinc formula in `auto_calculate_costs`**

Replace the current zinc block (lines ~754-757):
```python
        # Zinc
        total_zincs_matn = self.form_matn_spin.value() * text_colors
        total_zincs_jeld = self.form_jeld_spin.value() * cover_colors
        total_zinc_cost = (total_zincs_matn + total_zincs_jeld) * self.unit_price_zinc_spin.value()
        self.cost_inputs['هزینه زینک'].setValue(total_zinc_cost)
```

With:
```python
        # Zinc — per-size pricing
        total_zincs_matn = self.form_matn_spin.value() * text_colors
        total_zincs_jeld = self.form_jeld_spin.value() * cover_colors
        zinc_price_matn = self._get_zinc_price(self.zinc_size_matn_combo.currentText())
        zinc_price_jeld = self._get_zinc_price(self.zinc_size_jeld_combo.currentText())
        total_zinc_cost = (total_zincs_matn * zinc_price_matn) + (total_zincs_jeld * zinc_price_jeld)
        self.cost_inputs['هزینه زینک'].setValue(total_zinc_cost)
```

### Part B — Add zinc prices section to Tab 5

- [ ] **Step 8: Add `load_zinc_prices_table` and `save_zinc_price` methods**

Add these two new methods to `BookCostCalculator`:

```python
    def load_zinc_prices_table(self):
        zinc_sizes = ["زینک 2 ورقی", "زینک 2.5 ورقی", "زینک 3.5 ورقی", "زینک 4.5 ورقی", "زینک GTO"]
        self.zinc_prices_table.setRowCount(len(zinc_sizes))
        for i, zs in enumerate(zinc_sizes):
            self.zinc_prices_table.setItem(i, 0, QTableWidgetItem(zs))
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
            self.cursor.execute(
                "INSERT OR REPLACE INTO zinc_prices (zinc_size, unit_price) VALUES (?, ?)",
                (zinc_size, price)
            )
            self.db_conn.commit()
            self._update_zinc_price_labels()
            self.auto_calculate_costs()
            QMessageBox.information(self, "ذخیره شد", f"قیمت {zinc_size} ذخیره شد.")
        except sqlite3.Error as err:
            QMessageBox.critical(self, "خطا", f"ذخیره قیمت زینک با خطا مواجه شد:\n{err}")
```

- [ ] **Step 9: Prepend zinc prices group to `setup_default_costs_tab`**

At the very start of `setup_default_costs_tab` (line ~1766), before `layout = QVBoxLayout()`, do nothing — but right after `layout = QVBoxLayout()` add:

```python
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
```

Then at the end of `setup_default_costs_tab`, after `self.load_default_costs_table()`, add:
```python
        self.load_zinc_prices_table()
```

- [ ] **Step 10: Also refresh zinc labels when Tab 5 is opened**

Connect tab change signal so zinc labels update when switching to Tab 1. Add to the signal connections block in `setup_details_tab`:

```python
            self.tabs.currentChanged.connect(lambda idx: self._update_zinc_price_labels() if idx == 1 else None)
```

- [ ] **Step 11: Verify**

Run app. Go to Tab 5 (مدیریت قیمت‌های پایه) — zinc prices group appears at top with 5 rows. Enter 150000 for "زینک 3.5 ورقی", click ذخیره. Go to Tab 1, select "زینک 3.5 ورقی" for text — label shows "150,000 تومان". Select "زینک GTO" (no price) — label shows warning in red.

- [ ] **Step 12: Commit**

```bash
git add main.py
git commit -m "feat: per-size zinc pricing table in Tab 5 with auto-lookup in Tab 1"
```

---

## Task 5: Custom Book Sizes + Orientation Optimization

**Files:**
- Modify: `main.py:291-298` (`OPTIMAL_SPECS`)
- Modify: `main.py:521-728` (`setup_details_tab` — new UI widgets in form_layout)
- Modify: `main.py:710-713` (signal connections for قطع)
- Modify: `main.py:866-1033` (`save_project_to_db` — add new columns)
- Modify: `main.py:1256-1358` (`load_project_by_id` — restore new fields)
- Modify: `main.py:1373-1417` (`new_project` — reset)
- Modify: `main.py:2040-2064` (`suggest_optimal_layout`)
- Add new methods: `_compute_optimal_orientation`, `_on_qate_changed`

### Part A — Extend OPTIMAL_SPECS

- [ ] **Step 1: Add 4 new entries to OPTIMAL_SPECS**

Replace the current `OPTIMAL_SPECS` dict (lines 291-298) with:

```python
    OPTIMAL_SPECS = {
        "وزیری":    {"paper_size": "70x100", "pages_per_sheet": 32, "zinc": "زینک 3.5 ورقی", "default_dims": None},
        "رقعی":     {"paper_size": "60x90",  "pages_per_sheet": 32, "zinc": "زینک 2.5 ورقی", "default_dims": None},
        "رحلی کوچک": {"paper_size": "60x90", "pages_per_sheet": 16, "zinc": "زینک 2.5 ورقی", "default_dims": None},
        "رحلی بزرگ": {"paper_size": "70x100","pages_per_sheet": 16, "zinc": "زینک 3.5 ورقی", "default_dims": None},
        "جیبی":     {"paper_size": "60x90",  "pages_per_sheet": 64, "zinc": "زینک 2.5 ورقی", "default_dims": None},
        "خشتی":     {"paper_size": "50x70",  "pages_per_sheet": 12, "zinc": "زینک 2 ورقی",   "default_dims": None},
        "مربع":     {"paper_size": "60x90",  "pages_per_sheet": None, "zinc": "زینک 2.5 ورقی", "default_dims": (21, 21)},
        "بزرگ‌قطع": {"paper_size": "70x100", "pages_per_sheet": None, "zinc": "زینک 3.5 ورقی", "default_dims": (24, 34)},
        "کوچک‌قطع": {"paper_size": "60x90",  "pages_per_sheet": None, "zinc": "زینک 2.5 ورقی", "default_dims": (14, 20)},
        "سفارشی":   {"paper_size": "70x100", "pages_per_sheet": None, "zinc": "زینک 3.5 ورقی", "default_dims": (None, None)},
    }
```

### Part B — New UI in form_layout

- [ ] **Step 2: Add new format options to قطع combo**

In `setup_details_tab`, find:
```python
            self.inputs['قطع'].addItems(["وزیری", "رقعی", "رحلی کوچک", "رحلی بزرگ", "جیبی", "خشتی"])
```

Replace with:
```python
            self.inputs['قطع'].addItems([
                "وزیری", "رقعی", "رحلی کوچک", "رحلی بزرگ", "جیبی", "خشتی",
                "مربع", "بزرگ‌قطع", "کوچک‌قطع", "سفارشی"
            ])
```

- [ ] **Step 3: Add paper_size_combo, book dimension inputs, orientation_label to form_layout**

After `form_layout.addRow("تعداد صفحات کتاب:", self.total_pages_spin)` (line ~572), add:

```python
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
            width_lbl = QLabel("عرض:")
            height_lbl = QLabel("  ارتفاع:")
            dims_layout.addWidget(width_lbl)
            dims_layout.addWidget(self.book_width_spin)
            dims_layout.addWidget(height_lbl)
            dims_layout.addWidget(self.book_height_spin)
            self.book_dims_row_widget = dims_widget
            form_layout.addRow("ابعاد کتاب:", self.book_dims_row_widget)

            # ── Orientation result label ───────────────────────────────────
            self.orientation_label = QLabel("")
            self.orientation_label.setWordWrap(True)
            self.orientation_label.setStyleSheet("color: #64b5f6;")
            form_layout.addRow("جهت بهینه:", self.orientation_label)
```

### Part C — Add new methods

- [ ] **Step 4: Add `_compute_optimal_orientation` method**

Add this method to `BookCostCalculator` before `suggest_optimal_layout`:

```python
    def _compute_optimal_orientation(self, book_w, book_h, paper_w, paper_h):
        portrait  = int((paper_w // book_w) * (paper_h // book_h))
        landscape = int((paper_w // book_h) * (paper_h // book_w))
        if landscape >= portrait:
            return "landscape", landscape * 2
        return "portrait", portrait * 2
```

### Part D — Update suggest_optimal_layout

- [ ] **Step 5: Rewrite `suggest_optimal_layout` to handle `pages_per_sheet: None`**

Replace the entire `suggest_optimal_layout` method (lines 2040-2064) with:

```python
    def suggest_optimal_layout(self):
        qate = self.inputs['قطع'].currentText()
        total_pages = self.total_pages_spin.value()
        specs = self.OPTIMAL_SPECS.get(qate)

        # Determine visibility of custom dimension / orientation widgets
        is_custom = specs is not None and specs['pages_per_sheet'] is None
        self.book_dims_row_widget.setVisible(is_custom)
        self.orientation_label.setVisible(is_custom)

        if specs is None or total_pages == 0:
            self.lbl_optimal_paper.setText("کاغذ بهینه: - | ورق مصرفی هر جلد: -")
            return

        if specs['pages_per_sheet'] is not None:
            # Standard format: existing behaviour unchanged
            pages_per_sheet = specs['pages_per_sheet']
            self.paper_size_combo.setCurrentText(specs['paper_size'].replace("x", "×"))
            self.orientation_label.setText("")
        else:
            # Custom/semi-custom: pre-fill dimensions if first time
            if specs['default_dims'] and specs['default_dims'][0] is not None:
                if self.book_width_spin.value() == self.book_width_spin.minimum():
                    self.book_width_spin.setValue(specs['default_dims'][0])
                    self.book_height_spin.setValue(specs['default_dims'][1])
            self.paper_size_combo.setCurrentText(specs['paper_size'].replace("x", "×"))

            book_w = self.book_width_spin.value()
            book_h = self.book_height_spin.value()
            paper_str = self.paper_size_combo.currentText().replace("×", "x")
            try:
                paper_w, paper_h = map(float, paper_str.split("x"))
            except ValueError:
                self.lbl_optimal_paper.setText("اندازه کاغذ نامعتبر است")
                return

            if book_w > 0 and book_h > 0:
                orientation, pages_per_sheet = self._compute_optimal_orientation(
                    book_w, book_h, paper_w, paper_h
                )
                alt_orientation = "portrait" if orientation == "landscape" else "landscape"
                if orientation == "landscape":
                    alt_pages = int((paper_w // book_w) * (paper_h // book_h)) * 2
                else:
                    alt_pages = int((paper_w // book_h) * (paper_h // book_w)) * 2
                saving = round((pages_per_sheet - alt_pages) / alt_pages * 100) if alt_pages > 0 else 0
                label_map = {"landscape": "افقی", "portrait": "عمودی"}
                text = f"جهت: {label_map[orientation]} — {pages_per_sheet} صفحه در ورق"
                if saving > 0:
                    text += f" ({saving}٪ بهتر از {label_map[alt_orientation]})"
                self.orientation_label.setText(text)
            else:
                pages_per_sheet = 1

        if specs.get('zinc'):
            self.zinc_size_matn_combo.setCurrentText(specs['zinc'])

        multiplier = 2 if self.double_sided_matn_chk.isChecked() else 1
        sheets_per_book = math.ceil(total_pages / pages_per_sheet) if pages_per_sheet > 0 else 0
        calculated_forms = sheets_per_book * multiplier
        self.form_matn_spin.setValue(calculated_forms)
        self.lbl_optimal_paper.setText(
            f"کاغذ بهینه: {specs['paper_size']} | ورق مصرفی هر جلد: {sheets_per_book}"
        )
```

- [ ] **Step 6: Connect book dimension spinboxes and paper_size_combo to suggest_optimal_layout**

In the signal connections block in `setup_details_tab`, add:

```python
            self.book_width_spin.valueChanged.connect(self.suggest_optimal_layout)
            self.book_height_spin.valueChanged.connect(self.suggest_optimal_layout)
            self.paper_size_combo.currentIndexChanged.connect(self.suggest_optimal_layout)
```

Also, call `self.suggest_optimal_layout()` at the end of `setup_details_tab` to set initial visibility:

```python
            self.suggest_optimal_layout()
```

### Part E — Save/load new fields

- [ ] **Step 7: Add new columns to INSERT/UPDATE in `save_project_to_db`**

Extend the INSERT column list (after `waste_percent`) to also include:
`book_width, book_height, paper_size, orientation, pages_per_sheet`

Full column list addition in INSERT:
```python
                        unit_price_paper_matn, unit_price_paper_jeld, unit_price_zinc, waste_percent,
                        book_width, book_height, paper_size, orientation, pages_per_sheet,
```

Matching values in INSERT `val_details` (after `self.waste_percent_spin.value()`):
```python
                    self.unit_price_paper_matn_spin.value(), self.unit_price_paper_jeld_spin.value(),
                    0, self.waste_percent_spin.value(),
                    self.book_width_spin.value() if self.book_dims_row_widget.isVisible() else None,
                    self.book_height_spin.value() if self.book_dims_row_widget.isVisible() else None,
                    self.paper_size_combo.currentText().replace("×", "x"),
                    self.orientation_label.text() or None,
                    self.form_matn_spin.value(),
```

For UPDATE, add to the SET clause:
```python
                        book_width = ?, book_height = ?, paper_size = ?, orientation = ?, pages_per_sheet = ?,
```

And matching values in UPDATE `val_details`:
```python
                    self.book_width_spin.value() if self.book_dims_row_widget.isVisible() else None,
                    self.book_height_spin.value() if self.book_dims_row_widget.isVisible() else None,
                    self.paper_size_combo.currentText().replace("×", "x"),
                    self.orientation_label.text() or None,
                    self.form_matn_spin.value(),
```

- [ ] **Step 8: Load new fields in `load_project_by_id`**

After the `waste_percent` load block (added in Task 3), add:

```python
                if 'book_width' in details and details['book_width'] is not None:
                    self.book_width_spin.setValue(float(details['book_width']))
                if 'book_height' in details and details['book_height'] is not None:
                    self.book_height_spin.setValue(float(details['book_height']))
                if 'paper_size' in details and details['paper_size']:
                    self.paper_size_combo.setCurrentText(details['paper_size'].replace("x", "×"))
```

- [ ] **Step 9: Reset new fields in `new_project`**

Add after `self.waste_percent_spin.setValue(5.0)`:

```python
        self.book_width_spin.setValue(self.book_width_spin.minimum())
        self.book_height_spin.setValue(self.book_height_spin.minimum())
        self.paper_size_combo.setCurrentIndex(0)
        self.orientation_label.setText("")
```

- [ ] **Step 10: Verify**

Run app. Select "وزیری" — book_dims and orientation rows are hidden. Select "سفارشی" — they appear. Enter 20×30 cm, paper 70×100 — orientation label shows "جهت: افقی — 20 صفحه در ورق (11٪ بهتر از عمودی)". Select "مربع" — dims auto-fill to 21×21. 

- [ ] **Step 11: Commit**

```bash
git add main.py
git commit -m "feat: add custom book sizes with automatic orientation optimization"
```

---

## Task 6: Final Integration Check

- [ ] **Step 1: Run the app and do full end-to-end test**

```bash
cd /home/mg/book_price && source .venv/bin/activate && python main.py
```

Verify all spec verification scenarios:

1. **Formula 1 label**: Tab 4 → "ابعاد، وزن و قیمت" label reads "قیمت کاغذ (هر کیلوگرم):". Switch to "قیمت هر بند" → label reads "قیمت هر بند:". Same in popup dialog.
2. **Waste factor**: waste=10%, form_matn=16, دورو, tiraj=1000, unit price=1.0 → هزینه کاغذ متن = 8800. Set waste=0% → هزینه کاغذ متن = 8000.
3. **Zinc table**: Tab 5 → set زینک 3.5 ورقی = 150000, save. Tab 1 → select زینک 3.5 ورقی → label shows "150,000 تومان" in green.
4. **Zinc warning**: Select زینک 2 ورقی (price=0) → label shows "⚠ قیمت تنظیم نشده" in red.
5. **Zinc formula**: form_matn=4, 4 colors (text) + form_jeld=1, 4 colors (cover). Zinc 3.5 = 150000. Cost = (4×4×150000) + (1×4×150000) = 3,000,000.
6. **Orientation**: Enter book 20×30 cm, paper 70×100 → landscape wins (20 pages vs 18).
7. **Standard formats**: Select وزیری → dim fields hidden, pages_per_sheet=32.
8. **Old project load**: Save a project, reopen it → no errors, waste defaults to 5% if project is old.

- [ ] **Step 2: Commit with final verification note**

```bash
git add main.py
git commit -m "feat: calculation overhaul — waste factor, per-size zinc pricing, custom book sizes

- Fix Formula 1 paper price label (per-kg, not per-1000-sheets)
- Add configurable waste factor (default 5%) to paper cost formula
- Add per-size zinc price table in Tab 5; auto-lookup in Tab 1
- Remove single zinc unit price spinbox; prices now per-size from DB
- Add 4 new book formats: مربع، بزرگ‌قطع، کوچک‌قطع، سفارشی
- Orientation optimization: auto-pick portrait/landscape for max pages/sheet
- Save/load all new fields in project_details"
```

---

## Verification Checklist

After all tasks complete, run these manual checks before declaring done:

- [ ] Open old project → loads without error, waste shows 5%, zinc cost = 0 (expected since zinc prices were not set before)
- [ ] Tab 4 formula label updates dynamically when switching formula type
- [ ] PaperPriceDialog formula 1 label says "هر کیلوگرم"
- [ ] Zinc prices set in Tab 5 immediately reflect in Tab 1 labels
- [ ] Zinc cost formula uses per-size price (not a single shared price)
- [ ] Waste factor at 5% produces results 5% higher than waste=0
- [ ] Custom book size (سفارشی) shows dimension inputs and orientation label
- [ ] Standard formats (وزیری etc.) hide dimension inputs and orientation label
- [ ] Orientation optimization correctly picks the orientation with more pages/sheet
- [ ] Project save/load round-trips all new fields without data loss
