import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
import sqlite3
from db import BookDatabase


@pytest.fixture
def db():
    d = BookDatabase(':memory:')
    d.connect()
    return d


def _project(title='کتاب تست'):
    return {
        'title': title, 'subtitle': 'زیر عنوان', 'creation_date': '1403-01-01',
        'qate': 'وزیری', 'tiraj': 1000, 'royalty_percent': 10.0,
        'total_cost': 5_000_000, 'single_book_cost': 5000,
    }


def _details():
    return {
        'noeh_kaghaz_matn': 'تحریر', 'noeh_chap_matn': 'افست', 'noeh_rang_matn': 'تک رنگ',
        'noeh_zink_matn': 'زینک GTO', 'noeh_kaghaz_jeld': 'گلاسه', 'noeh_chap_jeld': 'افست',
        'noeh_rang_jeld': 'چهار رنگ', 'noeh_zink_jeld': 'زینک GTO',
        'form_matn': 16, 'is_double_sided_matn': 1, 'color_count_matn': 1, 'zinc_size_matn': 'زینک GTO',
        'form_jeld': 1, 'is_double_sided_jeld': 0, 'color_count_jeld': 4, 'zinc_size_jeld': 'زینک GTO',
        'unit_price_paper_matn': 500.0, 'unit_price_paper_jeld': 800.0, 'unit_price_zinc': 0,
        'waste_percent': 5.0, 'book_width': 17.0, 'book_height': 24.0, 'paper_size': '70x100',
        'orientation': None, 'pages_per_sheet': 32, 'total_pages': 320,
        'hazineh_talif': 2_000_000, 'hazineh_tarjomeh': 0, 'hazineh_tasvir': 0,
        'hazineh_virayesh': 500_000, 'hazineh_tarahi_jeld': 800_000, 'hazineh_modiriat_atelieh': 0,
        'hazineh_zink': 320_000, 'hazineh_chap_matn': 1_600_000, 'hazineh_chap_jeld': 400_000,
        'hazineh_kaghaz_matn': 4_200_000, 'hazineh_kaghaz_jeld': 840_000,
        'hazineh_rokesh_salfon': 300_000, 'hazineh_moghava_maghzi': 0,
        'hazineh_ghaleb_letterpress': 0, 'hazineh_ghaleb_diecut': 0, 'hazineh_khat_ta': 0,
        'hazineh_malzomat': 200_000, 'hazineh_jeldsazi': 500_000, 'hazineh_sahafi': 600_000,
        'hazineh_boresh_bastebandi': 250_000, 'hazineh_haml_naghl': 150_000, 'hazineh_montaj': 0,
        'hazineh_horoofchini': 1_500_000, 'hazineh_mojawwez_ershad': 200_000, 'hazineh_shabok': 100_000,
        'hazineh_talakoobi': 0, 'hazineh_uv_mowzei': 0, 'hazineh_barjasteh': 0,
        'book_type_preset': 'شومیز ساده', 'pricing_multiplier': 2.5, 'distribution_percent': 35.0,
    }


def test_connect_creates_tables(db):
    cur = db._conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cur.fetchall()}
    assert {'projects', 'project_details', 'zinc_prices',
            'paper_calculations', 'default_cost_mappings', 'categories'}.issubset(tables)


def test_connect_seeds_zinc_prices(db):
    prices = db.get_all_zinc_prices()
    zinc_names = [r['zinc_size'] for r in prices]
    assert 'زینک GTO' in zinc_names
    assert 'زینک 3.5 ورقی' in zinc_names
    assert len(prices) == 5


def test_insert_and_load_project(db):
    pid = db.insert_project(_project(), _details())
    assert pid > 0
    p = db.get_project(pid)
    assert p['title'] == 'کتاب تست'
    assert p['tiraj'] == 1000
    d = db.get_project_details(pid)
    assert d['form_matn'] == 16
    assert d['hazineh_horoofchini'] == 1_500_000


def test_update_project(db):
    pid = db.insert_project(_project('قدیم'), _details())
    new_p = _project('جدید')
    new_d = _details()
    new_d['form_matn'] = 32
    db.update_project(pid, new_p, new_d)
    assert db.get_project(pid)['title'] == 'جدید'
    assert db.get_project_details(pid)['form_matn'] == 32


def test_delete_project_cascades(db):
    pid = db.insert_project(_project(), _details())
    db.delete_project(pid)
    assert db.get_project(pid) is None
    assert db.get_project_details(pid) is None


def test_get_projects_filter(db):
    db.insert_project(_project('رمان'), _details())
    db.insert_project(_project('شعر'), _details())
    results = db.get_projects(filter_text='رمان')
    assert len(results) == 1
    assert results[0]['title'] == 'رمان'


