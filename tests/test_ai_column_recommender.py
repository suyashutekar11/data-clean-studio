"""
Tests for AI Column Query Recommender
tests/test_ai_column_recommender.py
"""

import json
from unittest.mock import MagicMock, patch
import pytest

from src.ai_column_config import AIColumnConfig
from src.ai_column_recommender import (
    ColumnQueryRecommendation,
    AIAnalysisResult,
    generate_grounded_recommendations,
    build_system_prompt,
    build_user_prompt,
    _parse_ai_recommendations,
    _validate_recommendation_item,
    _validate_statistical_grounding,
    analyze_column_with_ai,
    send_ai_chat_message,
)
from src.column_profiling_engine import (
    ColumnProfileResult,
    ValuePatternCategory,
    profile_values,
)


def test_grounded_recommendations_performance_score_text_24_na():
    """Verify performance_score_text with 24 N/As generates exact placeholder cleaning queries."""
    data = (
        ["N/A"] * 24 +
        ["95", "88.5", "100", "72", "80"] +
        ["Exceeds Expectations", "Needs Improvement", "Solid"] +
        [None, None] +
        [""]
    )
    profile = profile_values(data, column_name="performance_score_text", declared_type="VARCHAR(50)")
    workspace_tbl = "employees__cleaning_abc123"

    recs = generate_grounded_recommendations(profile, workspace_tbl, dialect="mysql")

    # Find the missing_placeholder recommendation
    ph_recs = [r for r in recs if r.issue_id == "missing_value_placeholders"]
    assert len(ph_recs) == 1
    ph_rec = ph_recs[0]

    assert ph_rec.affected_records == 24
    assert ph_rec.affected_percentage == 68.57
    assert "24 records" in ph_rec.issue_detected
    assert "employees__cleaning_abc123" in ph_rec.cleaning_query
    assert "employees__cleaning_abc123" in ph_rec.preview_query
    assert "employees__cleaning_abc123" in ph_rec.validation_query
    assert "UPDATE" in ph_rec.cleaning_query
    assert "SELECT" in ph_rec.preview_query
    assert "SELECT" in ph_rec.validation_query
    assert ph_rec.is_modifying is True


def test_grounded_recommendations_empty_and_whitespace():
    """Verify empty and whitespace strings generate nullification recommendation."""
    data = ["", "", "   ", "valid_text"]
    profile = profile_values(data, column_name="notes", declared_type="TEXT")
    workspace_tbl = "users__cleaning_test"

    recs = generate_grounded_recommendations(profile, workspace_tbl, dialect="mysql")
    empty_recs = [r for r in recs if r.issue_id == "empty_and_whitespace_strings"]
    assert len(empty_recs) == 1
    rec = empty_recs[0]

    assert rec.affected_records == 3
    assert "UPDATE `users__cleaning_test`" in rec.cleaning_query
    assert "SET `notes` = NULL" in rec.cleaning_query


def test_grounded_recommendations_numeric_special_formatting():
    """Verify formatted numbers ($1,000, 50%) generate symbol cleaning queries."""
    data = ["$1,200.00", "50%", "-10%"]
    profile = profile_values(data, column_name="rate", declared_type="VARCHAR(20)")
    workspace_tbl = "accounts__cleaning_test"

    recs = generate_grounded_recommendations(profile, workspace_tbl, dialect="mysql")
    ns_recs = [r for r in recs if r.issue_id == "formatted_numeric_symbols"]
    assert len(ns_recs) == 1
    rec = ns_recs[0]

    assert rec.affected_records == 3
    assert "REPLACE" in rec.cleaning_query
    assert "accounts__cleaning_test" in rec.cleaning_query


def test_grounded_recommendations_date_strings():
    """Verify date-like strings in VARCHAR generate standardization recommendations."""
    data = ["15/03/2023", "20/04/2023", "01/01/2024"]
    profile = profile_values(data, column_name="event_date", declared_type="VARCHAR(20)")
    workspace_tbl = "events__cleaning_test"

    recs = generate_grounded_recommendations(profile, workspace_tbl, dialect="mysql")
    date_recs = [r for r in recs if r.issue_id == "date_format_inconsistency"]
    assert len(date_recs) == 1
    rec = date_recs[0]

    assert rec.affected_records == 3
    assert "STR_TO_DATE" in rec.cleaning_query


def test_prompts_grounding_and_safety():
    """Verify prompts require targeting workspace table and include aggregated metrics."""
    data = ["N/A"] * 5 + ["100"] * 5
    profile = profile_values(data, column_name="score", declared_type="VARCHAR(10)")
    workspace_tbl = "tbl__cleaning_999"

    sys_prompt = build_system_prompt("mysql", workspace_tbl)
    usr_prompt = build_user_prompt(profile, workspace_tbl, "mysql")

    assert "tbl__cleaning_999" in sys_prompt
    assert "ZERO PRODUCTION RISK" in sys_prompt
    assert "tbl__cleaning_999" in usr_prompt
    assert "score" in usr_prompt
    assert "50.00%" in usr_prompt


