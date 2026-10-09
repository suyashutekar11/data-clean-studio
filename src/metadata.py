from typing import List, Dict, Any, Tuple
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
import pandas as pd
import logging

logger = logging.getLogger(__name__)

SYSTEM_DATABASES = {"information_schema", "performance_schema", "mysql", "sys"}

class MySQLMetadataInspector:
    """Discovers databases, tables, schemas, and data previews dynamically from MySQL metadata."""

    @staticmethod
    def get_databases(engine: Engine, include_system_dbs: bool = False) -> List[str]:
        """Retrieves list of databases available on the MySQL server."""
        try:
            inspector = inspect(engine)
            schemas = inspector.get_schema_names()
            if not include_system_dbs:
                schemas = [s for s in schemas if s.lower() not in SYSTEM_DATABASES]
            return sorted(schemas)
        except SQLAlchemyError as e:
            logger.error(f"Error fetching databases: {str(e)}")
            raise RuntimeError(f"Failed to retrieve databases: {str(e)}")

    @staticmethod
    def get_tables(engine: Engine, database: str) -> List[str]:
        """Retrieves all table names for the selected database."""
        try:
            # Re-inspect under the selected database schema context
            inspector = inspect(engine)
            tables = inspector.get_table_names(schema=database)
            return sorted(tables)
        except SQLAlchemyError as e:
            logger.error(f"Error fetching tables for database '{database}': {str(e)}")
            raise RuntimeError(f"Failed to retrieve tables for database '{database}': {str(e)}")

    @staticmethod
    def get_table_schema(engine: Engine, database: str, table_name: str) -> List[Dict[str, Any]]:
        """
        Retrieves schema info for a specific table:
        - Column Name
        - Data Type
        - Is Nullable
        - Key Info (Primary Key, Foreign Key, None)
        """
        try:
            inspector = inspect(engine)
            columns = inspector.get_columns(table_name, schema=database)
            pk_constraint = inspector.get_pk_constraint(table_name, schema=database)
            pk_cols = set(pk_constraint.get("constrained_columns", []))
            
            fk_info = inspector.get_foreign_keys(table_name, schema=database)
            fk_cols = set()
            for fk in fk_info:
                fk_cols.update(fk.get("constrained_columns", []))

            schema_info = []
            for col in columns:
                col_name = col["name"]
                
                # Determine Key designation
                keys = []
                if col_name in pk_cols:
                    keys.append("PRIMARY KEY")
                if col_name in fk_cols:
                    keys.append("FOREIGN KEY")
                
                key_str = ", ".join(keys) if keys else "-"

                schema_info.append({
                    "Column Name": col_name,
                    "Data Type": str(col["type"]),
                    "Nullable": "YES" if col.get("nullable", True) else "NO",
                    "Key Info": key_str,
                    "Default": str(col.get("default")) if col.get("default") is not None else "None"
                })
            return schema_info
        except SQLAlchemyError as e:
            logger.error(f"Error fetching schema for table '{table_name}': {str(e)}")
            raise RuntimeError(f"Failed to retrieve schema for table '{table_name}': {str(e)}")

    @staticmethod
    def get_table_preview(engine: Engine, database: str, table_name: str, limit: int = 10) -> pd.DataFrame:
        """Retrieves a preview dataframe of up to `limit` rows from the specified database table."""
        try:
            # Quote table and database names safely to prevent SQL injection or keyword conflicts
            quoted_target = f"`{database}`.`{table_name}`"
            query = f"SELECT * FROM {quoted_target} LIMIT :limit"
            
            with engine.connect() as conn:
                df = pd.read_sql_query(text(query), conn, params={"limit": limit})
            return df
        except SQLAlchemyError as e:
            logger.error(f"Error reading table preview for '{database}.{table_name}': {str(e)}")
            raise RuntimeError(f"Failed to preview data for table '{table_name}': {str(e)}")