def test_zinc_price_save_and_get(db):
    db.save_zinc_price('زینک GTO', 250_000)
    assert db.get_zinc_price('زینک GTO') == 250_000.0


def test_zinc_price_missing_returns_zero(db):
    assert db.get_zinc_price('زینک ناموجود') == 0.0


def test_paper_calculation_insert_and_list(db):
    data = {'paper_type': 'تحریر', 'formula_type': 'دستی', 'weight': 0,
            'height': 0, 'length': 0, 'bundle_count': 0, 'bundle_weight': 0,
            'price': 5000, 'unit_price': 5000}
    cid = db.insert_paper_calculation(data)
    rows = db.get_paper_calculations()
    assert any(r['id'] == cid for r in rows)


def test_paper_calculation_update(db):
    data = {'paper_type': 'تحریر', 'formula_type': 'دستی', 'weight': 0,
            'height': 0, 'length': 0, 'bundle_count': 0, 'bundle_weight': 0,
            'price': 5000, 'unit_price': 5000}
    cid = db.insert_paper_calculation(data)
    db.update_paper_calculation(cid, {**data, 'unit_price': 7000})
    rows = db.get_paper_calculations()
    updated = next(r for r in rows if r['id'] == cid)
    assert updated['unit_price'] == 7000


def test_paper_calculation_delete(db):
    data = {'paper_type': 'گلاسه', 'formula_type': 'دستی', 'weight': 0,
            'height': 0, 'length': 0, 'bundle_count': 0, 'bundle_weight': 0,
            'price': 9000, 'unit_price': 9000}
    cid = db.insert_paper_calculation(data)
    db.delete_paper_calculation(cid)
    assert not any(r['id'] == cid for r in db.get_paper_calculations())


def test_default_mapping_crud(db):
    db.insert_default_mapping('نوع کاغذ متن', 'تحریر', 'هزینه کاغذ متن', 500_000)
    rows = db.get_default_cost_mappings()
    assert len(rows) == 1
    mapping_id = rows[0]['id']
    db.update_default_mapping(mapping_id, 'نوع کاغذ متن', 'تحریر ۸۰', 'هزینه کاغذ متن', 600_000)
    rows = db.get_default_cost_mappings()
    assert rows[0]['item_value'] == 'تحریر ۸۰'
    db.delete_default_mapping(mapping_id)
    assert len(db.get_default_cost_mappings()) == 0


def test_get_default_cost(db):
    db.insert_default_mapping('نوع کاغذ متن', 'تحریر', 'هزینه کاغذ متن', 500_000)
    result = db.get_default_cost('نوع کاغذ متن', 'تحریر')
    assert result is not None
    assert result['target_cost_field'] == 'هزینه کاغذ متن'
    assert result['default_cost'] == 500_000


def test_get_default_cost_missing(db):
    assert db.get_default_cost('نوع کاغذ متن', 'ناموجود') is None


def test_get_default_costs_batch(db):
    db.insert_default_mapping('نوع کاغذ متن', 'تحریر', 'هزینه کاغذ متن', 500_000)
    db.insert_default_mapping('نوع چاپ متن', 'افست', 'هزینه چاپ متن', 1_200_000)
    results = db.get_default_costs_batch([
        ('نوع کاغذ متن', 'تحریر'),
        ('نوع چاپ متن', 'افست'),
    ])
    assert len(results) == 2


def test_upsert_default_mapping_inserts_new(db):
    db.upsert_default_mapping('نوع کاغذ جلد', 'گلاسه', 'هزینه کاغذ جلد', 800_000)
    assert db.get_default_cost('نوع کاغذ جلد', 'گلاسه')['default_cost'] == 800_000


def test_upsert_default_mapping_updates_existing(db):
    db.insert_default_mapping('نوع کاغذ جلد', 'گلاسه', 'هزینه کاغذ جلد', 800_000)
    db.upsert_default_mapping('نوع کاغذ جلد', 'گلاسه', 'هزینه کاغذ جلد', 900_000)
    assert db.get_default_cost('نوع کاغذ جلد', 'گلاسه')['default_cost'] == 900_000


def test_save_and_get_categories(db):
    db.save_category('نوع کاغذ متن', 'تحریر')
    db.save_category('نوع کاغذ متن', 'بالک')
    items = db.get_categories('نوع کاغذ متن')
    assert 'تحریر' in items
    assert 'بالک' in items


def test_save_category_duplicate_ignored(db):
    db.save_category('نوع کاغذ متن', 'تحریر')
    db.save_category('نوع کاغذ متن', 'تحریر')  # should not raise
    assert db.get_categories('نوع کاغذ متن').count('تحریر') == 1
