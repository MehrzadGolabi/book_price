"""Final calculation tab: totals plus a cost-breakdown pie chart."""

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from bookcost.resources import resource_path

# matplotlib >= 3.11 applies bidi reordering and Arabic joining itself, so
# chart text must be RAW Persian — running it through arabic_reshaper/bidi
# (reporting.farsi.shape, which reportlab DOES need) double-processes it into
# reversed, disconnected glyphs. The bundled Tahoma is passed by file path so
# rendering never depends on system font resolution.
_FARSI_FONT = FontProperties(fname=resource_path('tahoma.ttf'))
_FARSI_FONT_SMALL = _FARSI_FONT.copy()
_FARSI_FONT_SMALL.set_size(9)

# Slices smaller than this share of the total are folded into a single «سایر
# هزینه‌ها» wedge — with the unified cost model a project can have 15-30+
# non-zero cost lines (built-ins, subfields, custom fields), and on-wedge
# labels for that many thin slices always collide. A legend lists every slice
# by name instead, so no label ever overlaps another.
_MIN_SLICE_SHARE = 0.02


class CalcTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._total_cost = 0.0
        self._cost_per_book = 0.0

        layout = QVBoxLayout(self)

        def make_card(caption: str, value_object_name: str):
            card = QFrame()
            card.setObjectName("total_card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(20, 14, 20, 14)
            cap = QLabel(caption)
            cap.setStyleSheet("color: #475569; font-size: 13px;")
            cap.setAlignment(Qt.AlignCenter)
            value = QLabel("0")
            value.setObjectName(value_object_name)
            value.setAlignment(Qt.AlignCenter)
            card_layout.addWidget(cap)
            card_layout.addWidget(value)
            return card, value

        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)
        total_card, self.lbl_final_total = make_card(
            "قیمت تمام شده کل (تومان)", "lbl_final_total")
        single_card, self.lbl_single_price = make_card(
            "قیمت تمام شده یک جلد کتاب (تومان)", "lbl_single_price")
        cards_row.addWidget(total_card, 1)
        cards_row.addWidget(single_card, 1)
        layout.addLayout(cards_row)

        self.figure = Figure(figsize=(6, 6))
        self.canvas = FigureCanvasQTAgg(self.figure)
        layout.addWidget(self.canvas, 1)

    @property
    def total_cost(self) -> float:
        return self._total_cost

    @property
    def cost_per_book(self) -> float:
        return self._cost_per_book

    def set_totals(self, total_cost: float, cost_per_book: float):
        self._total_cost = total_cost
        self._cost_per_book = cost_per_book
        self.lbl_final_total.setText(f"{total_cost:,.0f}")
        self.lbl_single_price.setText(f"{cost_per_book:,.0f}")

    def reset(self):
        self.set_totals(0.0, 0.0)

    def update_chart(self, cost_values: dict):
        """Redraws the pie chart from {persian field name: value}.

        Labels live in a side legend rather than on the wedges — with many
        thin slices, on-wedge labels inevitably collide. Slices under
        ``_MIN_SLICE_SHARE`` of the total are grouped into «سایر هزینه‌ها» so
        the legend stays short and each remaining wedge is legible.
        """
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        items = sorted(((name, val) for name, val in cost_values.items() if val > 0),
                       key=lambda kv: kv[1], reverse=True)

        if not items:
            ax.text(0.5, 0.5, "هیچ هزینه‌ای وارد نشده است", ha='center', va='center',
                    fontproperties=_FARSI_FONT)
            self.canvas.draw()
            return

        total = sum(val for _, val in items)
        major = [(n, v) for n, v in items if v / total >= _MIN_SLICE_SHARE]
        minor = [(n, v) for n, v in items if v / total < _MIN_SLICE_SHARE]
        if len(minor) == 1:
            major.append(minor[0])
        elif len(minor) > 1:
            major.append(("سایر هزینه‌ها", sum(v for _, v in minor)))

        labels = [n for n, _ in major]
        sizes = [v for _, v in major]

        def autopct(pct):
            return f"{pct:.1f}%" if pct >= 4 else ""

        wedges, _labels, _pct_texts = ax.pie(
            sizes, labels=None, autopct=autopct, pctdistance=0.75, startangle=140,
            textprops={'fontproperties': _FARSI_FONT_SMALL, 'color': 'white'},
        )
        ax.axis('equal')

        legend_labels = [f"{n}  —  {v / total * 100:.1f}%" for n, v in major]
        ax.legend(wedges, legend_labels, loc='center left', bbox_to_anchor=(1.0, 0.5),
                  prop=_FARSI_FONT_SMALL, frameon=False)

        self.figure.tight_layout()
        self.canvas.draw()
