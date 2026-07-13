import sqlite3


SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_name TEXT NOT NULL,
        item_value TEXT NOT NULL,
        UNIQUE(category_name, item_value)
    );

    CREATE TABLE IF NOT EXISTS paper_calculations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        paper_type TEXT NOT NULL,
        formula_type TEXT NOT NULL,
        weight REAL,
        height REAL,
        length REAL,
        bundle_count INTEGER,
        bundle_weight REAL,
        price REAL,
        unit_price REAL
    );

    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        subtitle TEXT,
        creation_date DATE NOT NULL,
        qate TEXT,
        tiraj INTEGER NOT NULL,
        royalty_percent REAL,
        total_cost REAL,
        single_book_cost REAL
    );

    CREATE TABLE IF NOT EXISTS project_details (
        project_id INTEGER PRIMARY KEY,
        noeh_kaghaz_matn TEXT, noeh_chap_matn TEXT, noeh_rang_matn TEXT, noeh_zink_matn TEXT,
        noeh_kaghaz_jeld TEXT, noeh_chap_jeld TEXT, noeh_rang_jeld TEXT, noeh_zink_jeld TEXT,
        form_matn INTEGER, is_double_sided_matn BOOLEAN, color_count_matn INTEGER, zinc_size_matn TEXT,
        form_jeld INTEGER, is_double_sided_jeld BOOLEAN, color_count_jeld INTEGER, zinc_size_jeld TEXT,
        unit_price_paper_matn REAL, unit_price_paper_jeld REAL, unit_price_zinc REAL,
        waste_percent REAL DEFAULT 5,
        book_width REAL, book_height REAL, paper_size TEXT, orientation TEXT,
        pages_per_sheet INTEGER, total_pages INTEGER DEFAULT 0,
        hazineh_talif REAL DEFAULT 0, hazineh_tarjomeh REAL DEFAULT 0,
        hazineh_tasvir REAL DEFAULT 0, hazineh_virayesh REAL DEFAULT 0,
        hazineh_tarahi_jeld REAL DEFAULT 0, hazineh_modiriat_atelieh REAL DEFAULT 0,
        hazineh_zink REAL DEFAULT 0, hazineh_chap_matn REAL DEFAULT 0,
        hazineh_chap_jeld REAL DEFAULT 0, hazineh_kaghaz_matn REAL DEFAULT 0,
        hazineh_kaghaz_jeld REAL DEFAULT 0, hazineh_rokesh_salfon REAL DEFAULT 0,
        hazineh_moghava_maghzi REAL DEFAULT 0, hazineh_ghaleb_letterpress REAL DEFAULT 0,
        hazineh_ghaleb_diecut REAL DEFAULT 0, hazineh_khat_ta REAL DEFAULT 0,
        hazineh_malzomat REAL DEFAULT 0, hazineh_jeldsazi REAL DEFAULT 0,
        hazineh_sahafi REAL DEFAULT 0, hazineh_boresh_bastebandi REAL DEFAULT 0,
        hazineh_haml_naghl REAL DEFAULT 0, hazineh_montaj REAL DEFAULT 0,
        hazineh_horoofchini REAL DEFAULT 0, hazineh_mojawwez_ershad REAL DEFAULT 0,
        hazineh_shabok REAL DEFAULT 0, hazineh_talakoobi REAL DEFAULT 0,
        hazineh_uv_mowzei REAL DEFAULT 0, hazineh_barjasteh REAL DEFAULT 0,
        book_type_preset TEXT DEFAULT 'شومیز ساده',
        pricing_multiplier REAL DEFAULT 2.5,
        distribution_percent REAL DEFAULT 35.0,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS default_cost_mappings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_name TEXT NOT NULL,
        item_value TEXT NOT NULL,
        target_cost_field TEXT NOT NULL,
        default_cost REAL NOT NULL
    );

    CREATE TABLE IF NOT EXISTS zinc_prices (
        zinc_size TEXT PRIMARY KEY,
        unit_price REAL DEFAULT 0
    );
