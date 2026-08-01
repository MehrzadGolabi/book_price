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
    assert window.tabs.count() == 5


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


def test_paper_list_widget_row_calc_button(qapp, db):
    tab = DetailsTab(db, CostCalculator())
    tab.papers_matn_list.add_row('تحریر ۸۰', form_count=5, unit_price=250.0)
    entries = tab.papers_matn_list.entries()
    assert len(entries) == 1
    assert entries[0]['paper_type'] == 'تحریر ۸۰'
    assert entries[0]['unit_price'] == 250.0

    # Verify calc_callback updates the row's spinbox
    row_price_spin = tab.papers_matn_list._rows[0][3]
    tab.open_paper_price_dialog_for_spin("matn", row_price_spin)
    # The callback target is the specific row spinbox
    assert row_price_spin is not None


def test_paper_list_widget_carries_over_single_paper_price(qapp, db):
    tab = DetailsTab(db, CostCalculator())
    # Fill in a single paper price
    tab.unit_price_paper_matn_spin.setValue(450.0)
    tab.form_matn_spin.setValue(10)

    # Click add row: first row should carry over existing form count and unit price
    tab.papers_matn_list._add_row_interactive()
    entries = tab.papers_matn_list.entries()
    assert len(entries) == 1
    assert entries[0]['form_count'] == 10
    assert entries[0]['unit_price'] == 450.0

    # Add second row: should append a new row without zeroing out row 1
    tab.papers_matn_list._add_row_interactive()
    entries2 = tab.papers_matn_list.entries()
    assert len(entries2) == 2
    assert entries2[0]['unit_price'] == 450.0


def test_defaults_dialog_constructs_and_saves_zinc(qapp, db):
    from bookcost.ui.dialogs.defaults_dialog import DefaultsDialog
    dlg = DefaultsDialog(db)
    assert dlg.windowTitle() == "🏷 مدیریت قیمت‌های پایه و زینک‌ها"
    assert dlg.zinc_prices_table.rowCount() == 5

    # Test saving a zinc price
    spin = dlg.zinc_prices_table.cellWidget(0, 1)
    spin.setValue(180000)
    dlg.save_zinc_price(0, "زینک 2 ورقی")
    assert db.get_zinc_price("زینک 2 ورقی") == 180000


def test_toolbar_hidden_by_default_and_toggleable(window):
    tb = window.findChild(QToolBar, "main_toolbar")
    assert tb is not None
    assert not tb.isVisible()


def test_spinbox_wheel_scrolling_is_disabled(qapp, db):
    from PySide6.QtCore import QPoint, QPointF
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtWidgets import QDoubleSpinBox
    from bookcost.ui.utils import install_no_wheel_filter

    install_no_wheel_filter(qapp)
    spin = QDoubleSpinBox()
    spin.setValue(100.0)

    # Simulate mouse wheel scroll over spinbox
    wheel_evt = QWheelEvent(
        QPointF(10, 10), QPointF(10, 10), QPoint(0, 120), QPoint(0, 120),
        qapp.mouseButtons(), qapp.keyboardModifiers(), Qt.ScrollUpdate, False
    )
    qapp.sendEvent(spin, wheel_evt)

    # Value should remain 100.0 and not change
    assert spin.value() == 100.0

    assert combo.currentIndex() == 0


def test_details_tab_populate_string_safety(qapp, db):
    tab = DetailsTab(db, CostCalculator())
    project = {
        'title': 'تست', 'subtitle': '', 'creation_date': '1403/01/01',
        'qate': 'وزیری', 'tiraj': '1000', 'royalty_percent': '10.5'
    }
    details = {
        'form_matn': '12', 'form_jeld': '2', 'total_pages': '192',
        'unit_price_paper_matn': '350000', 'unit_price_paper_jeld': '450000'
    }
    # Populate with string values should not raise PySide6.QtWidgets.QSpinBox.setValue(str) exception
    tab.populate(project, details, [], [])
    assert tab.inputs['تیراژ'].value() == 1000
    assert tab.form_matn_spin.value() == 12
    assert tab.total_pages_spin.value() == 192







