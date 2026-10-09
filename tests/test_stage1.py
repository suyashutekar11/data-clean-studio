import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.exc import OperationalError
from src.connection import MySQLConnectionManager
from src.metadata import MySQLMetadataInspector
import pandas as pd

def test_test_connection_invalid_credentials():
    with patch("src.connection.create_engine") as mock_create_engine:
        # Mock operational error with code 1045 (Access Denied)
        orig_error = Exception("Access denied for user 'root'@'localhost'")
        setattr(orig_error, "errno", 1045)
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = OperationalError("statement", "params", orig_error)
        mock_create_engine.return_value = mock_engine

        success, msg = MySQLConnectionManager.test_connection("localhost", 3306, "root", "wrong_password")
        assert success is False
        assert "Access Denied" in msg

def test_test_connection_server_unavailable():
    with patch("src.connection.create_engine") as mock_create_engine:
        # Mock operational error with code 2003 (Can't connect to MySQL server)
        orig_error = Exception("Can't connect to MySQL server on 'invalid_host' (10061)")
        setattr(orig_error, "errno", 2003)
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = OperationalError("statement", "params", orig_error)
        mock_create_engine.return_value = mock_engine

        success, msg = MySQLConnectionManager.test_connection("invalid_host", 3306, "root", "password")
        assert success is False
        assert "Cannot reach MySQL server" in msg

def test_get_databases():
    with patch("src.metadata.inspect") as mock_inspect:
        mock_inspector = MagicMock()
        mock_inspector.get_schema_names.return_value = [
            "information_schema", "mysql", "performance_schema", "sys", "employee_db", "store_db"
        ]
        mock_inspect.return_value = mock_inspector

        mock_engine = MagicMock()

        # Test with system DBs excluded
        dbs = MySQLMetadataInspector.get_databases(mock_engine, include_system_dbs=False)
        assert dbs == ["employee_db", "store_db"]

        # Test with system DBs included
        dbs_all = MySQLMetadataInspector.get_databases(mock_engine, include_system_dbs=True)
        assert len(dbs_all) == 6

def test_get_tables():
    with patch("src.metadata.inspect") as mock_inspect:
        mock_inspector = MagicMock()
        mock_inspector.get_table_names.return_value = ["employees", "departments", "salaries"]
        mock_inspect.return_value = mock_inspector

        mock_engine = MagicMock()
        tables = MySQLMetadataInspector.get_tables(mock_engine, "employee_db")
        assert tables == ["departments", "employees", "salaries"]
        mock_inspector.get_table_names.assert_called_with(schema="employee_db")

def test_get_table_schema():
    with patch("src.metadata.inspect") as mock_inspect:
        mock_inspector = MagicMock()
        mock_inspector.get_columns.return_value = [
            {"name": "emp_id", "type": "INTEGER", "nullable": False, "default": None},
            {"name": "emp_name", "type": "VARCHAR(100)", "nullable": True, "default": None},
            {"name": "dept_id", "type": "INTEGER", "nullable": True, "default": None}
        ]
        mock_inspector.get_pk_constraint.return_value = {"constrained_columns": ["emp_id"]}
        mock_inspector.get_foreign_keys.return_value = [{"constrained_columns": ["dept_id"]}]
        mock_inspect.return_value = mock_inspector

        mock_engine = MagicMock()
        schema = MySQLMetadataInspector.get_table_schema(mock_engine, "employee_db", "employees")

        assert len(schema) == 3
        assert schema[0]["Column Name"] == "emp_id"
        assert schema[0]["Key Info"] == "PRIMARY KEY"
        assert schema[0]["Nullable"] == "NO"

        assert schema[1]["Column Name"] == "emp_name"
        assert schema[1]["Key Info"] == "-"

        assert schema[2]["Column Name"] == "dept_id"
        assert schema[2]["Key Info"] == "FOREIGN KEY"

def test_get_table_preview():
    with patch("pandas.read_sql_query") as mock_read_sql:
        expected_df = pd.DataFrame({
            "emp_id": [1, 2],
            "emp_name": ["Alice", "Bob"]
        })
        mock_read_sql.return_value = expected_df

        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        df = MySQLMetadataInspector.get_table_preview(mock_engine, "employee_db", "employees", limit=10)
        assert not df.empty
        assert len(df) == 2
        assert list(df.columns) == ["emp_id", "emp_name"]
