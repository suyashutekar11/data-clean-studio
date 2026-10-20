"""
Tests for AI Column Analysis and Cleaning card, navigation, and dedicated view
tests/test_ai_column_cleaning.py
"""

import json
from unittest.mock import MagicMock, patch
import pytest
import streamlit as st

from ui.cleaning_tabs import CLEANING_MODULES, CLEANING_TAB_NAMES, _CARD_DESCRIPTIONS
from ui.ai_column_cleaning_view import render_ai_column_cleaning_view, render_ai_chat_input
from app import _CANONICAL_NAV_MAP


def test_ai_column_cleaning_module_metadata():
    """Verify AI Column Analysis and Cleaning is present in CLEANING_MODULES with exact copy."""
    target_mods = [m for m in CLEANING_MODULES if m["id"] == "ai_column_cleaning"]
    assert len(target_mods) == 1
    mod = target_mods[0]

    assert mod["title"] == "AI Column Analysis and Cleaning"
    assert mod["name"] == "🧠 AI Column Analysis and Cleaning"
    assert mod["icon"] == "brain"
    expected_desc = "Analyze individual database columns, identify potential data-quality issues, and explore AI-assisted cleaning recommendations."
    assert mod["tooltip"] == expected_desc
    assert mod["description"] == expected_desc
    assert _CARD_DESCRIPTIONS.get("ai_column_cleaning") == expected_desc
    assert "🧠 AI Column Analysis and Cleaning" in CLEANING_TAB_NAMES


def test_ai_column_cleaning_canonical_nav_mapping():
    """Verify canonical navigation dictionary recognizes AI Column Analysis and Cleaning."""
    assert "AI Column Analysis and Cleaning" in _CANONICAL_NAV_MAP
    assert _CANONICAL_NAV_MAP["AI Column Analysis and Cleaning"] == "🧠 AI Column Analysis and Cleaning"


def test_chat_send_button_stays_enabled_for_new_follow_up_text():
    """A Streamlit form must not lock Send based on its not-yet-submitted text area."""
    form_context = MagicMock()
    form_context.__enter__.return_value = form_context
    form_context.__exit__.return_value = False
    column_context = MagicMock()
    column_context.__enter__.return_value = column_context
    column_context.__exit__.return_value = False

    with patch("streamlit.form", return_value=form_context), \
         patch("streamlit.columns", return_value=[column_context, column_context]), \
         patch("streamlit.text_area", return_value="which is the most affected column"), \
         patch("streamlit.form_submit_button", return_value=False) as submit:
        assert render_ai_chat_input(disabled=False) is None

    assert submit.call_args.kwargs["disabled"] is False


def test_render_ai_column_cleaning_view_heading_and_placeholder():
    """Verify dedicated view renders the correct heading, subtitle, and placeholder."""
    with patch("streamlit.button", return_value=False) as mock_btn, \
         patch("streamlit.markdown") as mock_md:
        
        render_ai_column_cleaning_view()

        # Check render_module_header outputs heading and placeholder description
        all_markdown_calls = [str(call[0][0]) for call in mock_md.call_args_list if call[0]]
        combined_text = " ".join(all_markdown_calls)

        assert "AI Column Analysis and Cleaning" in combined_text
        assert "Analyze individual database columns, identify potential data-quality issues, and explore AI-assisted cleaning recommendations." in combined_text


def test_render_ai_column_cleaning_view_back_button():
    """Verify clicking the back button triggers the back callback."""
    back_called = []

    def _on_back():
        back_called.append(True)

    with patch("streamlit.button", return_value=True):
        render_ai_column_cleaning_view(on_back_to_hub=_on_back)
        assert len(back_called) == 1


def test_render_ai_column_cleaning_view_acknowledgment():
    """Verify saved configuration acknowledgment alert is displayed when present in session state."""
    st.session_state.ai_col_save_ack = {
        "type": "success",
        "title": "Connected & Configuration Saved",
        "message": "Successfully connected to AI Model",
    }
    with patch("streamlit.button", return_value=False), \
         patch("streamlit.markdown") as mock_md:
        render_ai_column_cleaning_view()
        calls = [str(call[0][0]) for call in mock_md.call_args_list if call[0]]
        combined = " ".join(calls)
        assert ("Connected &amp; Configuration Saved" in combined or "Connected & Configuration Saved" in combined)
        assert "Successfully connected to AI Model" in combined
        # Verify ack was consumed
        assert "ai_col_save_ack" not in st.session_state


def test_render_ai_column_cleaning_view_no_connection():
    """Verify warning alert is shown when there is no active database connection."""
    with patch("streamlit.button", return_value=False), \
         patch("streamlit.markdown") as mock_md:
        render_ai_column_cleaning_view(engine=None)
        calls = [str(call[0][0]) for call in mock_md.call_args_list if call[0]]
        combined = " ".join(calls)
        assert "No Active Database Connection" in combined


def test_render_ai_column_cleaning_view_selectors():
    """Verify table and column selectboxes render properly and retrieve columns from metadata."""
    mock_engine = MagicMock()
    
    with patch("src.metadata.MySQLMetadataInspector.get_tables", return_value=["orders", "users"]), \
         patch("src.metadata.MySQLMetadataInspector.get_table_schema", return_value=[
             {"Column Name": "order_id", "Data Type": "INT"},
             {"Column Name": "status", "Data Type": "VARCHAR(20)"},
         ]), \
         patch("streamlit.selectbox") as mock_sb, \
         patch("streamlit.button") as mock_btn:

        mock_sb.side_effect = lambda label, *args, **kwargs: (
            "orders" if "Target Table" in label else (
                "status" if "Select Column to Analyze" in label else None
            )
        )
        mock_btn.return_value = False

        render_ai_column_cleaning_view(engine=mock_engine, db_name="shop_db")

        # Verify Target Table and Select Column to Analyze were called
        sb_labels = [call[0][0] for call in mock_sb.call_args_list if call[0]]
        assert any("Target Table" in l for l in sb_labels)
        assert any("Select Column to Analyze" in l for l in sb_labels)


