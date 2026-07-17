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
        """Redraws the pie chart from {persian field name: value}."""
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        labels = [name for name, val in cost_values.items() if val > 0]
        sizes = [val for val in cost_values.values() if val > 0]

        if not sizes:
            ax.text(0.5, 0.5, "هیچ هزینه‌ای وارد نشده است", ha='center', va='center',
                    fontproperties=_FARSI_FONT)
            self.canvas.draw()
            return

        ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140,
               textprops={'fontproperties': _FARSI_FONT})
        ax.axis('equal')
        self.figure.tight_layout()
        self.canvas.draw()
