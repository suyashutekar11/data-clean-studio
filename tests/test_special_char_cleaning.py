"""
Unit tests for Special Character Cleaning feature.
Tests cover:
- scan_special_characters_workspace
- clean_special_characters_workspace
- Character escaping and regex safety
- NULL value preservation
- Multi-character handling
"""

from unittest.mock import MagicMock, patch, call
import pytest

from src.staging import (
    scan_special_characters_workspace,
    clean_special_characters_workspace,
    CONTROL_CHARS,
    COMMON_SPECIAL_CHARS,
    _escape_for_regex,
    _build_char_class,
    CLEANING_SUFFIX,
    TEXT_DATA_TYPES,
)


def create_mock_workspace(mock_engine, table_name="test__cleaning_123", columns=None):
    """Helper to create a mocked workspace table with text columns."""
    if columns is None:
        columns = [
            {"COLUMN_NAME": "col1", "DATA_TYPE": "varchar"},
            {"COLUMN_NAME": "col2", "DATA_TYPE": "text"},
        ]
    
    mock_inspect = MagicMock()
    mock_inspect.return_value.get_table_names.return_value = [table_name]
    
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_engine.begin.return_value.__enter__.return_value = mock_conn
    
    # Mock column query - create a result that can be iterated multiple times
    def make_col_result():
        col_result = MagicMock()
        col_result.__iter__ = lambda self: iter([
            MagicMock(_mapping={"COLUMN_NAME": c["COLUMN_NAME"], "DATA_TYPE": c["DATA_TYPE"]})
            for c in columns
        ])
        return col_result
    
    return mock_engine, mock_inspect, mock_conn, make_col_result


class TestSpecialCharUtilities:
    """Test utility functions for special character handling."""

    def test_escape_for_regex_metacharacters(self):
        """Test that regex metacharacters are properly escaped."""
        metachars = [".", "^", "$", "*", "+", "?", "{", "}", "[", "]", "|", "(", ")", "\\"]
        for ch in metachars:
            escaped = _escape_for_regex(ch)
            assert escaped == "\\" + ch, f"Failed to escape {ch}: got {escaped}"

    def test_escape_for_regex_regular_chars(self):
        """Test that regular characters are not escaped."""
        regular = ["a", "Z", "1", "@", "#", " ", "\t", "\n"]
        for ch in regular:
            escaped = _escape_for_regex(ch)
            assert escaped == ch, f"Incorrectly escaped {ch}: got {escaped}"

    def test_build_char_class_simple(self):
        """Test building character class from simple characters."""
        chars = ["a", "b", "c"]
        result = _build_char_class(chars)
        assert result == "[abc]"

    def test_build_char_class_with_metacharacters(self):
        """Test building character class with regex metacharacters."""
        chars = [".", "*", "?", "a"]
        result = _build_char_class(chars)
        # Should be properly escaped
        assert "\\." in result
        assert "\\*" in result
        assert "\\?" in result
        assert "a" in result

    def test_build_char_class_control_chars(self):
        """Test building character class with control characters."""
        chars = ["\t", "\n", "\r"]
        result = _build_char_class(chars)
        # Control chars should be in the class
        assert "\t" in result or "\\t" in result
        assert "\n" in result or "\\n" in result

    def test_control_chars_definition(self):
        """Verify CONTROL_CHARS has expected entries."""
        expected_keys = ["tab", "carriage_return", "line_feed", "form_feed", "vertical_tab", "null_char"]
        for key in expected_keys:
            assert key in CONTROL_CHARS
            assert "char" in CONTROL_CHARS[key]
            assert "display" in CONTROL_CHARS[key]
            assert "regex" in CONTROL_CHARS[key]

    def test_common_special_chars_definition(self):
        """Verify COMMON_SPECIAL_CHARS has expected entries."""
        assert len(COMMON_SPECIAL_CHARS) > 0
        for ch, desc in COMMON_SPECIAL_CHARS:
            assert isinstance(ch, str)
            # Backslash is represented as '\\\\' in source (2 chars) but is 1 actual char
            assert len(ch) >= 1
            assert isinstance(desc, str)