def test_render_ai_column_cleaning_view_no_distinct_components_or_buttons():
    """Verify Show Distinct Values button and distinct values box are NOT rendered."""
    mock_engine = MagicMock()
    
    with patch("src.metadata.MySQLMetadataInspector.get_tables", return_value=["orders"]), \
         patch("src.metadata.MySQLMetadataInspector.get_table_schema", return_value=[
             {"Column Name": "order_id", "Data Type": "INT"}
         ]), \
         patch("streamlit.selectbox") as mock_sb, \
         patch("streamlit.button") as mock_btn, \
         patch("streamlit.markdown") as mock_md:

        mock_sb.side_effect = lambda label, *args, **kwargs: (
            "orders" if "Target Table" in label else "order_id"
        )
        mock_btn.return_value = False

        render_ai_column_cleaning_view(engine=mock_engine, db_name="shop_db")

        # Verify Show Distinct Values button was NOT created
        button_labels = [call[0][0] for call in mock_btn.call_args_list if call[0]]
        assert "Show Distinct Values" not in button_labels

        # Verify distinct value CSS/markup classes are NOT rendered
        all_md_calls = [str(call[0][0]) for call in mock_md.call_args_list if call[0]]
        combined_md = " ".join(all_md_calls)
        assert "dc-modern-comma-box" not in combined_md
        assert "dc-comma-sep" not in combined_md
        assert "Distinct Values for" not in combined_md


def test_ai_column_profile_button_disabled_state():
    """Verify Profile Column button is disabled when placeholder column is selected."""
    mock_engine = MagicMock()
    with patch("src.metadata.MySQLMetadataInspector.get_tables", return_value=["orders"]), \
         patch("src.metadata.MySQLMetadataInspector.get_table_schema", return_value=[
             {"Column Name": "order_id", "Data Type": "INT"}
         ]), \
         patch("streamlit.selectbox") as mock_sb, \
         patch("streamlit.button") as mock_btn:

        # Select placeholder option
        mock_sb.side_effect = lambda label, *args, **kwargs: (
            "orders" if "Target Table" in label else "-- Select Column to Analyze --"
        )
        mock_btn.return_value = False

        render_ai_column_cleaning_view(engine=mock_engine, db_name="shop_db")

        # Find the Profile Column button call
        profile_btn_calls = [call for call in mock_btn.call_args_list if call[0] and "Profile Column" in call[0][0]]
        assert len(profile_btn_calls) == 1
        _, kwargs = profile_btn_calls[0]
        assert kwargs.get("disabled") is True


def test_ai_column_profiling_execution_and_display():
    """Verify clicking Profile Column triggers profiling engine and renders metrics and chart."""
    mock_engine = MagicMock()
    st.session_state._ai_col_profile_result = None
    st.session_state._ai_col_active_selection = None

    from src.column_profiling_engine import ColumnProfileResult, ValuePatternCategory

    mock_profile_res = ColumnProfileResult(
        table_name="customers",
        column_name="email",
        column_declared_type="VARCHAR(255)",
        total_records=100,
        non_null_count=95,
        null_count=2,
        missing_count=5,
        dominant_pattern=ValuePatternCategory.TEXT_SPECIAL.value,
        dominant_pattern_label="Text with Special Characters",
        dominant_pattern_percentage=80.0,
        percentage_denominator="total_records_scanned",
        counts={
            ValuePatternCategory.TEXT_SPECIAL.value: 80,
            ValuePatternCategory.ALPHANUMERIC.value: 15,
            ValuePatternCategory.SQL_NULL.value: 2,
            ValuePatternCategory.EMPTY_STRING.value: 2,
            ValuePatternCategory.WHITESPACE_ONLY.value: 1,
        },
        percentages={
            ValuePatternCategory.TEXT_SPECIAL.value: 80.0,
            ValuePatternCategory.ALPHANUMERIC.value: 15.0,
            ValuePatternCategory.SQL_NULL.value: 2.0,
            ValuePatternCategory.EMPTY_STRING.value: 2.0,
            ValuePatternCategory.WHITESPACE_ONLY.value: 1.0,
        },
        success=True,
    )

    with patch("src.metadata.MySQLMetadataInspector.get_tables", return_value=["customers"]), \
         patch("src.metadata.MySQLMetadataInspector.get_table_schema", return_value=[
             {"Column Name": "email", "Data Type": "VARCHAR(255)"}
         ]), \
         patch("ui.ai_column_cleaning_view.profile_column", return_value=mock_profile_res) as mock_engine_call, \
         patch("streamlit.selectbox") as mock_sb, \
         patch("streamlit.button") as mock_btn, \
         patch("streamlit.plotly_chart") as mock_chart, \
         patch("streamlit.dataframe") as mock_df, \
         patch("streamlit.caption") as mock_cap, \
         patch("streamlit.markdown") as mock_md:

        mock_sb.side_effect = lambda label, *args, **kwargs: (
            "customers" if "Target Table" in label else "email"
        )
        # Profile Column clicked
        mock_btn.side_effect = lambda label, *args, **kwargs: label == "Profile Column"

        render_ai_column_cleaning_view(engine=mock_engine, db_name="shop_db")

        # Verify profile_column was called with proper args
        mock_engine_call.assert_called_once_with(
            engine=mock_engine,
            database="shop_db",
            table_name="customers",
            column_name="email",
        )

        # Verify Plotly chart was rendered
        assert mock_chart.called

        # Verify dataframe was rendered with pattern categories
        assert mock_df.called
        df_passed = mock_df.call_args[0][0]
        assert "Pattern Category" in df_passed.columns
        assert "Distribution (%)" in df_passed.columns
        assert "Missing-Value Placeholders" in list(df_passed["Pattern Category"])

        # Verify summary stats in markdown
        md_texts = " ".join([str(call[0][0]) for call in mock_md.call_args_list if call[0]])
        assert "Total Records" in md_texts
        assert "Missing Values" in md_texts
        assert "Dominant Pattern" in md_texts

        # Verify the dynamic scanned-records subtitle in the chart card
        assert "Distribution across 100 scanned records" in md_texts


