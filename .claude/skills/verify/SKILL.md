---
name: verify
description: Build/launch/drive recipe for verifying changes to this PySide6 desktop app end-to-end.
---

# Verifying the book cost calculator app

## Launch

```powershell
# Deps (checked-in .venv starts bare)
.venv\Scripts\python.exe -m pip install -r requirements.txt pytest

# Run the app for real (windowed)
.venv\Scripts\python.exe main.py
```

## Headless GUI driving

Drive the real `BookCostCalculator` window offscreen and screenshot with
`win.grab().save(...)`:

- `os.environ["QT_QPA_PLATFORM"] = "offscreen"` before importing Qt.
- Isolate the DB: `import bookcost.ui.main_window as mw; mw.DB_CONFIG = {"filename": tmpfile, "delete_password": "admin"}` **before** constructing the window, so the user's `book_publishing.db` stays untouched.
- Modals block: start a 50ms `QTimer` that closes `QApplication.activeModalWidget()` (acts as the user clicking OK). Record `windowTitle()`/`text()` before closing for evidence.
- Table row selection: programmatic `selectRow()` does **not** set `currentRow()` on a never-rendered table — use `QTest.mouseClick(table.viewport(), Qt.LeftButton, Qt.NoModifier, table.visualRect(index).center())` after switching to that tab.
- File dialogs are native and can't be driven headlessly: patch `QFileDialog.getSaveFileName` to return a temp path, then click the real button.
- Set `PYTHONIOENCODING=utf-8` or printing Persian widget text crashes on cp1252 consoles.

## Gotchas

- Offscreen platform renders Persian glyphs as tofu boxes in Qt widgets (no system font enumeration) — layout/logic still verifiable; do one short real-display run (no `QT_QPA_PLATFORM`) if font rendering matters. matplotlib text renders fine either way.
- The calculate button lives in the details tab: find it by text `ثبت اطلاعات و انجام محاسبات نهایی`; toolbar actions via `win.findChildren(QAction)` by Persian text.
- Flows worth driving: fill details → click calculate (auto-saves, switches to calc tab, chart draws) → pricing tab refresh → projects list → new/reload round-trip → PDF via report tab → zinc price save in defaults tab propagating to details labels.
