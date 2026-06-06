# Calculation Overhaul + Custom Book Sizes — Design Spec
**Date:** 2026-06-06

## Context

The current calculation engine has three bugs and one major limitation:
1. **Formula 1 label bug**: The paper unit price input in Tab 4 (and `PaperPriceDialog`) says "per 1000 sheets" but the formula actually expects a **per-kg price**. Users entering per-sheet prices get silently wrong results.
2. **Zinc pricing ignored**: `zinc_size_matn_combo` and `zinc_size_jeld_combo` are stored but never used in cost calculation. All zinc plates are priced identically regardless of size (2 ورقی costs the same as 4.5 ورقی).
3. **No waste factor**: Paper consumption is calculated as `(forms/sides) × tiraj` with no allowance for makeready and spoilage. Real jobs always consume more paper than the theoretical minimum.
4. **No custom book sizes**: Only 6 formats supported, all hardcoded. Non-standard books (children's books, square format, oversize) cannot be priced accurately.

**Goal:** Fix all three calculation bugs, add a per-plate-size zinc price table, add a configurable waste factor, and support non-standard book sizes with automatic orientation optimization.

---

## Database Changes

### New table: `zinc_prices`

Created in `connect_db()` alongside existing tables:

```sql
CREATE TABLE IF NOT EXISTS zinc_prices (
    zinc_size TEXT PRIMARY KEY,
    unit_price REAL DEFAULT 0
);
```

Pre-populated at startup with zero prices for all 5 sizes:
- `زینک 2 ورقی`
- `زینک 2.5 ورقی`
- `زینک 3.5 ورقی`
- `زینک 4.5 ورقی`
- `زینک GTO`

### `project_details` — new columns

Added via `ALTER TABLE` at startup (wrapped in try/except to be idempotent on existing DBs):

```sql
ALTER TABLE project_details ADD COLUMN waste_percent REAL DEFAULT 5;
ALTER TABLE project_details ADD COLUMN book_width REAL;
ALTER TABLE project_details ADD COLUMN book_height REAL;
ALTER TABLE project_details ADD COLUMN paper_size TEXT;
ALTER TABLE project_details ADD COLUMN orientation TEXT;
ALTER TABLE project_details ADD COLUMN pages_per_sheet INTEGER;
```

- `book_width` / `book_height`: `NULL` for standard formats; populated for custom/semi-custom
- `paper_size`: the selected print paper size string (e.g. `"70x100"`)
- `orientation`: `"portrait"` or `"landscape"` (the auto-selected result, or user override)
- `pages_per_sheet`: the computed or manually overridden value
- `unit_price_zinc` column stays in schema for backward compat but is no longer used in calculation

---

## Change 1: Formula 1 Label Fix

**File:** `main.py`

**In `setup_paper_calc_tab`** (Tab 4): change the label on `paper_price_spin`:
```
Before: "قیمت / قیمت بند (تومان):"
After (Formula 1 context): "قیمت کاغذ (هر کیلوگرم):"
```

The fix: the label must change based on the selected formula type. When `update_paper_inputs_visibility` sets Formula 1, the price label shows "هر کیلوگرم". For Formula 2 (bundle), it shows "قیمت هر بند". The label is a `QLabel` stored as `self.paper_price_label`; its text is updated in `update_paper_inputs_visibility`.

**Same fix in `PaperPriceDialog._setup_ui`**: the "قیمت (هر ۱۰۰۰ برگ)" label on `dlg_price1_spin` becomes `"قیمت کاغذ (هر کیلوگرم):"`.

---

## Change 2: Waste Factor

**UI change in Tab 1** (`setup_data_entry_tab`): add one new field inside the `calc_group` GroupBox, after the zinc unit price row:

```python
self.waste_percent_spin = QDoubleSpinBox()
self.waste_percent_spin.setRange(0, 50)
self.waste_percent_spin.setDecimals(1)
self.waste_percent_spin.setValue(5.0)
self.waste_percent_spin.setSuffix(" %")
calc_layout.addRow("ضایعات کاغذ:", self.waste_percent_spin)
```

Connect to `auto_calculate_costs`:
```python
self.waste_percent_spin.valueChanged.connect(self.auto_calculate_costs)
```

**Formula change in `auto_calculate_costs`**:
```python
waste = 1 + self.waste_percent_spin.value() / 100
total_paper_matn = (self.form_matn_spin.value() / sides_matn) * tiraj * waste
total_paper_jeld = (self.form_jeld_spin.value() / sides_jeld) * tiraj * waste
```

**Save/load**: `waste_percent` is saved to and loaded from `project_details`. Default on new project: 5.0.

---

## Change 3: Zinc Pricing Table

### Tab 5 — new zinc prices section

Add a new `QGroupBox("قیمت زینک‌ها")` at the top of Tab 5 (before the existing default_cost_mappings table). It contains a fixed 5-row `QTableWidget` — one row per zinc size, non-editable row count, with a spinbox in column 1 for the price:

| Column | Content |
|--------|---------|
| 0 | Zinc size label (read-only, e.g. "زینک 3.5 ورقی") |
| 1 | Unit price `QDoubleSpinBox` |
| 2 | "ذخیره" button |

Clicking "ذخیره" on a row: `INSERT OR REPLACE INTO zinc_prices (zinc_size, unit_price) VALUES (?, ?)`.

The table loads prices from the DB on tab open and on any save.

### Tab 1 — replace single zinc price spinbox

Remove: `self.unit_price_zinc_spin` and its `addRow`.

Add two read-only display labels inside the calc_group, immediately after each zinc size combo:

```
ابعاد زینک متن:   [زینک 3.5 ورقی ▾]
قیمت زینک متن:    [150,000 تومان]  ← read-only, from table
                                       OR  ⚠ قیمت تنظیم نشده

ابعاد زینک جلد:   [زینک 3.5 ورقی ▾]
قیمت زینک جلد:    [150,000 تومان]  ← read-only, from table
```

When a zinc size combo changes: look up `zinc_prices` table and update the displayed price label. If no price set (0 or missing), show a warning label styled in red/orange.

**New `auto_calculate_costs` zinc formula**:
```python
zinc_price_matn = self._get_zinc_price(self.zinc_size_matn_combo.currentText())
zinc_price_jeld = self._get_zinc_price(self.zinc_size_jeld_combo.currentText())
total_zinc_cost = (total_zincs_matn * zinc_price_matn) + (total_zincs_jeld * zinc_price_jeld)
```

New helper method:
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

**Save/load**: `unit_price_zinc` column is still written (set to 0) for backward compat. Loading old projects: `unit_price_zinc` is ignored (zinc cost is re-computed from the global zinc_prices table).

---

## Change 4: Custom Book Sizes + Orientation Optimization

### Extended `OPTIMAL_SPECS` dict

Add three new semi-standard entries with default dimensions (user can override):

```python
"مربع":       {"paper_size": "60x90",  "pages_per_sheet": None, "zinc": "زینک 2.5 ورقی", "default_dims": (21, 21)},
"بزرگ‌قطع":   {"paper_size": "70x100", "pages_per_sheet": None, "zinc": "زینک 3.5 ورقی", "default_dims": (24, 34)},
"کوچک‌قطع":   {"paper_size": "60x90",  "pages_per_sheet": None, "zinc": "زینک 2.5 ورقی", "default_dims": (14, 20)},
"سفارشی":     {"paper_size": "70x100", "pages_per_sheet": None, "zinc": "زینک 3.5 ورقی", "default_dims": (None, None)},
```

`pages_per_sheet: None` signals that orientation optimization must be run instead of using a hardcoded value.

### New UI widgets in Tab 1 — added to `form_layout` between the `قطع` row and `calc_group`

These widgets are added to the **main `form_layout`** (the scroll area form), not inside `calc_group`. They appear immediately after the `قطع` dropdown row and before the `calc_group` GroupBox:

```python
# Paper size selector — always visible
self.paper_size_combo = QComboBox()
self.paper_size_combo.addItems(["70×100", "60×90", "50×70"])
form_layout.addRow("اندازه کاغذ چاپ:", self.paper_size_combo)

# Custom book dimensions — hidden for standard formats, shown for semi-standard + سفارشی
self.book_width_spin  = QDoubleSpinBox()   # range 5–60 cm
self.book_height_spin = QDoubleSpinBox()   # range 5–100 cm
self.book_dims_row_widget = QWidget()      # container for both spinboxes, toggled hidden/shown
form_layout.addRow("ابعاد کتاب (cm):", self.book_dims_row_widget)

# Orientation result — read-only info label, hidden for standard formats
self.orientation_label = QLabel()          # e.g. "افقی — ۲۰ صفحه در ورق (۱۱٪ بهتر از عمودی)"
form_layout.addRow("جهت بهینه:", self.orientation_label)
```

`paper_size_combo` display values use "×" (Unicode); parsing uses `.replace("×", "x")` to match OPTIMAL_SPECS keys like `"70x100"`.

Visibility rule:
- Standard formats (وزیری, رقعی, رحلی کوچک, رحلی بزرگ, جیبی, خشتی): hide `book_dims_row_widget` and `orientation_label`; set `paper_size_combo` from OPTIMAL_SPECS but leave it editable in case the printer uses a non-standard stock
- Semi-standard (مربع, بزرگ‌قطع, کوچک‌قطع) + سفارشی: show all; for semi-standard pre-fill `book_width/height` from `default_dims`

### Orientation optimization — `_compute_optimal_orientation(book_w, book_h, paper_w, paper_h)`

```python
def _compute_optimal_orientation(self, book_w, book_h, paper_w, paper_h):
    portrait  = (paper_w // book_w) * (paper_h // book_h)
    landscape = (paper_w // book_h) * (paper_h // book_w)
    if landscape >= portrait:
        return "landscape", int(landscape * 2)   # ×2 for both sides
    return "portrait", int(portrait * 2)
```

Returns `(orientation_str, pages_per_sheet)`.

### Updated `suggest_optimal_layout`

```python
def suggest_optimal_layout(self):
    qate = self.inputs['قطع'].currentText()
    specs = self.OPTIMAL_SPECS.get(qate)

    if specs and specs['pages_per_sheet'] is not None:
        # Standard format: existing behaviour unchanged
        pages_per_sheet = specs['pages_per_sheet']
        self.orientation_label.setText("")
    else:
        # Custom/semi-custom: run orientation optimization
        book_w = self.book_width_spin.value()
        book_h = self.book_height_spin.value()
        paper_size = self.paper_size_combo.currentText()  # e.g. "70×100"
        paper_w, paper_h = map(float, paper_size.replace("×","x").split("x"))
        if book_w > 0 and book_h > 0:
            orientation, pages_per_sheet = self._compute_optimal_orientation(
                book_w, book_h, paper_w, paper_h
            )
            # Build informational label
            alt_orientation = "portrait" if orientation == "landscape" else "landscape"
            alt_pages = int(((paper_w//book_h)*(paper_h//book_w) if orientation=="landscape"
                             else (paper_w//book_w)*(paper_h//book_h)) * 2)
            saving = round((pages_per_sheet - alt_pages) / alt_pages * 100) if alt_pages > 0 else 0
            label_map = {"landscape": "افقی", "portrait": "عمودی"}
            self.orientation_label.setText(
                f"جهت: {label_map[orientation]} — {pages_per_sheet} صفحه در ورق"
                + (f" ({saving}٪ بهتر از {label_map[alt_orientation]})" if saving > 0 else "")
            )
        else:
            pages_per_sheet = 1  # guard against zero input

    # Rest of existing suggest_optimal_layout logic using pages_per_sheet
    ...
```

### Save / load

New columns `book_width`, `book_height`, `paper_size`, `orientation`, `pages_per_sheet` are saved on project save and restored on load, restoring the custom dimensions and orientation result without needing to recompute.

---

## What Does NOT Change

- Tab 2 (Final Calculations), Tab 3 (PDF), the 22 cost spinboxes and their formulas
- The `auto_calculate_costs` signal wiring (only the formula body changes)
- `PaperPriceDialog` library and calculator logic (only the label on `dlg_price1_spin`)
- The 6 original standard formats in `OPTIMAL_SPECS` — their behaviour is identical to today

---

## Backward Compatibility

- Existing projects load cleanly: new `project_details` columns default to `NULL`/`5`; `waste_percent` defaults to 5%; custom book fields are `NULL` (treated as standard format)
- `unit_price_zinc` stored in old projects is ignored at load time; zinc cost is re-derived from the global `zinc_prices` table
- If no zinc prices are set, `هزینه زینک` computes to 0 with a warning label — existing behaviour is preserved

---

## Verification

1. **Formula 1 label**: Open Tab 4, select "ابعاد، وزن و قیمت" — label reads "قیمت کاغذ (هر کیلوگرم)". Switch to "قیمت هر بند" — label reads "قیمت هر بند". Same in PaperPriceDialog.
2. **Waste factor**: Set waste to 10%, enter form/tiraj values, confirm `هزینه کاغذ متن` is 10% higher than with waste at 0%.
3. **Zinc table**: Set 3.5 ورقی price to 150,000 in Tab 5. Select "زینک 3.5 ورقی" in Tab 1 — price label shows 150,000. Select "زینک 2 ورقی" (no price set) — warning label appears.
4. **Zinc cost formula**: 4 forms × 4 colors (text) + 1 form × 4 colors (cover) = 20 plates × 150,000 = 3,000,000 Toman in `هزینه زینک`.
5. **Orientation**: Enter book 20×30 cm, paper 70×100. Confirm landscape (20 pages/sheet) beats portrait (18 pages/sheet) and is auto-selected.
6. **Standard formats**: Select وزیری — custom dimension fields hidden, pages_per_sheet = 32 as before.
7. **Load existing project**: Open a project saved before this change — loads without error, waste defaults to 5%, zinc cost recomputes from global table.