def test_parse_ai_recommendations_valid_json_with_fences():
    """Verify parser accepts clean JSON (no Markdown fences — prohibited by Phase 3 spec)."""
    fake_json = {
        "summary": "Data has placeholder issues.",
        "recommendations": [
            {
                "issue_id": "test_ph",
                "title": "Clean Placeholders",
                "issue_detected": "Found 24 N/A entries",
                "recommended_solution": "Set to NULL",
                "preview_query": "SELECT * FROM `tbl__cleaning` WHERE col = 'N/A';",
                "cleaning_query": "UPDATE `tbl__cleaning` SET col = NULL WHERE col = 'N/A';",
                "validation_query": "SELECT COUNT(*) FROM `tbl__cleaning` WHERE col = 'N/A';",
                "expected_result": "Col becomes NULL",
                "risks_and_assumptions": "Assumes N/A is missing",
                "is_modifying": True,
                "category": "missing_placeholder",
                "affected_records": 24,
                "affected_percentage": 68.57,
            }
        ]
    }
    # Clean JSON only — Markdown fences are prohibited by the Phase 3 system prompt
    raw_clean = json.dumps(fake_json)

    mock_profile = MagicMock(spec=ColumnProfileResult)
    mock_profile.column_name = "col"
    mock_profile.total_records = 35
    mock_profile.null_count = 0
    mock_profile.missing_count = 0
    mock_profile.placeholder_count = 24
    mock_profile.empty_string_records = 0
    mock_profile.whitespace_records = 0
    mock_profile.counts = {}
    mock_profile.percentages = {}
    recs, summary = _parse_ai_recommendations(raw_clean, mock_profile, "tbl__cleaning", "mysql")

    assert len(recs) == 1
    assert recs[0].issue_id == "test_ph"
    assert recs[0].affected_records == 24
    assert summary == "Data has placeholder issues."


def test_parse_ai_recommendations_rejects_markdown_fences():
    """Verify parser REJECTS Markdown fences — prohibited by Phase 3 spec."""
    fake_json = {
        "summary": "Data has placeholder issues.",
        "recommendations": [
            {
                "issue_id": "test_ph",
                "title": "Clean Placeholders",
                "issue_detected": "Found 24 N/A entries",
                "recommended_solution": "Set to NULL",
                "preview_query": "SELECT * FROM `tbl__cleaning` WHERE col = 'N/A';",
                "cleaning_query": "UPDATE `tbl__cleaning` SET col = NULL WHERE col = 'N/A';",
                "validation_query": "SELECT COUNT(*) FROM `tbl__cleaning` WHERE col = 'N/A';",
                "expected_result": "Col becomes NULL",
                "risks_and_assumptions": "Assumes N/A is missing",
                "is_modifying": True,
                "category": "missing_placeholder",
                "affected_records": 24,
                "affected_percentage": 68.57,
            }
        ]
    }
    raw_markdown = f"```json\n{json.dumps(fake_json)}\n```"

    mock_profile = MagicMock(spec=ColumnProfileResult)
    mock_profile.column_name = "col"
    mock_profile.total_records = 35
    mock_profile.null_count = 0
    mock_profile.missing_count = 0
    mock_profile.placeholder_count = 0
    mock_profile.empty_string_records = 0
    mock_profile.whitespace_records = 0
    mock_profile.counts = {}
    mock_profile.percentages = {}
    try:
        _parse_ai_recommendations(raw_markdown, mock_profile, "tbl__cleaning", "mysql")
        assert False, "Expected ValueError for Markdown fences"
    except ValueError as exc:
        assert "JSON object" in str(exc) or "text outside" in str(exc)


def test_analyze_column_with_ai_success():
    """Verify analyze_column_with_ai calls OpenAI client and returns structured recommendations."""
    config = AIColumnConfig(
        base_url="https://api.example.com/v1",
        model_name="test-model",
        api_key="secret-key-12345",
    )
    data = ["N/A"] * 24 + ["100"] * 6
    profile = profile_values(data, column_name="score", declared_type="VARCHAR(20)")

    ai_json_resp = json.dumps({
        "summary": "AI identified score placeholders",
        "recommendations": [
            {
                "issue_id": "ai_placeholder_na",
                "title": "Convert N/A Placeholders to NULL",
                "issue_detected": "24 occurrences of 'N/A' detected (80.0%)",
                "recommended_solution": "Convert to NULL in staging",
                "preview_query": "SELECT score FROM `scores__cleaning` WHERE score = 'N/A';",
                "cleaning_query": "UPDATE `scores__cleaning` SET score = NULL WHERE score = 'N/A';",
                "validation_query": "SELECT COUNT(*) FROM `scores__cleaning` WHERE score = 'N/A';",
                "expected_result": "24 rows updated to NULL",
                "risks_and_assumptions": "None",
                "is_modifying": True,
                "category": "missing_placeholder",
                "affected_records": 24,
                "affected_percentage": 80.0,
            }
        ]
    })

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = ai_json_resp
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    with patch("openai.OpenAI", return_value=mock_client):
        result = analyze_column_with_ai(profile, config, workspace_table="scores__cleaning", dialect="mysql")

        assert result.success is True
        assert result.source == "ai"
        assert len(result.recommendations) == 1
        assert result.recommendations[0].issue_id == "ai_placeholder_na"
        assert result.recommendations[0].affected_records == 24
        assert "scores__cleaning" in result.recommendations[0].cleaning_query


def test_analyze_column_with_ai_fallback_on_network_error():
    """Verify that network/API exceptions trigger graceful fallback to grounded rules without exposing keys."""
    config = AIColumnConfig(
        base_url="https://api.example.com/v1",
        model_name="test-model",
        api_key="sensitive-key-9999",
    )
    data = ["N/A"] * 10 + ["50"] * 10
    profile = profile_values(data, column_name="score", declared_type="VARCHAR(20)")

    with patch("openai.OpenAI", side_effect=Exception("Failed to connect with sensitive-key-9999")):
        result = analyze_column_with_ai(profile, config, workspace_table="tbl__cleaning", dialect="mysql")

        assert result.success is False
        assert result.source == "rules_fallback"
        assert len(result.recommendations) > 0
        # Ensure raw API key is NEVER exposed in the error message
        assert "sensitive-key-9999" not in str(result.error_message)
        entry = result.payload_debug[0]
        assert entry["status"] == "transport_error"


