import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import text

from src.staging import (
    list_workspaces_for_table,
    list_all_workspaces,
    attach_workspace,
    delete_all_workspaces,
)


@patch("src.staging.inspect")
def test_list_workspaces_for_table_finds_matches(mock_inspect):
    """Test discovering existing workspaces that match a source table."""
    mock_engine = MagicMock()
    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = [
        "users",
        "users__cleaning_111",
        "users__cleaning_222",
        "orders",
        "orders__cleaning_999",
    ]
    mock_inspect.return_value = mock_inspector

    mock_conn = MagicMock()
    mock_conn.execute.return_value.scalar.return_value = 50
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    results = list_workspaces_for_table(mock_engine, "test_db", "users")
    assert len(results) == 2
    table_names = [r["working_table_name"] for r in results]
    assert "users__cleaning_111" in table_names
    assert "users__cleaning_222" in table_names
    assert results[0]["source_table"] == "users"
    assert results[0]["row_count"] == 50


@patch("src.staging.inspect")
def test_list_workspaces_for_table_ignores_other_tables(mock_inspect):
    """Test that listing workspaces for a table does not return non-matching or production tables."""
    mock_engine = MagicMock()
    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = [
        "customers",
        "customers_archive",
        "orders__cleaning_123",
    ]
    mock_inspect.return_value = mock_inspector

    results = list_workspaces_for_table(mock_engine, "test_db", "customers")
    assert results == []


@patch("src.staging.inspect")
def test_list_all_workspaces_discovers_all(mock_inspect):
    """Test discovering all workspaces in the database across all tables."""
    mock_engine = MagicMock()
    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = [
        "users",
        "users__cleaning_abc",
        "orders",
        "orders__cleaning_xyz",
        "products",
    ]
    mock_inspect.return_value = mock_inspector

    mock_conn = MagicMock()
    mock_conn.execute.return_value.scalar.return_value = 10
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    all_ws = list_all_workspaces(mock_engine, "test_db")
    assert len(all_ws) == 2
    ws_names = [w["working_table_name"] for w in all_ws]
    assert "users__cleaning_abc" in ws_names
    assert "orders__cleaning_xyz" in ws_names


@patch("src.staging.get_workspace_info")
def test_attach_workspace_success(mock_get_info):
    """Test successfully attaching to an existing workspace table."""
    mock_engine = MagicMock()
    mock_get_info.return_value = {
        "working_table_name": "users__cleaning_abc123",
        "row_count": 150,
        "schema": [{"name": "id", "type": "int"}],
        "preview": None,
        "exists": True,
    }

    ok, msg, details = attach_workspace(
        mock_engine,
        "test_db",
        "users__cleaning_abc123",
    )

    assert ok is True
    assert "Successfully connected to existing workspace" in msg
    assert details["working_table_name"] == "users__cleaning_abc123"
    assert details["source_table"] == "users"
    assert details["working_row_count"] == 150
    assert details["status"] == "ready"


def test_attach_workspace_rejects_non_workspace():
    """Test that attempting to attach to a production table is rejected."""
    mock_engine = MagicMock()
    ok, msg, details = attach_workspace(
        mock_engine,
        "test_db",
        "users",  # Production table
    )
    assert ok is False
    assert "Refusing to attach" in msg
    assert details is None


@patch("src.staging.get_workspace_info")
def test_attach_workspace_not_found(mock_get_info):
    """Test error handling when workspace table does not exist in DB."""
    mock_engine = MagicMock()
    mock_get_info.return_value = None

    ok, msg, details = attach_workspace(
        mock_engine,
        "test_db",
        "users__cleaning_missing",
    )
    assert ok is False
    assert "does not exist in database" in msg
    assert details is None


@patch("src.staging.delete_workspace")
@patch("src.staging.list_workspaces_for_table")
def test_delete_all_workspaces_for_table(mock_list_ws, mock_delete_ws):
    """Test deleting all workspaces belonging to a source table."""
    mock_engine = MagicMock()
    mock_list_ws.return_value = [
        {"working_table_name": "users__cleaning_1"},
        {"working_table_name": "users__cleaning_2"},
    ]
    mock_delete_ws.return_value = (True, "Deleted")

    ok, msg, count = delete_all_workspaces(mock_engine, "test_db", source_table="users")
    assert ok is True
    assert count == 2
    assert mock_delete_ws.call_count == 2


@patch("src.staging.list_all_workspaces")
def test_delete_all_workspaces_empty(mock_list_all):
    """Test delete_all_workspaces when no workspaces exist."""
    mock_engine = MagicMock()
    mock_list_all.return_value = []

    ok, msg, count = delete_all_workspaces(mock_engine, "test_db")
    assert ok is True
    assert count == 0
    assert "No cleaning workspaces found" in msg

