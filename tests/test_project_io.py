"""Tests for single-project JSON import/export and database backup helpers."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
import pytest

from bookcost.core.db import BookDatabase, DETAIL_COLUMNS, is_valid_database_file
from bookcost.core.project_io import (
    FORMAT_NAME, export_project, import_project, load_project_file, save_project_file,
)


@pytest.fixture
def db():
    d = BookDatabase(':memory:')
    d.connect()
    return d


def _make_project(db, title='کتاب نمونه'):
    p = {'title': title, 'subtitle': 'زیرعنوان', 'creation_date': '1405/04/22',
         'qate': 'وزیری', 'tiraj': 2000, 'royalty_percent': 10.0,
         'total_cost': 113_135_000.0, 'single_book_cost': 56_568.0}
    d = {c: None for c in DETAIL_COLUMNS}
    d.update({'noeh_kaghaz_matn': 'تحریر ۸۰ گرم', 'form_matn': 10,
              'is_double_sided_matn': 1, 'zinc_size_matn': 'زینک 3.5 ورقی',
              'hazineh_talif': 5_000_000.0, 'hazineh_sahafi': 1_200_000.0,
              'total_pages': 160, 'waste_percent': 5.0,
              'book_type_preset': 'شومیز ساده', 'pricing_multiplier': 2.5,
              'distribution_percent': 35.0})
    return db.insert_project(p, d)


def test_export_import_roundtrip(db):
    pid = _make_project(db)
    data = export_project(db, pid)
    assert data['format'] == FORMAT_NAME
    assert data['project']['title'] == 'کتاب نمونه'
    assert data['details']['hazineh_talif'] == 5_000_000.0

    new_id = import_project(db, data)
    assert new_id != pid
    orig, copy = dict(db.get_project(pid)), dict(db.get_project(new_id))
    orig.pop('id'), copy.pop('id')
    assert orig == copy
    od, cd = dict(db.get_project_details(pid)), dict(db.get_project_details(new_id))
    od.pop('project_id'), cd.pop('project_id')
    assert od == cd


def test_import_registers_type_categories(db):
    pid = _make_project(db)
    data = export_project(db, pid)
    import_project(db, data)
    assert 'تحریر ۸۰ گرم' in db.get_categories('نوع کاغذ متن')


def test_file_roundtrip(db, tmp_path):
    pid = _make_project(db)
    path = tmp_path / 'کتاب نمونه.json'
    save_project_file(db, pid, str(path))
    raw = json.loads(path.read_text(encoding='utf-8'))
    assert raw['project']['tiraj'] == 2000

    new_id = load_project_file(db, str(path))
    assert db.get_project(new_id)['title'] == 'کتاب نمونه'


def test_import_rejects_wrong_format(db):
    with pytest.raises(ValueError):
        import_project(db, {'format': 'something-else', 'project': {'title': 'x'}})
    with pytest.raises(ValueError):
        import_project(db, {'format': FORMAT_NAME, 'project': {'title': ''}})
    with pytest.raises(ValueError):
        import_project(db, ['not', 'a', 'dict'])


def test_import_ignores_unknown_and_missing_columns(db):
    data = {'format': FORMAT_NAME, 'version': 99,
            'project': {'title': 'کتاب آینده', 'tiraj': 500,
                        'column_from_the_future': 'ignored'},
            'details': {'hazineh_talif': 1000.0, 'unknown_cost': 5.0}}
    new_id = import_project(db, data)
    row = db.get_project(new_id)
    assert row['title'] == 'کتاب آینده'
    details = db.get_project_details(new_id)
    assert details['hazineh_talif'] == 1000.0


def test_export_missing_project_raises(db):
    with pytest.raises(ValueError):
        export_project(db, 12345)


def test_backup_and_validate(tmp_path):
    src = BookDatabase(str(tmp_path / 'live.db'))
    src.connect()
    pid = _make_project(src)
    backup = tmp_path / 'backup.db'
    src.backup_to(str(backup))

    assert is_valid_database_file(str(backup))
    assert not is_valid_database_file(str(tmp_path / 'nope.db'))
    plain = tmp_path / 'plain.txt'
    plain.write_text('not a database')
    assert not is_valid_database_file(str(plain))

    restored = BookDatabase(str(backup))
    restored.connect()
    assert restored.get_project(pid)['title'] == 'کتاب نمونه'


def test_validate_handles_tricky_paths(tmp_path):
    """Persian names, spaces, '#' and '%' in the path must not break validation."""
    src = BookDatabase(str(tmp_path / 'live.db'))
    src.connect()
    tricky_dir = tmp_path / 'پشتیبان #1 % تست'
    tricky_dir.mkdir()
    dest = tricky_dir / 'پشتیبان شهرقلم #2.db'
    src.backup_to(str(dest))
    assert is_valid_database_file(str(dest))