def test_analyze_column_with_ai_unconfigured_fallback():
    """Verify that unconfigured AI configuration gracefully uses grounded recommendations."""
    config = AIColumnConfig(base_url="", model_name="", api_key="")
    data = ["N/A"] * 5 + ["hello"] * 5
    profile = profile_values(data, column_name="name", declared_type="VARCHAR(20)")

    result = analyze_column_with_ai(profile, config, workspace_table="users__cleaning", dialect="mysql")

    assert result.success is False
    assert result.source == "rules_fallback"
    assert len(result.recommendations) > 0
    assert any(r.issue_id == "missing_value_placeholders" for r in result.recommendations)
    assert result.payload_debug is not None
    assert result.payload_debug[0]["status"] == "not_sent_unconfigured"
    assert len(result.payload_debug[0]["payload"]["messages"]) == 2


def test_analyze_column_with_ai_captures_exact_debug_payload_performance_score_text():
    """Verify that Analyze with AI captures the exact request payload sent to the model for performance_score_text."""
    data = ["92.5"] * 76 + ["N/A"] * 24
    profile = profile_values(data, column_name="performance_score_text", declared_type="VARCHAR(50)")
    config = AIColumnConfig(base_url="https://api.openai.com/v1", model_name="gpt-4o", api_key="sk-test-secret-key-1234")

    mock_reply = json.dumps({
        "summary": "AI detected 24 missing-value placeholders.",
        "recommendations": [
            {
                "issue_id": "placeholder_na",
                "title": "Placeholder strings",
                "issue_detected": "24 records have N/A",
                "recommended_solution": "Convert to NULL",
                "preview_query": "SELECT `performance_score_text` FROM `employees__cleaning_test` WHERE `performance_score_text` = 'N/A';",
                "cleaning_query": "UPDATE `employees__cleaning_test` SET `performance_score_text` = NULL WHERE `performance_score_text` = 'N/A';",
                "validation_query": "SELECT COUNT(*) FROM `employees__cleaning_test` WHERE `performance_score_text` = 'N/A';",
                "expected_result": "Cleaned",
                "risks_and_assumptions": "None",
                "affected_records": 24,
                "affected_percentage": 24.0,
            }
        ]
    })

    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content=mock_reply))]

    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_resp

        result = analyze_column_with_ai(
            profile=profile,
            config=config,
            dialect="mysql",
            workspace_table="employees__cleaning_test",
        )

        # Verify debug payload exists
        assert result.payload_debug is not None
        assert len(result.payload_debug) == 1
        entry = result.payload_debug[0]
        assert entry["status"] == "sent_success"
        assert entry["model"] == "gpt-4o"

        payload = entry["payload"]
        assert payload["model"] == "gpt-4o"
        assert payload["temperature"] == 0.1
        assert payload["max_tokens"] in (2000, 2500, 3200, 8000)
        assert len(payload["messages"]) == 2

        sys_msg = payload["messages"][0]
        assert sys_msg["role"] == "system"
        assert "mysql" in sys_msg["content"].lower()
        assert "employees__cleaning_test" in sys_msg["content"]

        usr_msg = payload["messages"][1]
        assert usr_msg["role"] == "user"
        assert "performance_score_text" in usr_msg["content"]
        assert "24" in usr_msg["content"]
        assert "Missing-Value Placeholders" in usr_msg["content"]

        # Crucial security check: api_key must never appear in payload
        payload_str = json.dumps(entry)
        assert "sk-test-secret-key-1234" not in payload_str


def test_analyze_column_with_ai_captures_payload_on_timeout():
    """Verify that timeout during model execution preserves the exact request payload with failed status."""
    data = ["100"] * 10
    profile = profile_values(data, column_name="score", declared_type="INT")
    config = AIColumnConfig(base_url="https://api.openai.com/v1", model_name="gpt-4o", api_key="sk-test-key-5678")

    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        # Simulate timeout exception
        mock_client.chat.completions.create.side_effect = Exception("Request timed out after 30s")

        result = analyze_column_with_ai(
            profile=profile,
            config=config,
            dialect="mysql",
            workspace_table="test_tbl__cleaning_ws",
        )

        assert result.payload_debug is not None
        assert len(result.payload_debug) == 1
        entry = result.payload_debug[0]
        assert entry["status"] == "transport_error"
        assert "timed out" in entry["status_description"].lower()
        assert len(entry["payload"]["messages"]) == 2
        assert "sk-test-key-5678" not in json.dumps(entry)


# ─────────────────────────────────────────────────────────────────
# Phase 3: AI Response Parsing & Recommendation Validation Tests
# ─────────────────────────────────────────────────────────────────

def _make_profile() -> ColumnProfileResult:
    """Helper: small profile with 24 N/A placeholders out of 100 records."""
    data = ["92.5"] * 76 + ["N/A"] * 24
    return profile_values(data, column_name="performance_score_text", declared_type="VARCHAR(50)")


def _valid_ai_response() -> str:
    """Helper: a valid AI response JSON string."""
    return json.dumps({
        "summary": "AI detected missing-value placeholders.",
        "recommendations": [
            {
                "issue_id": "placeholder_na",
                "title": "Convert N/A Placeholders to NULL",
                "issue_detected": "24 records contain N/A placeholders",
                "recommended_solution": "Convert to NULL in staging",
                "preview_query": "SELECT `performance_score_text` FROM `employees__cleaning_test` WHERE `performance_score_text` = 'N/A';",
                "cleaning_query": "UPDATE `employees__cleaning_test` SET `performance_score_text` = NULL WHERE `performance_score_text` = 'N/A';",
                "validation_query": "SELECT COUNT(*) FROM `employees__cleaning_test` WHERE `performance_score_text` = 'N/A';",
                "expected_result": "24 rows updated to NULL",
                "risks_and_assumptions": "N/A values are missing data",
                "is_modifying": True,
                "category": "missing_placeholder",
                "affected_records": 24,
                "affected_percentage": 24.0,
            }
        ]
    })


