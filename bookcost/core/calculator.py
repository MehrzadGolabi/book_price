import math


class CostCalculator:

    OPTIMAL_SPECS = {
        "وزیری":      {"paper_size": "70x100", "pages_per_sheet": 32,   "zinc": "زینک 3.5 ورقی", "default_dims": None},
        "رقعی":       {"paper_size": "60x90",  "pages_per_sheet": 32,   "zinc": "زینک 2.5 ورقی", "default_dims": None},
        "رحلی کوچک": {"paper_size": "60x90",  "pages_per_sheet": 16,   "zinc": "زینک 2.5 ورقی", "default_dims": None},
        "رحلی بزرگ": {"paper_size": "70x100", "pages_per_sheet": 16,   "zinc": "زینک 3.5 ورقی", "default_dims": None},
        "جیبی":       {"paper_size": "60x90",  "pages_per_sheet": 64,   "zinc": "زینک 2.5 ورقی", "default_dims": None},
        "خشتی":       {"paper_size": "50x70",  "pages_per_sheet": 12,   "zinc": "زینک 2 ورقی",   "default_dims": None},
        "مربع":       {"paper_size": "60x90",  "pages_per_sheet": None, "zinc": "زینک 2.5 ورقی", "default_dims": (21, 21)},
        "بزرگ‌قطع":  {"paper_size": "70x100", "pages_per_sheet": None, "zinc": "زینک 3.5 ورقی", "default_dims": (24, 34)},
        "کوچک‌قطع":  {"paper_size": "60x90",  "pages_per_sheet": None, "zinc": "زینک 2.5 ورقی", "default_dims": (14, 20)},
        "سفارشی":    {"paper_size": "70x100", "pages_per_sheet": None, "zinc": "زینک 3.5 ورقی", "default_dims": (None, None)},
    }

    COST_GROUPS = {
        "خلاقیت و تحریریه": [
            "هزینه تالیف", "هزینه ترجمه", "هزینه تصویرگری", "هزینه ویرایش",
            "هزینه طراحی جلد", "هزینه مديريت آتليه", "هزینه حروفچینی و صفحه‌آرایی",
        ],
        "چاپ و مواد": [
            "هزینه زینک", "هزینه چاپ متن", "هزینه چاپ جلد",
            "هزینه کاغذ متن", "هزینه کاغذ جلد",
            "هزینه روکش سلفون", "هزینه مقوای مغذی",
        ],
        "تکمیل و صحافی": [
            "هزینه قالب لترپرس", "هزینه قالب دايكات", "هزینه خط تا",
            "هزینه ملزومات", "هزینه جلدسازی", "هزینه صحافی",
            "هزینه برش و بسته‌بندی", "هزینه حمل و نقل", "هزینه مونتاژ",
            "هزینه طلاکوبی", "هزینه UV موضعی", "هزینه برجسته‌کاری",
        ],
        "اداری و مجوزها": [
            "هزینه مجوز ارشاد", "هزینه ثبت شابک",
        ],
    }

    # None means show all fields
    BOOK_TYPE_PRESETS = {
        "شومیز ساده": [
            "هزینه تالیف", "هزینه ویرایش", "هزینه طراحی جلد",
            "هزینه مديريت آتليه", "هزینه حروفچینی و صفحه‌آرایی",
            "هزینه زینک", "هزینه چاپ متن", "هزینه چاپ جلد",
            "هزینه کاغذ متن", "هزینه کاغذ جلد", "هزینه روکش سلفون",
            "هزینه قالب لترپرس", "هزینه ملزومات", "هزینه جلدسازی",
            "هزینه صحافی", "هزینه برش و بسته‌بندی", "هزینه حمل و نقل",
            "هزینه مجوز ارشاد", "هزینه ثبت شابک",
        ],
        "گالینگور": [
            "هزینه تالیف", "هزینه ویرایش", "هزینه طراحی جلد",
            "هزینه مديريت آتليه", "هزینه حروفچینی و صفحه‌آرایی",
            "هزینه زینک", "هزینه چاپ متن", "هزینه چاپ جلد",
            "هزینه کاغذ متن", "هزینه کاغذ جلد", "هزینه مقوای مغذی",
            "هزینه قالب لترپرس", "هزینه قالب دايكات", "هزینه خط تا",
            "هزینه ملزومات", "هزینه جلدسازی", "هزینه صحافی",
            "هزینه برش و بسته‌بندی", "هزینه حمل و نقل", "هزینه مونتاژ",
            "هزینه مجوز ارشاد", "هزینه ثبت شابک",
        ],
        "کتاب مصور / رنگی": [
            "هزینه تالیف", "هزینه تصویرگری", "هزینه ویرایش", "هزینه طراحی جلد",
            "هزینه مديريت آتليه", "هزینه حروفچینی و صفحه‌آرایی",
            "هزینه زینک", "هزینه چاپ متن", "هزینه چاپ جلد",
            "هزینه کاغذ متن", "هزینه کاغذ جلد", "هزینه روکش سلفون",
            "هزینه قالب لترپرس", "هزینه ملزومات", "هزینه جلدسازی",
            "هزینه صحافی", "هزینه برش و بسته‌بندی", "هزینه حمل و نقل",
            "هزینه مجوز ارشاد", "هزینه ثبت شابک",
        ],
        "ترجمه": [
            "هزینه ترجمه", "هزینه ویرایش", "هزینه طراحی جلد",
            "هزینه مديريت آتليه", "هزینه حروفچینی و صفحه‌آرایی",
            "هزینه زینک", "هزینه چاپ متن", "هزینه چاپ جلد",
            "هزینه کاغذ متن", "هزینه کاغذ جلد", "هزینه روکش سلفون",
            "هزینه قالب لترپرس", "هزینه ملزومات", "هزینه جلدسازی",
            "هزینه صحافی", "هزینه برش و بسته‌بندی", "هزینه حمل و نقل",
            "هزینه مجوز ارشاد", "هزینه ثبت شابک",
        ],
        "ویژه / لوکس": [
            "هزینه تالیف", "هزینه تصویرگری", "هزینه ویرایش", "هزینه طراحی جلد",
            "هزینه مديريت آتليه", "هزینه حروفچینی و صفحه‌آرایی",
            "هزینه زینک", "هزینه چاپ متن", "هزینه چاپ جلد",
            "هزینه کاغذ متن", "هزینه کاغذ جلد",
            "هزینه روکش سلفون", "هزینه مقوای مغذی",
            "هزینه قالب لترپرس", "هزینه قالب دايكات", "هزینه خط تا",
            "هزینه ملزومات", "هزینه جلدسازی", "هزینه صحافی",
            "هزینه برش و بسته‌بندی", "هزینه حمل و نقل", "هزینه مونتاژ",
            "هزینه طلاکوبی", "هزینه UV موضعی", "هزینه برجسته‌کاری",
            "هزینه مجوز ارشاد", "هزینه ثبت شابک",
        ],
        "سفارشی": None,
    }

    ZINC_DIMS = {
        "زینک GTO":      (35, 50),
        "زینک 2 ورقی":   (50, 70),
        "زینک 2.5 ورقی": (60, 90),
        "زینک 3.5 ورقی": (70, 100),
        "زینک 4.5 ورقی": (90, 120),
    }

    BOOK_PAGE_DIMS = {
        "وزیری":     (17.0, 24.0),
        "رقعی":      (14.5, 21.0),
        "رحلی کوچک": (21.0, 28.5),
        "رحلی بزرگ": (24.0, 34.0),
        "جیبی":      (11.0, 18.0),
        "خشتی":      (21.0, 21.0),
        "مربع":      (21.0, 21.0),
        "بزرگ‌قطع":  (24.0, 34.0),
        "کوچک‌قطع":  (14.0, 20.0),
        "سفارشی":    (None, None),
    }

    def compute_auto_costs(
        self,
        form_matn: int, sides_matn: int,
        form_jeld: int, sides_jeld: int,
        tiraj: int, waste_pct: float,
        unit_price_matn: float, unit_price_jeld: float,
        text_colors: int, cover_colors: int,
        zinc_price_matn: float, zinc_price_jeld: float,
    ) -> dict:
        """Returns {هزینه کاغذ متن, هزینه کاغذ جلد, هزینه زینک} as computed values."""
        sides_matn = max(1, sides_matn)
        sides_jeld = max(1, sides_jeld)
        waste = 1.0 + waste_pct / 100.0
        paper_matn = (form_matn / sides_matn) * tiraj * waste * unit_price_matn
        paper_jeld = (form_jeld / sides_jeld) * tiraj * waste * unit_price_jeld
        zinc_cost = (form_matn * text_colors * zinc_price_matn) + (form_jeld * cover_colors * zinc_price_jeld)
        return {
            'هزینه کاغذ متن': paper_matn,
            'هزینه کاغذ جلد': paper_jeld,
            'هزینه زینک':     zinc_cost,
        }

    def compute_totals(self, cost_values: dict, royalty_pct: float, tiraj: int) -> dict:
        """Returns {total_cost, cost_per_book}. cost_per_book is 0 if tiraj is 0."""
        total = sum(cost_values.values())
        final = total * (1.0 + royalty_pct / 100.0)
        cost_per_book = final / tiraj if tiraj > 0 else 0.0
        return {'total_cost': final, 'cost_per_book': cost_per_book}

    def compute_optimal_orientation(
        self, book_w: float, book_h: float, paper_w: float, paper_h: float
    ) -> tuple:
        """Returns ('portrait'|'landscape', pages_per_sheet)."""
        if book_w <= 0 or book_h <= 0:
            return 'portrait', 0
        portrait  = int((paper_w // book_w) * (paper_h // book_h))
        landscape = int((paper_w // book_h) * (paper_h // book_w))
        if landscape >= portrait:
            return 'landscape', landscape * 2
        return 'portrait', portrait * 2

    def suggest_layout(
        self, qate: str, total_pages: int,
        book_w: float = 0.0, book_h: float = 0.0,
        paper_size_str: str = '',
    ) -> dict | None:
        """Returns a layout suggestion dict, or None if qate is unrecognised.

        Dict keys: is_custom, pages_per_sheet, sheets_per_book, paper_size,
                   zinc, orientation (None|'portrait'|'landscape'),
                   orientation_label (str), default_dims.
        """
        specs = self.OPTIMAL_SPECS.get(qate)
        if specs is None:
            return None

        is_custom = specs['pages_per_sheet'] is None
        paper_size = specs['paper_size'].replace('x', '×')
        zinc = specs.get('zinc', '')
        orientation = None
        orientation_label = ''

        if not is_custom:
            pages_per_sheet = specs['pages_per_sheet']
        else:
            if book_w > 0 and book_h > 0 and paper_size_str:
                try:
                    pw, ph = map(float, paper_size_str.replace('×', 'x').split('x'))
                except ValueError:
                    return None
                orientation, pages_per_sheet = self.compute_optimal_orientation(book_w, book_h, pw, ph)
                alt = 'portrait' if orientation == 'landscape' else 'landscape'
                if orientation == 'landscape':
                    alt_pages = int((pw // book_w) * (ph // book_h)) * 2
                else:
                    alt_pages = int((pw // book_h) * (ph // book_w)) * 2
                saving = round((pages_per_sheet - alt_pages) / alt_pages * 100) if alt_pages > 0 else 0
                label_map = {'landscape': 'افقی', 'portrait': 'عمودی'}
                orientation_label = f'جهت: {label_map[orientation]} — {pages_per_sheet} صفحه در ورق'
                if saving > 0:
                    orientation_label += f' ({saving}٪ بهتر از {label_map[alt]})'
            else:
                pages_per_sheet = 1

        sheets_per_book = math.ceil(total_pages / pages_per_sheet) if pages_per_sheet > 0 else 0

        return {
            'is_custom':         is_custom,
            'pages_per_sheet':   pages_per_sheet,
            'sheets_per_book':   sheets_per_book,
            'paper_size':        paper_size,
            'zinc':              zinc,
            'orientation':       orientation,
            'orientation_label': orientation_label,
            'default_dims':      specs.get('default_dims'),
        }

    def compute_paper_unit_price(
        self, formula_idx: int,
        height: float = 0.0, length: float = 0.0, weight: float = 0.0,
        price: float = 0.0, count: int = 0,
    ) -> float:
        """Formula 0: dims×weight×price. Formula 1: bundle price/count. Formula 2: manual."""
        if formula_idx == 0:
            if height > 0 and length > 0 and weight > 0:
                return ((height * length) * weight / 10_000) * (price / 1_000)
        elif formula_idx == 1:
            if count > 0:
                return price / count
        else:
            return price
        return 0.0
