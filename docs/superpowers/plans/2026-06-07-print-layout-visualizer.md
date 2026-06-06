# Print Layout Visualizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a live 240 px sidebar panel to Tab 2 that draws a page-imposition grid (top) and proportional size comparison of paper, book, and zinc plate (bottom), updating instantly as the user changes form values.

**Architecture:** A new `PrintLayoutWidget(QWidget)` class is added to `main.py` before `BookCostCalculator`. Its `paintEvent()` does all drawing with QPainter — no new dependencies. Tab 2's outer container changes from a plain `QVBoxLayout` to a `QHBoxLayout` containing the existing scroll area plus the new sidebar. A `_refresh_layout_widget()` method on `BookCostCalculator` gathers form state and calls `widget.update_layout(...)`, connected to every relevant signal.

**Tech Stack:** PySide6 (QPainter, QWidget — already in project), Python 3.x, SQLite (no changes)

---

## File Map

| File | Change |
|------|--------|
| `main.py:11` | Add `QPainter, QFont, QColor, QPen` to `from PySide6.QtGui import` |
| `main.py:288` | Insert `PrintLayoutWidget` class (≈ 120 lines) before `class BookCostCalculator` |
| `main.py:813-814` | Replace single-widget `QVBoxLayout` with `QHBoxLayout` containing sidebar + scroll area |
| `main.py` (new method) | Add `_refresh_layout_widget()` to `BookCostCalculator` |
| `main.py:838-843` | Add signal connections + startup call at end of `setup_details_tab` |

---

## Task 1: Add `PrintLayoutWidget` class

**Files:**
- Modify: `main.py:11` — imports
- Modify: `main.py:288` — insert class before `BookCostCalculator`

- [ ] **Step 1: Extend QtGui imports**

At `main.py:11`, replace:
```python
from PySide6.QtGui import QAction, QFontDatabase, QShortcut, QKeySequence
```
With:
```python
from PySide6.QtGui import QAction, QFontDatabase, QShortcut, QKeySequence, QPainter, QFont, QColor, QPen
```

- [ ] **Step 2: Insert `PrintLayoutWidget` class**

At `main.py:288` (the blank line just before `class BookCostCalculator`), insert the following class:

```python
class PrintLayoutWidget(QWidget):
    ZINC_DIMS = {
        "زینک GTO":      (35, 50),
        "زینک 2 ورقی":   (50, 70),
        "زینک 2.5 ورقی": (60, 90),
        "زینک 3.5 ورقی": (70, 100),
        "زینک 4.5 ورقی": (90, 120),
    }
    BOOK_PAGE_DIMS = {
        "وزیری":     (17.0, 24.0),
        "رقعی":      (14.5, 21.0),
        "رحلی کوچک": (21.0, 28.5),
        "رحلی بزرگ": (24.0, 34.0),
        "جیبی":      (11.0, 18.0),
        "خشتی":      (21.0, 21.0),
        "مربع":      (21.0, 21.0),
        "بزرگ‌قطع":  (24.0, 34.0),
        "کوچک‌قطع":  (14.0, 20.0),
        "سفارشی":    (None, None),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(220)
        self.setMinimumHeight(300)
        self._data = None

    def update_layout(self, paper_w, paper_h, book_w, book_h,
                      pages_per_sheet, zinc_matn, zinc_jeld):
        self._data = {
            'paper_w': paper_w, 'paper_h': paper_h,
            'book_w': book_w,   'book_h': book_h,
            'pages_per_sheet': pages_per_sheet,
            'zinc_matn': zinc_matn, 'zinc_jeld': zinc_jeld,
        }
        self.update()

    @staticmethod
    def _best_grid(n, aspect_w, aspect_h):
        """Return (cols, rows) where cols*rows==n and cols/rows is closest to aspect_w/aspect_h."""
        if n <= 0:
            return (1, 1)
        target = aspect_w / aspect_h if aspect_h else 1.0
        best = (1, n)
        best_diff = abs(1.0 / n - target)
        for c in range(1, n + 1):
            if n % c == 0:
                r = n // c
                diff = abs(c / r - target)
                if diff < best_diff:
                    best_diff = diff
                    best = (c, r)
        return best

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor('#1a1a2e'))

        if not self._data or not self._data.get('pages_per_sheet'):
            painter.setPen(QColor('#888888'))
            painter.setFont(QFont('Tahoma', 10))
            painter.drawText(self.rect(), Qt.AlignCenter, 'اطلاعات کافی نیست')
            painter.end()
            return

        d = self._data
        zone1_h = int(h * 0.60)
        zone2_h = h - zone1_h
        self._draw_imposition(painter, 0, 0, w, zone1_h, d)
        self._draw_size_strip(painter, 0, zone1_h, w, zone2_h, d)
        painter.end()

    def _draw_imposition(self, painter, x, y, w, h, d):
        pad, label_h = 10, 22
        paper_w, paper_h = d['paper_w'], d['paper_h']
        pages = d['pages_per_sheet']

        avail_w = w - pad * 2
        avail_h = h - pad * 2 - label_h
        if avail_w <= 0 or avail_h <= 0 or paper_w <= 0 or paper_h <= 0:
            return

        scale = min(avail_w / paper_w, avail_h / paper_h)
        sheet_w = int(paper_w * scale)
        sheet_h = int(paper_h * scale)
        sx = x + (w - sheet_w) // 2
        sy = y + pad

        painter.fillRect(sx, sy, sheet_w, sheet_h, QColor('#2a2a3e'))
        painter.setPen(QPen(QColor('#555555'), 1))
        painter.drawRect(sx, sy, sheet_w, sheet_h)

        cols, rows = self._best_grid(pages, paper_w, paper_h)
        cell_w = sheet_w // cols
        cell_h = sheet_h // rows
        for r in range(rows):
            for c in range(cols):
                cx = sx + c * cell_w + 1
                cy = sy + r * cell_h + 1
                cw = max(1, cell_w - 2)
                ch = max(1, cell_h - 2)
                painter.fillRect(cx, cy, cw, ch, QColor('#1a3a5a'))
                painter.setPen(QPen(QColor('#2a6496'), 1))
                painter.drawRect(cx, cy, cw, ch)
                pg_num = r * cols + c + 1
                painter.setFont(QFont('Tahoma', max(6, min(10, ch // 4))))
                painter.setPen(QColor('#64b5f6'))
                painter.drawText(cx, cy, cw, ch, Qt.AlignCenter, str(pg_num))

        label_y = sy + sheet_h + 4
        painter.setFont(QFont('Tahoma', 9))
        painter.setPen(QColor('#aaaaaa'))
        label = f'کاغذ {int(paper_w)}×{int(paper_h)} — {pages} صفحه در ورق'
        painter.drawText(x, label_y, w, label_h, Qt.AlignCenter, label)

    def _draw_size_strip(self, painter, x, y, w, h, d):
        pad, label_h = 8, 32
        avail_h = h - pad * 2 - label_h
        if avail_h <= 0:
            return

        paper_w, paper_h = d['paper_w'], d['paper_h']
        book_w, book_h = d['book_w'], d['book_h']
        zinc_w, zinc_h = self.ZINC_DIMS.get(d['zinc_matn'], (paper_w, paper_h))

        max_real_h = max(paper_h, book_h, zinc_h)
        if max_real_h <= 0:
            return
        scale = avail_h / max_real_h

        items = [
            (paper_w * scale, paper_h * scale, QColor('#3a3a4a'), QColor('#888888'),
             f'{int(paper_w)}×{int(paper_h)}', 'کاغذ'),
            (book_w * scale, book_h * scale, QColor('#1a3a5a'), QColor('#2a6496'),
             f'{book_w:.0f}×{book_h:.0f}', 'کتاب'),
            (zinc_w * scale, zinc_h * scale, QColor('#3a3a1a'), QColor('#8a8a40'),
             f'{int(zinc_w)}×{int(zinc_h)}', d['zinc_matn'].replace('زینک ', '')),
        ]

        total_rects_w = sum(max(8, int(pw)) for pw, *_ in items)
        spacing = max(8, (w - 2 * pad - total_rects_w) // (len(items) + 1))
        cur_x = x + pad + spacing

        for (pw, ph, fill, border, dims_lbl, name_lbl) in items:
            pw_i = max(8, int(pw))
            ph_i = max(4, int(ph))
            iy = y + pad + (avail_h - ph_i)
            painter.fillRect(cur_x, iy, pw_i, ph_i, fill)
            painter.setPen(QPen(border, 1))
            painter.drawRect(cur_x, iy, pw_i, ph_i)
            ly = y + pad + avail_h + 4
            painter.setFont(QFont('Tahoma', 8))
            painter.setPen(QColor('#aaaaaa'))
            painter.drawText(cur_x - 4, ly, pw_i + 8, 14, Qt.AlignCenter, dims_lbl)
            painter.setPen(QColor('#888888'))
            painter.drawText(cur_x - 4, ly + 14, pw_i + 8, 14, Qt.AlignCenter, name_lbl)
            cur_x += pw_i + spacing


```