# ── Test 1: Valid AI response → success, source="ai" ──
def test_phase3_valid_ai_response():
    """Valid JSON response with all required fields → success, source='ai'."""
    config = AIColumnConfig(
        base_url="https://api.example.com/v1",
        model_name="test-model",
        api_key="secret-key-12345",
    )
    profile = _make_profile()

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = _valid_ai_response()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    with patch("openai.OpenAI", return_value=mock_client):
        result = analyze_column_with_ai(
            profile, config, workspace_table="employees__cleaning_test", dialect="mysql"
        )

        assert result.success is True
        assert result.source == "ai"
        assert result.truncated is False
        assert len(result.recommendations) == 1
        assert result.recommendations[0].issue_id == "placeholder_na"
        assert result.recommendations[0].affected_records == 24
        assert result.recommendations[0].cleaning_query.startswith("UPDATE")
        assert result.recommendations[0].preview_query.startswith("SELECT")


# ── Test 2: Invalid JSON → content_error, source="rules_fallback" ──
def test_phase3_invalid_json():
    """Invalid JSON → content error, fallback labelled rules_fallback, not AI."""
    config = AIColumnConfig(
        base_url="https://api.example.com/v1",
        model_name="test-model",
        api_key="secret-key-12345",
    )
    profile = _make_profile()

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "This is not JSON at all, just conversational text."
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    with patch("openai.OpenAI", return_value=mock_client):
        result = analyze_column_with_ai(
            profile, config, workspace_table="employees__cleaning_test", dialect="mysql"
        )

        assert result.success is False
        assert result.source == "rules_fallback"
        # Grounded recommendations are generated (not empty), but clearly NOT AI-generated
        assert len(result.recommendations) > 0
        entry = result.payload_debug[0]
        assert entry["status"] == "content_error"
        assert "valid JSON object" in entry["sanitized_error_details"]


# ── Test 3: Missing required field → content_error ──
def test_phase3_missing_required_field():
    """Missing required field 'cleaning_query' → validation error."""
    config = AIColumnConfig(
        base_url="https://api.example.com/v1",
        model_name="test-model",
        api_key="secret-key-12345",
    )
    profile = _make_profile()

    bad = json.loads(_valid_ai_response())
    del bad["recommendations"][0]["cleaning_query"]
    bad_reply = json.dumps(bad)

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = bad_reply
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    with patch("openai.OpenAI", return_value=mock_client):
        result = analyze_column_with_ai(
            profile, config, workspace_table="employees__cleaning_test", dialect="mysql"
        )

        assert result.success is False
        assert result.source == "rules_fallback"
        entry = result.payload_debug[0]
        assert entry["status"] == "content_error"
        assert "cleaning_query" in entry["sanitized_error_details"]


# ── Test 4: Wrong field type → content_error ──
def test_phase3_wrong_field_type():
    """affected_records is a string instead of integer → validation error."""
    config = AIColumnConfig(
        base_url="https://api.example.com/v1",
        model_name="test-model",
        api_key="secret-key-12345",
    )
    profile = _make_profile()

    bad = json.loads(_valid_ai_response())
    bad["recommendations"][0]["affected_records"] = "twenty-four"
    bad_reply = json.dumps(bad)

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = bad_reply
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    with patch("openai.OpenAI", return_value=mock_client):
        result = analyze_column_with_ai(
            profile, config, workspace_table="employees__cleaning_test", dialect="mysql"
        )

        assert result.success is False
        assert result.source == "rules_fallback"
        entry = result.payload_debug[0]
        assert entry["status"] == "content_error"
        assert "affected_records" in entry["sanitized_error_details"]


# ── Test 5: Empty recommendations list → content_error ──
def test_phase3_empty_recommendations():
    """Empty recommendations array → validation error."""
    config = AIColumnConfig(
        base_url="https://api.example.com/v1",
        model_name="test-model",
        api_key="secret-key-12345",
    )
    profile = _make_profile()

    bad_reply = json.dumps({"summary": "none", "recommendations": []})

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = bad_reply
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    with patch("openai.OpenAI", return_value=mock_client):
        result = analyze_column_with_ai(
            profile, config, workspace_table="employees__cleaning_test", dialect="mysql"
        )

        assert result.success is False
        assert result.source == "rules_fallback"
        entry = result.payload_debug[0]
        assert entry["status"] == "content_error"
        assert "non-empty list" in entry["sanitized_error_details"]


# ── Test 6: Recommendation referencing unknown column → content_error ──
def test_phase3_unknown_column_reference():
    """SQL query references a column not in the profile → validation error."""
    config = AIColumnConfig(
        base_url="https://api.example.com/v1",
        model_name="test-model",
        api_key="secret-key-12345",
    )
    profile = _make_profile()

    bad = json.loads(_valid_ai_response())
    bad["recommendations"][0]["cleaning_query"] = (
        "UPDATE `employees__cleaning_test` SET `nonexistent_column` = NULL WHERE `nonexistent_column` = 'N/A';"
    )
    bad_reply = json.dumps(bad)

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = bad_reply
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    with patch("openai.OpenAI", return_value=mock_client):
        result = analyze_column_with_ai(
            profile, config, workspace_table="employees__cleaning_test", dialect="mysql"
        )

        assert result.success is False
        assert result.source == "rules_fallback"
        entry = result.payload_debug[0]
        assert entry["status"] == "content_error"
        assert "performance_score_text" in entry["sanitized_error_details"]


# ── Test 7: Duplicate issue_id → content_error ──
def test_phase3_duplicate_issue_id():
    """Duplicate issue_id → validation error."""
    config = AIColumnConfig(
        base_url="https://api.example.com/v1",
        model_name="test-model",
        api_key="secret-key-12345",
    )
    profile = _make_profile()

    rec = json.loads(_valid_ai_response())["recommendations"][0]
    bad_reply = json.dumps({
        "summary": "dup",
        "recommendations": [rec, dict(rec, issue_id=rec["issue_id"])]
    })

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = bad_reply
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    with patch("openai.OpenAI", return_value=mock_client):
        result = analyze_column_with_ai(
            profile, config, workspace_table="employees__cleaning_test", dialect="mysql"
        )

        assert result.success is False
        assert result.source == "rules_fallback"
        entry = result.payload_debug[0]
        assert entry["status"] == "content_error"
        assert "duplicate issue_id" in entry["sanitized_error_details"]