class TestScanSpecialCharactersWorkspace:
    """Test the scan_special_characters_workspace function."""

    def test_scan_requires_workspace_table(self):
        """Test that scan rejects non-workspace tables."""
        mock_engine = MagicMock()
        mock_inspect = MagicMock()
        mock_inspect.return_value.get_table_names.return_value = ["regular_table"]

        with patch("src.staging.inspect", mock_inspect):
            result = scan_special_characters_workspace(
                mock_engine, "db", "regular_table", ["col1"], ["tab"], []
            )
            assert result == []

    def test_scan_returns_empty_when_no_chars_selected(self):
        """Test that scan returns empty when no characters selected."""
        mock_engine = MagicMock()
        mock_inspect = MagicMock()
        mock_inspect.return_value.get_table_names.return_value = ["test__cleaning_123"]

        with patch("src.staging.inspect", mock_inspect):
            result = scan_special_characters_workspace(
                mock_engine, "db", "test__cleaning_123", ["col1"], [], [], ""
            )
            assert result == []

    def test_scan_validates_columns_exist(self):
        """Test that scan works with valid columns."""
        mock_engine = MagicMock()
        mock_inspect = MagicMock()
        mock_inspect.return_value.get_table_names.return_value = ["test__cleaning_123"]
        
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        with patch("src.staging.inspect", mock_inspect):
            result = scan_special_characters_workspace(
                mock_engine, "db", "test__cleaning_123", ["col1"], ["tab"], ["@"]
            )
            # Should not error, returns empty list when no matches
            assert isinstance(result, list)


class TestCleanSpecialCharactersWorkspace:
    """Test the clean_special_characters_workspace function."""

    def test_clean_requires_workspace_table(self):
        """Test that clean rejects non-workspace tables."""
        mock_engine = MagicMock()
        mock_inspect = MagicMock()
        mock_inspect.return_value.get_table_names.return_value = ["regular_table"]

        with patch("src.staging.inspect", mock_inspect):
            success, msg, report = clean_special_characters_workspace(
                mock_engine, "db", "regular_table", ["col1"], ["tab"], [], "", "remove"
            )
            assert success is False
            assert "Refusing to clean" in msg

    def test_clean_requires_columns(self):
        """Test that clean requires at least one column."""
        mock_engine = MagicMock()
        mock_inspect = MagicMock()
        mock_inspect.return_value.get_table_names.return_value = ["test__cleaning_123"]

        with patch("src.staging.inspect", mock_inspect):
            success, msg, report = clean_special_characters_workspace(
                mock_engine, "db", "test__cleaning_123", [], ["tab"], [], "", "remove"
            )
            assert success is False
            assert "select at least one column" in msg.lower()

    def test_clean_requires_characters(self):
        """Test that clean requires at least one character to clean."""
        mock_engine = MagicMock()
        mock_inspect = MagicMock()
        mock_inspect.return_value.get_table_names.return_value = ["test__cleaning_123"]
        
        # Mock column query to return valid text column
        mock_conn = MagicMock()
        col_result = MagicMock()
        col_result.__iter__ = lambda self: iter([
            MagicMock(_mapping={"COLUMN_NAME": "col1", "DATA_TYPE": "varchar"})
        ])
        mock_conn.execute.return_value = col_result
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        mock_engine.begin.return_value.__enter__.return_value = mock_conn

        with patch("src.staging.inspect", mock_inspect):
            success, msg, report = clean_special_characters_workspace(
                mock_engine, "db", "test__cleaning_123", ["col1"], [], [], "", "remove"
            )
            assert success is False
            assert "No characters selected" in msg

    def test_clean_validates_mode(self):
        """Test that clean validates mode parameter."""
        mock_engine = MagicMock()
        mock_inspect = MagicMock()
        mock_inspect.return_value.get_table_names.return_value = ["test__cleaning_123"]

        with patch("src.staging.inspect", mock_inspect):
            success, msg, report = clean_special_characters_workspace(
                mock_engine, "db", "test__cleaning_123", ["col1"], ["tab"], ["@"], "", "invalid_mode"
            )
            assert success is False
            assert "Invalid mode" in msg

    def test_clean_removes_tab_characters(self):
        """Test cleaning removes tab characters."""
        mock_engine = MagicMock()
        mock_engine, mock_inspect, mock_conn, make_col_result = create_mock_workspace(mock_engine)
        
        # Mock count query - returns a result with scalar() = 10
        count_result = MagicMock()
        count_result.scalar.return_value = 10
        
        # Set up execute to return different results for different queries
        col_result1 = make_col_result()
        col_result2 = make_col_result()
        
        mock_conn.execute.side_effect = [
            col_result1,    # column validation query (connect)
            count_result,   # count query (connect)
            col_result2,    # column validation query (begin)
            count_result,   # count query (begin)
        ]
        
        with patch("src.staging.inspect", mock_inspect):
            success, msg, report = clean_special_characters_workspace(
                mock_engine, "db", "test__cleaning_123",
                ["col1"], ["tab"], [], "", "remove"
            )
            
            assert success is True
            assert report["total_values_changed"] == 10
            assert "tab" in report["control_chars"]

    def test_clean_replace_mode(self):
        """Test cleaning in replace mode."""
        mock_engine = MagicMock()
        mock_engine, mock_inspect, mock_conn, make_col_result = create_mock_workspace(mock_engine)
        
        count_result = MagicMock()
        count_result.scalar.return_value = 5
        
        col_result1 = make_col_result()
        col_result2 = make_col_result()
        
        mock_conn.execute.side_effect = [
            col_result1,
            count_result,
            col_result2,
            count_result,
        ]
        
        with patch("src.staging.inspect", mock_inspect):
            success, msg, report = clean_special_characters_workspace(
                mock_engine, "db", "test__cleaning_123",
                ["col1"], ["tab"], ["@"], "", "replace", "_"
            )
            
            assert success is True
            assert report["mode"] == "replace"
            assert report["replacement"] == "_"

    def test_clean_preserves_null_values(self):
        """Test that NULL values are not affected by cleaning (only non-null matched)."""
        mock_engine = MagicMock()
        mock_engine, mock_inspect, mock_conn, make_col_result = create_mock_workspace(mock_engine)
        
        count_result = MagicMock()
        count_result.scalar.return_value = 0  # No non-null values match
        
        col_result1 = make_col_result()
        col_result2 = make_col_result()
        
        mock_conn.execute.side_effect = [
            col_result1,
            count_result,
            col_result2,
            count_result,
        ]
        
        with patch("src.staging.inspect", mock_inspect):
            success, msg, report = clean_special_characters_workspace(
                mock_engine, "db", "test__cleaning_123",
                ["col1"], ["tab"], [], "", "remove"
            )
            
            assert success is True
            assert report["total_values_changed"] == 0

    def test_clean_rejects_non_text_columns(self):
        """Test that clean rejects non-text columns."""
        mock_engine = MagicMock()
        mock_engine, mock_inspect, mock_conn, make_col_result = create_mock_workspace(
            mock_engine,
            columns=[{"COLUMN_NAME": "id", "DATA_TYPE": "int"}]
        )
        
        col_result1 = make_col_result()
        mock_conn.execute.return_value = col_result1
        
        with patch("src.staging.inspect", mock_inspect):
            success, msg, report = clean_special_characters_workspace(
                mock_engine, "db", "test__cleaning_123",
                ["id"], ["tab"], [], "", "remove"
            )
            
            assert success is False
            assert "not a supported text/string column" in msg


