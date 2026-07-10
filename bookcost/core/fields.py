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
    'هزینه قالب دايكات':           'hazineh_ghaleb_diecut',
    'هزینه خط تا':                 'hazineh_khat_ta',
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
