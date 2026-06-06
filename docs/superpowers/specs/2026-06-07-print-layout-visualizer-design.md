# Print Layout Visualizer — Design Spec

**Date:** 2026-06-07
**Goal:** Add a live sidebar panel to Tab 2 that shows a combined page-imposition diagram and proportional size comparison, so non-technical users can see exactly how their book, paper, and zinc plate relate.

---

## Context

The app estimates book production costs. Tab 2 (ورود اطلاعات و هزینه‌ها) is a data-entry form where users set book format (قطع), page count, paper size, and zinc size. These choices have a direct physical meaning (how pages are laid out on a press sheet, how big the zinc plate is) that non-technical users can't easily visualize from dropdown values alone.

---

## Placement

A fixed-width (240 px) sidebar panel is added to the **left side** of Tab 2 (RTL layout, so visually to the right of the form). It is always visible — no collapse, no separate tab, no scroll required.

The current Tab 2 is a single scroll area. The outer container changes to a `QHBoxLayout`:

```
Tab 2
├── QHBoxLayout (outer)
│   ├── PrintLayoutWidget  (left, 240 px fixed, stretches vertically)
│   └── QScrollArea        (right, stretches — existing form, unchanged)
```

No changes to the existing form layout or any form widgets.

---

## Widget Class: `PrintLayoutWidget(QWidget)`

New class added to `main.py` immediately before `class BookCostCalculator`.

### Public API

```python
def update_layout(
    self,
    paper_w: float, paper_h: float,    # print sheet size in cm
    book_w: float,  book_h: float,     # book page size in cm
    pages_per_sheet: int,              # how many book pages fit per sheet side
    zinc_matn: str,                    # e.g. "زینک 3.5 ورقی"
    zinc_jeld: str,                    # e.g. "زینک 3.5 ورقی"
) -> None
```

Stores the new state in `self._data` and calls `self.update()` to schedule a repaint.

### Drawing

`paintEvent()` splits the widget area into two vertical zones:

**Zone 1 — Page Imposition (top 60% of height)**

- Draws the print sheet as a filled rectangle with a border.
- Subdivides it into a `cols × rows` grid of cells where each cell represents one book-page position. Grid dimensions are computed from `pages_per_sheet` by iterating all factor pairs `(c, r)` where `c * r == pages_per_sheet` and picking the pair where `c / r` is closest to `paper_w / paper_h`.
- Each cell is drawn with a blue fill and numbered (page number) in small text.
- A label below the sheet reads: `کاغذ {paper_w}×{paper_h} — {pages_per_sheet} صفحه در ورق`

**Zone 2 — Size Comparison Strip (bottom 40% of height)**

- Draws three proportionally-scaled rectangles side by side, all normalised to fit the strip height:
  1. Print sheet (`paper_w × paper_h`)
  2. Book page (`book_w × book_h`)
  3. Zinc plate for متن (`zinc_matn` — dimensions from `ZINC_DIMS`)
- A text label below each rectangle shows its name and dimensions.
- Colour coding: paper = grey, book = blue, zinc = amber.

**Empty state:** When `pages_per_sheet` is 0 or `_data` is not set, the widget renders a centred placeholder: `اطلاعات کافی نیست`

### Zinc Plate Dimensions

A class-level dict used only for visualisation (approximate press plate sizes in cm):

```python
ZINC_DIMS = {
    "زینک GTO":      (35, 50),
    "زینک 2 ورقی":   (50, 70),
    "زینک 2.5 ورقی": (60, 90),
    "زینک 3.5 ورقی": (70, 100),
    "زینک 4.5 ورقی": (90, 120),
}
```

---

## Signal Wiring

A new method `_refresh_layout_widget()` on `BookCostCalculator` gathers current form values and calls `self.layout_widget.update_layout(...)`.

```python
def _refresh_layout_widget(self):
    # parse paper size from paper_size_combo ("70×100" → 70.0, 100.0)
    # get book dims from OPTIMAL_SPECS default_dims or book_width/height spinboxes
    # get pages_per_sheet from suggest_optimal_layout's last computed value
    # call self.layout_widget.update_layout(...)
```

Connected to (added in `setup_details_tab()` signal block):

| Signal | Widget |
|--------|--------|
| `currentIndexChanged` | `self.inputs['قطع']` |
| `valueChanged` | `self.total_pages_spin` |
| `currentIndexChanged` | `self.paper_size_combo` |
| `currentIndexChanged` | `self.zinc_size_matn_combo` |
| `currentIndexChanged` | `self.zinc_size_jeld_combo` |
| `valueChanged` | `self.book_width_spin` |
| `valueChanged` | `self.book_height_spin` |

Also called once at the end of `setup_details_tab()` to populate on startup.

**Pages-per-sheet source:** `suggest_optimal_layout()` already computes `pages_per_sheet`. To avoid duplication, `_refresh_layout_widget()` recomputes it using the same logic (`OPTIMAL_SPECS[qate]['pages_per_sheet']` for standard formats, or `_compute_optimal_orientation()` result for custom formats).

---

## Book Page Dimensions

For standard formats, `OPTIMAL_SPECS` only stores the paper size, not the individual book-page dimensions. A companion dict maps each format to its standard book-page size in cm:

```python
BOOK_PAGE_DIMS = {
    "وزیری":     (17.0, 24.0),
    "رقعی":      (14.5, 21.0),
    "رحلی کوچک": (21.0, 28.5),
    "رحلی بزرگ": (24.0, 34.0),
    "جیبی":      (11.0, 18.0),
    "خشتی":      (21.0, 21.0),
    "مربع":      (21.0, 21.0),   # default; overridden by user input
    "بزرگ‌قطع":  (24.0, 34.0),
    "کوچک‌قطع":  (14.0, 20.0),
    "سفارشی":    (None, None),   # always from spinboxes
}
```

For custom/semi-custom formats, `book_width_spin` and `book_height_spin` are used instead.

---

## File Changes

| File | Change |
|------|--------|
| `main.py` | Add `PrintLayoutWidget` class before `BookCostCalculator` |
| `main.py` | Add `ZINC_DIMS` and `BOOK_PAGE_DIMS` as class-level dicts on `PrintLayoutWidget` |
| `main.py` | Change Tab 2 outer container from single scroll area to `QHBoxLayout` with sidebar |
| `main.py` | Add `_refresh_layout_widget()` method to `BookCostCalculator` |
| `main.py` | Add signal connections and startup call in `setup_details_tab()` |

No new imports required (`QPainter`, `QWidget` are already imported).

---

## Out of Scope

- Visualizing the cover (جلد) separately from the text block (متن)
- Showing bleed/margin areas on the imposition grid
- Exporting or printing the diagram
- Displaying the zinc plate for جلد separately (متن zinc is shown as representative)