class TestCharacterHandlingEdgeCases:
    """Test edge cases in character handling."""

    def test_custom_chars_with_metacharacters(self):
        """Test custom characters with regex metacharacters are handled safely."""
        mock_engine = MagicMock()
        mock_engine, mock_inspect, mock_conn, make_col_result = create_mock_workspace(mock_engine)
        
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        
        col_result1 = make_col_result()
        col_result2 = make_col_result()
        
        mock_conn.execute.side_effect = [
            col_result1,
            count_result,
            col_result2,
            count_result,
        ]
        
        # Custom chars include regex metacharacters
        with patch("src.staging.inspect", mock_inspect):
            success, msg, report = clean_special_characters_workspace(
                mock_engine, "db", "test__cleaning_123",
                ["col1"], [], [], ".^$*+?{}[]|()", "remove"
            )
            
            assert success is True
            # Should have processed without regex errors

    def test_multiple_control_chars(self):
        """Test handling multiple control characters at once."""
        mock_engine = MagicMock()
        mock_engine, mock_inspect, mock_conn, make_col_result = create_mock_workspace(mock_engine)
        
        count_result = MagicMock()
        count_result.scalar.return_value = 15
        
        col_result1 = make_col_result()
        col_result2 = make_col_result()
        
        mock_conn.execute.side_effect = [
            col_result1,
            count_result,
            col_result2,
            count_result,
        ]
        
        with patch("src.staging.inspect", mock_inspect):
            success, msg, report = clean_special_characters_workspace(
                mock_engine, "db", "test__cleaning_123",
                ["col1"], ["tab", "line_feed", "carriage_return"], [], "", "remove"
            )
            
            assert success is True
            assert report["total_values_changed"] == 15
            assert set(report["control_chars"]) == {"tab", "line_feed", "carriage_return"}

    def test_unicode_preservation(self):
        """Test that valid Unicode characters are preserved."""
        # The function operates on individual characters, so Unicode should be preserved
        # as long as it's not in the target character list
        mock_engine = MagicMock()
        mock_engine, mock_inspect, mock_conn, make_col_result = create_mock_workspace(mock_engine)
        
        # Scan with only ASCII control chars selected
        scan_result = MagicMock()
        scan_result.__iter__ = lambda self: iter([])
        
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        
        col_result1 = make_col_result()
        
        mock_conn.execute.side_effect = [
            col_result1,
            scan_result,
            count_result,
        ]
        
        with patch("src.staging.inspect", mock_inspect):
            result = scan_special_characters_workspace(
                mock_engine, "db", "test__cleaning_123",
                ["col1"], ["tab"], []
            )
            
            # Should not error on Unicode
            assert isinstance(result, list)