# ── Test 8: Contradictory is_modifying/cleaning_query → content_error ──
def test_phase3_contradictory_modifying_flag():
    """is_modifying=true but cleaning_query is SELECT-only → validation error."""
    config = AIColumnConfig(
        base_url="https://api.example.com/v1",
        model_name="test-model",
        api_key="secret-key-12345",
    )
    profile = _make_profile()

    bad = json.loads(_valid_ai_response())
    bad["recommendations"][0]["cleaning_query"] = (
        "SELECT `performance_score_text` FROM `employees__cleaning_test` WHERE `performance_score_text` = 'N/A';"
    )
    bad_reply = json.dumps(bad)

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = bad_reply
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    with patch("openai.OpenAI", return_value=mock_client):
        result = analyze_column_with_ai(
            profile, config, workspace_table="employees__cleaning_test", dialect="mysql"
        )

        assert result.success is False
        assert result.source == "rules_fallback"
        entry = result.payload_debug[0]
        assert entry["status"] == "content_error"
        assert "is_modifying=true" in entry["sanitized_error_details"]


# ── Test 9: Truncated response → content_error, not success ──
def test_phase3_truncated_response():
    """finish_reason='length' → content error, not marked as successful AI analysis."""
    config = AIColumnConfig(
        base_url="https://api.example.com/v1",
        model_name="test-model",
        api_key="secret-key-12345",
    )
    profile = _make_profile()

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.finish_reason = "length"
    mock_choice.message.content = _valid_ai_response()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    with patch("openai.OpenAI", return_value=mock_client):
        result = analyze_column_with_ai(
            profile, config, workspace_table="employees__cleaning_test", dialect="mysql"
        )

        assert result.success is False
        assert result.source == "rules_fallback"
        assert result.truncated is True
        assert result.finish_reason == "length"
        entry = result.payload_debug[0]
        assert entry["status"] == "content_error"
        assert "truncated" in entry["sanitized_error_details"].lower()


# ── Test 10: Transport error vs content error distinction ──
def test_phase3_transport_vs_content_error_distinction():
    """Transport errors → status 'transport_error'; content errors → 'content_error'."""
    config = AIColumnConfig(
        base_url="https://api.example.com/v1",
        model_name="test-model",
        api_key="secret-key-12345",
    )
    profile = _make_profile()

    # Transport error
    with patch("openai.OpenAI", side_effect=Exception("Network failure")):
        result = analyze_column_with_ai(
            profile, config, workspace_table="employees__cleaning_test", dialect="mysql"
        )
        assert result.source == "rules_fallback"
        assert result.payload_debug[0]["status"] == "transport_error"
        assert result.http_status is None

    # Content error (invalid JSON)
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "not json"
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    with patch("openai.OpenAI", return_value=mock_client):
        result = analyze_column_with_ai(
            profile, config, workspace_table="employees__cleaning_test", dialect="mysql"
        )
        assert result.source == "rules_fallback"
        assert result.payload_debug[0]["status"] == "content_error"


# ── Test 11: Rule-based fallback correctly labelled ──
def test_phase3_fallback_not_labelled_as_ai():
    """Rule-based fallback is never labelled source='ai' or success=True."""
    config = AIColumnConfig(
        base_url="https://api.example.com/v1",
        model_name="test-model",
        api_key="secret-key-12345",
    )
    profile = _make_profile()

    # Trigger content error
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "invalid response"
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    with patch("openai.OpenAI", return_value=mock_client):
        result = analyze_column_with_ai(
            profile, config, workspace_table="employees__cleaning_test", dialect="mysql"
        )

        assert result.source == "rules_fallback"
        assert result.success is False
        assert "not AI-generated" in result.summary_narrative
        # No AI-generated claims
        assert result.source != "ai"


# ─────────────────────────────────────────────────────────────────
# Phase 3A: Exact Column Matching & Statistical Grounding Tests
# ─────────────────────────────────────────────────────────────────

def _make_profile_with_stats() -> ColumnProfileResult:
    """Profile with 100 records, 24 N/A placeholders (24.0%)."""
    data = ["92.5"] * 76 + ["N/A"] * 24
    return profile_values(data, column_name="performance_score_text", declared_type="VARCHAR(50)")


def _make_valid_item(col_name: str = "performance_score_text") -> Dict[str, Any]:
    """Build a valid recommendation item referencing the given column."""
    ws = "employees__cleaning_test"
    q_col = "`" + col_name + "`"
    q_ws = "`" + ws + "`"
    return {
        "issue_id": "test_col_match",
        "title": "Test Column Match",
        "issue_detected": f"Column {col_name} has issues",
        "recommended_solution": "Clean the column",
        "preview_query": f"SELECT {q_col} FROM {q_ws} WHERE {q_col} = 'N/A';",
        "cleaning_query": f"UPDATE {q_ws} SET {q_col} = NULL WHERE {q_col} = 'N/A';",
        "validation_query": f"SELECT COUNT(*) FROM {q_ws} WHERE {q_col} = 'N/A';",
        "expected_result": "Column cleaned",
        "risks_and_assumptions": "Low risk",
        "is_modifying": True,
        "category": "missing_placeholder",
        "affected_records": 24,
        "affected_percentage": 24.0,
    }


# ── Test 3A-1: Exact match for a valid column name ──
def test_phase3a_exact_column_match_valid():
    """Valid column name referenced as exact identifier passes validation."""
    profile = _make_profile_with_stats()
    item = _make_valid_item("performance_score_text")
    rec, err = _validate_recommendation_item(
        item, profile, "employees__cleaning_test", "mysql", set(), 0
    )
    assert err is None, f"Unexpected error: {err}"
    assert rec is not None
    assert rec.issue_id == "test_col_match"