def test_ai_column_profiling_stale_result_invalidation():
    """Verify switching column clears cached profiling results immediately."""
    from src.column_profiling_engine import ColumnProfileResult, ValuePatternCategory

    mock_profile_res = ColumnProfileResult(
        table_name="customers",
        column_name="old_col",
        data_type="INT",
        total_records=50,
        non_null_records=50,
        null_records=0,
        empty_string_records=0,
        whitespace_records=0,
        missing_records=0,
        categories={},
        dominant_category=ValuePatternCategory.NUMERIC_ONLY,
        dominant_count=50,
        dominant_percentage=100.0,
        success=True,
    )

    st.session_state._ai_col_profile_result = mock_profile_res
    st.session_state._ai_col_active_selection = ("customers", "old_col")

    mock_engine = MagicMock()
    with patch("src.metadata.MySQLMetadataInspector.get_tables", return_value=["customers"]), \
         patch("src.metadata.MySQLMetadataInspector.get_table_schema", return_value=[
             {"Column Name": "new_col", "Data Type": "VARCHAR(50)"}
         ]), \
         patch("streamlit.selectbox") as mock_sb, \
         patch("streamlit.button", return_value=False):

        # Selection changes to new_col
        mock_sb.side_effect = lambda label, *args, **kwargs: (
            "customers" if "Target Table" in label else "new_col"
        )

        render_ai_column_cleaning_view(engine=mock_engine, db_name="shop_db")

        # Active profiling result should be cleared
        assert st.session_state._ai_col_profile_result is None


def test_ai_column_profiling_empty_table_alert():
    """Verify empty table (0 records) displays an informative alert."""
    from src.column_profiling_engine import ColumnProfileResult, ValuePatternCategory

    mock_empty_res = ColumnProfileResult(
        table_name="empty_tbl",
        column_name="id",
        data_type="INT",
        total_records=0,
        non_null_records=0,
        null_records=0,
        empty_string_records=0,
        whitespace_records=0,
        missing_records=0,
        categories={},
        dominant_category=ValuePatternCategory.OTHER,
        dominant_count=0,
        dominant_percentage=0.0,
        success=True,
    )

    st.session_state._ai_col_profile_result = mock_empty_res
    st.session_state._ai_col_active_selection = ("empty_tbl", "id")

    mock_engine = MagicMock()
    with patch("src.metadata.MySQLMetadataInspector.get_tables", return_value=["empty_tbl"]), \
         patch("src.metadata.MySQLMetadataInspector.get_table_schema", return_value=[
             {"Column Name": "id", "Data Type": "INT"}
         ]), \
         patch("streamlit.selectbox") as mock_sb, \
         patch("streamlit.button", return_value=False), \
         patch("streamlit.markdown") as mock_md:

        mock_sb.side_effect = lambda label, *args, **kwargs: (
            "empty_tbl" if "Target Table" in label else "id"
        )

        render_ai_column_cleaning_view(engine=mock_engine, db_name="shop_db")

        md_texts = " ".join([str(call[0][0]) for call in mock_md.call_args_list if call[0]])
        assert "Empty Table Detected" in md_texts
        assert "contains 0 records" in md_texts


def test_ai_column_analyze_button_rendered_after_successful_profile():
    """Verify Analyze with AI button appears only after column profiling has completed."""
    from src.column_profiling_engine import ColumnProfileResult, ValuePatternCategory

    mock_profile_res = ColumnProfileResult(
        table_name="employees",
        column_name="performance_score_text",
        column_declared_type="VARCHAR(50)",
        total_records=100,
        non_null_count=76,
        null_count=0,
        missing_count=24,
        placeholder_records=24,
        dominant_pattern=ValuePatternCategory.MISSING_PLACEHOLDER.value,
        dominant_pattern_label="Missing-Value Placeholders",
        dominant_pattern_percentage=24.0,
        percentage_denominator="total_records_scanned",
        counts={
            ValuePatternCategory.NUMERIC_ONLY.value: 76,
            ValuePatternCategory.MISSING_PLACEHOLDER.value: 24,
        },
        percentages={
            ValuePatternCategory.NUMERIC_ONLY.value: 76.0,
            ValuePatternCategory.MISSING_PLACEHOLDER.value: 24.0,
        },
        success=True,
    )

    st.session_state._ai_col_profile_result = mock_profile_res
    st.session_state._ai_col_active_selection = ("employees", "performance_score_text")

    mock_engine = MagicMock()
    with patch("src.metadata.MySQLMetadataInspector.get_tables", return_value=["employees"]), \
         patch("src.metadata.MySQLMetadataInspector.get_table_schema", return_value=[
             {"Column Name": "performance_score_text", "Data Type": "VARCHAR(50)"}
         ]), \
         patch("streamlit.selectbox") as mock_sb, \
         patch("streamlit.button") as mock_btn:

        mock_sb.side_effect = lambda label, *args, **kwargs: (
            "employees" if "Target Table" in label else "performance_score_text"
        )
        mock_btn.return_value = False

        render_ai_column_cleaning_view(engine=mock_engine, db_name="hr_db")

        # Verify Analyze with AI button was rendered
        btn_labels = [call[0][0] for call in mock_btn.call_args_list if call[0]]
        assert any("Analyze with AI" in l for l in btn_labels)


