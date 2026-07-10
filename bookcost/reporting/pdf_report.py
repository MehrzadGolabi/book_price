"""PDF cost report generation, decoupled from the Qt UI.

The UI assembles a :class:`ReportData` snapshot and calls :func:`build_pdf_report`;
nothing here imports Qt, so the layout can be tested headlessly.

Sections (each toggleable): basic info, print specifications, technical
features, itemized costs grouped with subtotals and share-of-total, totals,
pricing & profitability, signature blocks. Every page gets a numbered footer.
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


class _Page:
    """Canvas wrapper: numbered footers, page breaks, common row primitives."""

    def __init__(self, c, width, height, margin, doc_title):
        self.c = c
        self.width = width
        self.height = height
        self.margin = margin
        self.doc_title = doc_title
        self.page_no = 1
        self.y = height - margin

    def text(self, txt, x, y, size=11, align='right', color=(0, 0, 0)):
        self.c.setFont(FONT_NAME, size)
        self.c.setFillColorRGB(*color)
        shaped = shape(str(txt))
        if align == 'right':
            self.c.drawRightString(x, y, shaped)
        elif align == 'center':
            self.c.drawCentredString(x, y, shaped)
        else:
            self.c.drawString(x, y, shaped)

    def _footer(self):
        self.c.setStrokeColorRGB(0.75, 0.75, 0.75)
        self.c.setLineWidth(0.5)
        self.c.line(self.margin, self.margin - 0.4 * cm,
                    self.width - self.margin, self.margin - 0.4 * cm)
        self.text(f"صفحه {self.page_no}", self.width / 2, self.margin - 0.9 * cm,
                  size=9, align='center', color=_GRAY)
        if self.doc_title:
            self.text(self.doc_title, self.width - self.margin, self.margin - 0.9 * cm,
                      size=9, color=_GRAY)

    def new_page(self):
        self._footer()
        self.c.showPage()
        self.page_no += 1
        self.y = self.height - self.margin

    def need(self, space):
        """Breaks the page unless `space` fits above the footer area."""
        if self.y < self.margin + 0.5 * cm + space:
            self.new_page()

    def finish(self):
        self._footer()
        self.c.save()

    # ── Row primitives ─────────────────────────────────────────────────────

    def section_header(self, title):
        self.need(3 * cm)
        self.c.setFillColorRGB(0.92, 0.94, 0.96)
        self.c.rect(self.margin, self.y - 0.3 * cm,
                    self.width - 2 * self.margin, 0.8 * cm, fill=1, stroke=0)
        self.text(title, self.width - self.margin - 0.2 * cm, self.y, size=12, color=_NAVY)
        self.y -= 1 * cm

    def row(self, key, value, size=11, key_color=(0, 0, 0), value_color=(0, 0, 0),
            leader=True, indent=0.0):
        self.need(1 * cm)
        if leader:
            self.c.setStrokeColorRGB(0.8, 0.8, 0.8)
            self.c.setDash(1, 4)
            self.c.line(self.margin + 4 * cm, self.y + 0.1 * cm,
                        self.width - self.margin - 4 * cm, self.y + 0.1 * cm)
            self.c.setDash()
        self.text(key, self.width - self.margin - indent, self.y, size=size, color=key_color)
        self.text(str(value), self.margin, self.y, size=size, align='left', color=value_color)
        self.y -= 0.8 * cm


def build_pdf_report(file_path: str, font_path: str, data: ReportData):
    """Renders the report to ``file_path``. Raises on I/O or font errors."""
    pdfmetrics.registerFont(TTFont(FONT_NAME, font_path))
    c = canvas.Canvas(file_path, pagesize=A4)
    width, height = A4
    margin = 2 * cm
    p = _Page(c, width, height, margin, data.title)

    # ── Header: logo, title, date ────────────────────────────────────────
    if data.logo_path and os.path.exists(data.logo_path):
        c.drawImage(data.logo_path, margin, p.y - 2 * cm, width=3 * cm, height=3 * cm,
                    preserveAspectRatio=True)
    else:
        c.setDash(3, 3)
        c.setStrokeColorRGB(0.5, 0.5, 0.5)
        c.rect(margin, p.y - 2 * cm, 3 * cm, 2.5 * cm)
        p.text("محل لوگوی ناشر", margin + 1.5 * cm, p.y - 0.9 * cm,
               size=10, align='center', color=(0.5, 0.5, 0.5))
        c.setDash()

    p.text("گزارش برآورد هزینه چاپ کتاب", width - margin, p.y - 0.5 * cm, size=18, color=_NAVY)
    p.text(data.title, width - margin, p.y - 1.5 * cm, size=14)
    today = jdatetime.date.today().strftime("%Y/%m/%d")
    p.text(f"تاریخ گزارش: {today}", width - margin, p.y - 2.3 * cm, size=10, color=_GRAY)
    p.y -= 3.5 * cm

    # ── Basic info ────────────────────────────────────────────────────────
    if data.include_basic_info:
        p.section_header("اطلاعات پایه")
        for key, val in data.basic_info:
            if val:
                p.row(key, val)
        p.row("تیراژ", f"{data.tiraj:,}")
        p.y -= 0.5 * cm

    # ── Print specifications ──────────────────────────────────────────────
    if data.include_specs and data.print_specs:
        p.section_header("مشخصات چاپ")
        for key, val in data.print_specs:
            if val not in (None, ''):
                p.row(key, val)
        p.y -= 0.5 * cm

    # ── Technical features ────────────────────────────────────────────────
    if data.include_features:
        p.section_header("ویژگی‌های فنی")
        for key, val in data.features:
            if val:
                p.row(key, val)
        p.y -= 0.5 * cm

    # ── Itemized costs, grouped, with subtotals and share of total ───────
    subtotal = sum(v for _, items in data.cost_groups for _, v in items)
    if data.include_costs:
        p.section_header("ریز هزینه‌ها (تومان)")
        for group_name, items in data.cost_groups:
            nonzero = [(k, v) for k, v in items if v > 0]
            if not nonzero:
                continue
            group_sum = sum(v for _, v in nonzero)
            p.need(2 * cm)
            p.row(group_name, "", size=11, key_color=_NAVY, leader=False)
            for key, val in nonzero:
                share = (val / subtotal * 100) if subtotal > 0 else 0
                p.row(key, f"{val:,.0f}   ({share:.1f}٪)", indent=0.5 * cm)
            p.row(f"جمع {group_name}", f"{group_sum:,.0f}",
                  key_color=_GRAY, value_color=_GRAY, leader=False)
        p.row("حق تالیف", f"{data.royalty_pct:g} ٪")
        p.y -= 0.5 * cm

    # ── Totals ────────────────────────────────────────────────────────────
    p.need(4 * cm)
    c.setStrokeColorRGB(*_NAVY)
    c.setLineWidth(2)
    c.line(margin, p.y, width - margin, p.y)
    p.y -= 1 * cm

    if subtotal > 0 and data.royalty_pct > 0:
        p.row("جمع هزینه‌ها (پیش از حق تالیف)", f"{subtotal:,.0f} تومان", size=12)
    p.row("جمع کل هزینه‌ها", f"{data.total_cost:,.0f} تومان",
          size=14, key_color=_RED, value_color=_RED, leader=False)
    p.row("هزینه تمام شده هر جلد", f"{data.single_cost:,.0f} تومان",
          size=14, key_color=_GREEN, value_color=_GREEN, leader=False)

    # ── Pricing & profitability ───────────────────────────────────────────
    if data.include_pricing and data.pricing_multiplier > 0 and data.single_cost > 0:
        p.y -= 0.5 * cm
        p.section_header("قیمت‌گذاری و سودآوری")

        cover = compute_cover_price(data.single_cost, data.pricing_multiplier)
        net = compute_net_revenue_per_copy(cover, data.distribution_pct, data.royalty_pct)
        be = compute_break_even(data.total_cost, net)
        bd = compute_breakdown_pcts(cover, data.single_cost,
                                    data.distribution_pct, data.royalty_pct)

        p.row("ضریب قیمت‌گذاری", f"×{data.pricing_multiplier:g}")
        p.row("قیمت پشت جلد پیشنهادی", f"{cover:,.0f} تومان",
              size=13, key_color=_NAVY, value_color=_NAVY)
        p.row("سهم کتابفروشی / توزیع", f"{data.distribution_pct:g} ٪")
        p.row("درآمد خالص ناشر (هر جلد)", f"{net:,.0f} تومان")
        p.row("توزیع قیمت پشت جلد",
              f"تولید {bd['production_pct']:g}٪ | توزیع {bd['distribution_pct']:g}٪ | "
              f"حق تالیف {bd['royalty_pct']:g}٪ | ناشر {bd['publisher_pct']:g}٪",
              size=10, leader=False)
        if net > 0:
            p.row("نقطه سر به سر", f"{be:,} جلد")
            profit = net * data.tiraj - data.total_cost
            color = _GREEN if profit >= 0 else _RED
            p.row(f"سود تخمینی فروش کامل تیراژ ({data.tiraj:,} جلد)",
                  f"{profit:+,.0f} تومان", key_color=color, value_color=color)
        else:
            p.row("نقطه سر به سر", "قابل محاسبه نیست — درآمد خالص صفر یا منفی است",
                  key_color=_RED, value_color=_RED)

    # ── Signature blocks — pinned to the bottom of the last page ─────────
    sig_y = margin + 1.6 * cm
    if p.y < sig_y + 0.5 * cm:
        p.new_page()
    c.setLineWidth(1)
    c.setStrokeColorRGB(0, 0, 0)
    c.line(width - margin - 5 * cm, sig_y, width - margin, sig_y)
    p.text("مهر و امضای ناشر", width - margin - 2.5 * cm, sig_y - 0.7 * cm,
           size=11, align='center')
    c.line(margin, sig_y, margin + 5 * cm, sig_y)
    p.text("امضای نویسنده / سفارش‌دهنده", margin + 2.5 * cm, sig_y - 0.7 * cm,
           size=11, align='center')

    p.finish()
