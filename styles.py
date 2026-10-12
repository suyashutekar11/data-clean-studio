"""
DataClean Studio — Theme Aliasing
styles.py

Re-exports inject_theme and inject_glass_theme from ui.theme.
"""
from ui.theme import inject_theme, inject_glass_theme

__all__ = ["inject_theme", "inject_glass_theme"]
