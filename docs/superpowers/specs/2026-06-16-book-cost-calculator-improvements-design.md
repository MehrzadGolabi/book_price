# Book Cost Calculator — Improvements Design Spec
**Date:** 2026-06-16
**Status:** Approved

---

## Problem Statement

The app's Tab 2 cost form has two UX problems for non-technical publishers:

1. **Cognitive overload** — 22 cost fields in a flat scroll, most irrelevant for a given book type
2. **Incomplete cost model** — three significant Iranian publishing costs are absent: typesetting/DTP, regulatory permits, and premium cover finishing

Additionally, the app calculates cost-per-book but stops there. Publishers also need to know what to put on the back cover, whether the print run is profitable, and how different pricing strategies compare.

---

## Decisions Made

| Question | Decision |
|---|---|
| Form UX approach | Book type presets — selector shows/hides relevant fields |
| Missing cost items | All three added: typesetting, permits/ISBN, foil/UV/embossing |
| New output tab | Both profitability breakdown AND scenario comparison table |
| Implementation approach | Preset-first reorganization (Approach 2) |

---

## Architecture Changes

### Tab order (after)
1. مدیریت پروژه‌ها *(unchanged)*
2. ورود اطلاعات و هزینه‌ها *(refactored)*
3. **قیمت‌گذاری و سودآوری** *(new)*
4. محاسبات نهایی *(was index 2 → now index 3)*
5. گزارش‌گیری (PDF) *(was 3 → 4)*
6. محاسبات پیش‌پردازش کاغذ *(was 4 → 5)*
7. مدیریت قیمت‌های پایه *(was 5 → 6)*

### Tab index updates required
- `perform_calculations()`: `self.tabs.setCurrentIndex(2)` → `setCurrentIndex(3)`
- Toolbar/menu actions that call `self.tabs.setCurrentIndex(4)` and `(5)` → `(5)` and `(6)`

### Components unchanged
`PaperPriceDialog`, `PrintLayoutWidget`, `auto_calculate_costs()`, `perform_calculations()` (logic only), `update_chart()`, `OPTIMAL_SPECS`, PDF generation tab, paper calculations tab, default costs tab.

---

## Section 2 — Form Redesign (Tab 2)

### Book type preset selector

A `QComboBox` added at the very top of the scroll area, above the basic info fields:

| Preset | Typical use |
|---|---|
| شومیز ساده | Standard paperback — default |
| گالینگور | Hardcover |
| کتاب مصور / رنگی | Illustrated or full-color |
| ترجمه | Translation (no authoring, has translation) |
| ویژه / لوکس | Premium (foil, UV, embossing relevant) |
| سفارشی | All groups and fields visible |

Preset logic lives in a single class-level dict `BOOK_TYPE_PRESETS`. Adding a new preset means adding one dict entry — no changes elsewhere.

```python
BOOK_TYPE_PRESETS = {
    "شومیز ساده": {
        "groups_expanded": [...],
        "fields_visible": [...]
    },
    ...
}
```

When a preset is applied, hidden fields are zeroed to prevent silent cost contribution.

### Five GroupBoxes replacing the flat list

Groups are **not** user-collapsible — they are shown or hidden in their entirety by the preset selector. QGroupBox is used purely for visual grouping and labeling, not as a toggle widget.

**① خلاقیت و تحریریه** (Creative & Editorial)
- هزینه تالیف
- هزینه ترجمه
- هزینه تصویرگری
- هزینه ویرایش
- هزینه طراحی جلد
- هزینه مديريت آتليه
- **هزینه حروفچینی و صفحه‌آرایی** *(new)*

**② پیش از چاپ** (Pre-press)
- Existing "محاسبات هوشمند کاغذ و زینک" GroupBox — kept as-is, just renamed

**③ چاپ و مواد** (Printing & Materials)
- هزینه چاپ متن
- هزینه چاپ جلد
- هزینه کاغذ متن *(auto)*
- هزینه کاغذ جلد *(auto)*
- هزینه روکش سلفون
- هزینه مقوای مغذی

**④ تکمیل و صحافی** (Post-press & Finishing)
- هزینه قالب لترپرس
- هزینه قالب دايكات
- هزینه خط تا
- هزینه ملزومات
- هزینه جلدسازی
- هزینه صحافی
- هزینه برش و بسته‌بندی
- هزینه حمل و نقل
- هزینه مونتاژ
- **هزینه طلاکوبی** *(new)*
- **هزینه UV موضعی** *(new)*
- **هزینه برجسته‌کاری** *(new)*

