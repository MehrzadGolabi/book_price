"""Single source of truth for the mapping between Persian display names used
in the UI and the romanized column names of the ``project_details`` table.

Adding a new cost field requires touching exactly three places:
  1. ``CostCalculator.COST_GROUPS`` (which section it appears in)
  2. ``COST_FIELD_COLUMNS`` here
  3. ``SCHEMA_SQL`` + ``_MIGRATION_COLS`` in ``core/db.py``
``tests/test_fields.py`` asserts these stay in sync.
"""

# Persian cost-field display name → project_details column
COST_FIELD_COLUMNS = {
    'هزینه تالیف':                 'hazineh_talif',
    'هزینه ترجمه':                 'hazineh_tarjomeh',
    'هزینه تصویرگری':              'hazineh_tasvir',
    'هزینه ویرایش':                'hazineh_virayesh',
    'هزینه طراحی جلد':             'hazineh_tarahi_jeld',
    'هزینه مديريت آتليه':          'hazineh_modiriat_atelieh',
    'هزینه حروفچینی و صفحه‌آرایی': 'hazineh_horoofchini',
    'هزینه زینک':                  'hazineh_zink',
    'هزینه چاپ متن':               'hazineh_chap_matn',
    'هزینه چاپ جلد':               'hazineh_chap_jeld',
    'هزینه کاغذ متن':              'hazineh_kaghaz_matn',
    'هزینه کاغذ جلد':              'hazineh_kaghaz_jeld',
    'هزینه روکش سلفون':            'hazineh_rokesh_salfon',
    'هزینه مقوای مغذی':            'hazineh_moghava_maghzi',
    'هزینه قالب لترپرس':           'hazineh_ghaleb_letterpress',
    'هزینه خدمات لترپرس':          'hazineh_khadamat_letterpress',
    'هزینه قالب دايكات':           'hazineh_ghaleb_diecut',
    'هزینه خدمات دايكات':          'hazineh_khadamat_diecut',
    'هزینه خط تا':                 'hazineh_khat_ta',
    'هزینه فیلم':                  'hazineh_film',
    'هزینه کلیشه':                 'hazineh_kelishe',
    'هزینه ملزومات':               'hazineh_malzomat',
    'هزینه جلدسازی':               'hazineh_jeldsazi',
    'هزینه صحافی':                 'hazineh_sahafi',
    'هزینه برش و بسته‌بندی':       'hazineh_boresh_bastebandi',
    'هزینه حمل و نقل':             'hazineh_haml_naghl',
    'هزینه مونتاژ':                'hazineh_montaj',
    'هزینه طلاکوبی':               'hazineh_talakoobi',
    'هزینه UV موضعی':              'hazineh_uv_mowzei',
    'هزینه برجسته‌کاری':           'hazineh_barjasteh',
    'هزینه مجوز ارشاد':            'hazineh_mojawwez_ershad',
    'هزینه ثبت شابک':              'hazineh_shabok',
}

# Persian dynamic-type category → project_details column
TYPE_FIELD_COLUMNS = {
    'نوع کاغذ متن': 'noeh_kaghaz_matn',
    'نوع چاپ متن':  'noeh_chap_matn',
    'نوع رنگ متن':  'noeh_rang_matn',
    'نوع زینک متن': 'noeh_zink_matn',
    'نوع کاغذ جلد': 'noeh_kaghaz_jeld',
    'نوع چاپ جلد':  'noeh_chap_jeld',
    'نوع رنگ جلد':  'noeh_rang_jeld',
    'نوع زینک جلد': 'noeh_zink_jeld',
}

# Categories offered by editable type combos (order matters in the UI)
DYNAMIC_TYPE_CATEGORIES = list(TYPE_FIELD_COLUMNS.keys())

# Cost fields whose values are computed automatically (read-only in the UI)
AUTO_COST_FIELDS = frozenset({'هزینه زینک', 'هزینه کاغذ متن', 'هزینه کاغذ جلد'})

# ── Per-field default calculation type (item 6) ───────────────────────────
# Only the exceptions are listed; everything else defaults to FIXED. Users can
# override per field via the calc-type combo. Values are CalcType .value
# strings to avoid importing cost_model here (keeps this module dependency-free).
#
#   per_tiraj → cost is per printed copy (binding, finishing, consumables)
DEFAULT_CALC_TYPES = {
    'هزینه صحافی':      'per_tiraj',
    'هزینه جلدسازی':    'per_tiraj',
    'هزینه ملزومات':    'per_tiraj',
    'هزینه خدمات دايكات': 'per_tiraj',
    'هزینه برش و بسته‌بندی': 'per_tiraj',
}


def default_calc_type(field_name: str) -> str:
    """CalcType.value for a built-in cost field (FIXED unless overridden)."""
    return DEFAULT_CALC_TYPES.get(field_name, 'fixed')

# ── Default-price ("قیمت پایه") categorization ────────────────────────────
#
# Prices live where their data lives:
#   کاغذ  → the paper-price library (paper_calculations), auto-filled into
#           the paper unit-price fields/rows
#   زینک  → the zinc_prices table
#   type-dependent services → default_cost_mappings rows constrained below
#   everything else → "general" defaults (GENERAL_CATEGORY) applied directly
#           to their cost field by دریافت قیمت‌های پایه

# Pseudo-category for defaults not tied to any type value
GENERAL_CATEGORY = 'عمومی'

# Type categories that may carry a default, and the only cost fields each
# one is allowed to target (kept small on purpose — paper and zinc types are
# priced elsewhere, and the auto-computed fields can't take defaults)
CATEGORY_TARGET_FIELDS = {
    'نوع چاپ متن': ['هزینه چاپ متن'],
    'نوع رنگ متن': ['هزینه چاپ متن'],
    'نوع چاپ جلد': ['هزینه چاپ جلد'],
    'نوع رنگ جلد': ['هزینه چاپ جلد'],
}
