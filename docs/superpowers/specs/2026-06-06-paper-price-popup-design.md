# Paper Price Calculator Popup — Design Spec
**Date:** 2026-06-06

## Context

The current workflow forces users to switch between multiple tabs to enter paper unit prices:
Tab 4 (Paper Preprocessing) → calculate price → export to Tab 5 (Base Price Management) → switch back to Tab 1 (Data Entry) → click toolbar button to import. This multi-tab round-trip interrupts the main data entry flow for something that should be inline.

**Goal:** Allow users to calculate and fill paper unit prices without ever leaving Tab 1.

---

## What Changes

### Tab 1 — Two new calculator buttons

Add a "🧮 محاسبه" button next to each of the two paper unit price spinboxes in the "محاسبات هوشمند کاغذ و زینک" GroupBox:

- `unit_price_paper_matn_spin` → "قیمت واحد هر ورق کاغذ متن"
- `unit_price_paper_jeld_spin` → "قیمت واحد هر ورق کاغذ جلد"

The zinc unit price field (`unit_price_zinc_spin`) does **not** get a button — zinc prices are simple flat values.

Each row becomes: `[spinbox] [🧮 محاسبه button]` aligned horizontally. The button is styled in blue (`#2a6496`) to visually distinguish it from the spinbox.

### New Dialog — `PaperPriceDialog`

A new `QDialog` class (added to `main.py`) with two sections:

**Section 1 — Saved Library (top)**
- Table showing all rows from the `paper_calculations` DB table: columns `نام کاغذ`, `فرمول`, `قیمت واحد`
- Each row has an "انتخاب" button that immediately populates the result and closes the dialog
- Empty state: show "هنوز محاسبه‌ای ذخیره نشده" label

**Section 2 — Fresh Calculator (below)**
- Three formula tabs matching the existing Tab 4 logic exactly:
  - **ابعاد × وزن × قیمت**: inputs for وزن (g), ارتفاع (cm), طول (cm), قیمت (per 1000 sheets) → `((H×L) × W / 10000) × (price / 1000)`
  - **قیمت بند**: inputs for تعداد در بند, قیمت هر بند → `price / count`
  - **دستی**: direct numeric input
- Optional "نام کاغذ" text field — if filled, saves result to `paper_calculations` table on Apply
- Live result display: shows calculated unit price updating as inputs change

**Footer**
- "✓ اعمال در فیلد" button: sets the target spinbox value and closes the dialog
- "انصراف" button: closes without changes

### Dialog Context

The dialog is instantiated with a `target` parameter (`"matn"` or `"jeld"`) so the header title and the spinbox that gets filled are correct. No other behavior differs between the two variants.

---

## What Does NOT Change

- Tab 4 (Paper Preprocessing) remains intact — power users who prefer managing calculations there can continue to do so.
- Tab 5 (Base Price Management) remains intact.
- The "دریافت قیمت‌های پایه" toolbar button remains for importing other (non-paper) default costs.
- The three read-only cost fields (`هزینه کاغذ متن`, `هزینه کاغذ جلد`, `هزینه زینک`) and `auto_calculate_costs()` are untouched.

---

## Data Flow

```
[🧮 محاسبه button clicked]
        ↓
PaperPriceDialog opens (reads paper_calculations table for library)
        ↓
User picks from library OR fills calculator
        ↓
"✓ اعمال در فیلد" clicked
        ↓
  [if name was entered] → INSERT into paper_calculations
        ↓
unit_price_paper_matn_spin.setValue(result)   ← or jeld variant
        ↓
auto_calculate_costs() fires (already connected via valueChanged)
        ↓
هزینه کاغذ متن / جلد updates automatically
```

---

## Visual Style

Match the existing app dark theme (from `style.qss`). The "🧮 محاسبه" button uses blue `#2a6496` background, white text, small padding. The result display in the dialog uses a green-tinted background (`#1a2a1a`, border `#2d5a27`) with green (`#4caf50`) price text — same feel as the mockup approved during design.

---

## Verification

1. Run `python main.py`
2. Open or create a project → navigate to Tab 1
3. Confirm "🧮 محاسبه" button appears next to both paper unit price fields
4. Click button → dialog opens
5. With an empty library: confirm empty-state message shows
6. Fill calculator (any formula) → confirm result updates live
7. Click "✓ اعمال در فیلد" → dialog closes, spinbox updates, `هزینه کاغذ متن`/`جلد` auto-recalculates
8. Repeat with a name entered → confirm row appears in library on next open
9. Open dialog again → click "انتخاب" on library row → spinbox fills, dialog closes
10. Confirm Tab 4 and Tab 5 still function normally
