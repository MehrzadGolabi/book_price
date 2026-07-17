"""Pricing & profitability tab: cover price, breakdown bar, break-even, scenarios."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
    QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from bookcost.core.pricing import (
    compute_break_even,
    compute_breakdown_pcts,
    compute_cover_price,
    compute_net_revenue_per_copy,
    compute_scenarios,
)

_LABELS_FA = {
    "production": "تولید", "distribution": "توزیع",
    "royalty": "حق تالیف", "publisher": "سود ناشر",
}


class PricingTab(QWidget):
    inputs_changed = Signal()  # multiplier or distribution edited; coordinator re-refreshes

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.pricing_multiplier_spin.valueChanged.connect(self.inputs_changed.emit)
        self.distribution_spin.valueChanged.connect(self.inputs_changed.emit)

    def _build_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content.setLayoutDirection(Qt.RightToLeft)
        main_vbox = QVBoxLayout(content)
        main_vbox.setSpacing(12)

        # ── Part A: Suggested cover price ────────────────────────────────
        grp_a = QGroupBox("قیمت‌گذاری پیشنهادی")
        grp_a_form = QFormLayout(grp_a)

        self.pricing_multiplier_spin = QDoubleSpinBox()
        self.pricing_multiplier_spin.setRange(1.0, 5.0)
        self.pricing_multiplier_spin.setSingleStep(0.1)
        self.pricing_multiplier_spin.setDecimals(1)
        self.pricing_multiplier_spin.setValue(2.5)
        grp_a_form.addRow("ضریب قیمت‌گذاری:", self.pricing_multiplier_spin)

        self.lbl_cover_price = QLabel("—")
        self.lbl_cover_price.setAlignment(Qt.AlignCenter)
        self.lbl_cover_price.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: #15803d;"
            "background-color: #f0fdf4; border: 1px solid #bbf7d0;"
            "padding: 10px; border-radius: 6px;"
        )
        grp_a_form.addRow("قیمت پشت جلد پیشنهادی:", self.lbl_cover_price)

        breakdown_container = QWidget()
        self.breakdown_layout = QHBoxLayout(breakdown_container)
        self.breakdown_layout.setContentsMargins(0, 0, 0, 0)
        self.breakdown_layout.setSpacing(2)
        self._breakdown_frames = {}
        # Dark enough for 4.5:1 white-on-color contrast
        colors = {
            "production":   "#1d4ed8",
            "distribution": "#b45309",
            "royalty":      "#7e22ce",
            "publisher":    "#15803d",
        }
        for key, color in colors.items():
            frame = QLabel(_LABELS_FA[key])
            frame.setAlignment(Qt.AlignCenter)
            frame.setStyleSheet(
                f"background-color: {color}; color: white; font-size: 10px;"
                "border-radius: 3px; padding: 4px;"
            )
            frame.setMinimumHeight(32)
            self.breakdown_layout.addWidget(frame, 1)
            self._breakdown_frames[key] = frame
        grp_a_form.addRow("توزیع قیمت پشت جلد:", breakdown_container)

        self.distribution_spin = QDoubleSpinBox()
        self.distribution_spin.setRange(0, 70)
        self.distribution_spin.setSingleStep(1)
        self.distribution_spin.setDecimals(0)
        self.distribution_spin.setValue(35.0)
        self.distribution_spin.setSuffix(" ٪")
        grp_a_form.addRow("سهم کتابفروشی / توزیع:", self.distribution_spin)

        main_vbox.addWidget(grp_a)

        # ── Part B: Break-even ───────────────────────────────────────────
        grp_b = QGroupBox("نقطه سر به سر")
        grp_b_form = QFormLayout(grp_b)

        self.lbl_total_project_cost = QLabel("—")
        grp_b_form.addRow("هزینه کل پروژه:", self.lbl_total_project_cost)

        self.lbl_net_per_copy = QLabel("—")
        grp_b_form.addRow("درآمد خالص ناشر (هر جلد):", self.lbl_net_per_copy)

        self.lbl_break_even = QLabel("—")
        self.lbl_break_even.setStyleSheet("font-weight: bold; font-size: 14px;")
        grp_b_form.addRow("نقطه سر به سر:", self.lbl_break_even)

        self.lbl_profit_status = QLabel("—")
        self.lbl_profit_status.setWordWrap(True)
        grp_b_form.addRow("وضعیت تیراژ فعلی:", self.lbl_profit_status)

        main_vbox.addWidget(grp_b)

        # ── Part C: Scenario table ───────────────────────────────────────
        grp_c = QGroupBox("جدول سناریوها (سود ناخالص — پیش از کسر تخفیف‌ها)")
        grp_c_vbox = QVBoxLayout(grp_c)

        self.scenario_table = QTableWidget(4, 3)
        self.scenario_table.setHorizontalHeaderLabels(["×۲.۵", "×۳.۰", "×۳.۵"])
        self.scenario_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.scenario_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.scenario_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        grp_c_vbox.addWidget(self.scenario_table)

        main_vbox.addWidget(grp_c)
        main_vbox.addStretch()

        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # ── State API ─────────────────────────────────────────────────────────

    def multiplier(self) -> float:
        return self.pricing_multiplier_spin.value()

    def distribution_pct(self) -> float:
        return self.distribution_spin.value()

    def set_values(self, multiplier: float = None, distribution_pct: float = None):
        if multiplier is not None:
            self.pricing_multiplier_spin.setValue(multiplier)
        if distribution_pct is not None:
            self.distribution_spin.setValue(distribution_pct)

    def reset(self):
        self.set_values(2.5, 35.0)

    # ── Rendering ─────────────────────────────────────────────────────────

    def refresh(self, total_cost: float, single_cost: float, tiraj: int, royalty_pct: float):
        """Recomputes and rerenders all pricing widgets from current project totals."""
        if total_cost <= 0 or single_cost <= 0 or tiraj <= 0:
            return

        multiplier = self.multiplier()
        dist_pct = self.distribution_pct()

        cover_price = compute_cover_price(single_cost, multiplier)
        net_per_copy = compute_net_revenue_per_copy(cover_price, dist_pct, royalty_pct)
        break_even = compute_break_even(total_cost, net_per_copy)
        bd = compute_breakdown_pcts(cover_price, single_cost, dist_pct, royalty_pct)

        # Part A — cover price label and breakdown bar
        self.lbl_cover_price.setText(f"{cover_price:,.0f} تومان")
        for key, frame in self._breakdown_frames.items():
            pct = bd[f'{key}_pct']
            amount = bd[key]
            frame.setText(f"{_LABELS_FA[key]}\n{pct:.1f}%")
            frame.setToolTip(f"{amount:,.0f} تومان")
            self.breakdown_layout.setStretchFactor(frame, max(1, int(pct)))

        # Part B — break-even analysis
        self.lbl_total_project_cost.setText(f"{total_cost:,.0f} تومان")
        self.lbl_net_per_copy.setText(f"{net_per_copy:,.0f} تومان")
        if break_even > 0:
            self.lbl_break_even.setText(f"{break_even:,} جلد")
            if tiraj >= break_even:
                profit = net_per_copy * tiraj - total_cost
                self.lbl_profit_status.setText(
                    f"✓ تیراژ {tiraj:,} جلد از نقطه سر به سر ({break_even:,}) عبور کرده | "
                    f"سود ناخالص تخمینی فروش کامل: {profit:,.0f} تومان"
                )
                self.lbl_profit_status.setStyleSheet("color: #15803d; font-weight: bold;")
            else:
                shortage = break_even - tiraj
                self.lbl_profit_status.setText(
                    f"✗ تیراژ {tiraj:,} جلد کمتر از نقطه سر به سر است | "
                    f"برای رسیدن به سر به سر {shortage:,} جلد بیشتر نیاز است"
                )
                self.lbl_profit_status.setStyleSheet("color: #b91c1c; font-weight: bold;")
        else:
            self.lbl_break_even.setText("قابل محاسبه نیست")
            self.lbl_profit_status.setText("درآمد خالص ناشر صفر یا منفی است")
            self.lbl_profit_status.setStyleSheet("color: #b91c1c;")

        # Part C — scenario table
        fixed_multipliers = [2.5, 3.0, 3.5]
        sales_pcts = [0.25, 0.5, 0.75, 1.0]
        rows_data = compute_scenarios(total_cost, single_cost, tiraj,
                                      dist_pct, royalty_pct, fixed_multipliers)
        row_labels = [f"{max(1, int(tiraj * p)):,} جلد ({int(p * 100)}٪)" for p in sales_pcts]
        self.scenario_table.setVerticalHeaderLabels(row_labels)

        for row_idx, pct in enumerate(sales_pcts):
            for col_idx, mult in enumerate(fixed_multipliers):
                sales_qty = max(1, int(tiraj * pct))
                entry = next((r for r in rows_data
                              if r['multiplier'] == mult and r['sales_qty'] == sales_qty), None)
                if entry is None:
                    continue
                profit = entry['net_profit']
                item = QTableWidgetItem(f"{profit:+,.0f} تومان")
                item.setTextAlignment(Qt.AlignCenter)
                if profit > 0:
                    item.setForeground(QColor('#15803d'))
                elif profit < -0.10 * total_cost:
                    item.setForeground(QColor('#b91c1c'))
                else:
                    item.setForeground(QColor('#b45309'))
                if abs(mult - multiplier) < 0.01 and pct == 1.0:
                    item.setBackground(QColor('#dbeafe'))
                self.scenario_table.setItem(row_idx, col_idx, item)
