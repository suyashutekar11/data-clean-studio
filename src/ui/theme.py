"""
DataClean Studio — Glass Design System  ·  Graphite & Silver Edition
src/ui/theme.py

Single source of truth alias pointing to styles.py.
"""
from styles import inject_glass_theme, _tokens, _build_css

__all__ = ["inject_glass_theme"]
