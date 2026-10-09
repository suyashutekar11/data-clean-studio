"""
Professional Data Quality Profile PDF Export Module.
Generates an executive-ready, publication-grade Data Quality Audit Report
using fpdf2 with modern branding, metrics cards, styled tables, and safety checks.
"""

from datetime import datetime
import re
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
from fpdf import FPDF
from fpdf.enums import XPos, YPos


def sanitize_pdf_text(text: Any) -> str:
    """
    Sanitizes arbitrary text or metadata to prevent UnicodeEncodeError in standard
    PDF fonts (Helvetica / Latin-1) by mapping Unicode symbols to clean ASCII equivalents.
    """
    if text is None:
        return ""
    s = str(text)
    replacements = {
        "➔": "->",
        "→": "->",
        "←": "<-",
        "✓": "[v]",
        "✔": "[v]",
        "✕": "[x]",
        "✖": "[x]",
        "❌": "[x]",
        "⚠️": "[!]",
        "⚡": "*",
        "📋": "",
        "🔬": "",
        "🧹": "",
        "📊": "",
        "🔎": "",
        "•": "-",
        "—": "--",
        "–": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "…": "...",
    }
    for orig, rep in replacements.items():
        s = s.replace(orig, rep)
    # Ensure strict latin-1 compatibility
    return s.encode("latin-1", "replace").decode("latin-1")


def hex_to_rgb(hex_str: Optional[str]) -> Tuple[int, int, int]:
    """Convert hex color code to RGB tuple."""
    if not hex_str:
        return (16, 185, 129)
    cleaned = hex_str.lstrip("#")
    if len(cleaned) >= 6:
        try:
            return (
                int(cleaned[0:2], 16),
                int(cleaned[2:4], 16),
                int(cleaned[4:6], 16),
            )
        except ValueError:
            pass
    return (16, 185, 129)