- [ ] **Step 3: Verify syntax**

```bash
cd /home/mg/book_price && source .venv/bin/activate && python -c "
import ast
with open('main.py') as f: src = f.read()
ast.parse(src)
print('Syntax OK')
"
```
Expected: `Syntax OK`

- [ ] **Step 4: Test `_best_grid` pure logic**

```bash
cd /home/mg/book_price && source .venv/bin/activate && python -c "
import sys, os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)
from main import PrintLayoutWidget

# 32 pages on portrait 70x100: expect (4, 8) — 4 cols, 8 rows
assert PrintLayoutWidget._best_grid(32, 70, 100) == (4, 8), f'got {PrintLayoutWidget._best_grid(32, 70, 100)}'
# 32 pages on landscape 100x70: expect (8, 4)
assert PrintLayoutWidget._best_grid(32, 100, 70) == (8, 4), f'got {PrintLayoutWidget._best_grid(32, 100, 70)}'
# 12 pages on 50x70: pairs (3,4)=0.75 vs (4,3)=1.33, target=0.71 → (3,4)
assert PrintLayoutWidget._best_grid(12, 50, 70) == (3, 4), f'got {PrintLayoutWidget._best_grid(12, 50, 70)}'
# Edge: 1 page
assert PrintLayoutWidget._best_grid(1, 70, 100) == (1, 1)
print('_best_grid: all assertions passed')
"
```
Expected: `_best_grid: all assertions passed`

- [ ] **Step 5: Test widget instantiation and `update_layout`**

```bash
cd /home/mg/book_price && source .venv/bin/activate && python -c "
import sys, os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)
from main import PrintLayoutWidget

w = PrintLayoutWidget()
assert w._data is None
w.update_layout(70, 100, 17, 24, 32, 'زینک 3.5 ورقی', 'زینک 3.5 ورقی')
assert w._data['paper_w'] == 70
assert w._data['pages_per_sheet'] == 32
assert w._data['zinc_matn'] == 'زینک 3.5 ورقی'
print('update_layout: OK')
"
```
Expected: `update_layout: OK`

- [ ] **Step 6: Commit**

```bash
git add main.py
git commit -m "feat: add PrintLayoutWidget with QPainter imposition + size-comparison drawing"
```

---

## Task 2: Wire `PrintLayoutWidget` into Tab 2

**Files:**
- Modify: `main.py:813-814` — Tab 2 outer container
- Modify: `main.py` — add `_refresh_layout_widget` method + signal connections

- [ ] **Step 1: Change Tab 2 outer layout**

In `setup_details_tab`, find these two lines (around line 813):
```python
            main_layout = QVBoxLayout(self.tab_details)
            main_layout.addWidget(scroll_area)
```

