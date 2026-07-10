"""PDF cost report generation, decoupled from the Qt UI.

The UI assembles a :class:`ReportData` snapshot and calls :func:`build_pdf_report`;
nothing here imports Qt, so the layout can be tested headlessly.

The report always fits on a single A4 page: the body sections (basic info,
print specs, features, itemized costs) flow through two columns whose row
height and font size are computed from the amount of ticked content, and a
fixed bottom band holds the totals, the pricing summary, and the signatures.
"""

import os
from dataclasses import dataclass, field

import jdatetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from bookcost.core.pricing import (
    compute_break_even,
    compute_breakdown_pcts,
    compute_cover_price,
    compute_net_revenue_per_copy,
)
from bookcost.reporting.farsi import shape

FONT_NAME = 'FarsiFont'

_NAVY = (0.1, 0.2, 0.4)
_GRAY = (0.4, 0.4, 0.4)
_RED = (0.6, 0.1, 0.1)
_GREEN = (0.1, 0.5, 0.1)


@dataclass
class ReportData:
    """Everything the PDF needs, captured from the UI at generation time."""
    title: str = ''
    basic_info: list = field(default_factory=list)    # [(label, value)]
    tiraj: int = 0
    print_specs: list = field(default_factory=list)   # [(label, value)]
    features: list = field(default_factory=list)      # [(label, value)]
    cost_groups: list = field(default_factory=list)   # [(group, [(label, number)])]
    royalty_pct: float = 0.0
    total_cost: float = 0.0                            # final, royalty applied
    single_cost: float = 0.0
    pricing_multiplier: float = 0.0                    # 0 → pricing section unavailable
    distribution_pct: float = 0.0
    include_basic_info: bool = True
    include_specs: bool = True
    include_features: bool = True
    include_costs: bool = True
    include_pricing: bool = True
    logo_path: str = ''                                # optional; placeholder if missing


def _collect_body_items(data: ReportData):
    """Flattens the ticked sections into a list of drawable items.

    Item kinds: ('header', title) | ('row', key, value, style)
    where style is 'normal' | 'sub' (indented) | 'subtotal'.
    """
    items = []

    if data.include_basic_info:
        items.append(('header', "اطلاعات پایه"))
        for key, val in data.basic_info:
            if val:
                items.append(('row', key, val, 'normal'))
        items.append(('row', "تیراژ", f"{data.tiraj:,}", 'normal'))

    if data.include_specs and data.print_specs:
        items.append(('header', "مشخصات چاپ"))
        for key, val in data.print_specs:
            if val not in (None, ''):
                items.append(('row', key, val, 'normal'))

    if data.include_features:
        feature_rows = [(k, v) for k, v in data.features if v]
        if feature_rows:
            items.append(('header', "ویژگی‌های فنی"))
            for key, val in feature_rows:
                items.append(('row', key, val, 'normal'))

    if data.include_costs:
        subtotal = sum(v for _, grp in data.cost_groups for _, v in grp)
        items.append(('header', "ریز هزینه‌ها (تومان)"))
        for group_name, group_items in data.cost_groups:
            nonzero = [(k, v) for k, v in group_items if v > 0]
            if not nonzero:
                continue
            for key, val in nonzero:
                share = (val / subtotal * 100) if subtotal > 0 else 0
                items.append(('row', key, f"{val:,.0f} ({share:.1f}٪)", 'sub'))
            items.append(('row', f"جمع {group_name}",
                          f"{sum(v for _, v in nonzero):,.0f}", 'subtotal'))
        items.append(('row', "حق تالیف", f"{data.royalty_pct:g} ٪", 'normal'))

    return items