def test_ai_column_analyze_button_triggers_recommender():
    """Verify clicking Analyze with AI sends a message via send_ai_chat_message and stores chat history."""
    from src.column_profiling_engine import ColumnProfileResult, ValuePatternCategory
    from src.ai_column_recommender import AIAnalysisResult, ColumnQueryRecommendation, send_ai_chat_message

    mock_profile_res = ColumnProfileResult(
        table_name="employees",
        column_name="performance_score_text",
        column_declared_type="VARCHAR(50)",
        total_records=100,
        non_null_count=76,
        null_count=0,
        missing_count=24,
        placeholder_records=24,
        dominant_pattern=ValuePatternCategory.NUMERIC_ONLY.value,
        dominant_pattern_label="Numeric Only",
        dominant_pattern_percentage=76.0,
        percentage_denominator="total_records_scanned",
        counts={
            ValuePatternCategory.NUMERIC_ONLY.value: 76,
            ValuePatternCategory.MISSING_PLACEHOLDER.value: 24,
        },
        percentages={
            ValuePatternCategory.NUMERIC_ONLY.value: 76.0,
            ValuePatternCategory.MISSING_PLACEHOLDER.value: 24.0,
        },
        success=True,
    )

    st.session_state._ai_col_profile_result = mock_profile_res
    st.session_state._ai_col_active_selection = ("employees", "performance_score_text")
    st.session_state._ai_col_analysis_result = None
    st.session_state._ai_col_chat_messages = []
    st.session_state["working_table_name"] = "employees__cleaning_test123"

    mock_engine = MagicMock()
    mock_engine.dialect.name = "mysql"

    with patch("src.metadata.MySQLMetadataInspector.get_tables", return_value=["employees"]), \
         patch("src.metadata.MySQLMetadataInspector.get_table_schema", return_value=[
             {"Column Name": "performance_score_text", "Data Type": "VARCHAR(50)"}
         ]), \
         patch("streamlit.selectbox") as mock_sb, \
         patch("streamlit.button") as mock_btn, \
         patch("ui.ai_column_cleaning_view.send_ai_chat_message", return_value=(
             json.dumps({"summary": "Detected 24 placeholder values in performance_score_text.", "recommendations": [{"issue_id": "placeholder_values", "title": "Replace placeholders", "issue_detected": "Detected 24 placeholder values", "recommended_solution": "Convert N/A to NULL", "preview_query": "SELECT `performance_score_text` FROM `employees__cleaning_test123` WHERE `performance_score_text` = 'N/A';", "cleaning_query": "UPDATE `employees__cleaning_test123` SET `performance_score_text` = NULL WHERE `performance_score_text` = 'N/A';", "validation_query": "SELECT COUNT(*) FROM `employees__cleaning_test123` WHERE `performance_score_text` = 'N/A';", "expected_result": "24 placeholders cleared", "risks_and_assumptions": "Review first", "is_modifying": True, "category": "missing_placeholder", "affected_records": 24, "affected_percentage": 24.0}]}),
             None
         )) as mock_ai_call:

        mock_sb.side_effect = lambda label, *args, **kwargs: (
            "employees" if "Target Table" in label else "performance_score_text"
        )
        mock_btn.side_effect = lambda label, *args, **kwargs: "Analyze with AI" in label

        render_ai_column_cleaning_view(engine=mock_engine, db_name="hr_db")

        # Verify send_ai_chat_message was called targeting the active workspace table
        mock_ai_call.assert_called_once()
        call_kwargs = mock_ai_call.call_args[1]
        assert call_kwargs["workspace_table"] == "employees__cleaning_test123"
        assert call_kwargs["dialect"] == "mysql"

        # Verify chat messages were stored
        assert len(st.session_state._ai_col_chat_messages) == 2
        assert st.session_state._ai_col_chat_messages[0]["role"] == "user"
        assert st.session_state._ai_col_chat_messages[1]["role"] == "assistant"
        assert "24 placeholder values" in st.session_state._ai_col_chat_messages[1]["content"]


