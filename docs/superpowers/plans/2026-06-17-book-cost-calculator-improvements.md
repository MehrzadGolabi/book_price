# Book Cost Calculator Improvements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add book-type preset-driven form grouping, 7 new cost fields, and a profitability/pricing tab to the existing single-file PySide6 desktop app.

**Architecture:** All code lives in `main.py` (single-file app, ~2582 lines). The refactor reorganizes `setup_details_tab()` into 5 `QGroupBox` sections driven by a `BOOK_TYPE_PRESETS` dict. A new `setup_pricing_tab()` method creates Tab 3 (shifting existing tabs right by one). Pure pricing calculation functions live at module level for testability.

**Tech Stack:** PySide6, SQLite (sqlite3), Python 3.x, pytest (dev only — `pip install pytest`)

---

## File Map

| File | Change |
|---|---|
| `main.py` | All changes — see tasks below |
| `tests/test_pricing.py` | New — unit tests for module-level pricing functions |

---

## Task 1: DB Migration — Add 9 New Columns

**Files:**
- Modify: `main.py:643-652` (end of `new_cols` list in `connect_db()`)

- [ ] **Step 1: Extend the `new_cols` list**

Find the end of the `new_cols` list in `connect_db()`. The list currently ends with:
```python
("total_pages", "INTEGER DEFAULT 0"),
```

Add these 9 entries immediately after that line (before the closing `]`):

```python
                    ("hazineh_horoofchini",    "REAL DEFAULT 0"),
                    ("hazineh_mojawwez_ershad", "REAL DEFAULT 0"),
                    ("hazineh_shabok",          "REAL DEFAULT 0"),
                    ("hazineh_talakoobi",       "REAL DEFAULT 0"),
                    ("hazineh_uv_mowzei",       "REAL DEFAULT 0"),
                    ("hazineh_barjasteh",       "REAL DEFAULT 0"),
                    ("book_type_preset",        "TEXT DEFAULT 'شومیز ساده'"),
                    ("pricing_multiplier",      "REAL DEFAULT 2.5"),
                    ("distribution_percent",    "REAL DEFAULT 35.0"),
```

- [ ] **Step 2: Run the app to verify migration succeeds**

```bash
source .venv/bin/activate
python main.py
```

Expected: app launches without errors. Open Tab 1, create a new project, save it. If no crash, migration succeeded. Close the app.

- [ ] **Step 3: Verify columns exist in DB**

```bash
source .venv/bin/activate
python -c "
import sqlite3
conn = sqlite3.connect('book_publishing.db')
cols = [row[1] for row in conn.execute('PRAGMA table_info(project_details)')]
new = ['hazineh_horoofchini','hazineh_mojawwez_ershad','hazineh_shabok',
       'hazineh_talakoobi','hazineh_uv_mowzei','hazineh_barjasteh',
       'book_type_preset','pricing_multiplier','distribution_percent']
for c in new:
    print(c, '✓' if c in cols else '✗ MISSING')
"
```

Expected: all 9 columns print `✓`.

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat: add 9 new columns to project_details for presets and pricing"
```

---

## Task 2: Pricing Calculation Functions + Tests

**Files:**
- Modify: `main.py` — add 5 module-level functions before the `PaperPriceDialog` class (around line 58)
- Create: `tests/test_pricing.py`

These functions are pure (no Qt, no DB) so they can be tested without a running app.

- [ ] **Step 1: Write the failing tests first**

Create `tests/test_pricing.py`:

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import math

# Import will fail until functions exist in main.py
from main import (
    compute_cover_price,
    compute_net_revenue_per_copy,
    compute_break_even,
    compute_breakdown_pcts,
    compute_scenarios,
)


def test_cover_price():
    assert compute_cover_price(10_000, 2.5) == 25_000.0


def test_cover_price_zero_multiplier():
    assert compute_cover_price(10_000, 0) == 0.0


def test_net_revenue_per_copy():
    # cover=25000, dist=35%, royalty=10% → net = 25000 * 0.55 = 13750
    assert compute_net_revenue_per_copy(25_000, 35.0, 10.0) == 13_750.0


def test_break_even():
    # total_cost=1_000_000, net_per_copy=13_750 → ceil(72.7) = 73
    assert compute_break_even(1_000_000, 13_750) == 73


def test_break_even_zero_net():
    assert compute_break_even(1_000_000, 0) == 0


def test_compute_breakdown_pcts():
    bd = compute_breakdown_pcts(
        cover_price=25_000,
        cost_per_book=10_000,
        distribution_pct=35.0,
        author_royalty_pct=10.0,
    )
    assert bd['production_pct'] == 40.0
    assert bd['distribution_pct'] == 35.0
    assert bd['royalty_pct'] == 10.0
    assert bd['publisher_pct'] == 15.0
    assert abs(bd['production'] - 10_000) < 0.01
    assert abs(bd['distribution'] - 8_750) < 0.01
    assert abs(bd['royalty'] - 2_500) < 0.01
    assert abs(bd['publisher'] - 3_750) < 0.01


def test_compute_scenarios_shape():
    rows = compute_scenarios(
        total_cost=1_000_000,
        cost_per_book=10_000,
        tiraj=1000,
        distribution_pct=35.0,
        author_royalty_pct=10.0,
        multipliers=[2.5, 3.0, 3.5],
    )
    # 4 sales levels × 3 multipliers = 12 rows
    assert len(rows) == 12
    assert all('multiplier' in r and 'sales_qty' in r and 'net_profit' in r for r in rows)


def test_compute_scenarios_profit_signs():
    rows = compute_scenarios(
        total_cost=10_000_000,
        cost_per_book=10_000,
        tiraj=1000,
        distribution_pct=35.0,
        author_royalty_pct=10.0,
        multipliers=[2.5],
    )
    # 25% sales (250 copies) should be a loss
    row_25 = next(r for r in rows if r['sales_qty'] == 250)
    assert row_25['net_profit'] < 0
    # 100% sales (1000 copies) should be a profit
    row_100 = next(r for r in rows if r['sales_qty'] == 1000)
    assert row_100['net_profit'] > 0
```