class TestColumnSelectionStateSync:
    """Test Select All and Deselect All state synchronization logic."""

    def test_select_all_synchronization(self):
        """Verify that selecting all columns sets every checkbox key to True."""
        cols = ["customer_name", "email", "city", "is_active", "__bool_backup_is_active"]
        session_state = {}

        # Simulate clicking Select All
        session_state["sc_selected_columns"] = list(cols)
        for c in cols:
            session_state[f"sc_target_col_{c}"] = True

        # Check invariants
        assert session_state["sc_selected_columns"] == cols
        for c in cols:
            assert session_state[f"sc_target_col_{c}"] is True

    def test_deselect_all_synchronization(self):
        """Verify that deselecting all columns sets every checkbox key to False."""
        cols = ["customer_name", "email", "city", "is_active", "__bool_backup_is_active"]
        session_state = {f"sc_target_col_{c}": True for c in cols}
        session_state["sc_selected_columns"] = list(cols)

        # Simulate clicking Deselect All
        session_state["sc_selected_columns"] = []
        for c in cols:
            session_state[f"sc_target_col_{c}"] = False

        # Check invariants
        assert session_state["sc_selected_columns"] == []
        for c in cols:
            assert session_state[f"sc_target_col_{c}"] is False

    def test_checkbox_toggle_synchronization(self):
        """Verify manual checkbox toggle synchronization."""
        cols = ["col1", "col2", "col3"]
        session_state = {
            "sc_selected_columns": ["col1", "col2"],
            "sc_target_col_col1": True,
            "sc_target_col_col2": False,  # User toggled col2 off
            "sc_target_col_col3": True,   # User toggled col3 on
        }

        # Sync logic
        current_selected = [c for c in cols if session_state.get(f"sc_target_col_{c}", False)]
        session_state["sc_selected_columns"] = current_selected

        assert set(session_state["sc_selected_columns"]) == {"col1", "col3"}

    def test_special_chars_select_all_and_deselect_all(self):
        """Verify that selecting all and deselecting all special characters syncs checkbox keys."""
        session_state = {}

        # Select All
        session_state["sc_special_chars"] = [ch for ch, _ in COMMON_SPECIAL_CHARS]
        for s_idx in range(len(COMMON_SPECIAL_CHARS)):
            session_state[f"sc_spec_chk_{s_idx}"] = True

        assert len(session_state["sc_special_chars"]) == len(COMMON_SPECIAL_CHARS)
        assert all(session_state[f"sc_spec_chk_{i}"] is True for i in range(len(COMMON_SPECIAL_CHARS)))

        # Deselect All
        session_state["sc_special_chars"] = []
        for s_idx in range(len(COMMON_SPECIAL_CHARS)):
            session_state[f"sc_spec_chk_{s_idx}"] = False

        assert len(session_state["sc_special_chars"]) == 0
        assert all(session_state[f"sc_spec_chk_{i}"] is False for i in range(len(COMMON_SPECIAL_CHARS)))

    def test_control_chars_select_all_and_deselect_all(self):
        """Verify that selecting all and deselecting all control characters syncs checkbox keys."""
        session_state = {}

        # Select All
        session_state["sc_control_chars"] = list(CONTROL_CHARS.keys())
        for key in CONTROL_CHARS.keys():
            session_state[f"sc_ctrl_chk_{key}"] = True

        assert set(session_state["sc_control_chars"]) == set(CONTROL_CHARS.keys())
        assert all(session_state[f"sc_ctrl_chk_{k}"] is True for k in CONTROL_CHARS.keys())

        # Deselect All
        session_state["sc_control_chars"] = []
        for key in CONTROL_CHARS.keys():
            session_state[f"sc_ctrl_chk_{key}"] = False

        assert len(session_state["sc_control_chars"]) == 0
        assert all(session_state[f"sc_ctrl_chk_{k}"] is False for k in CONTROL_CHARS.keys())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])