"""Final calculation tab: totals plus a cost-breakdown pie chart."""

import matplotlib
matplotlib.use('QtAgg')
matplotlib.rcParams['font.family'] = ['Tahoma', 'Arial', 'DejaVu Sans']
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from PySide6.QtWidgets import QFormLayout, QLabel, QVBoxLayout, QWidget

from bookcost.reporting.farsi import shape


class CalcTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._total_cost = 0.0
        self._cost_per_book = 0.0

        layout = QVBoxLayout(self)

        prices_layout = QFormLayout()
        self.lbl_final_total = QLabel("0")
        self.lbl_single_price = QLabel("0")
        self.lbl_final_total.setObjectName("lbl_final_total")
        self.lbl_single_price.setObjectName("lbl_single_price")
        prices_layout.addRow("قیمت تمام شده کل (تومان):", self.lbl_final_total)
        prices_layout.addRow("قیمت تمام شده یک جلد کتاب (تومان):", self.lbl_single_price)
        layout.addLayout(prices_layout)

        self.figure = Figure(figsize=(6, 6))
        self.canvas = FigureCanvasQTAgg(self.figure)
        layout.addWidget(self.canvas)

    @property
    def total_cost(self) -> float:
        return self._total_cost

    @property
    def cost_per_book(self) -> float:
        return self._cost_per_book

    def total_cost_text(self) -> str:
        return self.lbl_final_total.text()

    def single_cost_text(self) -> str:
        return self.lbl_single_price.text()

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

        labels = [shape(name) for name, val in cost_values.items() if val > 0]
        sizes = [val for val in cost_values.values() if val > 0]

        if not sizes:
            ax.text(0.5, 0.5, "هیچ هزینه‌ای وارد نشده است", ha='center', va='center')
            self.canvas.draw()
            return

        ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140)
        ax.axis('equal')
        self.figure.tight_layout()
        self.canvas.draw()
