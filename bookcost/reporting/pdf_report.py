"""PDF cost report generation, decoupled from the Qt UI.

The UI assembles a :class:`ReportData` snapshot and calls :func:`build_pdf_report`;
nothing here imports Qt, so the layout can be tested headlessly.
"""

from dataclasses import dataclass, field

import jdatetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from bookcost.reporting.farsi import shape

FONT_NAME = 'FarsiFont'


@dataclass
class ReportData:
    """Everything the PDF needs, captured from the UI at generation time."""
    title: str = ''
    basic_info: list = field(default_factory=list)      # [(label, value)] — title, date, qate…
    tiraj: int = 0
    features: list = field(default_factory=list)        # [(label, value)] — paper/print/color types
    costs: list = field(default_factory=list)           # [(label, numeric value)]
    royalty_pct: float = 0.0
    total_cost_text: str = '0'
    single_cost_text: str = '0'
    include_basic_info: bool = True
    include_features: bool = True
    include_costs: bool = True
    logo_path: str = ''                                  # optional; placeholder drawn if missing/empty


def _write_farsi(c, text, x, y, font_size=12, align='right', color=(0, 0, 0)):
    c.setFont(FONT_NAME, font_size)
    c.setFillColorRGB(*color)
    bidi_text = shape(str(text))
    if align == 'right':
        c.drawRightString(x, y, bidi_text)
    elif align == 'center':
        c.drawCentredString(x, y, bidi_text)
    else:
        c.drawString(x, y, bidi_text)


def build_pdf_report(file_path: str, font_path: str, data: ReportData):
    """Renders the report to ``file_path``. Raises on I/O or font errors."""
    import os

    pdfmetrics.registerFont(TTFont(FONT_NAME, font_path))
    c = canvas.Canvas(file_path, pagesize=A4)
    width, height = A4
    margin = 2 * cm
    y = height - margin

    def check_page_break(current_y, needed_space=2 * cm):
        if current_y < margin + needed_space:
            c.showPage()
            return height - margin
        return current_y

    # ── Header: logo, title, date ────────────────────────────────────────
    if data.logo_path and os.path.exists(data.logo_path):
        c.drawImage(data.logo_path, margin, y - 2 * cm, width=3 * cm, height=3 * cm,
                    preserveAspectRatio=True)
    else:
        c.setDash(3, 3)
        c.setStrokeColorRGB(0.5, 0.5, 0.5)
        c.rect(margin, y - 2 * cm, 3 * cm, 2.5 * cm)
        _write_farsi(c, "محل لوگوی ناشر", margin + 1.5 * cm, y - 0.9 * cm,
                     font_size=10, align='center', color=(0.5, 0.5, 0.5))
        c.setDash()

    _write_farsi(c, "گزارش برآورد هزینه چاپ کتاب", width - margin, y - 0.5 * cm,
                 font_size=18, color=(0.1, 0.2, 0.4))
    _write_farsi(c, data.title, width - margin, y - 1.5 * cm, font_size=14)

    today = jdatetime.date.today().strftime("%Y/%m/%d")
    _write_farsi(c, f"تاریخ گزارش: {today}", width - margin, y - 2.3 * cm,
                 font_size=10, color=(0.4, 0.4, 0.4))

    y -= 3.5 * cm

    def draw_section_header(title, current_y):
        current_y = check_page_break(current_y, 3 * cm)
        c.setFillColorRGB(0.92, 0.94, 0.96)
        c.rect(margin, current_y - 0.3 * cm, width - 2 * margin, 0.8 * cm, fill=1, stroke=0)
        _write_farsi(c, title, width - margin - 0.2 * cm, current_y,
                     font_size=12, color=(0.1, 0.2, 0.4))
        return current_y - 1 * cm

    def draw_row(key, value, current_y):
        current_y = check_page_break(current_y, 1 * cm)
        c.setStrokeColorRGB(0.8, 0.8, 0.8)
        c.setDash(1, 4)
        c.line(margin + 4 * cm, current_y + 0.1 * cm,
               width - margin - 4 * cm, current_y + 0.1 * cm)
        c.setDash()
        _write_farsi(c, key, width - margin, current_y, font_size=11)
        _write_farsi(c, str(value), margin, current_y, font_size=11, align='left')
        return current_y - 0.8 * cm

    # ── Sections ─────────────────────────────────────────────────────────
    if data.include_basic_info:
        y = draw_section_header("اطلاعات پایه", y)
        for key, val in data.basic_info:
            if val:
                y = draw_row(key, val, y)
        y = draw_row("تیراژ", str(data.tiraj), y)
        y -= 0.5 * cm

    if data.include_features:
        y = draw_section_header("ویژگی‌های فنی", y)
        for key, val in data.features:
            if val:
                y = draw_row(key, val, y)
        y -= 0.5 * cm

    if data.include_costs:
        y = draw_section_header("ریز هزینه‌ها (تومان)", y)
        for key, val in data.costs:
            if val > 0:
                y = draw_row(key, f"{val:,.0f}", y)
        y = draw_row("حق تالیف", f"{data.royalty_pct:g} %", y)
        y -= 0.5 * cm

    # ── Totals ───────────────────────────────────────────────────────────
    y = check_page_break(y, 4 * cm)
    c.setStrokeColorRGB(0.1, 0.2, 0.4)
    c.setLineWidth(2)
    c.line(margin, y, width - margin, y)
    y -= 1 * cm

    _write_farsi(c, "جمع کل هزینه‌ها:", width - margin, y, font_size=14, color=(0.6, 0.1, 0.1))
    _write_farsi(c, f"{data.total_cost_text} تومان", margin, y,
                 font_size=14, align='left', color=(0.6, 0.1, 0.1))
    y -= 1 * cm

    _write_farsi(c, "هزینه تمام شده هر جلد:", width - margin, y,
                 font_size=14, color=(0.1, 0.5, 0.1))
    _write_farsi(c, f"{data.single_cost_text} تومان", margin, y,
                 font_size=14, align='left', color=(0.1, 0.5, 0.1))

    # ── Signature blocks ─────────────────────────────────────────────────
    y -= 2 * cm
    y = check_page_break(y, 4 * cm)

    c.setLineWidth(1)
    c.setStrokeColorRGB(0, 0, 0)
    c.line(width - margin - 5 * cm, y, width - margin, y)
    _write_farsi(c, "مهر و امضای ناشر", width - margin - 2.5 * cm, y - 0.7 * cm,
                 font_size=11, align='center')
    c.line(margin, y, margin + 5 * cm, y)
    _write_farsi(c, "امضای نویسنده / سفارش‌دهنده", margin + 2.5 * cm, y - 0.7 * cm,
                 font_size=11, align='center')

    c.save()