class _SinglePage:
    """One-page renderer: header strip, two-column body, fixed bottom band."""

    def __init__(self, c, data):
        self.c = c
        self.data = data
        self.width, self.height = A4
        self.margin = 1.4 * cm
        self.col_gap = 0.7 * cm
        self.col_w = (self.width - 2 * self.margin - self.col_gap) / 2

    def text(self, txt, x, y, size, align='right', color=(0, 0, 0)):
        self.c.setFont(FONT_NAME, size)
        self.c.setFillColorRGB(*color)
        shaped = shape(str(txt))
        if align == 'right':
            self.c.drawRightString(x, y, shaped)
        elif align == 'center':
            self.c.drawCentredString(x, y, shaped)
        else:
            self.c.drawString(x, y, shaped)

    # ── Header strip ───────────────────────────────────────────────────────

    def draw_header(self):
        c, w, m = self.c, self.width, self.margin
        top = self.height - m
        if self.data.logo_path and os.path.exists(self.data.logo_path):
            c.drawImage(self.data.logo_path, m, top - 1.9 * cm, width=1.9 * cm,
                        height=1.9 * cm, preserveAspectRatio=True)
        self.text("گزارش برآورد هزینه چاپ کتاب", w - m, top - 0.55 * cm, 15, color=_NAVY)
        self.text(self.data.title, w - m, top - 1.25 * cm, 11.5)
        today = jdatetime.date.today().strftime("%Y/%m/%d")
        self.text(f"تاریخ گزارش: {today}", w - m, top - 1.85 * cm, 8, color=_GRAY)
        c.setStrokeColorRGB(*_NAVY)
        c.setLineWidth(1)
        c.line(m, top - 2.15 * cm, w - m, top - 2.15 * cm)
        return top - 2.45 * cm  # body top

    # ── Two-column body ────────────────────────────────────────────────────

    def draw_body(self, items, body_top, body_bottom):
        if not items:
            return
        avail = body_top - body_bottom
        # Headers cost ~1.3 rows (bar + breathing space)
        weight = sum(1.3 if kind == 'header' else 1.0 for kind, *_ in items)
        per_col = weight / 2 + 0.65          # headers never split; allow slack
        row_h = max(0.30 * cm, min(0.62 * cm, avail / max(1.0, per_col)))
        # Ensure even the worst case physically fits both columns
        while row_h * per_col > avail and row_h > 0.22 * cm:
            row_h *= 0.95
        font = max(6.0, min(9.5, row_h / cm * 15.5))

        col = 0  # 0 = right column (RTL reading order), 1 = left
        y = body_top

        def col_edges():
            if col == 0:
                return self.width - self.margin, self.width - self.margin - self.col_w
            return self.margin + self.col_w, self.margin

        for idx, item in enumerate(items):
            kind = item[0]
            need = row_h * (1.3 if kind == 'header' else 1.0)
            # keep a header attached to its first row
            if kind == 'header' and idx + 1 < len(items):
                need += row_h
            if y - need < body_bottom and col == 0:
                col, y = 1, body_top
            right, left = col_edges()

            if kind == 'header':
                y -= row_h * 0.3
                self.c.setFillColorRGB(0.92, 0.94, 0.96)
                self.c.rect(left, y - row_h * 0.78, self.col_w, row_h, fill=1, stroke=0)
                self.text(item[1], right - 0.1 * cm, y - row_h * 0.55, font, color=_NAVY)
                y -= row_h
            else:
                _, key, value, style = item
                y -= row_h
                base_y = y + row_h * 0.25
                if style == 'subtotal':
                    self.text(key, right, base_y, font - 0.5, color=_GRAY)
                    self.text(value, left, base_y, font - 0.5, align='left', color=_GRAY)
                else:
                    indent = 0.25 * cm if style == 'sub' else 0.0
                    self.c.setStrokeColorRGB(0.85, 0.85, 0.85)
                    self.c.setDash(1, 3)
                    self.c.line(left + self.col_w * 0.42, base_y + 1.5,
                                right - self.col_w * 0.45, base_y + 1.5)
                    self.c.setDash()
                    self.text(key, right - indent, base_y, font)
                    self.text(value, left, base_y, font, align='left')

    # ── Bottom band: totals, pricing, signatures ───────────────────────────

    def totals_height(self):
        return 1.45 * cm

    def pricing_height(self):
        if not (self.data.include_pricing and self.data.pricing_multiplier > 0
                and self.data.single_cost > 0):
            return 0
        return 3.25 * cm

    SIG_H = 1.5 * cm

    def _cell(self, label, value, col_i, top_y, value_color, value_size=9.5):
        """Draws a label-over-value cell; col_i 0 is the rightmost of 3 (RTL)."""
        cell_w = (self.width - 2 * self.margin) / 3
        cx = self.width - self.margin - col_i * cell_w
        self.text(label + ":", cx, top_y, 7.5, color=_GRAY)
        self.text(value, cx, top_y - 0.42 * cm, value_size, color=value_color)

    def draw_band(self):
        c, w, m, d = self.c, self.width, self.margin, self.data
        y = self.margin + self.SIG_H + self.pricing_height() + self.totals_height()

        # Totals — three cells under a rule
        c.setStrokeColorRGB(*_NAVY)
        c.setLineWidth(1.4)
        c.line(m, y, w - m, y)
        ty = y - 0.55 * cm
        self._cell("جمع کل هزینه‌ها", f"{d.total_cost:,.0f} تومان", 0, ty, _RED, 11)
        self._cell("هزینه تمام شده هر جلد", f"{d.single_cost:,.0f} تومان", 1, ty, _GREEN, 11)
        if d.royalty_pct > 0 and d.include_costs:
            subtotal = sum(v for _, grp in d.cost_groups for _, v in grp)
            self._cell("جمع پیش از حق تالیف", f"{subtotal:,.0f} تومان", 2, ty, _GRAY, 9.5)

        # Pricing summary — header bar, 2×3 cell grid, breakdown footnote
        if self.pricing_height():
            py = self.margin + self.SIG_H + self.pricing_height()
            c.setFillColorRGB(0.92, 0.94, 0.96)
            c.rect(m, py - 0.55 * cm, w - 2 * m, 0.5 * cm, fill=1, stroke=0)
            self.text("قیمت‌گذاری و سودآوری", w - m - 0.1 * cm, py - 0.42 * cm, 9.5, color=_NAVY)

            cover = compute_cover_price(d.single_cost, d.pricing_multiplier)
            net = compute_net_revenue_per_copy(cover, d.distribution_pct, d.royalty_pct)
            be = compute_break_even(d.total_cost, net)
            bd = compute_breakdown_pcts(cover, d.single_cost, d.distribution_pct, d.royalty_pct)

            if net > 0:
                profit = net * d.tiraj - d.total_cost
                be_txt = f"{be:,} جلد"
                profit_txt = f"{profit:+,.0f} تومان"
                profit_color = _GREEN if profit >= 0 else _RED
            else:
                be_txt = "قابل محاسبه نیست"
                profit_txt = "—"
                profit_color = _RED
            cells = [
                ("ضریب قیمت‌گذاری", f"×{d.pricing_multiplier:g}", (0, 0, 0)),
                ("قیمت پشت جلد پیشنهادی", f"{cover:,.0f} تومان", _NAVY),
                ("سهم توزیع", f"{d.distribution_pct:g} ٪", (0, 0, 0)),
                ("درآمد خالص ناشر (هر جلد)", f"{net:,.0f} تومان", (0, 0, 0)),
                ("نقطه سر به سر", be_txt, (0, 0, 0)),
                (f"سود فروش کامل ({d.tiraj:,} جلد)", profit_txt, profit_color),
            ]
            for i, (label, value, color) in enumerate(cells):
                row_i, col_i = divmod(i, 3)
                self._cell(label, value, col_i, py - 1.05 * cm - row_i * 0.95 * cm, color, 9)
            self.text(
                f"توزیع قیمت پشت جلد:  تولید {bd['production_pct']:g}٪ | "
                f"توزیع {bd['distribution_pct']:g}٪ | حق تالیف {bd['royalty_pct']:g}٪ | "
                f"ناشر {bd['publisher_pct']:g}٪",
                w / 2, py - 3.05 * cm, 7.5, align='center', color=_GRAY)

        # Signatures
        sig_y = self.margin + 0.85 * cm
        c.setLineWidth(0.8)
        c.setStrokeColorRGB(0, 0, 0)
        c.line(w - m - 4.5 * cm, sig_y, w - m, sig_y)
        self.text("مهر و امضای ناشر", w - m - 2.25 * cm, sig_y - 0.55 * cm, 8.5, align='center')
        c.line(m, sig_y, m + 4.5 * cm, sig_y)
        self.text("امضای نویسنده / سفارش‌دهنده", m + 2.25 * cm, sig_y - 0.55 * cm,
                  8.5, align='center')

        return y  # top of the band = bottom limit for the body


def build_pdf_report(file_path: str, font_path: str, data: ReportData):
    """Renders the report to ``file_path`` — always exactly one A4 page."""
    pdfmetrics.registerFont(TTFont(FONT_NAME, font_path))
    c = canvas.Canvas(file_path, pagesize=A4)
    page = _SinglePage(c, data)

    body_top = page.draw_header()
    band_top = page.draw_band()
    page.draw_body(_collect_body_items(data), body_top, band_top + 0.3 * cm)

    c.save()
