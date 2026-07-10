"""Consistency checks between the field mappings, COST_GROUPS, and the DB schema.

These guard the three-place contract documented in bookcost/core/fields.py:
a new cost field must appear in COST_GROUPS, COST_FIELD_COLUMNS, and the
project_details schema, or saving/loading silently drops it.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from bookcost.core.calculator import CostCalculator
from bookcost.core.db import BookDatabase
from bookcost.core.fields import (
    AUTO_COST_FIELDS, COST_FIELD_COLUMNS, DYNAMIC_TYPE_CATEGORIES, TYPE_FIELD_COLUMNS,
)


def _schema_columns():
    db = BookDatabase(':memory:')
    db.connect()
    cur = db._conn.execute("PRAGMA table_info(project_details)")
    return {row['name'] for row in cur.fetchall()}


def test_cost_groups_match_field_columns():
    group_fields = {f for fields in CostCalculator.COST_GROUPS.values() for f in fields}
    assert group_fields == set(COST_FIELD_COLUMNS.keys())


def test_cost_columns_exist_in_schema():
    cols = _schema_columns()
    missing = set(COST_FIELD_COLUMNS.values()) - cols
    assert not missing, f"columns missing from project_details schema: {missing}"


def test_type_columns_exist_in_schema():
    cols = _schema_columns()
    missing = set(TYPE_FIELD_COLUMNS.values()) - cols
    assert not missing, f"columns missing from project_details schema: {missing}"


def test_auto_cost_fields_are_known():
    assert AUTO_COST_FIELDS <= set(COST_FIELD_COLUMNS.keys())


def test_presets_reference_known_fields():
    known = set(COST_FIELD_COLUMNS.keys())
    for preset, fields in CostCalculator.BOOK_TYPE_PRESETS.items():
        if fields is None:
            continue
        unknown = set(fields) - known
        assert not unknown, f"preset {preset} references unknown fields: {unknown}"


def test_dynamic_type_categories_order():
    assert len(DYNAMIC_TYPE_CATEGORIES) == 8
    assert DYNAMIC_TYPE_CATEGORIES[0] == 'نوع کاغذ متن'
