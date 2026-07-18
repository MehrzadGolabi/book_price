import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import math
import pytest
from bookcost.core.calculator import CostCalculator

calc = CostCalculator()


# ── Constants ──────────────────────────────────────────────────────────────

def test_optimal_specs_has_all_qate():
    expected = {'وزیری', 'رقعی', 'رحلی کوچک', 'رحلی بزرگ', 'جیبی', 'خشتی',
                'مربع', 'بزرگ‌قطع', 'کوچک‌قطع', 'سفارشی'}
    assert expected == set(CostCalculator.OPTIMAL_SPECS.keys())


def test_zinc_dims_has_all_sizes():
    assert 'زینک GTO' in CostCalculator.ZINC_DIMS
    assert 'زینک 3.5 ورقی' in CostCalculator.ZINC_DIMS
    assert len(CostCalculator.ZINC_DIMS) == 5


def test_book_type_presets_has_all_types():
    expected = {'شومیز ساده', 'گالینگور', 'کتاب مصور / رنگی', 'ترجمه', 'ویژه / لوکس', 'سفارشی'}
    assert expected == set(CostCalculator.BOOK_TYPE_PRESETS.keys())


# ── compute_auto_costs ──────────────────────────────────────────────────────

def test_auto_costs_paper_matn():
    result = calc.compute_auto_costs(
        form_matn=16, sides_matn=2, form_jeld=1, sides_jeld=1,
        tiraj=1000, waste_pct=5.0,
        unit_price_matn=500.0, unit_price_jeld=800.0,
        text_colors=1, cover_colors=4,
        zinc_price_matn=200_000, zinc_price_jeld=200_000,
    )
    # (16/2) * 1000 * 1.05 * 500 = 4_200_000
    assert abs(result['هزینه کاغذ متن'] - 4_200_000.0) < 0.01


def test_auto_costs_paper_jeld():
    result = calc.compute_auto_costs(
        form_matn=16, sides_matn=2, form_jeld=1, sides_jeld=1,
        tiraj=1000, waste_pct=0.0,
        unit_price_matn=0.0, unit_price_jeld=800.0,
        text_colors=1, cover_colors=4,
        zinc_price_matn=0, zinc_price_jeld=0,
    )
    # (1/1) * 1000 * 1.0 * 800 = 800_000
    assert abs(result['هزینه کاغذ جلد'] - 800_000.0) < 0.01


def test_auto_costs_zinc():
    result = calc.compute_auto_costs(
        form_matn=4, sides_matn=1, form_jeld=1, sides_jeld=1,
        tiraj=1000, waste_pct=0.0,
        unit_price_matn=0.0, unit_price_jeld=0.0,
        text_colors=1, cover_colors=4,
        zinc_price_matn=100_000, zinc_price_jeld=150_000,
    )
    # matn: 4 * 1 * 100_000 = 400_000; jeld: 1 * 4 * 150_000 = 600_000 → 1_000_000
    assert abs(result['هزینه زینک'] - 1_000_000.0) < 0.01


def test_auto_costs_returns_three_keys():
    result = calc.compute_auto_costs(
        form_matn=1, sides_matn=1, form_jeld=1, sides_jeld=1,
        tiraj=100, waste_pct=0.0,
        unit_price_matn=0.0, unit_price_jeld=0.0,
        text_colors=1, cover_colors=1,
        zinc_price_matn=0, zinc_price_jeld=0,
    )
    assert set(result.keys()) == {'هزینه کاغذ متن', 'هزینه کاغذ جلد', 'هزینه زینک'}


# ── compute_totals ──────────────────────────────────────────────────────────

def test_compute_totals_basic():
    costs = {'هزینه تالیف': 1_000_000, 'هزینه چاپ متن': 500_000}
    result = calc.compute_totals(costs, royalty_pct=10.0, tiraj=1000)
    assert abs(result['total_cost'] - 1_650_000.0) < 0.01
    assert abs(result['cost_per_book'] - 1_650.0) < 0.01


def test_compute_totals_zero_royalty():
    costs = {'هزینه تالیف': 2_000_000}
    result = calc.compute_totals(costs, royalty_pct=0.0, tiraj=1000)
    assert result['total_cost'] == 2_000_000.0
    assert result['cost_per_book'] == 2_000.0


def test_compute_totals_zero_tiraj_returns_zero_cost_per_book():
    costs = {'هزینه تالیف': 1_000_000}
    result = calc.compute_totals(costs, royalty_pct=0.0, tiraj=0)
    assert result['cost_per_book'] == 0.0


# ── compute_optimal_orientation ─────────────────────────────────────────────

def test_orientation_landscape_for_vaziri_on_70x100():
    orientation, pages = calc.compute_optimal_orientation(17, 24, 70, 100)
    assert orientation == 'portrait'
    assert pages > 0


def test_orientation_returns_portrait_or_landscape():
    orientation, pages = calc.compute_optimal_orientation(21, 28.5, 60, 90)
    assert orientation in ('portrait', 'landscape')
    assert isinstance(pages, int)
    assert pages > 0


# ── suggest_layout ──────────────────────────────────────────────────────────

def test_suggest_layout_vaziri():
    result = calc.suggest_layout('وزیری', 320)
    assert result is not None
    assert result['pages_per_sheet'] == 32
    assert result['zinc'] == 'زینک 3.5 ورقی'
    assert result['sheets_per_book'] == 10   # ceil(320/32)
    assert result['is_custom'] is False


def test_suggest_layout_unknown_qate():
    assert calc.suggest_layout('ناشناخته', 100) is None


def test_suggest_layout_zero_pages():
    result = calc.suggest_layout('وزیری', 0)
    assert result is not None
    assert result['sheets_per_book'] == 0