**⑤ اداری و مجوزها** (Admin & Regulatory)
- **هزینه مجوز ارشاد** *(new)*
- **هزینه ثبت شابک** *(new)*

### Preset visibility matrix

| Field | شومیز ساده | گالینگور | مصور/رنگی | ترجمه | ویژه/لوکس | سفارشی |
|---|---|---|---|---|---|---|
| هزینه تالیف | ✓ | ✓ | ✓ | — | ✓ | ✓ |
| هزینه ترجمه | — | — | — | ✓ | — | ✓ |
| هزینه تصویرگری | — | — | ✓ | — | ✓ | ✓ |
| هزینه حروفچینی | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| هزینه مقوای مغذی | — | ✓ | — | — | ✓ | ✓ |
| طلاکوبی / UV / برجسته | — | — | — | — | ✓ | ✓ |
| هزینه مجوز / شابک | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

---

## Section 3 — Profitability Tab (Tab 3: قیمت‌گذاری و سودآوری)

This tab is read-only — it reads `total_cost` and `tiraj` computed by `perform_calculations()`. It refreshes whenever those values change.

### Part A — قیمت‌گذاری پیشنهادی

- `QDoubleSpinBox` for **ضریب قیمت‌گذاری** (default 2.5, range 1.0–5.0, step 0.1)
- Displays **قیمت پشت جلد پیشنهادی** = cost_per_book × multiplier, in large prominent font
- Horizontal segmented breakdown bar showing distribution of cover price:

| Segment | Default % | Editable |
|---|---|---|
| هزینه تولید | computed from actual cost | no |
| سهم کتابفروشی / توزیع | 35% | yes (QDoubleSpinBox) |
| حق تالیف | pulled from existing royalty field | no |
| سربار و سود ناشر | remainder | no (computed) |

The distribution % spinbox defaults to 35. Publishers with different contracts adjust it. All segments recompute live.

### Part B — نقطه سر به سر

- **هزینه کل پروژه** = total_cost (from perform_calculations)
- **درآمد خالص ناشر per copy** = cover_price × (1 - distribution_pct/100 - royalty_pct/100)
- **نقطه سر به سر** = ceil(total_cost / net_revenue_per_copy)
- Compared against current tiraj: green label if tiraj ≥ break-even, red if not
- Shows estimated profit/loss at full tiraj sell-through

### Part C — جدول سناریوها

`QTableWidget` — rows are 25%, 50%, 75%, 100% of current tiraj. Columns are ×2.5, ×3.0, ×3.5 (and the user's current custom multiplier if different from these three).

Each cell shows net profit/loss in tomans with color coding:
- 🔴 Red: loss
- 🟡 Yellow: within 10% of break-even
- 🟢 Green: profit

The cell matching the current multiplier + 100% tiraj row is highlighted with a border.

Table recalculates live when the multiplier spinner or distribution % changes.

---

## Section 4 — Data & Persistence

### New columns in `project_details`

Added via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` in `connect_db()`, same pattern as existing migration code:

| Column | Type | Default | Purpose |
|---|---|---|---|
| `hazineh_horoofchini` | REAL | 0 | هزینه حروفچینی و صفحه‌آرایی |
| `hazineh_mojawwez_ershad` | REAL | 0 | هزینه مجوز ارشاد |
| `hazineh_shabok` | REAL | 0 | هزینه ثبت شابک |
| `hazineh_talakoobi` | REAL | 0 | هزینه طلاکوبی |
| `hazineh_uv_mowzei` | REAL | 0 | هزینه UV موضعی |
| `hazineh_barjasteh` | REAL | 0 | هزینه برجسته‌کاری |
| `book_type_preset` | TEXT | 'شومیز ساده' | Preset name — restores form state on load |
| `pricing_multiplier` | REAL | 2.5 | ضریب قیمت‌گذاری |
| `distribution_percent` | REAL | 35.0 | سهم توزیع |

### Save/load impact
- `save_project_to_db()` — 9 new values added to INSERT/UPDATE
- `load_project_by_id()` — 9 new values read; `book_type_preset` triggers preset selector which restores field visibility
- `new_project()` — new fields zeroed, preset reset to "شومیز ساده", multiplier reset to 2.5, distribution_percent reset to 35.0

### Backward compatibility
Old projects get NULL for new columns, handled by the existing `if value is not None` guards in `load_project_by_id()`. No data migration needed.

---

## Out of Scope

- PDF report changes (Tab 5 unchanged)
- Print run cost comparison (tiraj vs. cost table) — deferred
- Digital/POD pricing model — deferred
- Editing or adding to `OPTIMAL_SPECS` — unchanged
