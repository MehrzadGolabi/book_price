import math

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QPainter, QFont, QColor, QPen

from bookcost.core.calculator import CostCalculator


class PrintLayoutWidget(QWidget):
    TITLE_H = 26

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(260)
        self.setMinimumHeight(380)
        self._data = None

    def update_layout(self, paper_w, paper_h, book_w, book_h,
                      pages_per_sheet, zinc_matn, zinc_jeld,
                      cut_in_half=False, papers_matn=None, papers_jeld=None):
        """paper_w/paper_h are the ACTUAL press-fed sheet size (already halved
        by the caller when cut_in_half is set) — the imposition grid and the
        «کاغذ» box in the size strip both reflect what's really printed on.
        papers_matn/papers_jeld (optional): [{'paper_type','form_count'}, ...]
        multi-paper entries, rendered as a composition breakdown when present.
        """
        self._data = {
            'paper_w': paper_w, 'paper_h': paper_h,
            'book_w': book_w,   'book_h': book_h,
            'pages_per_sheet': pages_per_sheet,
            'zinc_matn': zinc_matn, 'zinc_jeld': zinc_jeld,
            'cut_in_half': cut_in_half,
            'papers_matn': papers_matn or [],
            'papers_jeld': papers_jeld or [],
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

        # Background: slate-800 matching the app toolbar
        painter.fillRect(0, 0, w, h, QColor('#1e293b'))

        # Title bar
        title_h = self.TITLE_H
        painter.fillRect(0, 0, w, title_h, QColor('#0f172a'))
        painter.setFont(QFont('Tahoma', 9))
        painter.setPen(QColor('#94a3b8'))
        painter.drawText(0, 0, w, title_h, Qt.AlignCenter, 'نمایش ابعاد و صفحه‌آرایی')

        if not self._data or not self._data.get('pages_per_sheet'):
            painter.setPen(QColor('#64748b'))
            painter.setFont(QFont('Tahoma', 10))
            painter.drawText(0, title_h, w, h - title_h, Qt.AlignCenter, 'اطلاعات کافی نیست')
            painter.end()
            return

        d = self._data
        remaining = h - title_h
        has_multi = bool(d.get('papers_matn')) or bool(d.get('papers_jeld'))

        if has_multi:
            zone1_h = int(remaining * 0.44)
            zone3_h = int(remaining * 0.24)
            zone2_h = remaining - zone1_h - zone3_h
        else:
            zone1_h = int(remaining * 0.58)
            zone2_h = remaining - zone1_h
            zone3_h = 0
        zone1_y = title_h
        zone2_y = title_h + zone1_h
        zone3_y = zone2_y + zone2_h

        self._draw_imposition(painter, 0, zone1_y, w, zone1_h, d)

        painter.setPen(QPen(QColor('#334155'), 1))
        painter.drawLine(0, zone2_y, w, zone2_y)
        self._draw_size_strip(painter, 0, zone2_y, w, zone2_h, d)

        if has_multi:
            painter.setPen(QPen(QColor('#334155'), 1))
            painter.drawLine(0, zone3_y, w, zone3_y)
            self._draw_paper_composition(painter, 0, zone3_y, w, zone3_h, d)

        painter.end()

    def _draw_imposition(self, painter, x, y, w, h, d):
        pad, label_h = 10, 24
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

        painter.fillRect(sx, sy, sheet_w, sheet_h, QColor('#1e3a5f'))
        painter.setPen(QPen(QColor('#3b5998'), 1))
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
                painter.fillRect(cx, cy, cw, ch, QColor('#2563eb').darker(160))
                painter.setPen(QPen(QColor('#3b82f6'), 1))
                painter.drawRect(cx, cy, cw, ch)
                pg_num = r * cols + c + 1
                painter.setFont(QFont('Tahoma', max(9, min(11, ch // 4))))
                painter.setPen(QColor('#93c5fd'))
                painter.drawText(cx, cy, cw, ch, Qt.AlignCenter, str(pg_num))

        label_y = sy + sheet_h + 4
        painter.setFont(QFont('Tahoma', 9))
        painter.setPen(QColor('#94a3b8'))
        cut_note = ' (پس از برش)' if d.get('cut_in_half') else ''
        label = f'کاغذ {int(paper_w)}×{int(paper_h)}{cut_note} — {pages} صفحه در ورق'
        painter.drawText(x, label_y, w, label_h, Qt.AlignCenter, label)

    def _draw_size_strip(self, painter, x, y, w, h, d):
        pad, label_h = 10, 38
        min_spacing = 10
        n_items = 3
        avail_h = h - pad * 2 - label_h
        avail_w = w - pad * 2 - min_spacing * (n_items + 1)
        if avail_h <= 0 or avail_w <= 0:
            return

        paper_w, paper_h = d['paper_w'], d['paper_h']
        book_w, book_h = d['book_w'], d['book_h']
        zinc_w, zinc_h = CostCalculator.ZINC_DIMS.get(d['zinc_matn'], (paper_w, paper_h))

        max_real_h = max(paper_h, book_h, zinc_h)
        total_real_w = paper_w + book_w + zinc_w
        if max_real_h <= 0 or total_real_w <= 0:
            return

        # Constrain scale by both height and width so items never overflow
        scale = min(avail_h / max_real_h, avail_w / total_real_w)
        scale = max(scale, 0.01)  # guard against degenerate sizes

        paper_name = 'کاغذ (برش‌خورده)' if d.get('cut_in_half') else 'کاغذ'
        items = [
            (paper_w * scale, paper_h * scale, QColor('#374151'), QColor('#6b7280'),
             f'{int(paper_w)}×{int(paper_h)}', paper_name),
            (book_w * scale, book_h * scale, QColor('#1e3a5f'), QColor('#3b82f6'),
             f'{book_w:.0f}×{book_h:.0f}', 'کتاب'),
            (zinc_w * scale, zinc_h * scale, QColor('#3b2f04'), QColor('#ca8a04'),
             f'{int(zinc_w)}×{int(zinc_h)}', d['zinc_matn'].replace('زینک ', '')),
        ]

        total_rects_w = sum(max(6, int(pw)) for pw, *_ in items)
        spacing = max(min_spacing, (w - pad * 2 - total_rects_w) // (n_items + 1))
        cur_x = x + pad + spacing

        for (pw, ph, fill, border, dims_lbl, name_lbl) in items:
            pw_i = max(6, int(pw))
            ph_i = max(4, int(ph))
            iy = y + pad + (avail_h - ph_i)
            painter.fillRect(cur_x, iy, pw_i, ph_i, fill)
            painter.setPen(QPen(border, 1))
            painter.drawRect(cur_x, iy, pw_i, ph_i)
            ly = y + pad + avail_h + 6
            painter.setFont(QFont('Tahoma', 9))
            painter.setPen(QColor('#cbd5e1'))
            painter.drawText(cur_x - 6, ly, pw_i + 12, 16, Qt.AlignCenter, dims_lbl)
            painter.setPen(QColor('#94a3b8'))
            painter.drawText(cur_x - 6, ly + 16, pw_i + 12, 16, Qt.AlignCenter, name_lbl)
            cur_x += pw_i + spacing

    # Cycled swatch colors for paper-type chips (matches the app's blue/amber
    # accent family so it reads consistently with the rest of the UI)
    _COMPOSITION_COLORS = [
        QColor('#3b82f6'), QColor('#ca8a04'), QColor('#22c55e'),
        QColor('#ec4899'), QColor('#a855f7'), QColor('#14b8a6'),
    ]

    def _draw_paper_composition(self, painter, x, y, w, h, d):
        """Multiple-paper-type breakdown (item: matn/jeld each with several
        named paper types + form counts) — only drawn when in use."""
        pad = 10
        painter.setFont(QFont('Tahoma', 9))
        painter.setPen(QColor('#94a3b8'))
        painter.drawText(x + pad, y + pad, w - 2 * pad, 16, Qt.AlignRight, 'ترکیب کاغذ:')

        rows = [('متن', d.get('papers_matn') or []), ('جلد', d.get('papers_jeld') or [])]
        rows = [(label, entries) for label, entries in rows if entries]
        if not rows:
            return

        row_h = (h - pad * 2 - 18) / len(rows)
        cy = y + pad + 18
        color_i = 0
        for label, entries in rows:
            parts = []
            for e in entries:
                name = e.get('paper_type') or '—'
                forms = e.get('form_count') or 0
                parts.append((name, forms))

            painter.setFont(QFont('Tahoma', 8, QFont.Bold))
            painter.setPen(QColor('#cbd5e1'))
            rect = QRect(x + pad, int(cy), w - 2 * pad, int(row_h))
            painter.drawText(rect, Qt.AlignRight | Qt.AlignTop, f'{label}:')

            text = '  ·  '.join(f'{n} ({c:g} فرم)' for n, c in parts)
            painter.setFont(QFont('Tahoma', 8))
            swatch = self._COMPOSITION_COLORS[color_i % len(self._COMPOSITION_COLORS)]
            painter.setPen(swatch)
            text_rect = QRect(x + pad, int(cy) + 14, w - 2 * pad, int(row_h) - 14)
            painter.drawText(text_rect, Qt.AlignRight | Qt.AlignTop | Qt.TextWordWrap, text)

            color_i += 1
            cy += row_h
