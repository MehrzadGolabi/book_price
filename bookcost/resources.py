"""Locate bundled resource files (fonts, stylesheet, logo) in dev and frozen mode.

Dev checkout:  <repo root>/resources/<name>
Frozen exe:    files installed next to BookCostCalculator.exe (see book_setup.iss)
"""

import os
import sys


def app_dir() -> str:
    """Directory the application runs from: exe dir when frozen, repo root otherwise."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(name: str) -> str:
    """Absolute path to a resource file.

    Frozen: prefers files bundled into the PyInstaller archive (sys._MEIPASS),
    then files installed next to the exe (how book_setup.iss ships fonts).
    """
    if getattr(sys, 'frozen', False):
        bundled = os.path.join(getattr(sys, '_MEIPASS', ''), name)
        if os.path.exists(bundled):
            return bundled
        return os.path.join(app_dir(), name)
    return os.path.join(app_dir(), 'resources', name)
