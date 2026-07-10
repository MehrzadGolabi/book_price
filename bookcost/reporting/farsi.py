"""Farsi text shaping shared by the PDF report and matplotlib chart labels."""

import arabic_reshaper
from bidi.algorithm import get_display


def shape(text: str) -> str:
    """Reshape Arabic-script text and apply the bidi algorithm for display."""
    return get_display(arabic_reshaper.reshape(text))
