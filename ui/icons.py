"""
DataClean Studio — Monoline Lucide Icon Set
ui/icons.py

Consistent monoline icons (Lucide vector set):
- Standard dimensions: 18px x 18px (configurable)
- Standard stroke: 1.75px (configurable)
- Linecap: round, Linejoin: round
- Vector SVG with 'stroke="currentColor"' and 'fill="none"'
- Zero external network dependencies, 100% reliable offline rendering.
"""

from typing import Optional


def get_icon_svg(
    name: str,
    size: int = 18,
    stroke_width: float = 1.75,
    extra_class: str = "",
    color: Optional[str] = None,
) -> str:
    """Returns an inline SVG string for the requested Lucide icon."""
    color_attr = f' stroke="{color}"' if color else ' stroke="currentColor"'
    cls = f' class="dc-icon dc-icon-{name} {extra_class}".strip()'
    svg_header = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none"{color_attr} stroke-width="{stroke_width}" '
        f'stroke-linecap="round" stroke-linejoin="round"{cls}>'
    )

    paths = _ICONS.get(name, _ICONS["circle_dot"])
    return f"{svg_header}{paths}</svg>"


_ICONS = {
    # ── Cleaning Modules ──
    "hub": (
        '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>'
        '<polyline points="9 22 9 12 15 12 15 22"/>'
    ),
    "bot": (
        '<path d="M12 8V4H8"/>'
        '<rect width="16" height="12" x="4" y="8" rx="2"/>'
        '<path d="M2 14h2"/>'
        '<path d="M20 14h2"/>'
        '<path d="M15 13v2"/>'
        '<path d="M9 13v2"/>'
    ),
    "brain": (
        '<path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z"/>'
        '<path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z"/>'
        '<path d="M12 5v13"/>'
    ),
    "whitespace": (
        '<circle cx="6" cy="6" r="3"/>'
        '<circle cx="6" cy="18" r="3"/>'
        '<line x1="20" x2="8.12" y1="4" y2="15.88"/>'
        '<line x1="14.47" x2="20" y1="14.48" y2="20"/>'
        '<line x1="8.12" x2="12" y1="8.12" y2="12"/>'
    ),
    "blanks": (
        '<path d="M12 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>'
        '<path d="M18.375 2.625a2.121 2.121 0 1 1 3 3L12 15l-4 1 1-4Z"/>'
    ),
    "casing": (
        '<polyline points="4 7 4 4 20 4 20 7"/>'
        '<line x1="9" x2="15" y1="20" y2="20"/>'
        '<line x1="12" x2="12" y1="4" y2="20"/>'
    ),
    "duplicates": (
        '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/>'
        '<path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>'
    ),
    "special_chars": (
        '<line x1="4" x2="20" y1="9" y2="9"/>'
        '<line x1="4" x2="20" y1="15" y2="15"/>'
        '<line x1="10" x2="8" y1="3" y2="21"/>'
        '<line x1="16" x2="14" y1="3" y2="21"/>'
    ),
    "dates": (
        '<path d="M8 2v4"/>'
        '<path d="M16 2v4"/>'
        '<rect width="18" height="18" x="3" y="4" rx="2"/>'
        '<path d="M3 10h18"/>'
    ),
    "adv_dates": (
        '<path d="M8 2v4"/>'
        '<path d="M16 2v4"/>'
        '<rect width="18" height="18" x="3" y="4" rx="2"/>'
        '<path d="M3 10h18"/>'
        '<path d="m9 16 2 2 4-4"/>'
    ),
    "boolean": (
        '<rect width="18" height="18" x="3" y="3" rx="2"/>'
        '<path d="m9 12 2 2 4-4"/>'
    ),
    "numeric": (
        '<rect width="16" height="20" x="4" y="2" rx="2"/>'
        '<line x1="8" x2="16" y1="6" y2="6"/>'
        '<line x1="16" x2="16" y1="14" y2="18"/>'
        '<path d="M16 10h.01"/>'
        '<path d="M12 10h.01"/>'
        '<path d="M8 10h.01"/>'
        '<path d="M12 14h.01"/>'
        '<path d="M8 14h.01"/>'
        '<path d="M12 18h.01"/>'
        '<path d="M8 18h.01"/>'
    ),

    # ── Database & Platform ──
    "database": (
        '<ellipse cx="12" cy="5" rx="9" ry="3"/>'
        '<path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5"/>'
        '<path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3"/>'
    ),
    "table": (
        '<path d="M12 3v18"/>'
        '<rect width="18" height="18" x="3" y="3" rx="2"/>'
        '<path d="M3 9h18"/>'
        '<path d="M3 15h18"/>'
    ),
    "columns": (
        '<rect width="18" height="18" x="3" y="3" rx="2"/>'
        '<path d="M12 3v18"/>'
    ),
    "rows": (
        '<rect width="18" height="18" x="3" y="3" rx="2"/>'
        '<path d="M3 12h18"/>'
    ),
    "sparkles": (
        '<path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/>'
    ),
    "shield_check": (
        '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>'
        '<path d="m9 12 2 2 4-4"/>'
    ),
    "shield_alert": (
        '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>'
        '<line x1="12" x2="12" y1="8" y2="12"/>'
        '<line x1="12" x2="12.01" y1="16" y2="16"/>'
    ),
    "shield": (
        '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>'
    ),
    "lock": (
        '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/>'
        '<path d="M7 11V7a5 5 0 0 1 10 0v4"/>'
    ),

    # ── Feedback & Alerts ──
    "info": (
        '<circle cx="12" cy="12" r="10"/>'
        '<path d="M12 16v-4"/>'
        '<path d="M12 8h.01"/>'
    ),
    "check": (
        '<polyline points="20 6 9 17 4 12"/>'
    ),
    "check_circle": (
        '<circle cx="12" cy="12" r="10"/>'
        '<path d="m9 12 2 2 4-4"/>'
    ),
    "warning": (
        '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>'
        '<line x1="12" x2="12" y1="9" y2="13"/>'
        '<line x1="12" x2="12.01" y1="17" y2="17"/>'
    ),
    "error": (
        '<circle cx="12" cy="12" r="10"/>'
        '<line x1="12" x2="12" y1="8" y2="12"/>'
        '<line x1="12" x2="12.01" y1="16" y2="16"/>'
    ),
    "help": (
        '<circle cx="12" cy="12" r="10"/>'
        '<path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>'
        '<path d="M12 17h.01"/>'
    ),

    # ── Navigation & Actions ──
    "arrow_left": (
        '<path d="m12 19-7-7 7-7"/>'
        '<path d="M19 12H5"/>'
    ),
    "arrow_right": (
        '<path d="M5 12h14"/>'
        '<path d="m12 5 7 7-7 7"/>'
    ),
    "chevron_right": (
        '<path d="m9 18 6-6-6-6"/>'
    ),
    "chevron_down": (
        '<path d="m6 9 6 6 6-6"/>'
    ),
    "copy": (
        '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/>'
        '<path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>'
    ),
    "refresh": (
        '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/>'
        '<path d="M21 3v5h-5"/>'
        '<path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/>'
        '<path d="M8 16H3v5"/>'
    ),
    "logout": (
        '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>'
        '<polyline points="16 17 21 12 16 7"/>'
        '<line x1="21" x2="9" y1="12" y2="12"/>'
    ),
    "trash": (
        '<path d="M3 6h18"/>'
        '<path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/>'
        '<path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>'
    ),
    "download": (
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
        '<polyline points="7 10 12 15 17 10"/>'
        '<line x1="12" x2="12" y1="15" y2="3"/>'
    ),
    "search": (
        '<circle cx="11" cy="11" r="8"/>'
        '<path d="m21 21-4.3-4.3"/>'
    ),
    "filter": (
        '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>'
    ),
    "sliders": (
        '<line x1="4" x2="4" y1="21" y2="14"/>'
        '<line x1="4" x2="4" y1="10" y2="3"/>'
        '<line x1="12" x2="12" y1="21" y2="12"/>'
        '<line x1="12" x2="12" y1="8" y2="3"/>'
        '<line x1="20" x2="20" y1="21" y2="16"/>'
        '<line x1="20" x2="20" y1="12" y2="3"/>'
        '<line x1="1" x2="7" y1="14" y2="14"/>'
        '<line x1="9" x2="15" y1="8" y2="8"/>'
        '<line x1="17" x2="23" y1="16" y2="16"/>'
    ),
    "eye": (
        '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/>'
        '<circle cx="12" cy="12" r="3"/>'
    ),
    "circle_dot": (
        '<circle cx="12" cy="12" r="10"/>'
        '<circle cx="12" cy="12" r="3"/>'
    ),
}

# Convenient aliases for breadcrumbs & generic components
_ICONS["home"] = _ICONS["hub"]
_ICONS["folder"] = _ICONS["database"]
_ICONS["document"] = _ICONS["table"]
_ICONS["file_code"] = _ICONS["special_chars"]
_ICONS["tool"] = _ICONS["whitespace"]