# ── Test 3A-2: Similar column names (salary vs salary_text) ──
def test_phase3a_similar_column_names_rejected():
    """'salary' should NOT match 'salary_text' — prevents substring confusion."""
    profile = _make_profile_with_stats()
    profile.column_name = "salary"
    item = {
        "issue_id": "test_sal",
        "title": "Salary Test",
        "issue_detected": "Salary issues",
        "recommended_solution": "Clean salary",
        "preview_query": "SELECT `salary_text` FROM `employees__cleaning_test` WHERE `salary_text` = 'N/A';",
        "cleaning_query": "UPDATE `employees__cleaning_test` SET `salary_text` = NULL WHERE `salary_text` = 'N/A';",
        "validation_query": "SELECT COUNT(*) FROM `employees__cleaning_test` WHERE `salary_text` = 'N/A';",
        "expected_result": "Cleaned",
        "risks_and_assumptions": "Low risk",
        "is_modifying": True,
        "category": "missing_placeholder",
        "affected_records": 10,
        "affected_percentage": 10.0,
    }
    rec, err = _validate_recommendation_item(
        item, profile, "employees__cleaning_test", "mysql", set(), 0
    )
    assert err is not None, "Expected error for 'salary' vs 'salary_text' confusion"
    assert "salary" in err
    assert rec is None


# ── Test 3A-3: Quoted identifiers and dialect conventions ──
def test_phase3a_quoted_identifiers_mysql():
    """MySQL backtick-quoted column names are accepted."""
    profile = _make_profile_with_stats()
    item = _make_valid_item("performance_score_text")
    rec, err = _validate_recommendation_item(
        item, profile, "employees__cleaning_test", "mysql", set(), 0
    )
    assert err is None, f"Unexpected error: {err}"
    assert rec is not None


def test_phase3a_quoted_identifiers_sqlite():
    """SQLite double-quoted column names are accepted."""
    profile = _make_profile_with_stats()
    ws = "employees__cleaning_test"
    q_col = '"performance_score_text"'
    q_ws = '"employees__cleaning_test"'
    item = {
        "issue_id": "test_sqlite",
        "title": "SQLite Test",
        "issue_detected": "SQLite column issues",
        "recommended_solution": "Clean the column",
        "preview_query": f"SELECT {q_col} FROM {q_ws} WHERE {q_col} = 'N/A';",
        "cleaning_query": f"UPDATE {q_ws} SET {q_col} = NULL WHERE {q_col} = 'N/A';",
        "validation_query": f"SELECT COUNT(*) FROM {q_ws} WHERE {q_col} = 'N/A';",
        "expected_result": "Cleaned",
        "risks_and_assumptions": "Low risk",
        "is_modifying": True,
        "category": "missing_placeholder",
        "affected_records": 24,
        "affected_percentage": 24.0,
    }
    rec, err = _validate_recommendation_item(
        item, profile, ws, "sqlite", set(), 0
    )
    assert err is None, f"Unexpected error: {err}"
    assert rec is not None


# ── Test 3A-4: Unknown and ambiguous identifiers ──
def test_phase3a_unknown_column_rejected():
    """Column name not matching the profiled column is rejected."""
    profile = _make_profile_with_stats()
    item = _make_valid_item("nonexistent_column")
    rec, err = _validate_recommendation_item(
        item, profile, "employees__cleaning_test", "mysql", set(), 0
    )
    assert err is not None
    assert "performance_score_text" in err
    assert rec is None


# ── Test 3A-5: Correct affected-record count and percentage ──
def test_phase3a_correct_counts_and_percentage():
    """Correct affected_records and matching percentage pass validation."""
    profile = _make_profile_with_stats()
    item = _make_valid_item("performance_score_text")
    rec, err = _validate_recommendation_item(
        item, profile, "employees__cleaning_test", "mysql", set(), 0
    )
    assert err is None, f"Unexpected error: {err}"
    assert rec is not None
    assert rec.affected_records == 24
    assert rec.affected_percentage == 24.0


# ── Test 3A-6: Incorrect counts and percentages ──
def test_phase3a_incorrect_count():
    """affected_records exceeding total_records is rejected."""
    profile = _make_profile_with_stats()
    item = _make_valid_item("performance_score_text")
    item["affected_records"] = 150
    item["affected_percentage"] = 150.0
    rec, err = _validate_recommendation_item(
        item, profile, "employees__cleaning_test", "mysql", set(), 0
    )
    assert err is not None
    assert "outside valid range" in err
    assert rec is None


def test_phase3a_incorrect_percentage():
    """affected_percentage inconsistent with affected_records is rejected."""
    profile = _make_profile_with_stats()
    item = _make_valid_item("performance_score_text")
    item["affected_records"] = 24
    item["affected_percentage"] = 99.9
    rec, err = _validate_recommendation_item(
        item, profile, "employees__cleaning_test", "mysql", set(), 0
    )
    assert err is not None
    assert "inconsistent" in err
    assert rec is None


# ── Test 3A-7: Boundary values and rounding tolerance ──
def test_phase3a_rounding_tolerance_boundary():
    """Percentage within rounding tolerance (±0.01) passes."""
    profile = _make_profile_with_stats()
    item = _make_valid_item("performance_score_text")
    item["affected_records"] = 24
    item["affected_percentage"] = 24.005
    rec, err = _validate_recommendation_item(
        item, profile, "employees__cleaning_test", "mysql", set(), 0
    )
    assert err is None, f"Unexpected error: {err}"
    assert rec is not None