def test_ai_column_analyze_button_renders_chat_history():
    """Verify clicking Analyze with AI renders chat messages in the UI."""
    from src.column_profiling_engine import ColumnProfileResult, ValuePatternCategory

    mock_profile_res = ColumnProfileResult(
        table_name="employees",
        column_name="performance_score_text",
        column_declared_type="VARCHAR(50)",
        total_records=100,
        non_null_count=76,
        null_count=0,
        missing_count=24,
        placeholder_records=24,
        dominant_pattern=ValuePatternCategory.NUMERIC_ONLY.value,
        dominant_pattern_label="Numeric Only",
        dominant_pattern_percentage=76.0,
        percentage_denominator="total_records_scanned",
        counts={
            ValuePatternCategory.NUMERIC_ONLY.value: 76,
            ValuePatternCategory.MISSING_PLACEHOLDER.value: 24,
        },
        percentages={
            ValuePatternCategory.NUMERIC_ONLY.value: 76.0,
            ValuePatternCategory.MISSING_PLACEHOLDER.value: 24.0,
        },
        success=True,
    )

    st.session_state._ai_col_profile_result = mock_profile_res
    st.session_state._ai_col_active_selection = ("employees", "performance_score_text")
    st.session_state._ai_col_chat_messages = []
    st.session_state["working_table_name"] = "employees__cleaning_test123"

    mock_engine = MagicMock()
    with patch("src.metadata.MySQLMetadataInspector.get_tables", return_value=["employees"]), \
         patch("src.metadata.MySQLMetadataInspector.get_table_schema", return_value=[
             {"Column Name": "performance_score_text", "Data Type": "VARCHAR(50)"}
         ]), \
         patch("streamlit.selectbox") as mock_sb, \
         patch("streamlit.button") as mock_btn, \
         patch("streamlit.markdown") as mock_md, \
         patch("ui.ai_column_cleaning_view.send_ai_chat_message", return_value=(
             json.dumps({"summary": "Detected 24 placeholder values in performance_score_text.", "recommendations": [{"issue_id": "placeholder_values", "title": "Replace placeholders", "issue_detected": "Detected 24 placeholder values", "recommended_solution": "Convert N/A to NULL", "preview_query": "SELECT `performance_score_text` FROM `employees__cleaning_test123` WHERE `performance_score_text` = 'N/A';", "cleaning_query": "UPDATE `employees__cleaning_test123` SET `performance_score_text` = NULL WHERE `performance_score_text` = 'N/A';", "validation_query": "SELECT COUNT(*) FROM `employees__cleaning_test123` WHERE `performance_score_text` = 'N/A';", "expected_result": "24 placeholders cleared", "risks_and_assumptions": "Review first", "is_modifying": True, "category": "missing_placeholder", "affected_records": 24, "affected_percentage": 24.0}]}),
             None
         )):

        mock_sb.side_effect = lambda label, *args, **kwargs: (
            "employees" if "Target Table" in label else "performance_score_text"
        )
        mock_btn.side_effect = lambda label, *args, **kwargs: "Analyze with AI" in label

        render_ai_column_cleaning_view(engine=mock_engine, db_name="hr_db")

        # Verify chat messages were stored and rendered
        assert len(st.session_state._ai_col_chat_messages) == 2
        assert st.session_state._ai_col_chat_messages[0]["role"] == "user"
        assert st.session_state._ai_col_chat_messages[1]["role"] == "assistant"
        assert "24 placeholder values" in st.session_state._ai_col_chat_messages[1]["content"]

        # Verify markdown contains AI analysis content
        md_texts = " ".join([str(call[0][0]) for call in mock_md.call_args_list if call[0]])
        assert "24 placeholder values" in md_texts


def test_ai_column_recommendations_invalidated_on_table_or_column_change():
    """Verify that switching column or table clears cached AI recommendations."""
    from src.column_profiling_engine import ColumnProfileResult, ValuePatternCategory
    from src.ai_column_recommender import AIAnalysisResult

    st.session_state._ai_col_profile_result = ColumnProfileResult(
        table_name="employees",
        column_name="performance_score_text",
        total_records=10,
        non_null_count=10,
        null_count=0,
        missing_count=0,
        dominant_pattern=ValuePatternCategory.NUMERIC_ONLY.value,
        success=True,
    )
    st.session_state._ai_col_active_selection = ("employees", "performance_score_text")
    st.session_state._ai_col_analysis_result = AIAnalysisResult(
        table_name="employees",
        column_name="performance_score_text",
        workspace_table="employees__cleaning_ws",
        dialect="mysql",
        recommendations=[],
        success=True,
    )
    st.session_state._ai_col_chat_messages = [
        {"role": "user", "content": "Old column question", "timestamp": "10:00"},
        {"role": "assistant", "content": "Old column answer", "timestamp": "10:01"},
    ]

    mock_engine = MagicMock()
    with patch("src.metadata.MySQLMetadataInspector.get_tables", return_value=["employees"]), \
         patch("src.metadata.MySQLMetadataInspector.get_table_schema", return_value=[
             {"Column Name": "performance_score_text", "Data Type": "VARCHAR(50)"},
             {"Column Name": "department", "Data Type": "VARCHAR(100)"},
         ]), \
         patch("streamlit.selectbox") as mock_sb, \
         patch("streamlit.button", return_value=False):

        # User changes selection to "department"
        mock_sb.side_effect = lambda label, *args, **kwargs: (
            "employees" if "Target Table" in label else "department"
        )

        render_ai_column_cleaning_view(engine=mock_engine, db_name="hr_db")

        # Stale recommendations and profile should be cleared
        assert st.session_state._ai_col_analysis_result is None
        assert st.session_state._ai_col_profile_result is None
        assert st.session_state._ai_col_chat_messages == []


def test_ai_column_rules_fallback_alert_rendered():
    """Verify informative alert is rendered when recommendations come from rules fallback."""
    from src.column_profiling_engine import ColumnProfileResult, ValuePatternCategory

    mock_profile = ColumnProfileResult(
        table_name="sales",
        column_name="amount",
        column_declared_type="VARCHAR(20)",
        total_records=50,
        non_null_count=50,
        null_count=0,
        missing_count=0,
        dominant_pattern=ValuePatternCategory.NUMERIC_ONLY.value,
        success=True,
    )
    st.session_state._ai_col_profile_result = mock_profile
    st.session_state._ai_col_active_selection = ("sales", "amount")
    st.session_state._ai_col_chat_messages = [
        {"role": "user", "content": "Analyze this column...", "timestamp": "10:00"},
        {"role": "assistant", "content": "AI analysis failed: Connection refused to AI provider. Rule engine generated fallback recommendations.", "timestamp": "10:01"},
    ]

    mock_engine = MagicMock()
    with patch("src.metadata.MySQLMetadataInspector.get_tables", return_value=["sales"]), \
         patch("src.metadata.MySQLMetadataInspector.get_table_schema", return_value=[
             {"Column Name": "amount", "Data Type": "VARCHAR(20)"}
         ]), \
         patch("streamlit.selectbox") as mock_sb, \
         patch("streamlit.button", return_value=False), \
         patch("streamlit.markdown") as mock_md:

        mock_sb.side_effect = lambda label, *args, **kwargs: (
            "sales" if "Target Table" in label else "amount"
        )

        render_ai_column_cleaning_view(engine=mock_engine, db_name="sales_db")

        md_texts = " ".join([str(call[0][0]) for call in mock_md.call_args_list if call[0]])
        assert "Grounded Rule Engine Active" in md_texts or "AI Endpoint Offline" in md_texts