class ExecutiveProfilePDF(FPDF):
    """Custom FPDF subclass with branded two-tone headers and dynamic footers."""

    def __init__(
        self, db_name: str, tbl_name: str, is_workspace: bool, *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.db_name = sanitize_pdf_text(db_name)
        self.tbl_name = sanitize_pdf_text(tbl_name)
        self.is_workspace = is_workspace
        self.set_auto_page_break(auto=True, margin=16)
        self.alias_nb_pages()

    def header(self):
        # Top brand accent stripe
        self.set_fill_color(15, 23, 42)  # Deep Navy #0F172A
        self.rect(0, 0, self.w, 3.5, "F")
        self.set_fill_color(2, 132, 199)  # Electric Blue #0284C7
        self.rect(0, 2.7, self.w * 0.35, 0.8, "F")

        # Running header on subsequent pages (page 2+)
        if self.page_no() > 1:
            self.set_font("Helvetica", "B", 7.5)
            self.set_text_color(100, 116, 139)  # Slate muted
            self.set_y(6)
            self.set_x(15)
            self.cell(
                100,
                5,
                "DATACLEAN STUDIO  |  DATA QUALITY AUDIT REPORT",
                new_x=XPos.RIGHT,
                new_y=YPos.TOP,
            )

            scope_str = "SANDBOX WORKSPACE" if self.is_workspace else "SOURCE BASELINE"
            self.set_font("Helvetica", "", 7.5)
            self.cell(
                0,
                5,
                f"{self.db_name}.{self.tbl_name} ({scope_str})",
                align="R",
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )

            self.set_draw_color(226, 232, 240)
            self.set_line_width(0.3)
            self.line(15, 12, self.w - 15, 12)
            self.set_y(15)

    def footer(self):
        self.set_y(-14)
        self.set_draw_color(226, 232, 240)
        self.set_line_width(0.3)
        self.line(15, self.get_y(), self.w - 15, self.get_y())

        self.set_y(-11)
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(148, 163, 184)
        self.set_x(15)
        gen_time = datetime.now().strftime("%B %d, %Y - %H:%M:%S")
        self.cell(
            115,
            5,
            f"Automated Quality Audit  |  Generated: {gen_time}  |  Read-Only Baseline Verified",
            new_x=XPos.RIGHT,
            new_y=YPos.TOP,
        )
        self.set_font("Helvetica", "B", 7.5)
        self.set_text_color(100, 116, 139)
        self.cell(
            0,
            5,
            f"Page {self.page_no()} of {{nb}}",
            align="R",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )


def generate_executive_profile_pdf(
    db_name: str,
    target_tbl_name: str,
    is_workspace: bool,
    score: int,
    score_label: str,
    score_color_hex: str,
    profile_data: Dict[str, Any],
    delta_callout: str = "",
) -> bytes:
    """
    Builds a professional executive PDF report summarizing the data quality profile.
    Returns the generated PDF as raw bytes.
    """
    pdf = ExecutiveProfilePDF(db_name, target_tbl_name, is_workspace)
    pdf.set_margins(15, 15, 15)
    pdf.add_page()
    page_w = pdf.w - pdf.l_margin - pdf.r_margin  # Typically 180 mm on A4

    # -------------------------------------------------------------
    # 1. Executive Title Block
    # -------------------------------------------------------------
    pdf.set_y(10)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(2, 132, 199)  # Sky blue accent
    pdf.cell(
        0,
        5,
        "ENTERPRISE DATA QUALITY AUDIT REPORT",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(15, 23, 42)  # Slate Navy #0F172A
    pdf.cell(0, 8, "Data Quality Profile", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 116, 139)
    scope_str = (
        "Sandbox Workspace (Cleaning Staging)"
        if is_workspace
        else "Source Table (Production Read-Only Baseline)"
    )
    pdf.cell(
        0,
        5,
        f"Database: {sanitize_pdf_text(db_name)}   |   Table: {sanitize_pdf_text(target_tbl_name)}   |   Scope: {scope_str}",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.ln(3)

    # -------------------------------------------------------------
    # 2. Composite Health Index Hero Card
    # -------------------------------------------------------------
    card_y = pdf.get_y()
    card_h = 28

    # Outer rounded container
    pdf.set_fill_color(248, 250, 252)  # #F8FAFC
    pdf.set_draw_color(226, 232, 240)  # #E2E8F0
    pdf.set_line_width(0.35)
    try:
        pdf.rect(15, card_y, page_w, card_h, "FD", round_corners=True, corner_radius=3)
    except Exception:
        pdf.rect(15, card_y, page_w, card_h, "FD")

    # Score Badge Box on left
    sc_r, sc_g, sc_b = hex_to_rgb(score_color_hex)
    badge_w = 26
    badge_h = 20
    badge_x = 19
    badge_y = card_y + 4

    pdf.set_fill_color(sc_r, sc_g, sc_b)
    try:
        pdf.rect(
            badge_x, badge_y, badge_w, badge_h, "F", round_corners=True, corner_radius=2
        )
    except Exception:
        pdf.rect(badge_x, badge_y, badge_w, badge_h, "F")

    # Inside score badge
    pdf.set_xy(badge_x, badge_y + 2)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(badge_w, 6, str(score), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_xy(badge_x, badge_y + 9)
    pdf.set_font("Helvetica", "B", 6.5)
    pdf.cell(badge_w, 4, "HEALTH INDEX", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_xy(badge_x, badge_y + 13)
    pdf.set_font("Helvetica", "", 6)
    pdf.cell(badge_w, 3, "/ 100", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Health details text
    details_x = badge_x + badge_w + 6
    pdf.set_xy(details_x, card_y + 4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(sc_r, sc_g, sc_b)
    pdf.cell(80, 5, sanitize_pdf_text(score_label), new_x=XPos.RIGHT, new_y=YPos.TOP)

    # Pill tag
    tag_str = f"{'Workspace' if is_workspace else 'Source'} Score: {score}/100"
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_fill_color(241, 245, 249)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(
        46,
        5,
        f"  {tag_str}  ",
        align="C",
        fill=True,
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    pdf.set_xy(details_x, card_y + 11)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(
        page_w - badge_w - 12,
        4,
        "Quality evaluated across NULL density, blank strings, duplicate vectors, and detected anomalies.",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    if delta_callout:
        clean_delta = re.sub(r"<[^<]+?>", "", delta_callout).strip()
        clean_delta = sanitize_pdf_text(clean_delta)
        pdf.set_xy(details_x, card_y + 17)
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(
            page_w - badge_w - 12,
            4,
            clean_delta,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

    pdf.set_y(card_y + card_h + 5)

    # -------------------------------------------------------------
    # 3. Executive KPI Metric Cards (4 Cards)
    # -------------------------------------------------------------
    kpi_y = pdf.get_y()
    card_gap = 4
    num_cards = 4
    kpi_w = (page_w - (card_gap * (num_cards - 1))) / num_cards
    kpi_h = 19

    dup_cnt = profile_data.get("duplicate_row_count", 0)
    findings_list = profile_data.get("findings", [])
    f_cnt = len(findings_list)

    kpis = [
        {
            "label": "AUDITED ROWS",
            "value": f"{profile_data.get('row_count', 0):,}",
            "sub": "Total table records",
            "color": (2, 132, 199),
        },
        {
            "label": "COLUMNS",
            "value": str(profile_data.get("column_count", 0)),
            "sub": "Schema dimensions",
            "color": (15, 23, 42),
        },
        {
            "label": "DUPLICATE ROWS",
            "value": f"{dup_cnt:,}",
            "sub": "Redundant records" if dup_cnt > 0 else "Zero duplicates",
            "color": (239, 68, 68) if dup_cnt > 0 else (16, 185, 129),
        },
        {
            "label": "QUALITY FINDINGS",
            "value": str(f_cnt),
            "sub": "Anomalies detected" if f_cnt > 0 else "Clean profile",
            "color": (245, 158, 11) if f_cnt > 0 else (16, 185, 129),
        },
    ]

    for i, kpi in enumerate(kpis):
        cx = 15 + i * (kpi_w + card_gap)
        pdf.set_fill_color(248, 250, 252)
        pdf.set_draw_color(226, 232, 240)
        pdf.set_line_width(0.3)
        try:
            pdf.rect(cx, kpi_y, kpi_w, kpi_h, "FD", round_corners=True, corner_radius=2)
        except Exception:
            pdf.rect(cx, kpi_y, kpi_w, kpi_h, "FD")

        # Top border colored accent stripe
        cr, cg, cb = kpi["color"]
        pdf.set_fill_color(cr, cg, cb)
        pdf.rect(cx, kpi_y, kpi_w, 1.2, "F")

        # Label
        pdf.set_xy(cx + 2, kpi_y + 2.5)
        pdf.set_font("Helvetica", "B", 6.5)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(
            kpi_w - 4, 3.5, kpi["label"], align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT
        )

        # Value
        pdf.set_xy(cx + 2, kpi_y + 6.5)
        pdf.set_font("Helvetica", "B", 12.5)
        pdf.set_text_color(cr, cg, cb)
        pdf.cell(
            kpi_w - 4, 6.5, kpi["value"], align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT
        )

        # Subtext
        pdf.set_xy(cx + 2, kpi_y + 13.5)
        pdf.set_font("Helvetica", "", 6)
        pdf.set_text_color(148, 163, 184)
        pdf.cell(
            kpi_w - 4, 3.5, kpi["sub"], align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT
        )

    pdf.set_y(kpi_y + kpi_h + 6)

    # -------------------------------------------------------------
    # Helper: Styled Table Renderer
    # -------------------------------------------------------------
    def render_styled_table(
        headers: List[str],
        rows_data: List[List[str]],
        col_widths: List[float],
        title: str,
        subtitle: str = "",
        aligns: Optional[List[str]] = None,
        severity_col_idx: int = -1,
    ):
        if pdf.get_y() + 20 > pdf.h - pdf.b_margin:
            pdf.add_page()

        # Section Header
        pdf.set_font("Helvetica", "B", 10.5)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(
            page_w, 5.5, sanitize_pdf_text(title), new_x=XPos.LMARGIN, new_y=YPos.NEXT
        )
        if subtitle:
            pdf.set_font("Helvetica", "", 7.5)
            pdf.set_text_color(100, 116, 139)
            pdf.cell(
                page_w,
                4,
                sanitize_pdf_text(subtitle),
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )
        pdf.ln(1.5)

        # Table Header Bar
        pdf.set_fill_color(30, 41, 59)  # Slate Navy #1E293B
        pdf.set_text_color(255, 255, 255)
        pdf.set_draw_color(51, 65, 85)
        pdf.set_line_width(0.2)
        pdf.set_font("Helvetica", "B", 7.5)

        row_h = 6.2
        for col_i, h in enumerate(headers):
            w = col_widths[col_i]
            align = aligns[col_i] if aligns else "L"
            pdf.cell(
                w,
                row_h,
                f" {sanitize_pdf_text(h)} ",
                border=0,
                fill=True,
                align=align,
                new_x=XPos.RIGHT,
                new_y=YPos.TOP,
            )
        pdf.ln(row_h)

        # Data Rows
        pdf.set_font("Helvetica", "", 7)
        pdf.set_line_width(0.15)
        pdf.set_draw_color(226, 232, 240)

        for r_idx, row in enumerate(rows_data):
            if pdf.get_y() + 6.5 > pdf.h - pdf.b_margin:
                pdf.add_page()
                # Repeat header on newly added page
                pdf.set_fill_color(30, 41, 59)
                pdf.set_text_color(255, 255, 255)
                pdf.set_font("Helvetica", "B", 7.5)
                for col_i, h in enumerate(headers):
                    w = col_widths[col_i]
                    align = aligns[col_i] if aligns else "L"
                    pdf.cell(
                        w,
                        row_h,
                        f" {sanitize_pdf_text(h)} ",
                        border=0,
                        fill=True,
                        align=align,
                        new_x=XPos.RIGHT,
                        new_y=YPos.TOP,
                    )
                pdf.ln(row_h)
                pdf.set_font("Helvetica", "", 7)
                pdf.set_draw_color(226, 232, 240)

            # Alternating row fill
            if r_idx % 2 == 0:
                pdf.set_fill_color(255, 255, 255)
            else:
                pdf.set_fill_color(248, 250, 252)

            for col_i, val in enumerate(row):
                w = col_widths[col_i]
                align = aligns[col_i] if aligns else "L"
                val_str = sanitize_pdf_text(val)

                # Special formatting for severity pill
                if col_i == severity_col_idx:
                    sev_upper = val_str.upper()
                    if "HIGH" in sev_upper or "CRIT" in sev_upper:
                        pdf.set_fill_color(254, 226, 226)  # Red tint
                        pdf.set_text_color(185, 28, 28)
                        pdf.set_font("Helvetica", "B", 6.5)
                    elif "MED" in sev_upper or "WARN" in sev_upper:
                        pdf.set_fill_color(254, 243, 199)  # Amber tint
                        pdf.set_text_color(180, 83, 9)
                        pdf.set_font("Helvetica", "B", 6.5)
                    else:
                        pdf.set_fill_color(224, 242, 254)  # Sky blue tint
                        pdf.set_text_color(3, 105, 161)
                        pdf.set_font("Helvetica", "B", 6.5)

                    pdf.cell(
                        w,
                        5.4,
                        f" {val_str} ",
                        border="B",
                        fill=True,
                        align="C",
                        new_x=XPos.RIGHT,
                        new_y=YPos.TOP,
                    )
                    # Reset colors
                    pdf.set_font("Helvetica", "", 7)
                    if r_idx % 2 == 0:
                        pdf.set_fill_color(255, 255, 255)
                    else:
                        pdf.set_fill_color(248, 250, 252)
                    pdf.set_text_color(51, 65, 85)
                else:
                    # Truncate if exceptionally long
                    max_chars = max(1, int(w / 1.55))
                    if len(val_str) > max_chars:
                        val_str = val_str[: max_chars - 2] + ".."

                    # Null % highlight
                    if "Null %" in headers[col_i]:
                        try:
                            n_pct = float(str(val).replace("%", ""))
                            if n_pct > 10.0:
                                pdf.set_text_color(220, 38, 38)
                                pdf.set_font("Helvetica", "B", 7)
                            else:
                                pdf.set_text_color(51, 65, 85)
                                pdf.set_font("Helvetica", "", 7)
                        except Exception:
                            pdf.set_text_color(51, 65, 85)
                    else:
                        pdf.set_text_color(51, 65, 85)
                        pdf.set_font("Helvetica", "", 7)

                    pdf.cell(
                        w,
                        5.4,
                        f" {val_str} ",
                        border="B",
                        fill=True,
                        align=align,
                        new_x=XPos.RIGHT,
                        new_y=YPos.TOP,
                    )

            pdf.ln(5.4)
        pdf.ln(4)

    # -------------------------------------------------------------
    # 4. Table: Column Quality Profiles
    # -------------------------------------------------------------
    col_prof_df = profile_data.get("column_profiles")
    if isinstance(col_prof_df, pd.DataFrame) and not col_prof_df.empty:
        headers = ["Column Name", "Data Type", "Null Count", "Null %", "Unique Values"]
        c_name = "Column" if "Column" in col_prof_df.columns else col_prof_df.columns[0]
        c_type = (
            "Data Type"
            if "Data Type" in col_prof_df.columns
            else ("Type" if "Type" in col_prof_df.columns else "")
        )
        c_null_cnt = "Null Count" if "Null Count" in col_prof_df.columns else ""
        c_null_pct = "Null %" if "Null %" in col_prof_df.columns else ""
        c_uniq = "Unique Values" if "Unique Values" in col_prof_df.columns else ""

        rows_data = []
        for _, r in col_prof_df.iterrows():
            null_cnt_val = r.get(c_null_cnt, 0)
            null_pct_val = r.get(c_null_pct, 0.0)
            uniq_val = r.get(c_uniq, 0)

            rows_data.append(
                [
                    str(r.get(c_name, "")),
                    str(r.get(c_type, "VARCHAR")),
                    (
                        f"{null_cnt_val:,}"
                        if isinstance(null_cnt_val, (int, float))
                        else str(null_cnt_val)
                    ),
                    (
                        f"{float(null_pct_val):.1f}%"
                        if isinstance(null_pct_val, (int, float))
                        else str(null_pct_val)
                    ),
                    (
                        f"{uniq_val:,}"
                        if isinstance(uniq_val, (int, float))
                        else str(uniq_val)
                    ),
                ]
            )

        col_widths = [55, 35, 30, 25, 35]  # sum = 180
        aligns = ["L", "L", "R", "R", "R"]

        render_styled_table(
            headers=headers,
            rows_data=rows_data,
            col_widths=col_widths,
            title="1. Column Quality Profiles",
            subtitle="Complete structural inspection and nullity density per schema column",
            aligns=aligns,
        )

    # -------------------------------------------------------------
    # 5. Table: Detected Findings & Anomalies
    # -------------------------------------------------------------
    if findings_list:
        headers = ["Column", "Issue / Anomaly Detected", "Affected Count", "Severity"]
        rows_data = []
        for f in findings_list:
            rows_data.append(
                [
                    str(f.get("Column", "-")),
                    str(f.get("Issue", "-")),
                    str(f.get("Count", "-")),
                    str(f.get("Severity", "Info")),
                ]
            )

        col_widths = [40, 88, 26, 26]  # sum = 180
        aligns = ["L", "L", "R", "C"]

        render_styled_table(
            headers=headers,
            rows_data=rows_data,
            col_widths=col_widths,
            title="2. Detected Findings & Data Anomalies",
            subtitle="Rule-based algorithmic quality findings prioritized by severity",
            aligns=aligns,
            severity_col_idx=3,
        )
    else:
        # Note when table has 0 findings
        if pdf.get_y() + 15 > pdf.h - pdf.b_margin:
            pdf.add_page()
        pdf.set_font("Helvetica", "B", 10.5)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(
            page_w,
            5.5,
            "2. Detected Findings & Data Anomalies",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(16, 185, 129)
        pdf.cell(
            page_w,
            4,
            "[v] Zero anomalies or data quality issues detected across evaluated rules.",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        pdf.ln(3)

    # -------------------------------------------------------------
    # 6. Missingness Breakdown Visual Bar
    # -------------------------------------------------------------
    if (
        isinstance(col_prof_df, pd.DataFrame)
        and not col_prof_df.empty
        and "Null %" in col_prof_df.columns
    ):
        null_cols = col_prof_df[col_prof_df["Null %"] > 0]
        if not null_cols.empty:
            if pdf.get_y() + 25 > pdf.h - pdf.b_margin:
                pdf.add_page()

            pdf.set_font("Helvetica", "B", 10.5)
            pdf.set_text_color(15, 23, 42)
            pdf.cell(
                page_w,
                5.5,
                "3. Missingness & NULL Value Density",
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )
            pdf.set_font("Helvetica", "", 7.5)
            pdf.set_text_color(100, 116, 139)
            pdf.cell(
                page_w,
                4,
                "Columns exhibiting non-zero null value concentration with visual density rating",
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )
            pdf.ln(2)

            for _, row in null_cols.iterrows():
                if pdf.get_y() + 7 > pdf.h - pdf.b_margin:
                    pdf.add_page()

                c_name_val = sanitize_pdf_text(str(row["Column"]))
                null_pct_val = float(row["Null %"])
                null_cnt_val = int(row.get("Null Count", 0))

                pdf.set_font("Helvetica", "B", 7)
                pdf.set_text_color(51, 65, 85)
                pdf.cell(45, 5, c_name_val, new_x=XPos.RIGHT, new_y=YPos.TOP)

                # Progress bar
                bar_x = pdf.get_x()
                bar_y = pdf.get_y() + 1
                bar_max_w = 88
                bar_h = 3.2

                pdf.set_fill_color(241, 245, 249)
                pdf.rect(bar_x, bar_y, bar_max_w, bar_h, "F")

                fill_w = max(1.0, (min(null_pct_val, 100.0) / 100.0) * bar_max_w)
                if null_pct_val > 20:
                    pdf.set_fill_color(239, 68, 68)  # Crimson
                elif null_pct_val > 5:
                    pdf.set_fill_color(245, 158, 11)  # Amber
                else:
                    pdf.set_fill_color(2, 132, 199)  # Blue
                pdf.rect(bar_x, bar_y, fill_w, bar_h, "F")

                pdf.set_x(bar_x + bar_max_w + 5)
                pdf.set_font("Helvetica", "B", 6.8)
                pdf.set_text_color(71, 85, 105)
                pdf.cell(
                    0,
                    5,
                    f"{null_pct_val:.1f}% ({null_cnt_val:,} null rows)",
                    new_x=XPos.LMARGIN,
                    new_y=YPos.NEXT,
                )

    return bytes(pdf.output())
