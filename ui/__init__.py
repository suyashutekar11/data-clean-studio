"""
DataClean Studio UI Package
"""

from ui.theme import inject_theme
from ui.credential_dialog import (
    is_credential_error,
    render_credential_error_dialog,
    build_credential_dialog_html,
    EXACT_CREDENTIAL_ERROR_MESSAGE,
)
from ui.main_navigation import render_main_navigation, get_main_nav_css
from ui.welcome_view import render_app_header, render_hero_welcome
from ui.sidebar_view import (
    get_sidebar_css,
    render_sidebar_brand_redesign,
    render_sidebar_promo_card,
    render_sidebar_section_heading,
    render_sidebar_status_card_redesign,
    render_sidebar_bottom_waves,
)
from ui.cleaning_tabs import (
    render_cleaning_tabs,
    CLEANING_MODULES,
    CLEANING_TAB_NAMES,
    get_cleaning_tabs_css,
)
from ui.ai_assistant_view import (
    render_ai_assistant_page,
    render_ai_config_sidebar,
    render_ai_assistant_main,
)
from ui.ai_column_cleaning_view import render_ai_column_cleaning_view
from ui.icons import get_icon_svg
from ui.components import (
    render_page_header,
    render_section_header,
    render_card,
    render_alert,
    render_badge,
    render_metric_card,
    render_sandbox_banner,
    render_stepper,
    render_data_table,
    render_saas_table,
    render_saas_breadcrumb,
    render_module_header,
    render_html,
)

__all__ = [
    "inject_theme",
    "render_main_navigation",
    "get_main_nav_css",
    "is_credential_error",
    "render_credential_error_dialog",
    "build_credential_dialog_html",
    "EXACT_CREDENTIAL_ERROR_MESSAGE",
    "render_app_header",
    "render_hero_welcome",
    "get_sidebar_css",
    "render_sidebar_brand_redesign",
    "render_sidebar_promo_card",
    "render_sidebar_section_heading",
    "render_sidebar_status_card_redesign",
    "render_sidebar_bottom_waves",
    "render_cleaning_tabs",
    "render_ai_assistant_page",
    "render_ai_config_sidebar",
    "render_ai_assistant_main",
    "render_ai_column_cleaning_view",
    "CLEANING_MODULES",
    "CLEANING_TAB_NAMES",
    "get_cleaning_tabs_css",
    "get_icon_svg",
    "render_page_header",
    "render_section_header",
    "render_card",
    "render_alert",
    "render_badge",
    "render_metric_card",
    "render_sandbox_banner",
    "render_stepper",
    "render_data_table",
    "render_saas_table",
    "render_saas_breadcrumb",
    "render_module_header",
    "render_html",
]