"""

_MIGRATION_COLS = [
    ("form_matn", "INTEGER"),
    ("is_double_sided_matn", "BOOLEAN"),
    ("color_count_matn", "INTEGER"),
    ("zinc_size_matn", "TEXT"),
    ("form_jeld", "INTEGER"),
    ("is_double_sided_jeld", "BOOLEAN"),
    ("color_count_jeld", "INTEGER"),
    ("zinc_size_jeld", "TEXT"),
    ("unit_price_paper_matn", "REAL"),
    ("unit_price_paper_jeld", "REAL"),
    ("unit_price_zinc", "REAL"),
    ("waste_percent", "REAL DEFAULT 5"),
    ("book_width", "REAL"),
    ("book_height", "REAL"),
    ("paper_size", "TEXT"),
    ("orientation", "TEXT"),
    ("pages_per_sheet", "INTEGER"),
    ("total_pages", "INTEGER DEFAULT 0"),
    ("hazineh_horoofchini", "REAL DEFAULT 0"),
    ("hazineh_mojawwez_ershad", "REAL DEFAULT 0"),
    ("hazineh_shabok", "REAL DEFAULT 0"),
    ("hazineh_talakoobi", "REAL DEFAULT 0"),
    ("hazineh_uv_mowzei", "REAL DEFAULT 0"),
    ("hazineh_barjasteh", "REAL DEFAULT 0"),
    ("book_type_preset", "TEXT DEFAULT 'شومیز ساده'"),
    ("pricing_multiplier", "REAL DEFAULT 2.5"),
    ("distribution_percent", "REAL DEFAULT 35.0"),
]

_ZINC_SIZES = [
    "زینک 2 ورقی", "زینک 2.5 ورقی", "زینک 3.5 ورقی",
    "زینک 4.5 ورقی", "زینک GTO",
]

# Columns of the projects table that carry data (everything except id)
PROJECT_COLUMNS = [
    'title', 'subtitle', 'creation_date', 'qate', 'tiraj',
    'royalty_percent', 'total_cost', 'single_book_cost',
]

# Columns of project_details written by _insert_details (everything except project_id)
DETAIL_COLUMNS = [
    'noeh_kaghaz_matn', 'noeh_chap_matn', 'noeh_rang_matn', 'noeh_zink_matn',
    'noeh_kaghaz_jeld', 'noeh_chap_jeld', 'noeh_rang_jeld', 'noeh_zink_jeld',
    'form_matn', 'is_double_sided_matn', 'color_count_matn', 'zinc_size_matn',
    'form_jeld', 'is_double_sided_jeld', 'color_count_jeld', 'zinc_size_jeld',
    'unit_price_paper_matn', 'unit_price_paper_jeld', 'unit_price_zinc', 'waste_percent',
    'book_width', 'book_height', 'paper_size', 'orientation', 'pages_per_sheet',
    'total_pages',
    'hazineh_talif', 'hazineh_tarjomeh', 'hazineh_tasvir', 'hazineh_virayesh',
    'hazineh_tarahi_jeld', 'hazineh_modiriat_atelieh', 'hazineh_zink',
    'hazineh_chap_matn', 'hazineh_chap_jeld', 'hazineh_kaghaz_matn',
    'hazineh_kaghaz_jeld', 'hazineh_rokesh_salfon', 'hazineh_moghava_maghzi',
    'hazineh_ghaleb_letterpress', 'hazineh_ghaleb_diecut', 'hazineh_khat_ta',
    'hazineh_malzomat', 'hazineh_jeldsazi', 'hazineh_sahafi',
    'hazineh_boresh_bastebandi', 'hazineh_haml_naghl', 'hazineh_montaj',
    'hazineh_horoofchini', 'hazineh_mojawwez_ershad', 'hazineh_shabok',
    'hazineh_talakoobi', 'hazineh_uv_mowzei', 'hazineh_barjasteh',
    'book_type_preset', 'pricing_multiplier', 'distribution_percent',
]

# Tables a valid database (or backup) must contain
REQUIRED_TABLES = {
    'projects', 'project_details', 'categories', 'paper_calculations',
    'default_cost_mappings', 'zinc_prices',
}


def is_valid_database_file(path: str) -> bool:
    """True if `path` is an SQLite database containing all required tables."""
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            names = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            conn.close()
        return REQUIRED_TABLES <= names
    except sqlite3.Error:
        return False


class BookDatabase:
    def __init__(self, path: str):
        self._path = path
        self._conn: sqlite3.Connection | None = None

    def connect(self):
        """Create schema, seed zinc defaults, run column migrations. Raises sqlite3.Error on failure."""
        self._conn = sqlite3.connect(self._path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        cur = self._conn.cursor()
        cur.executescript(SCHEMA_SQL)
        self._conn.commit()

        for zs in _ZINC_SIZES:
            cur.execute(
                "INSERT OR IGNORE INTO zinc_prices (zinc_size, unit_price) VALUES (?, 0)", (zs,)
            )
        self._conn.commit()

        for col_name, col_def in _MIGRATION_COLS:
            try:
                cur.execute(f"ALTER TABLE project_details ADD COLUMN {col_name} {col_def}")
                self._conn.commit()
            except sqlite3.OperationalError:
                pass  # column already exists

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def backup_to(self, dest_path: str):
        """Writes a consistent copy of the live database to `dest_path`."""
        dest = sqlite3.connect(dest_path)
        try:
            self._conn.backup(dest)
        finally:
            dest.close()

    # ── Projects ──────────────────────────────────────────────────────────

    def get_projects(self, filter_text: str = '') -> list:
        cur = self._conn.cursor()
        if filter_text:
            cur.execute(
                "SELECT id, title, creation_date, tiraj FROM projects "
                "WHERE title LIKE ? ORDER BY id DESC",
                (f'%{filter_text}%',)
            )
        else:
            cur.execute("SELECT id, title, creation_date, tiraj FROM projects ORDER BY id DESC")
        return cur.fetchall()

    def get_project(self, project_id: int):
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        return cur.fetchone()

    def get_project_details(self, project_id: int):
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM project_details WHERE project_id = ?", (project_id,))
        return cur.fetchone()

    def insert_project(self, p: dict, d: dict) -> int:
        """Insert into projects + project_details. Returns new project id."""
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO projects (title, subtitle, creation_date, qate, tiraj, "
            "royalty_percent, total_cost, single_book_cost) VALUES (?,?,?,?,?,?,?,?)",
            (p['title'], p.get('subtitle'), p['creation_date'], p.get('qate'),
             p['tiraj'], p.get('royalty_percent', 0), p.get('total_cost', 0),
             p.get('single_book_cost', 0))
        )
        project_id = cur.lastrowid
        self._insert_details(cur, project_id, d)
        self._conn.commit()
        return project_id

    def update_project(self, project_id: int, p: dict, d: dict):
        """Update projects + project_details rows in place."""
        cur = self._conn.cursor()
        cur.execute(
            "UPDATE projects SET title=?, subtitle=?, creation_date=?, qate=?, "
            "tiraj=?, royalty_percent=?, total_cost=?, single_book_cost=? WHERE id=?",
            (p['title'], p.get('subtitle'), p['creation_date'], p.get('qate'),
             p['tiraj'], p.get('royalty_percent', 0), p.get('total_cost', 0),
             p.get('single_book_cost', 0), project_id)
        )
        cur.execute("DELETE FROM project_details WHERE project_id = ?", (project_id,))
        self._insert_details(cur, project_id, d)
        self._conn.commit()

    def _insert_details(self, cur, project_id: int, d: dict):
        """Insert a project_details row. d keys match DETAIL_COLUMNS names."""
        placeholders = ', '.join(['?'] * (len(DETAIL_COLUMNS) + 1))
        col_list = 'project_id, ' + ', '.join(DETAIL_COLUMNS)
        values = [project_id] + [d.get(c) for c in DETAIL_COLUMNS]
        cur.execute(
            f"INSERT INTO project_details ({col_list}) VALUES ({placeholders})",
            values
        )

    def delete_project(self, project_id: int):
        cur = self._conn.cursor()
        cur.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        self._conn.commit()

    # ── Categories ────────────────────────────────────────────────────────

    def save_category(self, category_name: str, item_value: str):
        cur = self._conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO categories (category_name, item_value) VALUES (?, ?)",
            (category_name, item_value)
        )
        self._conn.commit()

    def get_categories(self, category_name: str) -> list:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT item_value FROM categories WHERE category_name = ? ORDER BY item_value",
            (category_name,)
        )
        return [row['item_value'] for row in cur.fetchall()]

    # ── Zinc prices ───────────────────────────────────────────────────────

    def get_zinc_price(self, zinc_size: str) -> float:
        cur = self._conn.cursor()
        cur.execute("SELECT unit_price FROM zinc_prices WHERE zinc_size = ?", (zinc_size,))
        row = cur.fetchone()
        return float(row['unit_price']) if row else 0.0

    def get_all_zinc_prices(self) -> list:
        cur = self._conn.cursor()
        cur.execute("SELECT zinc_size, unit_price FROM zinc_prices ORDER BY zinc_size")
        return cur.fetchall()

    def save_zinc_price(self, zinc_size: str, price: float):
        cur = self._conn.cursor()
        cur.execute(
            "UPDATE zinc_prices SET unit_price = ? WHERE zinc_size = ?", (price, zinc_size)
        )
        self._conn.commit()

    # ── Paper calculations ────────────────────────────────────────────────

    def get_paper_calculations(self) -> list:
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM paper_calculations ORDER BY id DESC")
        return cur.fetchall()

    def insert_paper_calculation(self, data: dict) -> int:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO paper_calculations "
            "(paper_type, formula_type, weight, height, length, "
            "bundle_count, bundle_weight, price, unit_price) VALUES (?,?,?,?,?,?,?,?,?)",
            (data['paper_type'], data['formula_type'], data.get('weight', 0),
             data.get('height', 0), data.get('length', 0), data.get('bundle_count', 0),
             data.get('bundle_weight', 0), data.get('price', 0), data['unit_price'])
        )
        self._conn.commit()
        return cur.lastrowid

    def update_paper_calculation(self, calc_id: int, data: dict):
        cur = self._conn.cursor()
        cur.execute(
            "UPDATE paper_calculations SET paper_type=?, formula_type=?, weight=?, height=?, "
            "length=?, bundle_count=?, bundle_weight=?, price=?, unit_price=? WHERE id=?",
            (data['paper_type'], data['formula_type'], data.get('weight', 0),
             data.get('height', 0), data.get('length', 0), data.get('bundle_count', 0),
             data.get('bundle_weight', 0), data.get('price', 0), data['unit_price'], calc_id)
        )
        self._conn.commit()

    def delete_paper_calculation(self, calc_id: int):
        cur = self._conn.cursor()
        cur.execute("DELETE FROM paper_calculations WHERE id = ?", (calc_id,))
        self._conn.commit()

    # ── Default cost mappings ─────────────────────────────────────────────

    def get_default_cost_mappings(self) -> list:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id, category_name, item_value, target_cost_field, default_cost "
            "FROM default_cost_mappings ORDER BY category_name, item_value"
        )
        return cur.fetchall()

    def get_default_cost(self, category: str, value: str):
        cur = self._conn.cursor()
        cur.execute(
            "SELECT target_cost_field, default_cost FROM default_cost_mappings "
            "WHERE category_name = ? AND item_value = ?",
            (category, value)
        )
        return cur.fetchone()

    def get_default_costs_batch(self, items: list) -> list:
        """items: list of (category_name, item_value) tuples. Returns all matching rows."""
        if not items:
            return []
        conditions = ' OR '.join(['(category_name = ? AND item_value = ?)'] * len(items))
        params = []
        for cat, val in items:
            params.extend([cat, val])
        cur = self._conn.cursor()
        cur.execute(
            f"SELECT category_name, item_value, target_cost_field, default_cost "
            f"FROM default_cost_mappings WHERE {conditions}",
            params
        )
        return cur.fetchall()

    def upsert_default_mapping(self, category: str, value: str, field: str, cost: float):
        """Insert or update a mapping identified by (category, value)."""
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id FROM default_cost_mappings WHERE category_name=? AND item_value=?",
            (category, value)
        )
        existing = cur.fetchone()
        if existing:
            cur.execute(
                "UPDATE default_cost_mappings SET target_cost_field=?, default_cost=? WHERE id=?",
                (field, cost, existing['id'])
            )
        else:
            cur.execute(
                "INSERT INTO default_cost_mappings "
                "(category_name, item_value, target_cost_field, default_cost) VALUES (?,?,?,?)",
                (category, value, field, cost)
            )
        self._conn.commit()

    def insert_default_mapping(self, category: str, value: str, field: str, cost: float):
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO default_cost_mappings "
            "(category_name, item_value, target_cost_field, default_cost) VALUES (?,?,?,?)",
            (category, value, field, cost)
        )
        self._conn.commit()

    def update_default_mapping(self, mapping_id: int, category: str, value: str,
                                field: str, cost: float):
        cur = self._conn.cursor()
        cur.execute(
            "UPDATE default_cost_mappings SET category_name=?, item_value=?, "
            "target_cost_field=?, default_cost=? WHERE id=?",
            (category, value, field, cost, mapping_id)
        )
        self._conn.commit()

    def delete_default_mapping(self, mapping_id: int):
        cur = self._conn.cursor()
        cur.execute("DELETE FROM default_cost_mappings WHERE id = ?", (mapping_id,))
        self._conn.commit()