def test_phase3a_rounding_tolerance_exceeded():
    """Percentage outside rounding tolerance is rejected."""
    profile = _make_profile_with_stats()
    item = _make_valid_item("performance_score_text")
    item["affected_records"] = 24
    item["affected_percentage"] = 24.5
    rec, err = _validate_recommendation_item(
        item, profile, "employees__cleaning_test", "mysql", set(), 0
    )
    assert err is not None
    assert "inconsistent" in err
    assert rec is None


# ── Test 3A-8: Missing profile evidence ──
def test_phase3a_missing_profile_evidence():
    """Profile with total_records=0 cannot verify statistically — handled explicitly."""
    profile = ColumnProfileResult(
        table_name="empty",
        column_name="col",
        total_records=0,
        placeholder_count=0,
    )
    item = _make_valid_item("col")
    item["affected_records"] = 5
    item["affected_percentage"] = 100.0
    rec, err = _validate_recommendation_item(
        item, profile, "employees__cleaning_test", "mysql", set(), 0
    )
    assert err is None, f"Unexpected error when no profile evidence: {err}"
    assert rec is not None


# ── Test 3A-9: Existing valid recommendations remain compatible ──
def test_phase3a_existing_valid_recommendations_compatible():
    """Real-world performance_score_text scenario passes end-to-end."""
    profile = _make_profile_with_stats()
    item = _make_valid_item("performance_score_text")
    rec, err = _validate_recommendation_item(
        item, profile, "employees__cleaning_test", "mysql", set(), 0
    )
    assert err is None, f"Unexpected error: {err}"
    assert rec is not None
    assert rec.affected_records == 24
    assert rec.affected_percentage == 24.0
    assert rec.category == "missing_placeholder"


# ─────────────────────────────────────────────────────────────────
# Phase 3B: Final Identifier Validation & Grounding Verification Tests
# ─────────────────────────────────────────────────────────────────

def _make_valid_item_with_ws(col_name: str, ws: str) -> Dict[str, Any]:
    """Build a valid recommendation item referencing the given column and workspace table."""
    q_col = "`" + col_name + "`"
    q_ws = "`" + ws + "`"
    return {
        "issue_id": "test_ws_match",
        "title": "Workspace Table Match",
        "issue_detected": f"Column {col_name} has issues",
        "recommended_solution": "Clean the column",
        "preview_query": f"SELECT {q_col} FROM {q_ws} WHERE {q_col} = 'N/A';",
        "cleaning_query": f"UPDATE {q_ws} SET {q_col} = NULL WHERE {q_col} = 'N/A';",
        "validation_query": f"SELECT COUNT(*) FROM {q_ws} WHERE {q_col} = 'N/A';",
        "expected_result": "Column cleaned",
        "risks_and_assumptions": "Low risk",
        "is_modifying": True,
        "category": "missing_placeholder",
        "affected_records": 24,
        "affected_percentage": 24.0,
    }


# ── Test 3B-1: Exact workspace-table matching ──
def test_phase3b_exact_workspace_table_match():
    """Workspace table referenced as exact identifier passes validation."""
    profile = _make_profile_with_stats()
    item = _make_valid_item_with_ws("performance_score_text", "employees__cleaning_test")
    rec, err = _validate_recommendation_item(
        item, profile, "employees__cleaning_test", "mysql", set(), 0
    )
    assert err is None, f"Unexpected error: {err}"
    assert rec is not None


# ── Test 3B-2: Table names containing underscores ──
def test_phase3b_table_name_with_underscores():
    """Workspace table with multiple underscores matches as exact identifier."""
    profile = _make_profile_with_stats()
    item = _make_valid_item_with_ws("performance_score_text", "my_db__cleaning__uuid_123")
    rec, err = _validate_recommendation_item(
        item, profile, "my_db__cleaning__uuid_123", "mysql", set(), 0
    )
    assert err is None, f"Unexpected error: {err}"
    assert rec is not None


# ── Test 3B-3: Similarly named tables ──
def test_phase3b_similarly_named_tables_rejected():
    """'employees__cleaning_test' should NOT match 'employees__cleaning_test_backup'."""
    profile = _make_profile_with_stats()
    item = _make_valid_item_with_ws("performance_score_text", "employees__cleaning_test_backup")
    rec, err = _validate_recommendation_item(
        item, profile, "employees__cleaning_test", "mysql", set(), 0
    )
    assert err is not None, "Expected error for similarly named table confusion"
    assert "employees__cleaning_test" in err
    assert rec is None


# ── Test 3B-4: Quoted identifiers in supported dialects ──
def test_phase3b_quoted_workspace_table_mysql():
    """MySQL backtick-quoted workspace table name is accepted."""
    profile = _make_profile_with_stats()
    item = _make_valid_item_with_ws("performance_score_text", "employees__cleaning_test")
    rec, err = _validate_recommendation_item(
        item, profile, "employees__cleaning_test", "mysql", set(), 0
    )
    assert err is None, f"Unexpected error: {err}"
    assert rec is not None


def test_phase3b_quoted_workspace_table_sqlite():
    """SQLite double-quoted workspace table name is accepted."""
    profile = _make_profile_with_stats()
    ws = "employees__cleaning_test"
    q_col = '"performance_score_text"'
    q_ws = '"employees__cleaning_test"'
    item = {
        "issue_id": "test_sqlite_ws",
        "title": "SQLite Workspace Test",
        "issue_detected": "SQLite workspace table issues",
        "recommended_solution": "Clean the column",
        "preview_query": f"SELECT {q_col} FROM {q_ws} WHERE {q_col} = 'N/A';",
        "cleaning_query": f"UPDATE {q_ws} SET {q_col} = NULL WHERE {q_col} = 'N/A';",
        "validation_query": f"SELECT COUNT(*) FROM {q_ws} WHERE {q_col} = 'N/A';",
        "expected_result": "Cleaned",
        "risks_and_assumptions": "Low risk",
        "is_modifying": True,
        "category": "missing_placeholder",
        "affected_records": 24,
        "affected_percentage": 24.0,
    }
    rec, err = _validate_recommendation_item(
        item, profile, ws, "sqlite", set(), 0
    )
    assert err is None, f"Unexpected error: {err}"
    assert rec is not None