def test_ai_column_debug_payload_section_rendered():
    """Verify Debug: Exact Data Sent to AI section renders with textarea and Copy Payload button."""
    from src.column_profiling_engine import ColumnProfileResult, ValuePatternCategory
    from src.ai_column_recommender import AIAnalysisResult

    mock_profile = ColumnProfileResult(
        table_name="employees",
        column_name="performance_score_text",
        column_declared_type="VARCHAR(50)",
        total_records=100,
        non_null_count=76,
        null_count=0,
        missing_count=24,
        placeholder_records=24,
        dominant_pattern=ValuePatternCategory.NUMERIC_ONLY.value,
        success=True,
    )

    mock_debug_entry = {
        "request_index": 1,
        "model": "gpt-4o",
        "status": "sent_success",
        "status_description": "Successfully dispatched to model and received response.",
        "payload": {
            "model": "gpt-4o",
            "temperature": 0.1,
            "max_tokens": 3200,
            "messages": [
                {"role": "system", "content": "System prompt for MySQL staging"},
                {"role": "user", "content": "User prompt for performance_score_text with 24 N/A"},
            ],
        },
    }

    mock_analysis = AIAnalysisResult(
        table_name="employees",
        column_name="performance_score_text",
        workspace_table="employees__cleaning_ws",
        dialect="mysql",
        recommendations=[],
        summary_narrative="Analysis complete.",
        success=True,
        source="ai",
        payload_debug=[mock_debug_entry],
    )

    st.session_state._ai_col_profile_result = mock_profile
    st.session_state._ai_col_active_selection = ("employees", "performance_score_text")
    st.session_state._ai_col_analysis_result = mock_analysis
    st.session_state._ai_col_payload_debug = [mock_debug_entry]

    mock_engine = MagicMock()
    with patch("src.metadata.MySQLMetadataInspector.get_tables", return_value=["employees"]), \
         patch("src.metadata.MySQLMetadataInspector.get_table_schema", return_value=[
             {"Column Name": "performance_score_text", "Data Type": "VARCHAR(50)"}
         ]), \
         patch("streamlit.selectbox") as mock_sb, \
         patch("streamlit.button", return_value=False) as mock_btn, \
         patch("streamlit.text_area") as mock_ta, \
         patch("streamlit.expander") as mock_exp:

        mock_sb.side_effect = lambda label, *args, **kwargs: (
            "employees" if "Target Table" in label else "performance_score_text"
        )

        render_ai_column_cleaning_view(engine=mock_engine, db_name="hr_db")

        # Verify expander was called with Debug title
        exp_labels = [call[0][0] for call in mock_exp.call_args_list if call[0]]
        assert any("Debug: Exact Data Sent to AI" in l for l in exp_labels)

        # Verify Copy Payload button was rendered
        btn_labels = [call[0][0] for call in mock_btn.call_args_list if call[0]]
        assert any("Copy Payload" in b for b in btn_labels)

        # Verify read-only text area was called
        assert mock_ta.called
        debug_call = next(
            call for call in mock_ta.call_args_list
            if call[1].get("key") == "ai_col_debug_payload_textarea"
        )
        ta_val = debug_call[1].get("value", "")
        assert "System prompt for MySQL staging" in ta_val
        assert "performance_score_text with 24 N/A" in ta_val
        assert debug_call[1].get("disabled") is True


def test_ai_column_debug_payload_section_hidden_when_flag_disabled():
    """Verify Debug: Exact Data Sent to AI is not rendered when SHOW_AI_PAYLOAD_DEBUG = False."""
    from src.column_profiling_engine import ColumnProfileResult, ValuePatternCategory
    from src.ai_column_recommender import AIAnalysisResult
    import ui.ai_column_cleaning_view

    mock_profile = ColumnProfileResult(
        table_name="employees",
        column_name="performance_score_text",
        total_records=100,
        success=True,
    )
    mock_debug_entry = {
        "request_index": 1,
        "model": "gpt-4o",
        "status": "sent_success",
        "payload": {"messages": [{"role": "system", "content": "test"}]},
    }
    mock_analysis = AIAnalysisResult(
        table_name="employees",
        column_name="performance_score_text",
        workspace_table="employees__cleaning_ws",
        dialect="mysql",
        recommendations=[],
        success=True,
        payload_debug=[mock_debug_entry],
    )

    st.session_state._ai_col_profile_result = mock_profile
    st.session_state._ai_col_active_selection = ("employees", "performance_score_text")
    st.session_state._ai_col_analysis_result = mock_analysis
    st.session_state._ai_col_payload_debug = [mock_debug_entry]

    mock_engine = MagicMock()
    with patch.object(ui.ai_column_cleaning_view, "SHOW_AI_PAYLOAD_DEBUG", False), \
         patch("src.metadata.MySQLMetadataInspector.get_tables", return_value=["employees"]), \
         patch("src.metadata.MySQLMetadataInspector.get_table_schema", return_value=[
             {"Column Name": "performance_score_text", "Data Type": "VARCHAR(50)"}
         ]), \
         patch("streamlit.selectbox") as mock_sb, \
         patch("streamlit.button", return_value=False), \
         patch("streamlit.expander") as mock_exp:

        mock_sb.side_effect = lambda label, *args, **kwargs: (
            "employees" if "Target Table" in label else "performance_score_text"
        )

        render_ai_column_cleaning_view(engine=mock_engine, db_name="hr_db")

        # Verify Debug expander was NOT rendered
        exp_labels = [call[0][0] for call in mock_exp.call_args_list if call[0]]
        assert not any("Debug: Exact Data Sent to AI" in l for l in exp_labels)