- [ ] **Step 2: Run tests — expect import failure**

```bash
source .venv/bin/activate
pytest tests/test_pricing.py -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name 'compute_cover_price' from 'main'`

- [ ] **Step 3: Add the 5 functions to `main.py`**

Insert these functions immediately before the `class PaperPriceDialog` line (around line 58, after the `get_db_config` block and `DB_CONFIG = get_db_config()`):

```python
def compute_cover_price(cost_per_book: float, multiplier: float) -> float:
    return cost_per_book * multiplier


def compute_net_revenue_per_copy(cover_price: float, distribution_pct: float,
                                  author_royalty_pct: float) -> float:
    return cover_price * (1.0 - distribution_pct / 100.0 - author_royalty_pct / 100.0)


def compute_break_even(total_cost: float, net_revenue_per_copy: float) -> int:
    if net_revenue_per_copy <= 0:
        return 0
    return math.ceil(total_cost / net_revenue_per_copy)


def compute_breakdown_pcts(cover_price: float, cost_per_book: float,
                            distribution_pct: float, author_royalty_pct: float) -> dict:
    if cover_price <= 0:
        return {k: 0.0 for k in ['production_pct', 'distribution_pct', 'royalty_pct',
                                   'publisher_pct', 'production', 'distribution',
                                   'royalty', 'publisher']}
    production_pct = round(cost_per_book / cover_price * 100, 2)
    publisher_pct = max(0.0, round(100.0 - production_pct - distribution_pct - author_royalty_pct, 2))
    return {
        'production_pct':    production_pct,
        'distribution_pct':  distribution_pct,
        'royalty_pct':       author_royalty_pct,
        'publisher_pct':     publisher_pct,
        'production':        cost_per_book,
        'distribution':      cover_price * distribution_pct / 100.0,
        'royalty':           cover_price * author_royalty_pct / 100.0,
        'publisher':         cover_price * publisher_pct / 100.0,
    }


def compute_scenarios(total_cost: float, cost_per_book: float, tiraj: int,
                       distribution_pct: float, author_royalty_pct: float,
                       multipliers: list) -> list:
    rows = []
    for pct in [0.25, 0.5, 0.75, 1.0]:
        sales = max(1, int(tiraj * pct))
        for mult in multipliers:
            cover = compute_cover_price(cost_per_book, mult)
            net_per = compute_net_revenue_per_copy(cover, distribution_pct, author_royalty_pct)
            profit = net_per * sales - total_cost
            rows.append({'multiplier': mult, 'sales_qty': sales, 'net_profit': profit})
    return rows
```

- [ ] **Step 4: Run tests — expect all pass**

```bash
source .venv/bin/activate
pytest tests/test_pricing.py -v
```

Expected: 8 tests pass, 0 failures.

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_pricing.py
git commit -m "feat: add module-level pricing calculation functions with tests"
```

---

## Task 3: Add `BOOK_TYPE_PRESETS` and `COST_GROUPS` to `BookCostCalculator`

**Files:**
- Modify: `main.py:490` — add two class-level dicts immediately after `OPTIMAL_SPECS` (around line 490)

- [ ] **Step 1: Insert the two dicts**

Find the closing `}` of `OPTIMAL_SPECS` (around line 490). Insert the following immediately after it, before `def __init__`:

```python
    COST_GROUPS = {
        "خلاقیت و تحریریه": [
            "هزینه تالیف", "هزینه ترجمه", "هزینه تصویرگری", "هزینه ویرایش",
            "هزینه طراحی جلد", "هزینه مديريت آتليه", "هزینه حروفچینی و صفحه‌آرایی",
        ],
        "چاپ و مواد": [
            "هزینه زینک", "هزینه چاپ متن", "هزینه چاپ جلد",
            "هزینه کاغذ متن", "هزینه کاغذ جلد",
            "هزینه روکش سلفون", "هزینه مقوای مغذی",
        ],
        "تکمیل و صحافی": [
            "هزینه قالب لترپرس", "هزینه قالب دايكات", "هزینه خط تا",
            "هزینه ملزومات", "هزینه جلدسازی", "هزینه صحافی",
            "هزینه برش و بسته‌بندی", "هزینه حمل و نقل", "هزینه مونتاژ",
            "هزینه طلاکوبی", "هزینه UV موضعی", "هزینه برجسته‌کاری",
        ],
        "اداری و مجوزها": [
            "هزینه مجوز ارشاد", "هزینه ثبت شابک",
        ],
    }

    # None means show all fields
    BOOK_TYPE_PRESETS = {
        "شومیز ساده": [
            "هزینه تالیف", "هزینه ویرایش", "هزینه طراحی جلد",
            "هزینه مديريت آتليه", "هزینه حروفچینی و صفحه‌آرایی",
            "هزینه زینک", "هزینه چاپ متن", "هزینه چاپ جلد",
            "هزینه کاغذ متن", "هزینه کاغذ جلد", "هزینه روکش سلفون",
            "هزینه قالب لترپرس", "هزینه ملزومات", "هزینه جلدسازی",
            "هزینه صحافی", "هزینه برش و بسته‌بندی", "هزینه حمل و نقل",
            "هزینه مجوز ارشاد", "هزینه ثبت شابک",
        ],
        "گالینگور": [
            "هزینه تالیف", "هزینه ویرایش", "هزینه طراحی جلد",
            "هزینه مديريت آتليه", "هزینه حروفچینی و صفحه‌آرایی",
            "هزینه زینک", "هزینه چاپ متن", "هزینه چاپ جلد",
            "هزینه کاغذ متن", "هزینه کاغذ جلد", "هزینه مقوای مغذی",
            "هزینه قالب لترپرس", "هزینه قالب دايكات", "هزینه خط تا",
            "هزینه ملزومات", "هزینه جلدسازی", "هزینه صحافی",
            "هزینه برش و بسته‌بندی", "هزینه حمل و نقل", "هزینه مونتاژ",
            "هزینه مجوز ارشاد", "هزینه ثبت شابک",
        ],
        "کتاب مصور / رنگی": [
            "هزینه تالیف", "هزینه تصویرگری", "هزینه ویرایش", "هزینه طراحی جلد",
            "هزینه مديريت آتليه", "هزینه حروفچینی و صفحه‌آرایی",
            "هزینه زینک", "هزینه چاپ متن", "هزینه چاپ جلد",
            "هزینه کاغذ متن", "هزینه کاغذ جلد", "هزینه روکش سلفون",
            "هزینه قالب لترپرس", "هزینه ملزومات", "هزینه جلدسازی",
            "هزینه صحافی", "هزینه برش و بسته‌بندی", "هزینه حمل و نقل",
            "هزینه مجوز ارشاد", "هزینه ثبت شابک",
        ],
        "ترجمه": [
            "هزینه ترجمه", "هزینه ویرایش", "هزینه طراحی جلد",
            "هزینه مديريت آتليه", "هزینه حروفچینی و صفحه‌آرایی",
            "هزینه زینک", "هزینه چاپ متن", "هزینه چاپ جلد",
            "هزینه کاغذ متن", "هزینه کاغذ جلد", "هزینه روکش سلفون",
            "هزینه قالب لترپرس", "هزینه ملزومات", "هزینه جلدسازی",
            "هزینه صحافی", "هزینه برش و بسته‌بندی", "هزینه حمل و نقل",
            "هزینه مجوز ارشاد", "هزینه ثبت شابک",
        ],
        "ویژه / لوکس": [
            "هزینه تالیف", "هزینه تصویرگری", "هزینه ویرایش", "هزینه طراحی جلد",
            "هزینه مديريت آتليه", "هزینه حروفچینی و صفحه‌آرایی",
            "هزینه زینک", "هزینه چاپ متن", "هزینه چاپ جلد",
            "هزینه کاغذ متن", "هزینه کاغذ جلد",
            "هزینه روکش سلفون", "هزینه مقوای مغذی",
            "هزینه قالب لترپرس", "هزینه قالب دايكات", "هزینه خط تا",
            "هزینه ملزومات", "هزینه جلدسازی", "هزینه صحافی",
            "هزینه برش و بسته‌بندی", "هزینه حمل و نقل", "هزینه مونتاژ",
            "هزینه طلاکوبی", "هزینه UV موضعی", "هزینه برجسته‌کاری",
            "هزینه مجوز ارشاد", "هزینه ثبت شابک",
        ],
        "سفارشی": None,
    }