Replace with:
```python
            self.layout_widget = PrintLayoutWidget()
            self.layout_widget.setFixedWidth(240)

            outer_layout = QHBoxLayout(self.tab_details)
            outer_layout.setContentsMargins(0, 0, 0, 0)
            outer_layout.setSpacing(0)
            outer_layout.setLayoutDirection(Qt.LeftToRight)
            outer_layout.addWidget(scroll_area)
            outer_layout.addWidget(self.layout_widget)
```

- [ ] **Step 2: Add `_refresh_layout_widget` method to `BookCostCalculator`**

Add this method after `_update_zinc_price_labels` (around line 870):

```python
    def _refresh_layout_widget(self):
        qate = self.inputs['قطع'].currentText()
        specs = self.OPTIMAL_SPECS.get(qate, {})

        paper_str = self.paper_size_combo.currentText().replace('×', 'x')
        try:
            paper_w, paper_h = map(float, paper_str.split('x'))
        except ValueError:
            return

        if specs.get('pages_per_sheet') is None and self.book_dims_row_widget.isVisible():
            book_w = self.book_width_spin.value()
            book_h = self.book_height_spin.value()
        else:
            dims = PrintLayoutWidget.BOOK_PAGE_DIMS.get(qate, (None, None))
            book_w = dims[0] if dims[0] else paper_w / 4
            book_h = dims[1] if dims[1] else paper_h / 4

        if specs.get('pages_per_sheet') is not None:
            pages_per_sheet = specs['pages_per_sheet']
        elif book_w > 0 and book_h > 0:
            _, pages_per_sheet = self._compute_optimal_orientation(
                book_w, book_h, paper_w, paper_h
            )
        else:
            pages_per_sheet = 0

        self.layout_widget.update_layout(
            paper_w, paper_h,
            book_w, book_h,
            pages_per_sheet,
            self.zinc_size_matn_combo.currentText(),
            self.zinc_size_jeld_combo.currentText(),
        )
```

- [ ] **Step 3: Add signal connections and startup call**

In `setup_details_tab`, find the existing signal block that ends with:
```python
            self._update_zinc_price_labels()
            self.suggest_optimal_layout()
```

Add the following connections before that block (after `self.paper_size_combo.currentIndexChanged.connect(self.suggest_optimal_layout)`):
```python
            self.inputs['قطع'].currentIndexChanged.connect(self._refresh_layout_widget)
            self.total_pages_spin.valueChanged.connect(self._refresh_layout_widget)
            self.paper_size_combo.currentIndexChanged.connect(self._refresh_layout_widget)
            self.zinc_size_matn_combo.currentIndexChanged.connect(self._refresh_layout_widget)
            self.zinc_size_jeld_combo.currentIndexChanged.connect(self._refresh_layout_widget)
            self.book_width_spin.valueChanged.connect(self._refresh_layout_widget)
            self.book_height_spin.valueChanged.connect(self._refresh_layout_widget)
```

Then add the startup call after `self.suggest_optimal_layout()`:
```python
            self._refresh_layout_widget()
```

- [ ] **Step 4: Verify syntax**

```bash
cd /home/mg/book_price && source .venv/bin/activate && python -c "
import ast
with open('main.py') as f: src = f.read()
ast.parse(src)
print('Syntax OK')
"
```
Expected: `Syntax OK`

- [ ] **Step 5: Verify app launches and sidebar is populated**

