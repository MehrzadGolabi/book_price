"""PDF report generation tests — pure reporting layer, no Qt required."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from bookcost.reporting.pdf_report import ReportData, build_pdf_report

FONT = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'resources', 'tahoma.ttf')


def _sample_data(**overrides):
    data = ReportData(
        title='کتاب آزمایشی',
        basic_info=[('عنوان کتاب', 'کتاب آزمایشی'), ('تاریخ', '1405/04/19'), ('قطع', 'وزیری')],
        tiraj=2000,
        print_specs=[('تعداد صفحات کتاب', '160'), ('اندازه کاغذ چاپ', '70×100'),
                     ('تعداد فرم متن', '10'), ('ضایعات کاغذ', '5 ٪')],
        features=[('نوع کاغذ متن', 'تحریر ۸۰ گرم'), ('نوع چاپ جلد', 'افست')],
        cost_groups=[
            ('خلاقیت و تحریریه', [('هزینه تالیف', 5_000_000.0), ('هزینه ویرایش', 0.0)]),
            ('چاپ و مواد', [('هزینه کاغذ متن', 94_500_000.0), ('هزینه زینک', 2_500_000.0)]),
            ('تکمیل و صحافی', [('هزینه صحافی', 1_200_000.0)]),
            ('اداری و مجوزها', [('هزینه ثبت شابک', 0.0)]),
        ],
        royalty_pct=10.0,
        total_cost=113_520_000.0,
        single_cost=56_760.0,
        pricing_multiplier=2.5,
        distribution_pct=35.0,
    )
    for k, v in overrides.items():
        setattr(data, k, v)
    return data


def _page_count(path) -> int:
    raw = path.read_bytes()
    return raw.count(b'/Type /Page') - raw.count(b'/Type /Pages')


def test_full_report_generates_single_page(tmp_path):
    out = tmp_path / 'full.pdf'
    build_pdf_report(str(out), FONT, _sample_data())
    assert out.exists() and out.stat().st_size > 10_000
    assert _page_count(out) == 1


def test_sections_toggled_off(tmp_path):
    out = tmp_path / 'minimal.pdf'
    build_pdf_report(str(out), FONT, _sample_data(
        include_basic_info=False, include_specs=False, include_features=False,
        include_costs=False, include_pricing=False,
    ))
    assert out.exists() and out.stat().st_size > 1_000


def test_negative_net_revenue_pricing(tmp_path):
    # 100% distribution share → net revenue <= 0 → "not computable" branch
    out = tmp_path / 'negative.pdf'
    build_pdf_report(str(out), FONT, _sample_data(distribution_pct=100.0))
    assert out.exists()


def test_heavy_content_still_single_page(tmp_path):
    # Every section ticked and far more cost rows than the real app can
    # produce — the adaptive layout must still fit one A4 page
    groups = [(f'گروه {i}', [(f'هزینه شماره {j}', 1000.0 * (i + j + 1)) for j in range(12)])
              for i in range(6)]
    out = tmp_path / 'heavy.pdf'
    build_pdf_report(str(out), FONT, _sample_data(cost_groups=groups))
    assert out.exists() and out.stat().st_size > 10_000
    assert _page_count(out) == 1


def test_zero_pricing_multiplier_skips_pricing(tmp_path):
    out = tmp_path / 'no_pricing.pdf'
    build_pdf_report(str(out), FONT, _sample_data(pricing_multiplier=0.0))
    assert out.exists()