```

- [ ] **Step 2: Run the app to confirm no syntax errors**

```bash
source .venv/bin/activate
python main.py
```

Expected: app opens normally.

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add BOOK_TYPE_PRESETS and COST_GROUPS class-level dicts"
```

---

## Task 4: Add `_make_cost_row()` Helper and Initialize `cost_input_rows`

**Files:**
- Modify: `main.py` — add helper method to `BookCostCalculator`, initialize `self.cost_input_rows` in `__init__`

- [ ] **Step 1: Initialize `self.cost_input_rows` in `__init__`**

In `__init__`, after `self.db_conn = None`, add:

```python
        self.cost_input_rows: dict = {}   # field_name → QWidget row container
        self.cost_group_boxes: dict = {}  # group_name → QGroupBox
```

- [ ] **Step 2: Add `_make_cost_row()` method**

Add this method to `BookCostCalculator`, after `connect_db()` and before `init_ui()`:

```python
    def _make_cost_row(self, field_name: str, readonly: bool = False) -> 'QWidget':
        """Creates a labeled row widget for a cost field and registers it."""
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(4, 1, 4, 1)
        layout.setSpacing(8)
        label = QLabel(field_name + ":")
        label.setMinimumWidth(200)
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        spin = QDoubleSpinBox()
        spin.setMaximum(9_999_999_999.99)
        spin.setGroupSeparatorShown(True)
        spin.setDecimals(0)
        spin.lineEdit().setAlignment(Qt.AlignCenter)
        if readonly:
            spin.setReadOnly(True)
            spin.setStyleSheet("background-color: #1e2d1e; color: #4caf50;")
        layout.addWidget(label)
        layout.addWidget(spin)
        self.cost_inputs[field_name] = spin
        self.cost_input_rows[field_name] = row
        return row
```

- [ ] **Step 3: Run the app to confirm no errors**

```bash
source .venv/bin/activate
python main.py
```

