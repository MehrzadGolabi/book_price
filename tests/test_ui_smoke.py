"""Headless UI smoke tests: construct the full main window offscreen, then
exercise the save → reload round-trip through the tab APIs.

Requires PySide6 (skipped otherwise); runs with the offscreen Qt platform so
no display is needed.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from bookcost.core.calculator import CostCalculator
from bookcost.core.db import BookDatabase
from bookcost.ui.tabs.details_tab import DetailsTab


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def db():
    d = BookDatabase(':memory:')
    d.connect()
    return d


@pytest.fixture
def window(qapp, db, monkeypatch, tmp_path):
    """Full main window against a temp-file DB, with popups suppressed."""
    import bookcost.ui.main_window as mw
    monkeypatch.setattr(mw, 'DB_CONFIG',
                        {'filename': str(tmp_path / 'test.db'), 'delete_password': 'admin'})
    for fn in ('information', 'warning', 'critical'):
        monkeypatch.setattr(QMessageBox, fn, staticmethod(lambda *a, **k: QMessageBox.Ok))
    win = mw.BookCostCalculator()
    yield win
    win.db._conn.close()


def test_main_window_constructs(window):
    assert window.tabs.count() == 7


def test_details_tab_collect_populate_roundtrip(qapp, db):
    tab = DetailsTab(db, CostCalculator())
    tab.inputs['عنوان کتاب'].setText('کتاب آزمایشی')
    tab.inputs['تیراژ'].setValue(1500)
    tab.total_pages_spin.setValue(160)
    tab.royalty_input.setValue(10)
    tab.set_cost_value('هزینه تالیف', 5_000_000)
    tab.set_cost_value('هزینه صحافی', 1_200_000)

    p = tab.collect_project()
    d = tab.collect_details()
    assert p['title'] == 'کتاب آزمایشی'
    assert p['tiraj'] == 1500
    assert d['hazineh_talif'] == 5_000_000
    assert d['hazineh_sahafi'] == 1_200_000
    assert d['total_pages'] == 160

    tab2 = DetailsTab(db, CostCalculator())
    tab2.populate({**p, 'royalty_percent': p['royalty_percent']}, d)
    assert tab2.title() == 'کتاب آزمایشی'
    assert tab2.tiraj() == 1500
    assert tab2.cost_values()['هزینه تالیف'] == 5_000_000
    assert tab2.total_pages_spin.value() == 160


def test_save_and_reload_project_through_window(window):
    win = window
    win.details_tab.inputs['عنوان کتاب'].setText('پروژه دور کامل')
    win.details_tab.inputs['تیراژ'].setValue(2000)
    win.details_tab.set_cost_value('هزینه تالیف', 3_000_000)
    win.details_tab.royalty_input.setValue(12)
    win.pricing_tab.set_values(3.0, 40.0)

    win.perform_calculations()
    assert win.current_project_id is not None
    assert win.calc_tab.total_cost > 0

    saved_id = win.current_project_id
    win.new_project()
    assert win.details_tab.title() == ''
    assert win.calc_tab.total_cost == 0

    win.load_project_by_id(saved_id)
    assert win.details_tab.title() == 'پروژه دور کامل'
    assert win.details_tab.tiraj() == 2000
    assert win.details_tab.cost_values()['هزینه تالیف'] == 3_000_000
    assert win.pricing_tab.multiplier() == 3.0
    assert win.pricing_tab.distribution_pct() == 40.0


def test_paper_size_combo_user_override_and_qate_change(qapp, db):
    tab = DetailsTab(db, CostCalculator())
    # Initial default for وزیری is 70×100
    assert tab.inputs['قطع'].currentText() == 'وزیری'
    assert tab.paper_size_combo.currentText() == '70×100'

    # User manually overrides paper_size_combo to 60×90
    tab.paper_size_combo.setCurrentText('60×90')
    assert tab.paper_size_combo.currentText() == '60×90'

    # Page count changes should NOT overwrite user's paper size choice
    tab.total_pages_spin.setValue(200)
    assert tab.paper_size_combo.currentText() == '60×90'

    # Changing trim size (قطع) SHOULD set paper_size_combo to recommended default for new qate
    tab.inputs['قطع'].setCurrentText('رقعی')
    assert tab.paper_size_combo.currentText() == '60×90'

    tab.inputs['قطع'].setCurrentText('خشتی')
    assert tab.paper_size_combo.currentText() == '50×70'