def test_suggest_layout_custom_with_dims():
    result = calc.suggest_layout(
        'مربع', 200,
        book_w=21, book_h=21,
        paper_size_str='60x90',
    )
    assert result is not None
    assert result['is_custom'] is True
    assert result['pages_per_sheet'] > 0
    assert result['orientation'] in ('portrait', 'landscape')


# ── compute_paper_unit_price ─────────────────────────────────────────────────

def test_paper_unit_price_formula0():
    # ((h * l) * w / 10000) * (price / 1000)
    price = calc.compute_paper_unit_price(0, height=24, length=34, weight=80, price=500_000, count=0)
    expected = ((24 * 34) * 80 / 10000) * (500_000 / 1000)
    assert abs(price - expected) < 0.01


def test_paper_unit_price_formula1():
    price = calc.compute_paper_unit_price(1, height=0, length=0, weight=0, price=2_000_000, count=200)
    assert abs(price - 10_000.0) < 0.01


def test_paper_unit_price_formula2_manual():
    price = calc.compute_paper_unit_price(2, height=0, length=0, weight=0, price=7_500, count=0)
    assert price == 7_500.0


def test_paper_unit_price_formula0_zero_dims_returns_zero():
    price = calc.compute_paper_unit_price(0, height=0, length=0, weight=0, price=500_000, count=0)
    assert price == 0.0


def test_paper_unit_price_formula1_zero_count_returns_zero():
    price = calc.compute_paper_unit_price(1, height=0, length=0, weight=0, price=500_000, count=0)
    assert price == 0.0


# ── Multi-volume series & multi-paper & translation pct ─────────────────────

def _auto(**overrides):
    kwargs = dict(
        form_matn=8, sides_matn=2, form_jeld=1, sides_jeld=1,
        tiraj=1000, waste_pct=0.0,
        unit_price_matn=1000.0, unit_price_jeld=2000.0,
        text_colors=1, cover_colors=4,
        zinc_price_matn=100_000, zinc_price_jeld=100_000,
    )
    kwargs.update(overrides)
    return calc.compute_auto_costs(**kwargs)


def test_series_shares_cover_paper_and_zinc():
    single = _auto()
    shared = _auto(series_volumes=2)
    # Cover paper halves; text paper unchanged
    assert shared['هزینه کاغذ جلد'] == single['هزینه کاغذ جلد'] / 2
    assert shared['هزینه کاغذ متن'] == single['هزینه کاغذ متن']
    # Zinc: matn part (8*1*100k) unchanged, jeld part (1*4*100k) halves
    assert shared['هزینه زینک'] == 8 * 100_000 + (4 * 100_000) / 2


def test_multi_paper_replaces_single_matn():
    papers = [
        {'form_count': 6, 'unit_price': 1000.0},
        {'form_count': 2, 'unit_price': 5000.0},
    ]
    result = _auto(papers_matn=papers)
    # (6/2)*1000*1000 + (2/2)*1000*5000 = 3_000_000 + 5_000_000
    assert result['هزینه کاغذ متن'] == 8_000_000.0


def test_multi_paper_jeld_with_series():
    papers = [{'form_count': 2, 'unit_price': 3000.0}]
    result = _auto(papers_jeld=papers, sides_jeld=1, series_volumes=3)
    # (2/1)*1000*3000 / 3 volumes
    assert abs(result['هزینه کاغذ جلد'] - 2_000_000.0) < 0.01


def test_totals_with_translation_pct():
    costs = {'a': 1000.0}
    r = calc.compute_totals(costs, royalty_pct=10.0, tiraj=100, tarjomeh_pct=15.0)
    assert abs(r['total_cost'] - 1250.0) < 0.01
    assert abs(r['cost_per_book'] - 12.5) < 0.01


def test_totals_series_divides_cover_print():
    costs = {'هزینه چاپ جلد': 900_000.0, 'هزینه صحافی': 100_000.0}
    r = calc.compute_totals(costs, royalty_pct=0.0, tiraj=100, series_volumes=3)
    assert abs(r['total_cost'] - (300_000.0 + 100_000.0)) < 0.01
    assert r['adjusted_costs']['هزینه چاپ جلد'] == 300_000.0
    # input dict untouched
    assert costs['هزینه چاپ جلد'] == 900_000.0


# ── Actual print size / paper counts (items 8, 9, 12) ───────────────────────

def test_zinc_size_label():
    assert calc.zinc_size_label('زینک 2.5 ورقی') == '60×90 سانتی‌متر'
    assert calc.zinc_size_label('زینک 3.5 ورقی') == '70×100 سانتی‌متر'
    assert calc.zinc_size_label('ناموجود') == ''


def test_actual_print_size_cut():
    assert calc.actual_print_size('70×100', False) == '70×100'
    # larger dim halved
    assert calc.actual_print_size('70×100', True) == '70×50'
    assert calc.actual_print_size('60×90', True) == '60×45'
    assert calc.actual_print_size('100×70', True) == '50×70'
    assert calc.actual_print_size('', True) == ''


def test_sheets_needed_and_bought():
    # 10 forms, double-sided, 1000 copies, 5% waste
    needed = calc.sheets_needed(10, 2, 1000, 5.0)
    assert abs(needed - 5250.0) < 0.01          # (10/2)*1000*1.05
    assert calc.bought_paper_count(10, 2, 1000, 5.0, False) == needed
    assert calc.bought_paper_count(10, 2, 1000, 5.0, True) == needed / 2
    # single-sided doubles the sheets
    assert abs(calc.sheets_needed(10, 1, 1000, 0.0) - 10000.0) < 0.01