Expected: app opens normally (the helper isn't called yet — that happens in Task 5).

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat: add _make_cost_row helper and cost_input_rows tracking dict"
```

---

## Task 5: Refactor `setup_details_tab()` — Cost Fields into 5 GroupBoxes

This is the largest task. The existing flat cost list (lines ~938–960) is replaced with 4 new GroupBoxes. The existing `self.calc_group` becomes Group ②.

**Files:**
- Modify: `main.py:938-960` (the `cost_types` loop and `setReadOnly` lines)

- [ ] **Step 1: Add the preset selector above the basic info section**

In `setup_details_tab()`, find the line:
```python
            form_layout = QFormLayout()
            self.inputs = {}
```

After `form_layout = QFormLayout()` and before `self.inputs = {}`, add:

```python
            # ── Preset selector ───────────────────────────────────────────────
            self.book_type_combo = QComboBox()
            self.book_type_combo.addItems(list(self.BOOK_TYPE_PRESETS.keys()))
            self.book_type_combo.setCurrentText("شومیز ساده")
            form_layout.addRow("نوع کتاب:", self.book_type_combo)
```

- [ ] **Step 2: Remove the old flat cost_types loop**

Find and remove this entire block (roughly lines 938–960):

```python
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
                spin.setMaximum(9999999999.99)
                spin.setGroupSeparatorShown(True)
                spin.setDecimals(0)
                spin.lineEdit().setAlignment(Qt.AlignCenter) 
                self.cost_inputs[ctype] = spin
                form_layout.addRow(ctype + ":", spin)
                
            # Protect auto-calculated fields
            self.cost_inputs['هزینه کاغذ متن'].setReadOnly(True)
            self.cost_inputs['هزینه کاغذ جلد'].setReadOnly(True)
            self.cost_inputs['هزینه زینک'].setReadOnly(True)
```

Replace it with the following 4-GroupBox block. Insert this in its place (the `self.cost_inputs = {}` line that was here is now handled by `_make_cost_row`):

```python
            self.cost_inputs = {}

            # ── Group ①: خلاقیت و تحریریه ─────────────────────────────────
            grp1 = QGroupBox("① خلاقیت و تحریریه")
            grp1_layout = QVBoxLayout(grp1)
            grp1_layout.setSpacing(2)
            for fname in self.COST_GROUPS["خلاقیت و تحریریه"]:
                grp1_layout.addWidget(self._make_cost_row(fname))
            form_layout.addRow(grp1)
            self.cost_group_boxes["خلاقیت و تحریریه"] = grp1

            # ── Rename existing calc_group as Group ② ────────────────────
            # (calc_group is set up above; just retitle it)
            self.calc_group.setTitle("② پیش از چاپ — محاسبات هوشمند کاغذ و زینک")

            # ── Group ③: چاپ و مواد ───────────────────────────────────────
            # Includes the 3 auto-calculated cost fields (readonly) so their
            # values are visible alongside the manual printing/materials costs.
            grp3 = QGroupBox("③ چاپ و مواد")
            grp3_layout = QVBoxLayout(grp3)
            grp3_layout.setSpacing(2)
            readonly_auto = {"هزینه زینک", "هزینه کاغذ متن", "هزینه کاغذ جلد"}
            for fname in self.COST_GROUPS["چاپ و مواد"]:
                grp3_layout.addWidget(self._make_cost_row(fname, readonly=fname in readonly_auto))
            form_layout.addRow(grp3)
            self.cost_group_boxes["چاپ و مواد"] = grp3

            # ── Group ④: تکمیل و صحافی ───────────────────────────────────
            grp4 = QGroupBox("④ تکمیل و صحافی")
            grp4_layout = QVBoxLayout(grp4)
            grp4_layout.setSpacing(2)
            for fname in self.COST_GROUPS["تکمیل و صحافی"]:
                grp4_layout.addWidget(self._make_cost_row(fname))
            form_layout.addRow(grp4)
            self.cost_group_boxes["تکمیل و صحافی"] = grp4

            # ── Group ⑤: اداری و مجوزها ─────────────────────────────────
            grp5 = QGroupBox("⑤ اداری و مجوزها")
            grp5_layout = QVBoxLayout(grp5)
            grp5_layout.setSpacing(2)
            for fname in self.COST_GROUPS["اداری و مجوزها"]:
                grp5_layout.addWidget(self._make_cost_row(fname))
            form_layout.addRow(grp5)
            self.cost_group_boxes["اداری و مجوزها"] = grp5
```

**Important note:** `self.COST_GROUPS["چاپ و مواد"]` includes `"هزینه زینک"`, `"هزینه کاغذ متن"`, and `"هزینه کاغذ جلد"`. These three are rendered readonly (green background) by the `readonly_auto` set. The `_apply_preset` method already skips zeroing readonly fields, so their auto-calculated values are preserved across preset switches.

- [ ] **Step 3: Connect preset selector signal**

At the end of `setup_details_tab()`, in the signal connections block, add:

```python
            self.book_type_combo.currentTextChanged.connect(
                lambda name: self._apply_preset(name, zero_hidden=True)
            )
```

- [ ] **Step 4: Run the app and visually verify**

```bash
source .venv/bin/activate
python main.py
```

Expected: Tab 2 shows a "نوع کتاب" selector at the top. Below the calc group, 4 new GroupBoxes appear with cost field rows. All 29 cost fields are visible (preset logic comes in Task 6). Check that "هزینه زینک", "هزینه کاغذ متن", "هزینه کاغذ جلد" appear inside Group ② with green readonly styling.

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "feat: reorganize Tab 2 cost fields into 5 labeled GroupBoxes"
```

---

## Task 6: Add `_apply_preset()` Method

**Files:**
- Modify: `main.py` — add method after `_make_cost_row()`

- [ ] **Step 1: Add the method**

Add this method immediately after `_make_cost_row()`:

```python
    def _apply_preset(self, preset_name: str, zero_hidden: bool = True):
        """Show/hide cost field rows and groups based on the selected book type preset."""
        visible_fields = self.BOOK_TYPE_PRESETS.get(preset_name)  # None = show all
        all_fields = [f for fields in self.COST_GROUPS.values() for f in fields]

        for field_name in all_fields:
            row = self.cost_input_rows.get(field_name)
            if row is None:
                continue
            should_show = (visible_fields is None) or (field_name in visible_fields)
            row.setVisible(should_show)
            if not should_show and zero_hidden:
                spin = self.cost_inputs.get(field_name)
                if spin and not spin.isReadOnly():
                    spin.setValue(0.0)

        # Show/hide each GroupBox based on whether any field in it is visible
        for group_name, group_box in self.cost_group_boxes.items():
            group_fields = self.COST_GROUPS[group_name]
            any_visible = (visible_fields is None) or any(
                f in visible_fields for f in group_fields
            )
            group_box.setVisible(any_visible)
```

- [ ] **Step 2: Apply initial preset on form setup**

At the end of `setup_details_tab()`, after the signal connections block, add:

```python
            # Apply default preset on first load
            self._apply_preset("شومیز ساده", zero_hidden=False)
```

- [ ] **Step 3: Run the app and verify preset filtering**

```bash
source .venv/bin/activate
python main.py
```

Expected:
- On Tab 2, default preset "شومیز ساده" is selected. Fields like "هزینه ترجمه", "هزینه تصویرگری", "هزینه مقوای مغذی", "هزینه طلاکوبی", "هزینه UV موضعی" are hidden.
- Switching to "سفارشی" in the dropdown shows ALL fields.
- Switching to "ویژه / لوکس" shows طلاکوبی/UV/برجسته.
- Switching to "ترجمه" hides "هزینه تالیف" and shows "هزینه ترجمه".

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat: add _apply_preset method with show/hide and zero-out logic"
```

---

## Task 7: Update `save_project_to_db()` for New Fields

**Files:**
- Modify: `main.py` — `save_project_to_db()` method (around line 1262)

- [ ] **Step 1: Add new fields to the UPDATE query**

Find the UPDATE `query_details` string in `save_project_to_db()`. It currently ends with:
```python
                        hazineh_haml_naghl = ?, hazineh_montaj = ?
                    WHERE project_id = ?
```

Change that ending to:
```python
                        hazineh_haml_naghl = ?, hazineh_montaj = ?,
                        hazineh_horoofchini = ?, hazineh_mojawwez_ershad = ?,
                        hazineh_shabok = ?, hazineh_talakoobi = ?,
                        hazineh_uv_mowzei = ?, hazineh_barjasteh = ?,
                        book_type_preset = ?, pricing_multiplier = ?,
                        distribution_percent = ?
                    WHERE project_id = ?
```

- [ ] **Step 2: Add new values to the UPDATE `val_details` tuple**

Find the UPDATE `val_details` tuple. It currently ends with:
```python
                    self.cost_inputs['هزینه حمل و نقل'].value(), self.cost_inputs['هزینه مونتاژ'].value(),
                    self.current_project_id
```

Change that ending to:
```python
                    self.cost_inputs['هزینه حمل و نقل'].value(), self.cost_inputs['هزینه مونتاژ'].value(),
                    self.cost_inputs['هزینه حروفچینی و صفحه‌آرایی'].value(),
                    self.cost_inputs['هزینه مجوز ارشاد'].value(),
                    self.cost_inputs['هزینه ثبت شابک'].value(),
                    self.cost_inputs['هزینه طلاکوبی'].value(),
                    self.cost_inputs['هزینه UV موضعی'].value(),
                    self.cost_inputs['هزینه برجسته‌کاری'].value(),
                    self.book_type_combo.currentText(),
                    getattr(self, 'pricing_multiplier_spin', None) and self.pricing_multiplier_spin.value() or 2.5,
                    getattr(self, 'distribution_spin', None) and self.distribution_spin.value() or 35.0,
                    self.current_project_id
```

- [ ] **Step 3: Add new fields to the INSERT query**

Find the INSERT `query_details` string. It currently ends with:
```python
                        hazineh_boresh_bastebandi, hazineh_haml_naghl, hazineh_montaj
                    ) VALUES (
```

Change to:
```python
                        hazineh_boresh_bastebandi, hazineh_haml_naghl, hazineh_montaj,
                        hazineh_horoofchini, hazineh_mojawwez_ershad, hazineh_shabok,
                        hazineh_talakoobi, hazineh_uv_mowzei, hazineh_barjasteh,
                        book_type_preset, pricing_multiplier, distribution_percent
                    ) VALUES (
```

- [ ] **Step 4: Add new values to the INSERT `val_details` tuple**

Find the INSERT `val_details` tuple. It currently ends with:
```python
                    self.cost_inputs['هزینه حمل و نقل'].value(), self.cost_inputs['هزینه مونتاژ'].value(),
                    self.current_project_id
```

Wait — the INSERT val_details does NOT include `self.current_project_id` at the end (that's only UPDATE). The INSERT ends with the last cost value, then closes the tuple and passes to `cursor.execute`. Find the last line of the INSERT val_details and append:

```python
                    self.cost_inputs['هزینه حمل و نقل'].value(), self.cost_inputs['هزینه مونتاژ'].value(),
                    self.cost_inputs['هزینه حروفچینی و صفحه‌آرایی'].value(),
                    self.cost_inputs['هزینه مجوز ارشاد'].value(),
                    self.cost_inputs['هزینه ثبت شابک'].value(),
                    self.cost_inputs['هزینه طلاکوبی'].value(),
                    self.cost_inputs['هزینه UV موضعی'].value(),
                    self.cost_inputs['هزینه برجسته‌کاری'].value(),
                    self.book_type_combo.currentText(),
                    getattr(self, 'pricing_multiplier_spin', None) and self.pricing_multiplier_spin.value() or 2.5,
                    getattr(self, 'distribution_spin', None) and self.distribution_spin.value() or 35.0,
```

- [ ] **Step 5: Test save round-trip**

```bash
source .venv/bin/activate
python main.py
```

Open Tab 2, fill in "عنوان کتاب", enter a value for "هزینه حروفچینی و صفحه‌آرایی". Press Ctrl+S. Expected: no crash, status bar shows project name.

- [ ] **Step 6: Commit**

```bash
git add main.py
git commit -m "feat: save new cost fields and preset/pricing settings to DB"
```

---

## Task 8: Update `load_project_by_id()` and `new_project()` for New Fields

**Files:**
- Modify: `main.py` — `load_project_by_id()` and `new_project()`

- [ ] **Step 1: Add new cost fields to `cost_mapping` in `load_project_by_id()`**

Find the `cost_mapping` dict in `load_project_by_id()` (around line 1750). It maps Persian field names to DB column names. Add these entries to the dict:

```python
                    'هزینه حروفچینی و صفحه‌آرایی': 'hazineh_horoofchini',
                    'هزینه مجوز ارشاد':             'hazineh_mojawwez_ershad',
                    'هزینه ثبت شابک':              'hazineh_shabok',
                    'هزینه طلاکوبی':               'hazineh_talakoobi',
                    'هزینه UV موضعی':              'hazineh_uv_mowzei',
                    'هزینه برجسته‌کاری':           'hazineh_barjasteh',
```

- [ ] **Step 2: Restore preset and pricing settings in `load_project_by_id()`**

After the `cost_mapping` loop (which restores all cost values), add:

```python
                # Restore preset — do NOT zero hidden fields when loading
                if 'book_type_preset' in details and details['book_type_preset']:
                    self.book_type_combo.blockSignals(True)
                    self.book_type_combo.setCurrentText(details['book_type_preset'])
                    self.book_type_combo.blockSignals(False)
                    self._apply_preset(details['book_type_preset'], zero_hidden=False)

                # Restore pricing settings (Tab 3 spinboxes may not exist yet on first load)
                if hasattr(self, 'pricing_multiplier_spin') and details.get('pricing_multiplier'):
                    self.pricing_multiplier_spin.setValue(float(details['pricing_multiplier']))
                if hasattr(self, 'distribution_spin') and details.get('distribution_percent'):
                    self.distribution_spin.setValue(float(details['distribution_percent']))
```

- [ ] **Step 3: Reset new fields in `new_project()`**

In `new_project()`, find the block that clears cost inputs:
```python
        # Clear costs
        for spin in self.cost_inputs.values():
            spin.setValue(0.0)
```

After this block, add:

```python
        self.book_type_combo.blockSignals(True)
        self.book_type_combo.setCurrentText("شومیز ساده")
        self.book_type_combo.blockSignals(False)
        self._apply_preset("شومیز ساده", zero_hidden=False)
        if hasattr(self, 'pricing_multiplier_spin'):
            self.pricing_multiplier_spin.setValue(2.5)
        if hasattr(self, 'distribution_spin'):
            self.distribution_spin.setValue(35.0)
```

- [ ] **Step 4: Test load round-trip**

```bash
source .venv/bin/activate
python main.py
```

1. Create a new project, switch preset to "ترجمه", enter "هزینه ترجمه" = 500,000. Press Ctrl+S.
2. Go to Tab 1, click the project, press Ctrl+O (or double-click).
3. Expected: Tab 2 shows preset = "ترجمه", "هزینه ترجمه" = 500,000, "هزینه تالیف" is hidden.

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "feat: restore preset and new cost fields on project load; reset in new_project"
```

---

## Task 9: Build `setup_pricing_tab()` UI (Tab 3)

**Files:**
- Modify: `main.py` — add `setup_pricing_tab()` method after `setup_calc_tab()`

- [ ] **Step 1: Add `setup_pricing_tab()` method**

Add this method after `setup_calc_tab()`:

```python
    def setup_pricing_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content.setLayoutDirection(Qt.RightToLeft)
        main_vbox = QVBoxLayout(content)
        main_vbox.setSpacing(12)

        # ── Part A: Suggested cover price ────────────────────────────────
        grp_a = QGroupBox("قیمت‌گذاری پیشنهادی")
        grp_a_form = QFormLayout(grp_a)

        self.pricing_multiplier_spin = QDoubleSpinBox()
        self.pricing_multiplier_spin.setRange(1.0, 5.0)
        self.pricing_multiplier_spin.setSingleStep(0.1)
        self.pricing_multiplier_spin.setDecimals(1)
        self.pricing_multiplier_spin.setValue(2.5)
        grp_a_form.addRow("ضریب قیمت‌گذاری:", self.pricing_multiplier_spin)

        self.lbl_cover_price = QLabel("—")
        self.lbl_cover_price.setAlignment(Qt.AlignCenter)
        self.lbl_cover_price.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: #4caf50;"
            "background-color: #1a2a1a; padding: 10px; border-radius: 6px;"
        )
        grp_a_form.addRow("قیمت پشت جلد پیشنهادی:", self.lbl_cover_price)

        # Breakdown bar — 4 colored QFrame widgets in an HBoxLayout
        breakdown_container = QWidget()
        self.breakdown_layout = QHBoxLayout(breakdown_container)
        self.breakdown_layout.setContentsMargins(0, 0, 0, 0)
        self.breakdown_layout.setSpacing(2)
        self._breakdown_frames = {}
        colors = {
            "production":    "#2196f3",
            "distribution":  "#ff9800",
            "royalty":       "#9c27b0",
            "publisher":     "#4caf50",
        }
        labels_fa = {
            "production": "تولید", "distribution": "توزیع",
            "royalty": "حق تالیف", "publisher": "سود ناشر",
        }
        for key, color in colors.items():
            frame = QLabel(labels_fa[key])
            frame.setAlignment(Qt.AlignCenter)
            frame.setStyleSheet(
                f"background-color: {color}; color: white; font-size: 10px;"
                "border-radius: 3px; padding: 4px;"
            )
            frame.setMinimumHeight(32)
            self.breakdown_layout.addWidget(frame, 1)
            self._breakdown_frames[key] = frame
        grp_a_form.addRow("توزیع قیمت پشت جلد:", breakdown_container)

        self.distribution_spin = QDoubleSpinBox()
        self.distribution_spin.setRange(0, 70)
        self.distribution_spin.setSingleStep(1)
        self.distribution_spin.setDecimals(0)
        self.distribution_spin.setValue(35.0)
        self.distribution_spin.setSuffix(" %")
        grp_a_form.addRow("سهم کتابفروشی / توزیع:", self.distribution_spin)

        main_vbox.addWidget(grp_a)

        # ── Part B: Break-even ───────────────────────────────────────────
        grp_b = QGroupBox("نقطه سر به سر")
        grp_b_form = QFormLayout(grp_b)

        self.lbl_total_project_cost = QLabel("—")
        grp_b_form.addRow("هزینه کل پروژه:", self.lbl_total_project_cost)

        self.lbl_net_per_copy = QLabel("—")
        grp_b_form.addRow("درآمد خالص ناشر (هر جلد):", self.lbl_net_per_copy)

        self.lbl_break_even = QLabel("—")
        self.lbl_break_even.setStyleSheet("font-weight: bold; font-size: 14px;")
        grp_b_form.addRow("نقطه سر به سر:", self.lbl_break_even)

        self.lbl_profit_status = QLabel("—")
        self.lbl_profit_status.setWordWrap(True)
        grp_b_form.addRow("وضعیت تیراژ فعلی:", self.lbl_profit_status)

        main_vbox.addWidget(grp_b)

        # ── Part C: Scenario table ───────────────────────────────────────
        grp_c = QGroupBox("جدول سناریوها")
        grp_c_vbox = QVBoxLayout(grp_c)

        self.scenario_table = QTableWidget(4, 3)
        self.scenario_table.setHorizontalHeaderLabels(["×۲.۵", "×۳.۰", "×۳.۵"])
        self.scenario_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.scenario_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.scenario_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        grp_c_vbox.addWidget(self.scenario_table)

        main_vbox.addWidget(grp_c)
        main_vbox.addStretch()

        scroll.setWidget(content)
        pricing_outer = QVBoxLayout(self.tab_pricing)
        pricing_outer.setContentsMargins(0, 0, 0, 0)
        pricing_outer.addWidget(scroll)

        # Wire live updates
        self.pricing_multiplier_spin.valueChanged.connect(self._refresh_pricing_tab)
        self.distribution_spin.valueChanged.connect(self._refresh_pricing_tab)
```

- [ ] **Step 2: Verify syntax**

```bash
source .venv/bin/activate
python -c "import main" 2>&1
```

Expected: no output (no errors).

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add setup_pricing_tab UI (Part A/B/C — cover price, break-even, scenarios)"
```

---

## Task 10: Add `_refresh_pricing_tab()` Calculation Method

**Files:**
- Modify: `main.py` — add method after `setup_pricing_tab()`

- [ ] **Step 1: Add `_refresh_pricing_tab()` method**

```python
    def _refresh_pricing_tab(self):
        """Recalculate and repaint all three parts of the pricing tab."""
        try:
            total_cost = float(self.lbl_final_total.text().replace(',', ''))
            single_cost = float(self.lbl_single_price.text().replace(',', ''))
            tiraj = self.inputs['تیراژ'].value()
        except (ValueError, AttributeError):
            return
        if total_cost <= 0 or single_cost <= 0 or tiraj <= 0:
            return

        multiplier = self.pricing_multiplier_spin.value()
        dist_pct = self.distribution_spin.value()
        royalty_pct = self.royalty_input.value()

        cover_price = compute_cover_price(single_cost, multiplier)
        net_per_copy = compute_net_revenue_per_copy(cover_price, dist_pct, royalty_pct)
        break_even = compute_break_even(total_cost, net_per_copy)
        bd = compute_breakdown_pcts(cover_price, single_cost, dist_pct, royalty_pct)

        # Part A
        self.lbl_cover_price.setText(f"{cover_price:,.0f} تومان")
        for key, frame in self._breakdown_frames.items():
            pct = bd[f'{key}_pct']
            amount = bd[key]
            labels_fa = {"production": "تولید", "distribution": "توزیع",
                         "royalty": "حق تالیف", "publisher": "سود ناشر"}
            frame.setText(f"{labels_fa[key]}\n{pct:.1f}%")
            frame.setToolTip(f"{amount:,.0f} تومان")
            self.breakdown_layout.setStretchFactor(frame, max(1, int(pct)))

        # Part B
        self.lbl_total_project_cost.setText(f"{total_cost:,.0f} تومان")
        self.lbl_net_per_copy.setText(f"{net_per_copy:,.0f} تومان")
        if break_even > 0:
            self.lbl_break_even.setText(f"{break_even:,} جلد")
            if tiraj >= break_even:
                profit = net_per_copy * tiraj - total_cost
                self.lbl_profit_status.setText(
                    f"✓ تیراژ {tiraj:,} جلد از نقطه سر به سر ({break_even:,}) عبور کرده | "
                    f"سود تخمینی فروش کامل: {profit:,.0f} تومان"
                )
                self.lbl_profit_status.setStyleSheet("color: #4caf50; font-weight: bold;")
            else:
                shortage = break_even - tiraj
                self.lbl_profit_status.setText(
                    f"✗ تیراژ {tiraj:,} جلد کمتر از نقطه سر به سر است | "
                    f"برای رسیدن به سر به سر {shortage:,} جلد بیشتر نیاز است"
                )
                self.lbl_profit_status.setStyleSheet("color: #e57373; font-weight: bold;")
        else:
            self.lbl_break_even.setText("قابل محاسبه نیست")
            self.lbl_profit_status.setText("درآمد خالص ناشر صفر یا منفی است")
            self.lbl_profit_status.setStyleSheet("color: #e57373;")

        # Part C — scenario table
        fixed_multipliers = [2.5, 3.0, 3.5]
        sales_pcts = [0.25, 0.5, 0.75, 1.0]
        rows_data = compute_scenarios(total_cost, single_cost, tiraj,
                                      dist_pct, royalty_pct, fixed_multipliers)
        row_labels = [f"{int(tiraj * p):,} جلد ({int(p*100)}٪)" for p in sales_pcts]
        self.scenario_table.setVerticalHeaderLabels(row_labels)

        for row_idx, pct in enumerate(sales_pcts):
            for col_idx, mult in enumerate(fixed_multipliers):
                entry = next(r for r in rows_data
                             if r['multiplier'] == mult and r['sales_qty'] == max(1, int(tiraj * pct)))
                profit = entry['net_profit']
                item = QTableWidgetItem(f"{profit:+,.0f} تومان")
                item.setTextAlignment(Qt.AlignCenter)
                if profit > 0:
                    item.setForeground(QColor('#4caf50'))
                elif profit < -0.10 * total_cost:
                    item.setForeground(QColor('#e57373'))
                else:
                    item.setForeground(QColor('#ffb74d'))
                # Highlight the cell matching current multiplier + full tiraj
                if abs(mult - multiplier) < 0.01 and pct == 1.0:
                    item.setBackground(QColor('#1a2a1a'))
                self.scenario_table.setItem(row_idx, col_idx, item)
```

- [ ] **Step 2: Verify by running the app**

```bash
source .venv/bin/activate
python main.py
```

Expected: no crash (Tab 3 doesn't show yet — wired in Task 11).

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add _refresh_pricing_tab calculation and display logic"
```

---

## Task 11: Wire Everything into `init_ui()` and `perform_calculations()`

This task connects all the pieces: adds Tab 3 to the tab widget, updates tab indices, and calls `_refresh_pricing_tab()` from `perform_calculations()`.

**Files:**
- Modify: `main.py` — `init_ui()` and `perform_calculations()`

- [ ] **Step 1: Add `tab_pricing` widget and `setup_pricing_tab()` call to `init_ui()`**

In `init_ui()`, find these lines (around line 686–700):
```python
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
```

Replace with:

```python
        self.tab_project = QWidget()
        self.tab_details = QWidget()
        self.tab_pricing = QWidget()   # NEW — Tab 3
        self.tab_calc = QWidget()
        self.tab_report = QWidget()
        self.tab_paper_calc = QWidget()
        self.tab_defaults = QWidget()

        self.tabs.addTab(self.tab_project,   "مدیریت پروژه‌ها")
        self.tabs.addTab(self.tab_details,   "ورود اطلاعات و هزینه‌ها")
        self.tabs.addTab(self.tab_pricing,   "قیمت‌گذاری و سودآوری")  # NEW
        self.tabs.addTab(self.tab_calc,      "محاسبات نهایی")
        self.tabs.addTab(self.tab_report,    "گزارش‌گیری (PDF)")
        self.tabs.addTab(self.tab_paper_calc,"محاسبات پیش‌پردازش کاغذ")
        self.tabs.addTab(self.tab_defaults,  "مدیریت قیمت‌های پایه")
```

- [ ] **Step 2: Add `setup_pricing_tab()` call in `init_ui()`**

Find the block that calls all setup methods:
```python
        self.setup_project_tab()
        self.setup_details_tab()
        self.setup_calc_tab()
        self.setup_report_tab()
        self.setup_paper_calc_tab()
        self.setup_default_costs_tab()
```

Replace with:

```python
        self.setup_project_tab()
        self.setup_details_tab()
        self.setup_pricing_tab()        # NEW
        self.setup_calc_tab()
        self.setup_report_tab()
        self.setup_paper_calc_tab()
        self.setup_default_costs_tab()
```

- [ ] **Step 3: Fix tab index references — menu actions**

In `init_ui()`, find:
```python
        paper_calc_menu_action.triggered.connect(lambda: self.tabs.setCurrentIndex(4))
        ...
        defaults_menu_action.triggered.connect(lambda: self.tabs.setCurrentIndex(5))
```

Change to:
```python
        paper_calc_menu_action.triggered.connect(lambda: self.tabs.setCurrentIndex(5))
        ...
        defaults_menu_action.triggered.connect(lambda: self.tabs.setCurrentIndex(6))
```

- [ ] **Step 4: Fix tab index in `perform_calculations()`**

Find:
```python
        # Switch to calculation tab
        self.tabs.setCurrentIndex(2)
```

Change to:
```python
        # Switch to calculation tab
        self.tabs.setCurrentIndex(3)
```

- [ ] **Step 5: Call `_refresh_pricing_tab()` from `perform_calculations()`**

In `perform_calculations()`, find:
```python
        # Update the chart
        self.update_chart()
        
        # Switch to calculation tab
        self.tabs.setCurrentIndex(3)
```

Replace with:
```python
        # Update the chart
        self.update_chart()

        # Update the pricing tab
        self._refresh_pricing_tab()

        # Switch to calculation tab
        self.tabs.setCurrentIndex(3)
```

- [ ] **Step 6: Full integration test**

```bash
source .venv/bin/activate
python main.py
```

Full golden path test:
1. Create new project: عنوان = "تست کامل", تیراژ = 2000, preset = "شومیز ساده"
2. Enter: هزینه حروفچینی = 5,000,000, هزینه چاپ متن = 8,000,000, هزینه صحافی = 3,000,000, هزینه مجوز ارشاد = 500,000, هزینه ثبت شابک = 200,000
3. Set paper unit price and let auto-calc run on کاغذ/زینک
4. Press "ثبت اطلاعات و انجام محاسبات نهایی"
5. Expected: app switches to Tab 4 (محاسبات نهایی) — verify the tab is the right one (pie chart visible)
6. Switch to Tab 3 (قیمت‌گذاری و سودآوری) — verify:
   - Cover price label shows a non-zero value at ×2.5
   - Breakdown bar shows 4 colored segments
   - Break-even shows a number
   - Scenario table shows 4 rows × 3 columns with color-coded values
7. Change the ضریب spinner to 3.0 — verify all values update live
8. Press Ctrl+S, reopen the project — verify preset and (if pricing_multiplier_spin saved) multiplier are restored

- [ ] **Step 7: Commit**

```bash
git add main.py
git commit -m "feat: wire Tab 3 pricing tab into init_ui and perform_calculations"
```

---

## Task 12: Self-Review and Final Commit

- [ ] **Step 1: Run all tests**

```bash
source .venv/bin/activate
pytest tests/test_pricing.py -v
```

Expected: 8 tests pass.

- [ ] **Step 2: Verify tab 5 (paper calc) and tab 6 (defaults) still reachable from menu**

Open app → Settings menu → "محاسبات پیش‌پردازش کاغذ" → verify Tab 5 opens.  
Settings menu → "مدیریت قیمت‌های پایه" → verify Tab 6 opens.

- [ ] **Step 3: Test existing project load (backward compatibility)**

```bash
source .venv/bin/activate
python -c "
import sqlite3
conn = sqlite3.connect('book_publishing.db')
rows = conn.execute('SELECT id, title FROM projects').fetchall()
for r in rows:
    print(r)
"
```

Load one existing project (that predates this change). Expected: loads without crash, old cost fields still populate correctly, new fields default to 0.

- [ ] **Step 4: Final commit**

```bash
git add main.py tests/test_pricing.py
git commit -m "feat: complete book cost calculator improvements — presets, new fields, pricing tab"
```

---

## Summary of Changes

| What | Where | Tasks |
|---|---|---|
| 9 new DB columns | `connect_db()` | 1 |
| 5 module-level pricing functions | before `PaperPriceDialog` | 2 |
| `BOOK_TYPE_PRESETS`, `COST_GROUPS` dicts | class body after `OPTIMAL_SPECS` | 3 |
| `_make_cost_row()`, `cost_input_rows` init | `__init__` + new method | 4 |
| Form refactor into 5 GroupBoxes | `setup_details_tab()` | 5 |
| `_apply_preset()` | new method | 6 |
| Save updated | `save_project_to_db()` | 7 |
| Load + new_project updated | `load_project_by_id()`, `new_project()` | 8 |
| Pricing tab UI | `setup_pricing_tab()` | 9 |
| Pricing tab logic | `_refresh_pricing_tab()` | 10 |
| Tab wiring | `init_ui()`, `perform_calculations()` | 11 |