def test_ai_column_view_renders_fallback_alert_when_ai_fails():
    """Verify UI displays failure message when AI request fails."""
    from src.column_profiling_engine import ColumnProfileResult

    mock_profile = ColumnProfileResult(
        table_name="employees",
        column_name="performance_score_text",
        total_records=100,
        success=True,
    )

    st.session_state._ai_col_profile_result = mock_profile
    st.session_state._ai_col_active_selection = ("employees", "performance_score_text")
    st.session_state._ai_col_chat_messages = [
        {"role": "user", "content": "Analyze this column...", "timestamp": "10:00"},
        {"role": "assistant", "content": "⚠️ Error: HTTP 500: Failed to generate completions", "timestamp": "10:01"},
    ]

    mock_engine = MagicMock()
    with patch("src.metadata.MySQLMetadataInspector.get_tables", return_value=["employees"]), \
         patch("src.metadata.MySQLMetadataInspector.get_table_schema", return_value=[
             {"Column Name": "performance_score_text", "Data Type": "VARCHAR(50)"}
         ]), \
         patch("streamlit.selectbox") as mock_sb, \
         patch("streamlit.button", return_value=False), \
         patch("streamlit.markdown") as mock_md:

        mock_sb.side_effect = lambda label, *args, **kwargs: (
            "employees" if "Target Table" in label else "performance_score_text"
        )

        render_ai_column_cleaning_view(engine=mock_engine, db_name="hr_db")

        md_texts = " ".join([str(call[0][0]) for call in mock_md.call_args_list if call[0]])
        assert "HTTP 500: Failed to generate completions" in md_texts


# ─────────────────────────────────────────────────────────────────
# Phase 4B Scope Correction Tests
# ─────────────────────────────────────────────────────────────────

def test_ai_column_analyze_button_enabled_when_column_ai_flag_false():
    """Verify 'Analyze with AI' button is enabled when TEMP_DISABLE_COLUMN_AI_ANALYSIS = False."""
    from src.ai_service import TEMP_DISABLE_COLUMN_AI_ANALYSIS

    assert TEMP_DISABLE_COLUMN_AI_ANALYSIS is False, (
        "Column AI analysis flag should be False (enabled) after Phase 4B scope correction"
    )

    from src.column_profiling_engine import ColumnProfileResult, ValuePatternCategory

    mock_profile_res = ColumnProfileResult(
        table_name="employees",
        column_name="performance_score_text",
        column_declared_type="VARCHAR(50)",
        total_records=100,
        non_null_count=76,
        null_count=0,
        missing_count=24,
        placeholder_records=24,
        dominant_pattern=ValuePatternCategory.NUMERIC_ONLY.value,
        dominant_pattern_label="Numeric Only",
        dominant_pattern_percentage=76.0,
        percentage_denominator="total_records_scanned",
        counts={
            ValuePatternCategory.NUMERIC_ONLY.value: 76,
            ValuePatternCategory.MISSING_PLACEHOLDER.value: 24,
        },
        percentages={
            ValuePatternCategory.NUMERIC_ONLY.value: 76.0,
            ValuePatternCategory.MISSING_PLACEHOLDER.value: 24.0,
        },
        success=True,
    )

    st.session_state._ai_col_profile_result = mock_profile_res
    st.session_state._ai_col_active_selection = ("employees", "performance_score_text")

    mock_engine = MagicMock()
    with patch("src.metadata.MySQLMetadataInspector.get_tables", return_value=["employees"]), \
         patch("src.metadata.MySQLMetadataInspector.get_table_schema", return_value=[
             {"Column Name": "performance_score_text", "Data Type": "VARCHAR(50)"}
         ]), \
         patch("streamlit.selectbox") as mock_sb, \
         patch("streamlit.button", return_value=False) as mock_btn:

        mock_sb.side_effect = lambda label, *args, **kwargs: (
            "employees" if "Target Table" in label else "performance_score_text"
        )

        render_ai_column_cleaning_view(engine=mock_engine, db_name="hr_db")

        # Verify "Analyze with AI" button is enabled (disabled=False)
        analyze_btn_calls = [call for call in mock_btn.call_args_list
                             if call[0] and "Analyze with AI" in call[0][0]]
        assert len(analyze_btn_calls) == 1, (
            "Expected exactly one 'Analyze with AI' button"
        )
        _, kwargs = analyze_btn_calls[0]
        assert kwargs.get("disabled") is False, (
            "Analyze with AI button should be enabled when TEMP_DISABLE_COLUMN_AI_ANALYSIS = False"
        )


def test_ai_column_analyze_table_button_disabled():
    """Verify 'Analyze Table' button remains disabled when TEMP_DISABLE_AI_ANALYSIS = True."""
    import ui.ai_assistant_view as aav
    from src.ai_service import TEMP_DISABLE_AI_ANALYSIS

    assert TEMP_DISABLE_AI_ANALYSIS is True, (
        "Master AI analysis flag should be True (disabled) for table-level entry points"
    )

    mock_engine = MagicMock()
    st.session_state.connected = True
    st.session_state.engine = mock_engine
    st.session_state.selected_db = "hr_db"
    st.session_state.selected_table = "employees"
    st.session_state.ai_table_profile = None
    st.session_state.ai_table_analysis = None

    with patch("src.metadata.MySQLMetadataInspector.get_databases", return_value=["hr_db"]), \
         patch("src.metadata.MySQLMetadataInspector.get_tables", return_value=["employees"]), \
         patch("streamlit.selectbox") as mock_sb, \
         patch("streamlit.button", return_value=False) as mock_btn:

        def selectbox_side_effect(label, *args, **kwargs):
            if "Database" in label:
                return "hr_db"
            if "Table" in label:
                return "employees"
            if "Provider" in label:
                return "openai"
            if "Model" in label:
                return "gpt-4o"
            return None

        mock_sb.side_effect = selectbox_side_effect

        aav.render_ai_assistant_page()

        # Verify "Analyze Table" button is disabled (disabled=True)
        analyze_btn_calls = [call for call in mock_btn.call_args_list
                             if call[0] and "Analyze Table" in call[0][0]]
        assert len(analyze_btn_calls) == 1, (
            "Expected exactly one 'Analyze Table' button"
        )
        _, kwargs = analyze_btn_calls[0]
        assert kwargs.get("disabled") is True, (
            "Analyze Table button should remain disabled when TEMP_DISABLE_AI_ANALYSIS = True"
        )