```bash
cd /home/mg/book_price && source .venv/bin/activate && python -c "
import sys, os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication
import main as m

app = QApplication(sys.argv)
w = m.BookCostCalculator()
w.show()
QCoreApplication.processEvents()

# layout_widget exists
assert hasattr(w, 'layout_widget'), 'layout_widget not found'
assert w.layout_widget.width() == 240, f'expected 240px, got {w.layout_widget.width()}'

# After selecting وزیری + pages, _data should be populated
w.inputs['قطع'].setCurrentText('وزیری')
w.total_pages_spin.setValue(192)
QCoreApplication.processEvents()
assert w.layout_widget._data is not None, '_data is None after setting قطع'
assert w.layout_widget._data['paper_w'] == 70.0
assert w.layout_widget._data['pages_per_sheet'] == 32
print('Sidebar wired correctly — data:', w.layout_widget._data)
" 2>&1 | grep -v 'libGL\|libEGL\|Warning\|qt.qpa\|QStandardPaths\|xcb\|MESA\|Fontconfig\|propagate\|Cannot create\|^$'
```
Expected: `Sidebar wired correctly — data: {...}` with `paper_w: 70.0, pages_per_sheet: 32`

- [ ] **Step 6: Test custom size (سفارشی) updates diagram**

```bash
cd /home/mg/book_price && source .venv/bin/activate && python -c "
import sys, os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication
import main as m

app = QApplication(sys.argv)
w = m.BookCostCalculator()
w.show()
QCoreApplication.processEvents()

w.inputs['قطع'].setCurrentText('سفارشی')
w.total_pages_spin.setValue(100)
w.book_width_spin.setValue(20)
w.book_height_spin.setValue(30)
QCoreApplication.processEvents()

d = w.layout_widget._data
assert d['book_w'] == 20.0, f'expected 20, got {d[\"book_w\"]}'
assert d['book_h'] == 30.0, f'expected 30, got {d[\"book_h\"]}'
# _compute_optimal_orientation(book_w=20, book_h=30, paper_w=70, paper_h=100):
#   portrait  = (70//20)*(100//30)*2 = 3*3*2 = 18
#   landscape = (70//30)*(100//20)*2 = 2*5*2 = 20  ← wins (20 >= 18)
assert d['pages_per_sheet'] == 20, f'expected 20, got {d[\"pages_per_sheet\"]}'
print('Custom size: OK — pages_per_sheet:', d['pages_per_sheet'])
" 2>&1 | grep -v 'libGL\|libEGL\|Warning\|qt.qpa\|QStandardPaths\|xcb\|MESA\|Fontconfig\|propagate\|Cannot create\|^$'
```
Expected: `Custom size: OK — pages_per_sheet: 20`

- [ ] **Step 7: Commit**

```bash
git add main.py
git commit -m "feat: wire PrintLayoutWidget sidebar into Tab 2 with live signal updates"
```

---

## Task 3: Final Visual Check

- [ ] **Step 1: Run app and manually inspect sidebar**

```bash
cd /home/mg/book_price && source .venv/bin/activate && python main.py
```

Verify:
1. Tab 2 shows the sidebar panel on the right side of the form
2. On startup, the sidebar shows "اطلاعات کافی نیست" (page count is 0)
3. Enter any page count (e.g. 192) → imposition grid appears with numbered cells
4. Switch book format (قطع) → grid and size comparison update immediately
5. Select "سفارشی" → enter 20×30 cm → orientation label and diagram update
6. Go to Tab 5, set a zinc price, come back to Tab 2 → zinc plate label in strip updates
7. Change zinc size combo → size strip's zinc rectangle changes proportions

- [ ] **Step 2: Commit (only if any small visual tweaks were made)**

```bash
git add main.py
git commit -m "fix: visual polish on PrintLayoutWidget sidebar"
```

---

## Verification Checklist

- [ ] `_best_grid` unit tests pass for 32-up portrait, 32-up landscape, 12-up, edge case n=1
- [ ] `update_layout()` stores all 7 fields in `self._data`
- [ ] Empty state renders "اطلاعات کافی نیست" when `pages_per_sheet` is 0
- [ ] Sidebar is exactly 240 px wide and stretches full height of Tab 2
- [ ] Switching قطع from وزیری to سفارشی updates both zones of the diagram
- [ ] Custom dimensions (book_width/height spinboxes) drive the diagram for custom formats
- [ ] App starts without errors and Tab 2 layout is not broken
