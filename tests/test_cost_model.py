"""Tests for the unified cost-line model (pure)."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from bookcost.core.cost_model import (
    CalcType, CostContext, CostLine, resolve_amount, resolve_total, resolved_breakdown,
)
from bookcost.core.fields import default_calc_type


def _ctx(tiraj=1000, total_forms=12, volume_count=1):
    return CostContext(tiraj=tiraj, total_forms=total_forms, volume_count=volume_count)


def test_resolve_amount_per_type():
    ctx = _ctx(tiraj=1000, total_forms=12, volume_count=3)
    assert resolve_amount(500, CalcType.FIXED, ctx) == 500
    assert resolve_amount(500, CalcType.PER_TIRAJ, ctx) == 500_000
    assert resolve_amount(500, CalcType.PER_FORM, ctx) == 6_000
    assert resolve_amount(500, CalcType.PER_VOLUME, ctx) == 1_500


def test_coerce_accepts_strings_and_junk():
    assert CalcType.coerce('per_form') is CalcType.PER_FORM
    assert CalcType.coerce(CalcType.FIXED) is CalcType.FIXED
    assert CalcType.coerce(None) is CalcType.FIXED
    assert CalcType.coerce('nonsense') is CalcType.FIXED
    # string calc type still resolves correctly through resolve_amount
    assert resolve_amount(10, 'per_tiraj', _ctx(tiraj=5)) == 50


def test_per_volume_single_volume_is_one_off():
    ctx = _ctx(volume_count=1)
    assert resolve_amount(9000, CalcType.PER_VOLUME, ctx) == 9000


def test_resolve_total_mixes_types():
    lines = [
        CostLine('talif', 'هزینه تالیف', 5_000_000, CalcType.FIXED),
        CostLine('sahafi', 'هزینه صحافی', 2_000, CalcType.PER_TIRAJ),
        CostLine('print', 'چاپ', 50_000, CalcType.PER_FORM),
    ]
    ctx = _ctx(tiraj=1000, total_forms=10)
    # 5,000,000 + 2,000*1000 + 50,000*10 = 7,500,000
    assert resolve_total(lines, ctx) == 7_500_000


def test_subfields_are_ordinary_lines():
    lines = [
        CostLine('letterpress', 'هزینه قالب لترپرس', 800_000, CalcType.FIXED),
        CostLine('lp_service', 'خدمات', 300_000, CalcType.FIXED, parent_key='letterpress'),
        CostLine('lp_mold', 'قالب', 500_000, CalcType.FIXED, parent_key='letterpress'),
    ]
    assert resolve_total(lines, _ctx()) == 1_600_000


def test_resolved_breakdown_keys_by_name():
    lines = [
        CostLine('a', 'هزینه صحافی', 2_000, CalcType.PER_TIRAJ),
        CostLine('b', 'هزینه تالیف', 1_000_000, CalcType.FIXED),
    ]
    bd = resolved_breakdown(lines, _ctx(tiraj=500))
    assert bd['هزینه صحافی'] == 1_000_000
    assert bd['هزینه تالیف'] == 1_000_000


def test_default_calc_types_match_spec():
    for name in ('هزینه صحافی', 'هزینه جلدسازی', 'هزینه ملزومات'):
        assert default_calc_type(name) == 'per_tiraj'
    assert default_calc_type('هزینه تالیف') == 'fixed'
    assert default_calc_type('هزینه مجوز ارشاد') == 'fixed'


def test_project_total_applies_percentages():
    from bookcost.core.cost_model import project_total
    lines = [
        CostLine('a', 'تالیف', 1_000_000, CalcType.FIXED),
        CostLine('b', 'صحافی', 2_000, CalcType.PER_TIRAJ),
    ]
    ctx = _ctx(tiraj=1000, total_forms=0)
    r = project_total(lines, ctx, royalty_pct=10.0, tarjomeh_pct=5.0)
    # base = 1,000,000 + 2,000,000 = 3,000,000 ; ×1.15 = 3,450,000
    assert r['base'] == 3_000_000
    assert abs(r['total_cost'] - 3_450_000) < 0.01
    assert abs(r['cost_per_book'] - 3450.0) < 0.01