# ── Test 3B-5: Unknown and ambiguous table references ──
def test_phase3b_unknown_workspace_table_rejected():
    """Unknown workspace table reference is rejected."""
    profile = _make_profile_with_stats()
    item = _make_valid_item_with_ws("performance_score_text", "nonexistent_table__cleaning")
    rec, err = _validate_recommendation_item(
        item, profile, "employees__cleaning_test", "mysql", set(), 0
    )
    assert err is not None
    assert "employees__cleaning_test" in err
    assert rec is None


# ── Test 3B-6: Verified versus unverified statistical claims ──
def test_phase3b_verified_statistical_claims():
    """Sufficient profile evidence → claims verified and accepted."""
    profile = _make_profile_with_stats()
    item = _make_valid_item_with_ws("performance_score_text", "employees__cleaning_test")
    item["affected_records"] = 24
    item["affected_percentage"] = 24.0
    rec, err = _validate_recommendation_item(
        item, profile, "employees__cleaning_test", "mysql", set(), 0
    )
    assert err is None, f"Unexpected error: {err}"
    assert rec is not None
    assert rec.affected_records == 24
    assert rec.affected_percentage == 24.0


def test_phase3b_unverified_statistical_claims_no_evidence():
    """Insufficient profile evidence (total_records=0) → claim accepted but not verified."""
    profile = ColumnProfileResult(
        table_name="empty",
        column_name="col",
        total_records=0,
        placeholder_count=0,
    )
    item = _make_valid_item_with_ws("col", "ws__cleaning_test")
    item["affected_records"] = 5
    item["affected_percentage"] = 100.0
    rec, err = _validate_recommendation_item(
        item, profile, "ws__cleaning_test", "mysql", set(), 0
    )
    assert err is None, f"Unexpected error when no profile evidence: {err}"
    assert rec is not None
    assert rec.affected_records == 5
    assert rec.affected_percentage == 100.0


def test_phase3b_unverified_statistical_claims_insufficient_evidence():
    """Profile evidence present but category count doesn't cover the claim → rejected."""
    profile = _make_profile_with_stats()
    item = _make_valid_item_with_ws("performance_score_text", "employees__cleaning_test")
    item["affected_records"] = 100
    item["affected_percentage"] = 100.0
    rec, err = _validate_recommendation_item(
        item, profile, "employees__cleaning_test", "mysql", set(), 0
    )
    assert err is not None, "Expected error for claim exceeding profile-verified count"
    assert "exceeds" in err.lower() or "missing_placeholder" in err.lower()
    assert rec is None


# ── Test 3B-7: Existing valid recommendation compatibility ──
def test_phase3b_existing_valid_recommendation_compatible():
    """Real-world performance_score_text scenario passes end-to-end validation."""
    profile = _make_profile_with_stats()
    item = _make_valid_item_with_ws("performance_score_text", "employees__cleaning_test")
    rec, err = _validate_recommendation_item(
        item, profile, "employees__cleaning_test", "mysql", set(), 0
    )
    assert err is None, f"Unexpected error: {err}"
    assert rec is not None
    assert rec.affected_records == 24
    assert rec.affected_percentage == 24.0
    assert rec.category == "missing_placeholder"
    assert rec.issue_id == "test_ws_match"


# ── Conversational chat transport ────────────────────────────────

def test_chat_streams_incremental_deltas_and_returns_complete_response():
    """Supported OpenAI-compatible streams invoke the UI callback in order."""
    config = AIColumnConfig(base_url="https://api.example.com/v1", model_name="test", api_key="key")
    profile = _make_profile()
    first = MagicMock()
    first.choices = [MagicMock(delta=MagicMock(content="Hello"))]
    second = MagicMock()
    second.choices = [MagicMock(delta=MagicMock(content=" world"))]
    client = MagicMock()
    client.chat.completions.create.return_value = iter([first, second])
    deltas = []

    with patch("openai.OpenAI", return_value=client):
        response, error = send_ai_chat_message(
            profile, config, [{"role": "user", "content": "Explain the profile."}],
            on_delta=deltas.append,
        )

    assert error is None
    assert response == "Hello world"
    assert deltas == ["Hello", "Hello world"]


def test_chat_uses_non_streaming_fallback_only_when_provider_rejects_streaming():
    """A known stream incompatibility is retried once without arbitrary fake chunks."""
    config = AIColumnConfig(base_url="https://api.example.com/v1", model_name="test", api_key="key")
    profile = _make_profile()
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        Exception("stream is not supported by this provider"),
        MagicMock(choices=[MagicMock(message=MagicMock(content="Fallback reply"))]),
    ]

    with patch("openai.OpenAI", return_value=client):
        response, error = send_ai_chat_message(
            profile, config, [{"role": "user", "content": "Explain the profile."}],
        )

    assert error is None
    assert response == "Fallback reply"
    assert client.chat.completions.create.call_count == 2
    assert client.chat.completions.create.call_args_list[1].kwargs["stream"] is False


def test_chat_rejects_interrupted_partial_stream():
    """A partial response is never returned as a completed recommendation."""
    config = AIColumnConfig(base_url="https://api.example.com/v1", model_name="test", api_key="key")
    profile = _make_profile()

    def interrupted_stream():
        chunk = MagicMock()
        chunk.choices = [MagicMock(delta=MagicMock(content='{"summary":'))]
        yield chunk
        raise Exception("connection interrupted")

    client = MagicMock()
    client.chat.completions.create.return_value = interrupted_stream()

    with patch("openai.OpenAI", return_value=client):
        response, error = send_ai_chat_message(
            profile, config, [{"role": "user", "content": "Analyze this column."}],
        )

    assert response == ""
    assert error is not None
    assert "interrupted" in error.lower()


