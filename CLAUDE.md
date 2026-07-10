# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A Persian-language (Farsi, RTL) PySide6 desktop app for estimating and managing book printing costs for the publisher انتشارات شهرقلم. All UI strings are Persian and the entire window uses `Qt.RightToLeft` layout direction.

## Commands

```powershell
# Setup (the checked-in .venv is bare — install deps first)
.venv\Scripts\python.exe -m pip install -r requirements.txt pytest

# Run the app
.venv\Scripts\python.exe main.py

# Run tests (pure-logic + offscreen UI smoke tests; no display needed)
.venv\Scripts\python.exe -m pytest tests/ -q

# Run a single test
.venv\Scripts\python.exe -m pytest tests/test_calculator.py::test_auto_costs_zinc -q
```

Packaging: PyInstaller builds `BookCostCalculator.exe`, then `book_setup.iss` (Inno Setup) makes the installer. `bookcost/resources.py` locates resource files: frozen mode checks the PyInstaller bundle (`sys._MEIPASS`) then the exe directory; dev mode uses `resources/`. `config.ini` is read from next to the exe (frozen) or the repo root (dev).

## Architecture

Everything lives in the `bookcost` package; `main.py` is only the entry point. Layering is strict — `core/` and `reporting/` never import Qt:

- **[bookcost/core/](bookcost/core/)** — pure logic:
  - [calculator.py](bookcost/core/calculator.py) — `CostCalculator`: cost math plus domain constants (`OPTIMAL_SPECS` per trim-size/قطع, `ZINC_DIMS`, `BOOK_PAGE_DIMS`, `COST_GROUPS` — the 28 cost fields in 4 sections, `BOOK_TYPE_PRESETS` — visible fields per book type, `None` = show all).
  - [pricing.py](bookcost/core/pricing.py) — cover price, net revenue, break-even, breakdown, profit scenarios.
  - [db.py](bookcost/core/db.py) — `BookDatabase` (sqlite3). Schema in `SCHEMA_SQL`; migrations are additive only: new `project_details` columns are appended to both `SCHEMA_SQL` and `_MIGRATION_COLS` (try/except `ALTER TABLE` on connect).
  - [fields.py](bookcost/core/fields.py) — single source of truth mapping Persian display names ↔ `project_details` columns (`COST_FIELD_COLUMNS`, `TYPE_FIELD_COLUMNS`). **A new cost field touches exactly: `COST_GROUPS`, `COST_FIELD_COLUMNS`, and the db schema/migrations — [tests/test_fields.py](tests/test_fields.py) enforces this.**
- **[bookcost/reporting/](bookcost/reporting/)** — PDF report via reportlab. UI builds a `ReportData` snapshot; `build_pdf_report()` renders it. Farsi shaping (`arabic_reshaper` + `python-bidi`) lives in [farsi.py](bookcost/reporting/farsi.py), shared with chart labels.
- **[bookcost/ui/](bookcost/ui/)** — all Qt code:
  - [main_window.py](bookcost/ui/main_window.py) — thin coordinator: toolbar/menu/status bar, owns `current_project_id`, orchestrates calculate/save/load/delete/PDF flows. **Tabs never talk to each other directly** — they expose Qt signals plus small state APIs and the main window wires them.
  - [tabs/](bookcost/ui/tabs/) — one module per tab. `DetailsTab` owns the whole input form and maps to/from DB rows via `collect_project()` / `collect_details()` / `populate()` / `reset()`; other tabs follow the same signal + accessor pattern.
  - [widgets/print_layout_widget.py](bookcost/ui/widgets/print_layout_widget.py) — QPainter imposition/size visualization; [dialogs/paper_price_dialog.py](bookcost/ui/dialogs/paper_price_dialog.py) — paper unit price dialog (3 formulas, `paper_calculations` table).
- **[resources/](resources/)** — `style.qss` (dark theme), Farsi fonts, logo.

Data flow: `DetailsTab` collects inputs → `CostCalculator`/`pricing` compute → `BookDatabase` persists (`projects` + `project_details`) → `reporting` renders the PDF.

Tests add the repo root to `sys.path` themselves. [tests/test_ui_smoke.py](tests/test_ui_smoke.py) builds the real main window offscreen and round-trips save→reload; keep it passing when touching tab APIs.

## Domain vocabulary

Cost values are keyed by Persian display names (e.g. `هزینه کاغذ متن`) in memory, stored as romanized `hazineh_*` columns in `project_details` (mapping in `core/fields.py`). Recurring terms: **matn** = text block, **jeld** = cover, **tiraj** = print run, **qate/قطع** = trim size, **zinc/زینک** = printing plate, **form** = printing signature.

## Conventions

- `style.qss` holds the dark theme; QLabels need explicit high-contrast colors or they vanish against the dark background.
- Bulk table/combo population: wrap in `setUpdatesEnabled(False)`/`(True)`, pre-set `setRowCount()`, use `addItems(list)` — not per-row inserts.
- Avoid N+1 DB queries from UI loops; batch instead (see `BookDatabase.get_default_costs_batch`).
- Feature design docs and implementation plans live in `docs/superpowers/specs/` and `docs/superpowers/plans/`.
- Verifying changes end-to-end: see `.claude/skills/verify/SKILL.md` for the headless GUI-driving recipe.
