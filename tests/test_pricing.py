import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import math

from pricing import (
    compute_cover_price,
    compute_net_revenue_per_copy,
    compute_break_even,
    compute_breakdown_pcts,
    compute_scenarios,
)


def test_cover_price():
    assert compute_cover_price(10_000, 2.5) == 25_000.0


def test_cover_price_zero_multiplier():
    assert compute_cover_price(10_000, 0) == 0.0


def test_net_revenue_per_copy():
    # cover=25000, dist=35%, royalty=10% → net = 25000 * 0.55 = 13750
    assert compute_net_revenue_per_copy(25_000, 35.0, 10.0) == 13_750.0


def test_break_even():
    # total_cost=1_000_000, net_per_copy=13_750 → ceil(72.7) = 73
    assert compute_break_even(1_000_000, 13_750) == 73


def test_break_even_zero_net():
    assert compute_break_even(1_000_000, 0) == 0


def test_compute_breakdown_pcts():
    bd = compute_breakdown_pcts(
        cover_price=25_000,
        cost_per_book=10_000,
        distribution_pct=35.0,
        author_royalty_pct=10.0,
    )
    assert bd['production_pct'] == 40.0
    assert bd['distribution_pct'] == 35.0
    assert bd['royalty_pct'] == 10.0
    assert bd['publisher_pct'] == 15.0
    assert abs(bd['production'] - 10_000) < 0.01
    assert abs(bd['distribution'] - 8_750) < 0.01
    assert abs(bd['royalty'] - 2_500) < 0.01
    assert abs(bd['publisher'] - 3_750) < 0.01


def test_compute_scenarios_shape():
    rows = compute_scenarios(
        total_cost=1_000_000,
        cost_per_book=10_000,
        tiraj=1000,
        distribution_pct=35.0,
        author_royalty_pct=10.0,
        multipliers=[2.5, 3.0, 3.5],
    )
    # 4 sales levels × 3 multipliers = 12 rows
    assert len(rows) == 12
    assert all('multiplier' in r and 'sales_qty' in r and 'net_profit' in r for r in rows)


def test_compute_scenarios_profit_signs():
    rows = compute_scenarios(
        total_cost=10_000_000,
        cost_per_book=10_000,
        tiraj=1000,
        distribution_pct=35.0,
        author_royalty_pct=10.0,
        multipliers=[2.5],
    )
    # 25% sales (250 copies) should be a loss
    row_25 = next(r for r in rows if r['sales_qty'] == 250)
    assert row_25['net_profit'] < 0
    # 100% sales (1000 copies) should be a profit
    row_100 = next(r for r in rows if r['sales_qty'] == 1000)
    assert row_100['net_profit'] > 0


def test_compute_breakdown_pcts_zero_cover():
    bd = compute_breakdown_pcts(0, 10_000, 35.0, 10.0)
    assert all(v == 0.0 for v in bd.values())
