"""
Comprehensive accuracy tests for CostCalculator and BookDatabase.

Covers:
  1. Calculator formula correctness — hand-computed expected values
  2. Database round-trip fidelity — every field stored comes back identical
  3. Integration — calculator uses DB data; results stored and reloaded
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import math
import pytest
from bookcost.core.calculator import CostCalculator
from bookcost.core.db import BookDatabase


@pytest.fixture
def db():
    d = BookDatabase(':memory:')
    d.connect()
    return d


calc = CostCalculator()


# ─── helpers ────────────────────────────────────────────────────────────────

def _proj(title='دقت‌سنج'):
    return {
        'title': title, 'subtitle': 'زیرعنوان نمونه', 'creation_date': '1403-03-15',
        'qate': 'وزیری', 'tiraj': 2000, 'royalty_percent': 12.5,
        'total_cost': 18_000_000.0, 'single_book_cost': 9000.0,
    }


def _det():
    """Full project_details row with every column explicitly set."""
    return {
        'noeh_kaghaz_matn': 'تحریر ۸۰ گرم', 'noeh_chap_matn': 'افست',
        'noeh_rang_matn': 'تک رنگ', 'noeh_zink_matn': 'زینک 3.5 ورقی',
        'noeh_kaghaz_jeld': 'گلاسه ۱۳۵ گرم', 'noeh_chap_jeld': 'افست',
        'noeh_rang_jeld': 'چهار رنگ', 'noeh_zink_jeld': 'زینک 3.5 ورقی',
        'form_matn': 10, 'is_double_sided_matn': 1, 'color_count_matn': 1,
        'zinc_size_matn': 'زینک 3.5 ورقی',
        'form_jeld': 1, 'is_double_sided_jeld': 0, 'color_count_jeld': 4,
        'zinc_size_jeld': 'زینک 3.5 ورقی',
        'unit_price_paper_matn': 28_000.0, 'unit_price_paper_jeld': 45_000.0,
        'unit_price_zinc': 0.0,
        'waste_percent': 5.0, 'book_width': 17.0, 'book_height': 24.0,
        'paper_size': '70×100', 'orientation': 'portrait', 'pages_per_sheet': 32,
        'total_pages': 320,
        'hazineh_talif': 3_000_000.0, 'hazineh_tarjomeh': 0.0, 'hazineh_tasvir': 500_000.0,
        'hazineh_virayesh': 800_000.0, 'hazineh_tarahi_jeld': 1_200_000.0,
        'hazineh_modiriat_atelieh': 300_000.0,
        'hazineh_zink': 2_200_000.0, 'hazineh_chap_matn': 3_500_000.0,
        'hazineh_chap_jeld': 700_000.0,
        'hazineh_kaghaz_matn': 2_940_000.0, 'hazineh_kaghaz_jeld': 94_500.0,
        'hazineh_rokesh_salfon': 450_000.0, 'hazineh_moghava_maghzi': 0.0,
        'hazineh_ghaleb_letterpress': 0.0, 'hazineh_ghaleb_diecut': 0.0,
        'hazineh_khat_ta': 0.0,
        'hazineh_malzomat': 350_000.0, 'hazineh_jeldsazi': 0.0,
        'hazineh_sahafi': 900_000.0,
        'hazineh_boresh_bastebandi': 400_000.0, 'hazineh_haml_naghl': 250_000.0,
        'hazineh_montaj': 0.0,
        'hazineh_horoofchini': 2_000_000.0, 'hazineh_mojawwez_ershad': 300_000.0,
        'hazineh_shabok': 150_000.0,
        'hazineh_talakoobi': 0.0, 'hazineh_uv_mowzei': 0.0, 'hazineh_barjasteh': 0.0,
        'book_type_preset': 'کتاب مصور / رنگی', 'pricing_multiplier': 3.0,
        'distribution_percent': 40.0,
    }


# ════════════════════════════════════════════════════════════════════════════
# 1. CALCULATOR FORMULA ACCURACY
# ════════════════════════════════════════════════════════════════════════════

class TestAutoCotsFormulas:

    def test_paper_matn_exact(self):
        # (10/2) * 1000 * 1.05 * 500 = 5 * 1050 * 500 = 2_625_000
        r = calc.compute_auto_costs(
            form_matn=10, sides_matn=2, form_jeld=1, sides_jeld=1,
            tiraj=1000, waste_pct=5.0,
            unit_price_matn=500.0, unit_price_jeld=0.0,
            text_colors=1, cover_colors=1,
            zinc_price_matn=0, zinc_price_jeld=0,
        )
        assert abs(r['هزینه کاغذ متن'] - 2_625_000.0) < 0.01

    def test_paper_jeld_exact(self):
        # (1/1) * 2000 * 1.08 * 1500 = 3_240_000
        r = calc.compute_auto_costs(
            form_matn=1, sides_matn=1, form_jeld=1, sides_jeld=1,
            tiraj=2000, waste_pct=8.0,
            unit_price_matn=0.0, unit_price_jeld=1500.0,
            text_colors=1, cover_colors=1,
            zinc_price_matn=0, zinc_price_jeld=0,
        )
        assert abs(r['هزینه کاغذ جلد'] - 3_240_000.0) < 0.01

    def test_zinc_matn_exact(self):
        # 8 forms × 2 colors × 120_000 = 1_920_000
        r = calc.compute_auto_costs(
            form_matn=8, sides_matn=1, form_jeld=1, sides_jeld=1,
            tiraj=500, waste_pct=0.0,
            unit_price_matn=0.0, unit_price_jeld=0.0,
            text_colors=2, cover_colors=1,
            zinc_price_matn=120_000, zinc_price_jeld=0,
        )
        assert abs(r['هزینه زینک'] - 1_920_000.0) < 0.01

    def test_zinc_jeld_exact(self):
        # 1 form × 4 colors × 150_000 = 600_000
        r = calc.compute_auto_costs(
            form_matn=1, sides_matn=1, form_jeld=1, sides_jeld=1,
            tiraj=500, waste_pct=0.0,
            unit_price_matn=0.0, unit_price_jeld=0.0,
            text_colors=1, cover_colors=4,
            zinc_price_matn=0, zinc_price_jeld=150_000,
        )
        assert abs(r['هزینه زینک'] - 600_000.0) < 0.01

    def test_zinc_combined_exact(self):
        # matn: 8×2×120_000=1_920_000; jeld: 2×4×180_000=1_440_000; total=3_360_000
        r = calc.compute_auto_costs(
            form_matn=8, sides_matn=1, form_jeld=2, sides_jeld=1,
            tiraj=500, waste_pct=0.0,
            unit_price_matn=0.0, unit_price_jeld=0.0,
            text_colors=2, cover_colors=4,
            zinc_price_matn=120_000, zinc_price_jeld=180_000,
        )
        assert abs(r['هزینه زینک'] - 3_360_000.0) < 0.01

    def test_zero_waste_no_markup(self):
        # (1/1) * 1000 * 1.0 * 1000 = 1_000_000 exactly
        r = calc.compute_auto_costs(
            form_matn=1, sides_matn=1, form_jeld=1, sides_jeld=1,
            tiraj=1000, waste_pct=0.0,
            unit_price_matn=1000.0, unit_price_jeld=0.0,
            text_colors=1, cover_colors=1,
            zinc_price_matn=0, zinc_price_jeld=0,
        )
        assert r['هزینه کاغذ متن'] == 1_000_000.0

    def test_sides_zero_clamped_to_one(self):
        # sides_matn=0 and sides_jeld=0 should not raise ZeroDivisionError
        r = calc.compute_auto_costs(
            form_matn=4, sides_matn=0, form_jeld=1, sides_jeld=0,
            tiraj=100, waste_pct=0.0,
            unit_price_matn=1000.0, unit_price_jeld=500.0,
            text_colors=1, cover_colors=1,
            zinc_price_matn=0, zinc_price_jeld=0,
        )
        assert r['هزینه کاغذ متن'] == 400_000.0   # 4/1 * 100 * 1000
        assert r['هزینه کاغذ جلد'] == 50_000.0    # 1/1 * 100 * 500

    def test_all_three_components_simultaneously(self):
        # paper_matn = (16/2)*500*1.05*400 = 8*500*1.05*400 = 1_680_000
        # paper_jeld = (1/1)*500*1.05*1200 = 630_000
        # zinc = 16*1*100_000 + 1*4*150_000 = 1_600_000+600_000 = 2_200_000
        r = calc.compute_auto_costs(
            form_matn=16, sides_matn=2, form_jeld=1, sides_jeld=1,
            tiraj=500, waste_pct=5.0,
            unit_price_matn=400.0, unit_price_jeld=1200.0,
            text_colors=1, cover_colors=4,
            zinc_price_matn=100_000, zinc_price_jeld=150_000,
        )
        assert abs(r['هزینه کاغذ متن'] - 1_680_000.0) < 0.01
        assert abs(r['هزینه کاغذ جلد'] - 630_000.0) < 0.01
        assert abs(r['هزینه زینک'] - 2_200_000.0) < 0.01

    def test_high_tiraj_scales_linearly(self):
        # Doubling tiraj should double paper costs
        base = calc.compute_auto_costs(
            form_matn=8, sides_matn=2, form_jeld=1, sides_jeld=1,
            tiraj=1000, waste_pct=0.0,
            unit_price_matn=500.0, unit_price_jeld=800.0,
            text_colors=1, cover_colors=1,
            zinc_price_matn=0, zinc_price_jeld=0,
        )
        double = calc.compute_auto_costs(
            form_matn=8, sides_matn=2, form_jeld=1, sides_jeld=1,
            tiraj=2000, waste_pct=0.0,
            unit_price_matn=500.0, unit_price_jeld=800.0,
            text_colors=1, cover_colors=1,
            zinc_price_matn=0, zinc_price_jeld=0,
        )
        assert abs(double['هزینه کاغذ متن'] - base['هزینه کاغذ متن'] * 2) < 0.01
        assert abs(double['هزینه کاغذ جلد'] - base['هزینه کاغذ جلد'] * 2) < 0.01


class TestComputeTotals:

    def test_royalty_multiplier_exact(self):
        # 3_000_000 * 1.20 = 3_600_000 ; per-book = 3_600
        r = calc.compute_totals({'الف': 1_000_000, 'ب': 2_000_000}, royalty_pct=20.0, tiraj=1000)
        assert abs(r['total_cost'] - 3_600_000.0) < 0.01
        assert abs(r['cost_per_book'] - 3_600.0) < 0.01

    def test_zero_royalty_passes_through(self):
        r = calc.compute_totals({'الف': 5_000_000}, royalty_pct=0.0, tiraj=500)
        assert r['total_cost'] == 5_000_000.0
        assert r['cost_per_book'] == 10_000.0

    def test_100_pct_royalty_doubles_cost(self):
        r = calc.compute_totals({'الف': 1_000_000}, royalty_pct=100.0, tiraj=1000)
        assert abs(r['total_cost'] - 2_000_000.0) < 0.01

    def test_sum_of_many_components(self):
        # 20 components × 100_000 = 2_000_000 with 0% royalty
        costs = {f'هزینه {i}': 100_000 for i in range(20)}
        r = calc.compute_totals(costs, royalty_pct=0.0, tiraj=1000)
        assert abs(r['total_cost'] - 2_000_000.0) < 0.01

    def test_cost_per_book_with_fractional_result(self):
        # 1_000_000 / 3 → fractional, should not error
        r = calc.compute_totals({'الف': 1_000_000}, royalty_pct=0.0, tiraj=3)
        assert abs(r['cost_per_book'] - (1_000_000 / 3)) < 0.001

    def test_royalty_applied_to_sum_not_per_book(self):
        # royalty on 5_000_000 at 10% = 5_500_000 total; /1000 = 5500
        r = calc.compute_totals({'الف': 3_000_000, 'ب': 2_000_000}, royalty_pct=10.0, tiraj=1000)
        assert abs(r['total_cost'] - 5_500_000.0) < 0.01
        assert abs(r['cost_per_book'] - 5_500.0) < 0.01


class TestOrientation:

    def test_vaziri_portrait_on_70x100(self):
        # portrait = floor(70/17)*floor(100/24)*2 = 4*4*2 = 32
        # landscape = floor(70/24)*floor(100/17)*2 = 2*5*2 = 20
        orientation, pages = calc.compute_optimal_orientation(17, 24, 70, 100)
        assert orientation == 'portrait'
        assert pages == 32

    def test_raqi_portrait_on_60x90(self):
        # portrait = floor(60/14.5)*floor(90/21)*2 = 4*4*2 = 32
        # landscape = floor(60/21)*floor(90/14.5)*2 = 2*6*2 = 24
        orientation, pages = calc.compute_optimal_orientation(14.5, 21, 60, 90)
        assert orientation == 'portrait'
        assert pages == 32

    def test_landscape_wins_for_wide_book(self):
        # 30×10 book on 100×60:
        # portrait  = floor(100/30)*floor(60/10)*2 = 3*6*2 = 36
        # landscape = floor(100/10)*floor(60/30)*2 = 10*2*2 = 40
        orientation, pages = calc.compute_optimal_orientation(30, 10, 100, 60)
        assert orientation == 'landscape'
        assert pages == 40

    def test_khashti_square_on_50x70(self):
        # portrait = landscape = floor(50/21)*floor(70/21)*2 = 2*3*2 = 12
        _, pages = calc.compute_optimal_orientation(21, 21, 50, 70)
        assert pages == 12

    def test_zero_dims_returns_portrait_zero(self):
        orientation, pages = calc.compute_optimal_orientation(0, 0, 70, 100)
        assert orientation == 'portrait'
        assert pages == 0

    def test_negative_dims_returns_portrait_zero(self):
        orientation, pages = calc.compute_optimal_orientation(-5, 10, 70, 100)
        assert orientation == 'portrait'
        assert pages == 0

    def test_pages_result_always_even(self):
        # Both branches of the formula multiply by 2
        for bw, bh in [(17, 24), (14.5, 21), (11, 18), (21, 21), (24, 34)]:
            _, pages = calc.compute_optimal_orientation(bw, bh, 70, 100)
            if pages > 0:
                assert pages % 2 == 0, f"pages={pages} for book {bw}×{bh} is not even"

    def test_landscape_beats_portrait_counted_correctly(self):
        # Verify the winning count is actually returned (not the losing one)
        orientation, pages = calc.compute_optimal_orientation(30, 10, 100, 60)
        # landscape=40 wins; portrait=36 would be wrong
        assert pages == 40


class TestSuggestLayout:

    STANDARD_SPECS = {
        'وزیری':      {'pages_per_sheet': 32, 'paper_size': '70×100', 'zinc': 'زینک 3.5 ورقی'},
        'رقعی':       {'pages_per_sheet': 32, 'paper_size': '60×90',  'zinc': 'زینک 2.5 ورقی'},
        'رحلی کوچک': {'pages_per_sheet': 16, 'paper_size': '60×90',  'zinc': 'زینک 2.5 ورقی'},
        'رحلی بزرگ': {'pages_per_sheet': 16, 'paper_size': '70×100', 'zinc': 'زینک 3.5 ورقی'},
        'جیبی':       {'pages_per_sheet': 64, 'paper_size': '60×90',  'zinc': 'زینک 2.5 ورقی'},
        'خشتی':       {'pages_per_sheet': 12, 'paper_size': '50×70',  'zinc': 'زینک 2 ورقی'},
    }

    @pytest.mark.parametrize('qate,expected', STANDARD_SPECS.items())
    def test_standard_qate_specs(self, qate, expected):
        r = calc.suggest_layout(qate, 100)
        assert r is not None
        assert r['pages_per_sheet'] == expected['pages_per_sheet']
        assert r['paper_size'] == expected['paper_size']
        assert r['zinc'] == expected['zinc']
        assert r['is_custom'] is False

    def test_sheets_per_book_exact_division(self):
        # 320 / 32 = 10.0 → ceil = 10
        assert calc.suggest_layout('وزیری', 320)['sheets_per_book'] == 10

    def test_sheets_per_book_ceil_rounds_up(self):
        # 321 / 32 = 10.03 → ceil = 11
        assert calc.suggest_layout('وزیری', 321)['sheets_per_book'] == 11

    def test_sheets_per_book_one_page_over(self):
        # 65 / 64 = 1.015 → ceil = 2
        assert calc.suggest_layout('جیبی', 65)['sheets_per_book'] == 2

    def test_sheets_per_book_exactly_one_sheet(self):
        assert calc.suggest_layout('جیبی', 64)['sheets_per_book'] == 1

    def test_zero_pages_gives_zero_sheets(self):
        r = calc.suggest_layout('وزیری', 0)
        assert r['sheets_per_book'] == 0

    def test_unknown_qate_returns_none(self):
        assert calc.suggest_layout('ناشناخته', 100) is None

    def test_custom_marba_with_dims_uses_orientation_formula(self):
        # 21×21 on 60×90: both orientations give 16 → landscape chosen (>=)
        r = calc.suggest_layout('مربع', 96, book_w=21, book_h=21, paper_size_str='60x90')
        assert r['is_custom'] is True
        assert r['pages_per_sheet'] == 16
        assert r['orientation'] == 'landscape'

    def test_custom_without_dims_defaults_to_one_page_per_sheet(self):
        r = calc.suggest_layout('مربع', 200)
        assert r['pages_per_sheet'] == 1
        assert r['sheets_per_book'] == 200

    def test_paper_size_uses_unicode_times_sign(self):
        # OPTIMAL_SPECS stores '70x100'; suggest_layout must convert to '70×100'
        for qate in self.STANDARD_SPECS:
            r = calc.suggest_layout(qate, 100)
            assert '×' in r['paper_size'], f"{qate} paper_size uses ASCII 'x' not '×'"
            assert 'x' not in r['paper_size']


class TestPaperUnitPrice:

    def test_formula0_standard_vaziri_paper(self):
        # ((70*100)*80/10000) * (500_000/1000) = 56 * 500 = 28_000
        result = calc.compute_paper_unit_price(0, height=70, length=100, weight=80, price=500_000)
        assert abs(result - 28_000.0) < 0.01

    def test_formula0_higher_grammage(self):
        # 100g paper: ((70*100)*100/10000) * 600 = 70 * 600 = 42_000
        result = calc.compute_paper_unit_price(0, height=70, length=100, weight=100, price=600_000)
        assert abs(result - 42_000.0) < 0.01

    def test_formula0_smaller_sheet(self):
        # 60×90, 80g, 400_000/ton: ((60*90)*80/10000) * 400 = 43.2 * 400 = 17_280
        result = calc.compute_paper_unit_price(0, height=60, length=90, weight=80, price=400_000)
        assert abs(result - 17_280.0) < 0.01

    def test_formula0_zero_dims_returns_zero(self):
        assert calc.compute_paper_unit_price(0, height=0, length=0, weight=80, price=500_000) == 0.0

    def test_formula1_bundle_price_divided_by_count(self):
        # 3_000_000 / 250 = 12_000
        result = calc.compute_paper_unit_price(1, price=3_000_000, count=250)
        assert abs(result - 12_000.0) < 0.01

    def test_formula1_zero_count_returns_zero(self):
        assert calc.compute_paper_unit_price(1, price=3_000_000, count=0) == 0.0

    def test_formula1_count_one(self):
        assert calc.compute_paper_unit_price(1, price=50_000, count=1) == 50_000.0

    def test_formula2_manual_pass_through(self):
        assert calc.compute_paper_unit_price(2, price=8_750) == 8_750.0

    def test_formula2_ignores_other_params(self):
        # formula 2 should return price regardless of other params
        r1 = calc.compute_paper_unit_price(2, price=5000)
        r2 = calc.compute_paper_unit_price(2, height=99, length=99, weight=99, price=5000, count=99)
        assert r1 == r2 == 5000.0


# ════════════════════════════════════════════════════════════════════════════
# 2. DATABASE ROUND-TRIP FIDELITY
# ════════════════════════════════════════════════════════════════════════════

class TestDatabaseRoundTrip:

    def test_all_project_fields_preserved(self, db):
        p = _proj()
        pid = db.insert_project(p, _det())
        loaded = db.get_project(pid)
        for key, value in p.items():
            assert loaded[key] == value, f"project field '{key}': expected {value!r}, got {loaded[key]!r}"

    def test_all_detail_string_fields_preserved(self, db):
        d = _det()
        pid = db.insert_project(_proj(), d)
        loaded = db.get_project_details(pid)
        string_fields = [
            'noeh_kaghaz_matn', 'noeh_chap_matn', 'noeh_rang_matn', 'noeh_zink_matn',
            'noeh_kaghaz_jeld', 'noeh_chap_jeld', 'noeh_rang_jeld', 'noeh_zink_jeld',
            'zinc_size_matn', 'zinc_size_jeld', 'paper_size', 'orientation',
            'book_type_preset',
        ]
        for f in string_fields:
            assert loaded[f] == d[f], f"string field '{f}' mismatch"

    def test_all_detail_integer_fields_preserved(self, db):
        d = _det()
        pid = db.insert_project(_proj(), d)
        loaded = db.get_project_details(pid)
        int_fields = [
            'form_matn', 'is_double_sided_matn', 'color_count_matn',
            'form_jeld', 'is_double_sided_jeld', 'color_count_jeld',
            'pages_per_sheet', 'total_pages',
        ]
        for f in int_fields:
            assert loaded[f] == d[f], f"integer field '{f}' mismatch"

    def test_all_detail_float_fields_preserved(self, db):
        d = _det()
        pid = db.insert_project(_proj(), d)
        loaded = db.get_project_details(pid)
        float_fields = [
            'unit_price_paper_matn', 'unit_price_paper_jeld', 'waste_percent',
            'book_width', 'book_height', 'pricing_multiplier', 'distribution_percent',
        ]
        for f in float_fields:
            assert loaded[f] == pytest.approx(d[f], rel=1e-9), f"float field '{f}' mismatch"

    def test_all_hazineh_fields_preserved(self, db):
        d = _det()
        pid = db.insert_project(_proj(), d)
        loaded = db.get_project_details(pid)
        hazineh_fields = [k for k in d if k.startswith('hazineh_')]
        for f in hazineh_fields:
            assert loaded[f] == pytest.approx(d[f], abs=0.001), f"cost field '{f}' mismatch"

    def test_none_orientation_preserved(self, db):
        d = _det()
        d['orientation'] = None
        pid = db.insert_project(_proj(), d)
        assert db.get_project_details(pid)['orientation'] is None

    def test_zero_cost_fields_stay_zero(self, db):
        d = _det()
        zero_fields = ['hazineh_tarjomeh', 'hazineh_moghava_maghzi',
                       'hazineh_talakoobi', 'hazineh_ghaleb_diecut', 'hazineh_montaj']
        for f in zero_fields:
            d[f] = 0.0
        pid = db.insert_project(_proj(), d)
        loaded = db.get_project_details(pid)
        for f in zero_fields:
            assert loaded[f] == 0.0, f"field '{f}' should remain 0"

    def test_update_changes_only_targeted_field(self, db):
        pid = db.insert_project(_proj(), _det())
        new_d = _det()
        new_d['hazineh_talif'] = 5_000_000.0
        db.update_project(pid, _proj('عنوان جدید'), new_d)
        loaded = db.get_project_details(pid)
        assert loaded['hazineh_talif'] == 5_000_000.0
        assert loaded['hazineh_sahafi'] == _det()['hazineh_sahafi']
        assert loaded['pages_per_sheet'] == _det()['pages_per_sheet']

    def test_multiple_projects_isolated(self, db):
        pid1 = db.insert_project(_proj('کتاب یک'), _det())
        d2 = _det()
        d2['form_matn'] = 99
        d2['hazineh_talif'] = 9_999_999.0
        pid2 = db.insert_project(_proj('کتاب دو'), d2)
        assert db.get_project_details(pid1)['form_matn'] == _det()['form_matn']
        assert db.get_project_details(pid2)['form_matn'] == 99
        assert db.get_project_details(pid1)['hazineh_talif'] == _det()['hazineh_talif']
        assert db.get_project_details(pid2)['hazineh_talif'] == 9_999_999.0

    def test_delete_removes_details_too(self, db):
        pid = db.insert_project(_proj(), _det())
        db.delete_project(pid)
        assert db.get_project(pid) is None
        assert db.get_project_details(pid) is None


class TestZincPriceAccuracy:

    def test_seeded_five_zinc_types(self, db):
        rows = db.get_all_zinc_prices()
        assert len(rows) == 5

    def test_all_calculator_zinc_dims_seeded_in_db(self, db):
        db_sizes = {r['zinc_size'] for r in db.get_all_zinc_prices()}
        for zinc_name in CostCalculator.ZINC_DIMS:
            assert zinc_name in db_sizes, f"'{zinc_name}' seeded in DB"

    def test_save_and_retrieve_exact_price(self, db):
        db.save_zinc_price('زینک 3.5 ورقی', 175_000)
        assert db.get_zinc_price('زینک 3.5 ورقی') == 175_000.0

    def test_all_five_zinc_prices_independent(self, db):
        prices = {'زینک GTO': 50_000, 'زینک 2 ورقی': 100_000,
                  'زینک 2.5 ورقی': 130_000, 'زینک 3.5 ورقی': 175_000,
                  'زینک 4.5 ورقی': 220_000}
        for name, price in prices.items():
            db.save_zinc_price(name, price)
        for name, expected in prices.items():
            assert db.get_zinc_price(name) == expected

    def test_update_overwrites_previous_price(self, db):
        db.save_zinc_price('زینک GTO', 50_000)
        db.save_zinc_price('زینک GTO', 75_000)
        assert db.get_zinc_price('زینک GTO') == 75_000.0

    def test_missing_zinc_returns_zero(self, db):
        assert db.get_zinc_price('زینک ناموجود') == 0.0


class TestDefaultMappingAccuracy:

    def test_all_eight_categories_stored_and_retrieved(self, db):
        categories = [
            'نوع کاغذ متن', 'نوع چاپ متن', 'نوع رنگ متن', 'نوع زینک متن',
            'نوع کاغذ جلد', 'نوع چاپ جلد', 'نوع رنگ جلد', 'نوع زینک جلد',
        ]
        for i, cat in enumerate(categories):
            db.insert_default_mapping(cat, 'نمونه', 'هزینه تالیف', (i + 1) * 100_000)
        for i, cat in enumerate(categories):
            row = db.get_default_cost(cat, 'نمونه')
            assert row is not None, f"category '{cat}' not found"
            assert row['default_cost'] == (i + 1) * 100_000

    def test_batch_fetch_returns_all_matches(self, db):
        pairs = [
            ('نوع کاغذ متن', 'تحریر',  'هزینه کاغذ متن',  500_000),
            ('نوع چاپ متن',  'افست',   'هزینه چاپ متن',  1_200_000),
            ('نوع کاغذ جلد', 'گلاسه',  'هزینه کاغذ جلد',   800_000),
        ]
        for cat, val, field, cost in pairs:
            db.insert_default_mapping(cat, val, field, cost)
        results = db.get_default_costs_batch([(c, v) for c, v, _, _ in pairs])
        assert len(results) == 3
        cost_map = {(r['category_name'], r['item_value']): r['default_cost'] for r in results}
        for cat, val, _, expected in pairs:
            assert cost_map[(cat, val)] == expected

    def test_upsert_does_not_duplicate(self, db):
        for _ in range(3):
            db.upsert_default_mapping('نوع کاغذ متن', 'تحریر', 'هزینه کاغذ متن', 500_000)
        rows = [r for r in db.get_default_cost_mappings()
                if r['category_name'] == 'نوع کاغذ متن']
        assert len(rows) == 1

    def test_upsert_updates_cost_on_second_call(self, db):
        db.upsert_default_mapping('نوع کاغذ متن', 'تحریر', 'هزینه کاغذ متن', 500_000)
        db.upsert_default_mapping('نوع کاغذ متن', 'تحریر', 'هزینه کاغذ متن', 650_000)
        assert db.get_default_cost('نوع کاغذ متن', 'تحریر')['default_cost'] == 650_000

    def test_different_values_same_category_coexist(self, db):
        db.insert_default_mapping('نوع کاغذ متن', 'تحریر', 'هزینه کاغذ متن', 500_000)
        db.insert_default_mapping('نوع کاغذ متن', 'بالک',  'هزینه کاغذ متن', 400_000)
        assert db.get_default_cost('نوع کاغذ متن', 'تحریر')['default_cost'] == 500_000
        assert db.get_default_cost('نوع کاغذ متن', 'بالک')['default_cost'] == 400_000


# ════════════════════════════════════════════════════════════════════════════
# 3. INTEGRATION: CALCULATOR + DATABASE
# ════════════════════════════════════════════════════════════════════════════

class TestIntegration:

    def test_full_vaziri_pipeline(self, db):
        """
        Paper unit price → zinc from DB → compute_auto_costs → verify outputs.

        Vaziri 17×24 on 70×100, tiraj=1000, waste=5%
          unit_price_matn = ((70*100)*80/10000) * (500_000/1000) = 56*500 = 28_000
          zinc             = 160_000 (saved to DB)

          paper_matn = (10/2) * 1000 * 1.05 * 28_000 = 147_000_000
          paper_jeld = (1/1)  * 1000 * 1.05 * 45_000 =  47_250_000
          zinc_cost  = 10*1*160_000 + 1*4*160_000    =   2_240_000
        """
        db.save_zinc_price('زینک 3.5 ورقی', 160_000)

        unit_price_matn = calc.compute_paper_unit_price(
            0, height=70, length=100, weight=80, price=500_000
        )
        assert abs(unit_price_matn - 28_000.0) < 0.01

        zinc_price = db.get_zinc_price('زینک 3.5 ورقی')
        assert zinc_price == 160_000.0

        r = calc.compute_auto_costs(
            form_matn=10, sides_matn=2, form_jeld=1, sides_jeld=1,
            tiraj=1000, waste_pct=5.0,
            unit_price_matn=unit_price_matn, unit_price_jeld=45_000.0,
            text_colors=1, cover_colors=4,
            zinc_price_matn=zinc_price, zinc_price_jeld=zinc_price,
        )
        assert r['هزینه کاغذ متن'] == pytest.approx(147_000_000.0, rel=1e-6)
        assert r['هزینه کاغذ جلد'] == pytest.approx(47_250_000.0,  rel=1e-6)
        assert r['هزینه زینک']     == pytest.approx(2_240_000.0,   rel=1e-6)

    def test_computed_costs_survive_db_round_trip(self, db):
        """Costs from compute_auto_costs stored in DB and reloaded must match."""
        db.save_zinc_price('زینک 2.5 ورقی', 140_000)
        zinc_price = db.get_zinc_price('زینک 2.5 ورقی')

        costs = calc.compute_auto_costs(
            form_matn=16, sides_matn=2, form_jeld=1, sides_jeld=1,
            tiraj=500, waste_pct=5.0,
            unit_price_matn=25_000.0, unit_price_jeld=40_000.0,
            text_colors=1, cover_colors=4,
            zinc_price_matn=zinc_price, zinc_price_jeld=zinc_price,
        )

        d = _det()
        d['hazineh_kaghaz_matn'] = costs['هزینه کاغذ متن']
        d['hazineh_kaghaz_jeld'] = costs['هزینه کاغذ جلد']
        d['hazineh_zink']        = costs['هزینه زینک']

        pid = db.insert_project(_proj(), d)
        loaded = db.get_project_details(pid)

        assert loaded['hazineh_kaghaz_matn'] == pytest.approx(costs['هزینه کاغذ متن'], rel=1e-9)
        assert loaded['hazineh_kaghaz_jeld'] == pytest.approx(costs['هزینه کاغذ جلد'], rel=1e-9)
        assert loaded['hazineh_zink']        == pytest.approx(costs['هزینه زینک'],      rel=1e-9)

    def test_compute_totals_stored_and_reloaded(self, db):
        """compute_totals result stored in projects.total_cost matches on reload."""
        d = _det()
        cost_components = {
            'هزینه تالیف':    d['hazineh_talif'],
            'هزینه زینک':     d['hazineh_zink'],
            'هزینه چاپ متن':  d['hazineh_chap_matn'],
            'هزینه چاپ جلد':  d['hazineh_chap_jeld'],
            'هزینه کاغذ متن': d['hazineh_kaghaz_matn'],
            'هزینه کاغذ جلد': d['hazineh_kaghaz_jeld'],
            'هزینه صحافی':    d['hazineh_sahafi'],
        }
        totals = calc.compute_totals(cost_components, royalty_pct=12.5, tiraj=2000)

        p = _proj()
        p['total_cost']      = totals['total_cost']
        p['single_book_cost'] = totals['cost_per_book']
        p['tiraj']           = 2000
        p['royalty_percent'] = 12.5

        pid = db.insert_project(p, d)
        loaded_p = db.get_project(pid)

        assert loaded_p['total_cost']       == pytest.approx(totals['total_cost'],    rel=1e-9)
        assert loaded_p['single_book_cost'] == pytest.approx(totals['cost_per_book'], rel=1e-9)

    def test_suggest_layout_fields_stored_and_reloaded(self, db):
        """suggest_layout output fields survive a DB round-trip unchanged."""
        layout = calc.suggest_layout('رقعی', 256)
        assert layout['pages_per_sheet'] == 32
        assert layout['paper_size'] == '60×90'

        d = _det()
        d['pages_per_sheet'] = layout['pages_per_sheet']
        d['paper_size']      = layout['paper_size']
        d['total_pages']     = 256

        pid = db.insert_project(_proj(), d)
        loaded = db.get_project_details(pid)

        assert loaded['pages_per_sheet'] == 32
        assert loaded['paper_size']      == '60×90'
        assert loaded['total_pages']     == 256

    def test_zinc_price_change_affects_computed_cost(self, db):
        """Changing a zinc price in DB changes the computed zinc cost proportionally."""
        def compute_with_zinc(price):
            db.save_zinc_price('زینک GTO', price)
            z = db.get_zinc_price('زینک GTO')
            r = calc.compute_auto_costs(
                form_matn=4, sides_matn=1, form_jeld=1, sides_jeld=1,
                tiraj=100, waste_pct=0.0,
                unit_price_matn=0.0, unit_price_jeld=0.0,
                text_colors=1, cover_colors=4,
                zinc_price_matn=z, zinc_price_jeld=z,
            )
            return r['هزینه زینک']

        cost_low  = compute_with_zinc(50_000)
        cost_high = compute_with_zinc(100_000)
        # doubling the zinc price should double the zinc cost
        assert abs(cost_high - cost_low * 2) < 0.01

    def test_default_mapping_lookup_and_category_storage(self, db):
        """Insert a default mapping + category; verify both lookups work."""
        db.insert_default_mapping('نوع کاغذ متن', 'تحریر ۸۰ گرم', 'هزینه کاغذ متن', 28_000)
        db.save_category('نوع کاغذ متن', 'تحریر ۸۰ گرم')

        row = db.get_default_cost('نوع کاغذ متن', 'تحریر ۸۰ گرم')
        assert row['target_cost_field'] == 'هزینه کاغذ متن'
        assert row['default_cost'] == 28_000

        items = db.get_categories('نوع کاغذ متن')
        assert 'تحریر ۸۰ گرم' in items