def test_ai_column_refresh_profiling_button_disabled():
    """Verify 'Refresh Profiling' button remains disabled when TEMP_DISABLE_AI_ANALYSIS = True."""
    import ui.ai_assistant_view as aav
    from src.ai_service import TEMP_DISABLE_AI_ANALYSIS

    assert TEMP_DISABLE_AI_ANALYSIS is True

    mock_engine = MagicMock()
    st.session_state.connected = True
    st.session_state.engine = mock_engine
    st.session_state.selected_db = "hr_db"
    st.session_state.selected_table = "employees"
    st.session_state.ai_table_profile = None
    st.session_state.ai_table_analysis = None

    with patch("src.metadata.MySQLMetadataInspector.get_databases", return_value=["hr_db"]), \
         patch("src.metadata.MySQLMetadataInspector.get_tables", return_value=["employees"]), \
         patch("streamlit.selectbox") as mock_sb, \
         patch("streamlit.button", return_value=False) as mock_btn:

        def selectbox_side_effect(label, *args, **kwargs):
            if "Database" in label:
                return "hr_db"
            if "Table" in label:
                return "employees"
            if "Provider" in label:
                return "openai"
            if "Model" in label:
                return "gpt-4o"
            return None

        mock_sb.side_effect = selectbox_side_effect

        aav.render_ai_assistant_page()

        # Verify "Refresh Profiling" button is disabled (disabled=True)
        refresh_btn_calls = [call for call in mock_btn.call_args_list
                             if call[0] and "Refresh Profiling" in call[0][0]]
        assert len(refresh_btn_calls) == 1, (
            "Expected exactly one 'Refresh Profiling' button"
        )
        _, kwargs = refresh_btn_calls[0]
        assert kwargs.get("disabled") is True, (
            "Refresh Profiling button should remain disabled when TEMP_DISABLE_AI_ANALYSIS = True"
        )


def test_ai_column_ask_ai_button_disabled():
    """Verify 'Ask AI about column' button remains disabled when TEMP_DISABLE_AI_ANALYSIS = True."""
    import ui.ai_assistant_view as aav
    from src.ai_service import TEMP_DISABLE_AI_ANALYSIS

    assert TEMP_DISABLE_AI_ANALYSIS is True, (
        "Master AI analysis flag should be True (disabled) for table-level entry points"
    )

    # Verify the Ask AI about column button uses TEMP_DISABLE_AI_ANALYSIS
    # by inspecting the source code directly
    import inspect
    source = inspect.getsource(aav.render_ai_column_drilldown)
    assert "disabled=TEMP_DISABLE_AI_ANALYSIS" in source, (
        "Ask AI about column button should use TEMP_DISABLE_AI_ANALYSIS flag"
    )
    assert TEMP_DISABLE_AI_ANALYSIS is True, (
        "Ask AI about column button should be disabled when TEMP_DISABLE_AI_ANALYSIS = True"
    )


def test_ai_column_no_disabled_alert_when_column_ai_enabled():
    """Verify no 'AI Analysis Temporarily Disabled' alert when column AI is enabled."""
    from src.ai_service import TEMP_DISABLE_COLUMN_AI_ANALYSIS
    from src.column_profiling_engine import ColumnProfileResult, ValuePatternCategory

    assert TEMP_DISABLE_COLUMN_AI_ANALYSIS is False

    mock_profile_res = ColumnProfileResult(
        table_name="employees",
        column_name="performance_score_text",
        column_declared_type="VARCHAR(50)",
        total_records=100,
        non_null_count=76,
        null_count=0,
        missing_count=24,
        placeholder_records=24,
        dominant_pattern=ValuePatternCategory.NUMERIC_ONLY.value,
        dominant_pattern_label="Numeric Only",
        dominant_pattern_percentage=76.0,
        percentage_denominator="total_records_scanned",
        counts={
            ValuePatternCategory.NUMERIC_ONLY.value: 76,
            ValuePatternCategory.MISSING_PLACEHOLDER.value: 24,
        },
        percentages={
            ValuePatternCategory.NUMERIC_ONLY.value: 76.0,
            ValuePatternCategory.MISSING_PLACEHOLDER.value: 24.0,
        },
        success=True,
    )

    st.session_state._ai_col_profile_result = mock_profile_res
    st.session_state._ai_col_active_selection = ("employees", "performance_score_text")

    mock_engine = MagicMock()
    with patch("src.metadata.MySQLMetadataInspector.get_tables", return_value=["employees"]), \
         patch("src.metadata.MySQLMetadataInspector.get_table_schema", return_value=[
             {"Column Name": "performance_score_text", "Data Type": "VARCHAR(50)"}
         ]), \
         patch("streamlit.selectbox") as mock_sb, \
         patch("streamlit.button", return_value=False), \
         patch("streamlit.markdown") as mock_md:

        mock_sb.side_effect = lambda label, *args, **kwargs: (
            "employees" if "Target Table" in label else "performance_score_text"
        )

        render_ai_column_cleaning_view(engine=mock_engine, db_name="hr_db")

        # Verify no "AI Analysis Temporarily Disabled" alert is rendered
        md_calls = [str(call[0][0]) for call in mock_md.call_args_list if call[0]]
        combined = " ".join(md_calls)
        assert "AI Analysis Temporarily Disabled" not in combined, (
            "No disabled alert should appear when column AI analysis is enabled"
        )



