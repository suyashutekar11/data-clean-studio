from typing import Optional, Tuple, Dict, Any, List
import uuid
import re
import logging

import pandas as pd
from sqlalchemy import inspect, text

from src.metadata import MySQLMetadataInspector
from src.date_rules import (
    analyze_column,
    ParseResult,
    ColumnAnalysis,
    transform_value,
)

def _fmt_to_regex(mysql_fmt: str) -> str:
    """Convert a MySQL STR_TO_DATE format into a REGEXP that matches exactly
    the strings that format can parse."""
    token_map = {
        "%d": r"[0-9]{2}",
        "%m": r"[0-9]{2}",
        "%Y": r"[0-9]{4}",
        "%y": r"[0-9]{2}",
        "%b": r"[A-Za-z]{3}",
        "%B": r"[A-Za-z]+",
        "%H": r"[0-9]{2}",
        "%M": r"[0-9]{2}",
        "%S": r"[0-9]{2}",
    }
    parts = re.split(r"(%[dmyYbBHMS])", mysql_fmt)
    regex = ""
    for p in parts:
        if p in token_map:
            regex += token_map[p]
        else:
            regex += re.escape(p)
    return "^" + regex + "$"

logger = logging.getLogger(__name__)

CLEANING_SUFFIX = "__cleaning_"
MAX_IDENTIFIER_LENGTH = 64


def _quote_identifier(identifier: str) -> str:
    """Safely quote a MySQL identifier."""
    if not isinstance(identifier, str) or not identifier:
        raise ValueError("Identifier must be a non-empty string.")

    return f"`{identifier.replace('`', '``')}`"


def _quote_table(database: str, table_name: str) -> str:
    """Return a fully-qualified quoted MySQL table name."""
    return f"{_quote_identifier(database)}.{_quote_identifier(table_name)}"


def _make_safe_table_name(table_name: str) -> str:
    """
    Convert an arbitrary table name into a safe MySQL identifier.

    Examples:
        employees       -> employees
        my-table        -> my_table
        table with spaces -> table_with_spaces
        1table          -> _table
        ""              -> cleaning_table
    """
    if not table_name:
        return "cleaning_table"

    # Replace invalid characters with underscores.
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", table_name)

    # MySQL identifiers cannot start with a digit.
    # Remove all leading digits and replace them with one underscore.
    if safe and safe[0].isdigit():
        safe = re.sub(r"^\d+", "", safe)
        safe = "_" + safe

    if not safe:
        safe = "cleaning_table"

    return safe


def _generate_working_table_name(
    source_db: str,
    source_table: str,
    unique_id: str,
) -> str:
    """
    Generate:

        <safe_source_table>__cleaning_<unique_id>
    """
    safe_table = _make_safe_table_name(source_table)

    suffix = f"{CLEANING_SUFFIX}{unique_id}"

    # MySQL identifiers are limited to 64 characters.
    max_source_length = MAX_IDENTIFIER_LENGTH - len(suffix)

    if max_source_length < 1:
        raise ValueError("Cleaning suffix is too long for a MySQL identifier.")

    safe_table = safe_table[:max_source_length]

    return f"{safe_table}{suffix}"


def _build_workspace_create_sql(
    create_statement: str,
    database: str,
    source_table: str,
    working_table_name: str,
) -> str:
    """
    Transform the source SHOW CREATE TABLE statement so that it
    creates the working table instead.

    Only the CREATE TABLE target is replaced.
    The remainder of the original CREATE statement is preserved.
    """
    if not create_statement:
        raise ValueError("Source CREATE TABLE statement is empty.")

    qualified_target = _quote_table(database, working_table_name)

    pattern = re.compile(
        r"^(CREATE\s+TABLE\s+)"
        r"(?:IF\s+NOT\s+EXISTS\s+)?"
        r"(?:`[^`]+`|\w+)"
        r"(?:\s*\.\s*(?:`[^`]+`|\w+))?",
        re.IGNORECASE,
    )

    match = pattern.search(create_statement)

    if not match:
        raise ValueError(
            f"Could not identify CREATE TABLE target for '{source_table}'."
        )

    # Preserve CREATE TABLE / IF NOT EXISTS exactly as supplied.
    prefix = match.group(1)

    # Detect whether IF NOT EXISTS was present.
    matched_text = match.group(0)
    if re.search(r"IF\s+NOT\s+EXISTS", matched_text, re.IGNORECASE):
        replacement = f"{prefix}IF NOT EXISTS {qualified_target}"
    else:
        replacement = f"{prefix}{qualified_target}"

    return replacement + create_statement[match.end() :]


def create_workspace(
    engine,
    source_db: str,
    source_table: str,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Create a persistent cleaning workspace for a source table.

    The production/source table is never modified.

    Workflow:
        1. Verify source table exists.
        2. Count source rows.
        3. Generate unique workspace table name.
        4. Read SHOW CREATE TABLE from source.
        5. Create workspace using the source structure.
        6. Copy source data into workspace.
        7. Verify row counts match.
        8. Return workspace details.
    """
    working_table_name = None
    workspace_created = False

    try:
        # ---------------------------------------------------------
        # 1. Verify source table exists
        # ---------------------------------------------------------
        inspector = inspect(engine)

        source_tables = inspector.get_table_names(schema=source_db)

        if source_table not in source_tables:
            return (
                False,
                f"Source table '{source_table}' not found in database '{source_db}'.",
                None,
            )

        quoted_source = _quote_table(source_db, source_table)

        # ---------------------------------------------------------
        # 2. Count source rows
        # ---------------------------------------------------------
        count_query = text(f"SELECT COUNT(*) AS cnt FROM {quoted_source}")

        with engine.connect() as conn:
            source_count_result = conn.execute(count_query)
            source_row_count = source_count_result.scalar()

        # ---------------------------------------------------------
        # 3. Generate unique workspace name
        # ---------------------------------------------------------
        unique_id = uuid.uuid4().hex[:12]

        working_table_name = _generate_working_table_name(
            source_db,
            source_table,
            unique_id,
        )

        quoted_working = _quote_table(
            source_db,
            working_table_name,
        )

        # ---------------------------------------------------------
        # 4. Get source CREATE TABLE statement
        # ---------------------------------------------------------
        show_create_query = text(f"SHOW CREATE TABLE {quoted_source}")

        with engine.connect() as conn:
            create_result = conn.execute(show_create_query)
            create_row = create_result.fetchone()

        if create_row is None:
            return (
                False,
                f"Could not retrieve CREATE TABLE for '{source_table}'.",
                None,
            )

        create_statement = create_row[1]

        # ---------------------------------------------------------
        # 5. Build and execute CREATE TABLE for workspace
        # ---------------------------------------------------------
        working_create_statement = _build_workspace_create_sql(
            create_statement=create_statement,
            database=source_db,
            source_table=source_table,
            working_table_name=working_table_name,
        )

        with engine.connect() as conn:
            conn.execute(text(working_create_statement))
            conn.commit()

        workspace_created = True

        # ---------------------------------------------------------
        # 6. Copy data from production -> workspace
        # ---------------------------------------------------------
        insert_query = text(
            f"INSERT INTO {quoted_working} " f"SELECT * FROM {quoted_source}"
        )

        with engine.connect() as conn:
            conn.execute(insert_query)
            conn.commit()

        # ---------------------------------------------------------
        # 7. Verify row counts
        # ---------------------------------------------------------
        working_count_query = text(f"SELECT COUNT(*) AS cnt FROM {quoted_working}")

        with engine.connect() as conn:
            working_count_result = conn.execute(working_count_query)
            working_row_count = working_count_result.scalar()

        if source_row_count != working_row_count:
            # Safe cleanup: only the generated workspace can be dropped.
            drop_query = text(f"DROP TABLE IF EXISTS {quoted_working}")

            with engine.connect() as conn:
                conn.execute(drop_query)
                conn.commit()

            workspace_created = False

            return (
                False,
                (
                    f"Row count mismatch: source has {source_row_count} rows, "
                    f"working table has {working_row_count} rows. "
                    f"Working table cleaned up."
                ),
                None,
            )

        # ---------------------------------------------------------
        # 8. Return success details
        # ---------------------------------------------------------
        details = {
            "working_table_name": working_table_name,
            "source_db": source_db,
            "source_table": source_table,
            "source_row_count": source_row_count,
            "working_row_count": working_row_count,
            "status": "ready",
        }

        success_message = (
            "Workspace created successfully!\n"
            f"Working table: `{working_table_name}`\n"
            f"Rows: {source_row_count} source -> {working_row_count} working"
        )

        return True, success_message, details

    except Exception as e:
        logger.error(
            "Error creating workspace '%s': %s",
            working_table_name,
            str(e),
        )

        # Best-effort cleanup if CREATE succeeded but a later step failed.
        if workspace_created and working_table_name:
            try:
                quoted_working = _quote_table(
                    source_db,
                    working_table_name,
                )

                drop_query = text(f"DROP TABLE IF EXISTS {quoted_working}")

                with engine.connect() as conn:
                    conn.execute(drop_query)
                    conn.commit()

            except Exception as cleanup_error:
                logger.error(
                    "Failed to clean up workspace '%s': %s",
                    working_table_name,
                    cleanup_error,
                )

        return (
            False,
            f"Error creating workspace: {str(e)}",
            None,
        )


def delete_workspace(
    engine,
    database: str,
    working_table_name: str,
) -> Tuple[bool, str]:
    """
    Delete a cleaning workspace.

    Safety rule:
    Only tables containing the exact cleaning suffix are eligible.
    This prevents accidental deletion of production tables.
    """
    try:
        # ---------------------------------------------------------
        # Safety validation
        # ---------------------------------------------------------
        safe_name = _make_safe_table_name(working_table_name)

        if safe_name != working_table_name:
            return (
                False,
                "Refusing to delete an invalid table identifier.",
            )

        if working_table_name.count(CLEANING_SUFFIX) != 1:
            return (
                False,
                "Refusing to delete a table that is not identified as a cleaning workspace.",
            )

        quoted_working = _quote_table(
            database,
            working_table_name,
        )

        # ---------------------------------------------------------
        # Drop workspace
        # ---------------------------------------------------------
        drop_query = text(f"DROP TABLE IF EXISTS {quoted_working}")

        with engine.connect() as conn:
            conn.execute(drop_query)
            conn.commit()

        # ---------------------------------------------------------
        # Verify deletion
        # ---------------------------------------------------------
        inspector = inspect(engine)

        tables = inspector.get_table_names(schema=database)

        if working_table_name in tables:
            return (
                False,
                f"Working table '{working_table_name}' still exists.",
            )

        return (
            True,
            f"Working table '{working_table_name}' deleted successfully.",
        )

    except Exception as e:
        logger.error(
            "Error deleting workspace '%s': %s",
            working_table_name,
            str(e),
        )

        return (
            False,
            f"Error deleting workspace: {str(e)}",
        )


def get_workspace_info(
    engine, database: str, working_table_name: str
) -> Optional[Dict[str, Any]]:
    """
    Get information about an existing cleaning workspace.

    Returns:
        Dictionary containing workspace information.

        Returns None only when the workspace table genuinely
        does not exist.

        If another error occurs, the error is raised so the
        application can show the real problem instead of
        incorrectly saying that the workspace disappeared.
    """

    inspector = inspect(engine)

    # --------------------------------------------------------
    # Step 1: Check whether the workspace actually exists
    # --------------------------------------------------------

    tables = inspector.get_table_names(schema=database)

    if working_table_name not in tables:
        return None

    # --------------------------------------------------------
    # Step 2: Build safely quoted table reference
    # --------------------------------------------------------

    quoted = f"`{database}`.`{working_table_name}`"

    # --------------------------------------------------------
    # Step 3: Get row count
    # --------------------------------------------------------

    count_query = f"""
        SELECT COUNT(*) AS cnt
        FROM {quoted}
    """

    with engine.connect() as conn:
        count_result = conn.execute(text(count_query))
        row_count = count_result.scalar()

    # --------------------------------------------------------
    # Step 4: Get preview
    # --------------------------------------------------------

    preview_query = f"""
        SELECT *
        FROM {quoted}
        LIMIT 5
    """

    with engine.connect() as conn:
        preview_df = pd.read_sql_query(
            text(preview_query),
            conn,
        )

    # --------------------------------------------------------
    # Step 5: Get workspace schema
    # --------------------------------------------------------

    schema = MySQLMetadataInspector.get_table_schema(
        engine,
        database,
        working_table_name,
    )

    # --------------------------------------------------------
    # Step 6: Return workspace information
    # --------------------------------------------------------

    return {
        "working_table_name": working_table_name,
        "row_count": row_count,
        "schema": schema,
        "preview": preview_df,
        "exists": True,
    }


def list_workspaces_for_table(
    engine,
    database: str,
    source_table: str,
) -> List[Dict[str, Any]]:
    """
    Discover all existing cleaning workspaces in the database that belong to source_table.
    """
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names(schema=database)
        safe_source = _make_safe_table_name(source_table)
        prefix = f"{safe_source}{CLEANING_SUFFIX}"

        # Match tables that start with prefix and have exactly one CLEANING_SUFFIX
        ws_tables = [
            t for t in tables if t.startswith(prefix) and t.count(CLEANING_SUFFIX) == 1
        ]

        workspaces = []
        for t in ws_tables:
            quoted = _quote_table(database, t)
            row_count = 0
            try:
                with engine.connect() as conn:
                    res = conn.execute(text(f"SELECT COUNT(*) FROM {quoted}"))
                    row_count = res.scalar() or 0
            except Exception:
                row_count = 0

            workspaces.append(
                {
                    "working_table_name": t,
                    "source_table": source_table,
                    "database": database,
                    "row_count": row_count,
                }
            )
        return workspaces
    except Exception as e:
        logger.error(
            "Error listing workspaces for table '%s.%s': %s",
            database,
            source_table,
            str(e),
        )
        return []


def list_all_workspaces(
    engine,
    database: str,
) -> List[Dict[str, Any]]:
    """
    Discover all cleaning workspace tables currently existing in the database.
    """
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names(schema=database)
        ws_tables = [
            t for t in tables if CLEANING_SUFFIX in t and t.count(CLEANING_SUFFIX) == 1
        ]

        workspaces = []
        for t in ws_tables:
            source_table_part = t.split(CLEANING_SUFFIX)[0]
            quoted = _quote_table(database, t)
            row_count = 0
            try:
                with engine.connect() as conn:
                    res = conn.execute(text(f"SELECT COUNT(*) FROM {quoted}"))
                    row_count = res.scalar() or 0
            except Exception:
                row_count = 0

            workspaces.append(
                {
                    "working_table_name": t,
                    "source_table": source_table_part,
                    "database": database,
                    "row_count": row_count,
                }
            )
        return workspaces
    except Exception as e:
        logger.error(
            "Error listing all workspaces in database '%s': %s",
            database,
            str(e),
        )
        return []


def attach_workspace(
    engine,
    database: str,
    working_table_name: str,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Attach to an existing cleaning workspace in the database.
    Validates workspace table safety and existence, then loads full details.
    """
    try:
        if not working_table_name or working_table_name.count(CLEANING_SUFFIX) != 1:
            return (
                False,
                "Refusing to attach to a table that is not identified as a cleaning workspace.",
                None,
            )

        info = get_workspace_info(engine, database, working_table_name)
        if not info:
            return (
                False,
                f"Workspace table '{working_table_name}' does not exist in database '{database}'.",
                None,
            )

        source_table_part = working_table_name.split(CLEANING_SUFFIX)[0]

        details = {
            "working_table_name": working_table_name,
            "source_db": database,
            "source_table": source_table_part,
            "working_row_count": info["row_count"],
            "status": "ready",
        }

        return (
            True,
            f"Successfully connected to existing workspace `{working_table_name}`.",
            details,
        )
    except Exception as e:
        logger.error(
            "Error attaching to workspace '%s.%s': %s",
            database,
            working_table_name,
            str(e),
        )
        return (
            False,
            f"Error attaching to workspace: {str(e)}",
            None,
        )


def delete_all_workspaces(
    engine,
    database: str,
    source_table: Optional[str] = None,
) -> Tuple[bool, str, int]:
    """
    Safely drop multiple workspace tables (either for a specific source table or all in the database).
    Strictly verifies each table contains CLEANING_SUFFIX before dropping.
    """
    try:
        if source_table:
            workspaces = list_workspaces_for_table(engine, database, source_table)
        else:
            workspaces = list_all_workspaces(engine, database)

        if not workspaces:
            return True, "No cleaning workspaces found to delete.", 0

        dropped_count = 0
        for ws in workspaces:
            tbl_name = ws["working_table_name"]
            if tbl_name.count(CLEANING_SUFFIX) != 1:
                continue
            ok, _ = delete_workspace(engine, database, tbl_name)
            if ok:
                dropped_count += 1

        return (
            True,
            f"Successfully torn down {dropped_count} workspace table(s).",
            dropped_count,
        )
    except Exception as e:
        logger.error(
            "Error deleting workspaces in database '%s': %s",
            database,
            str(e),
        )
        return (
            False,
            f"Error deleting workspaces: {str(e)}",
            0,
        )


TEXT_DATA_TYPES = {
    "char",
    "varchar",
    "text",
    "tinytext",
    "mediumtext",
    "longtext",
    "string",
    "nvarchar",
    "nchar",
}

DATE_DATA_TYPES = {
    "date",
    "datetime",
    "timestamp",
    "time",
    "year",
}

NUMERIC_DATA_TYPES = {
    "tinyint",
    "smallint",
    "mediumint",
    "int",
    "bigint",
    "decimal",
    "numeric",
    "float",
    "double",
    "real",
}

BOOLEAN_DATA_TYPES = {
    "boolean",
    "bool",
}

UNSUPPORTED_DATA_TYPES = {
    "blob",
    "tinyblob",
    "mediumblob",
    "longblob",
    "binary",
    "varbinary",
    "json",
    "geometry",
    "point",
    "linestring",
    "polygon",
    "multipoint",
    "multilinestring",
    "multipolygon",
    "geometrycollection",
}


def classify_column_type(data_type: str) -> str:
    """Classify MySQL data type into category: 'text', 'numeric', 'date', 'boolean', 'unsupported'."""
    norm = _normalize_data_type(data_type)
    if norm in TEXT_DATA_TYPES:
        return "text"
    if norm in NUMERIC_DATA_TYPES:
        return "numeric"
    if norm in DATE_DATA_TYPES:
        return "date"
    if norm in BOOLEAN_DATA_TYPES:
        return "boolean"
    if norm == "tinyint":
        return "boolean"
    if norm in UNSUPPORTED_DATA_TYPES:
        return "unsupported"
    return "unsupported"


def _normalize_data_type(data_type: str) -> str:
    """
    Normalize MySQL data type by extracting base type name.
    e.g., 'varchar(30)' -> 'varchar', 'char(10)' -> 'char', 'decimal(10,2)' -> 'decimal'
    """
    if not data_type:
        return ""
    return str(data_type).lower().split("(")[0].strip()


FORMAT_MAP = {
    "YYYY-MM-DD": "%Y-%m-%d",
    "DD-MM-YYYY": "%d-%m-%Y",
    "MM-DD-YYYY": "%m-%d-%Y",
    "DD/MM/YYYY": "%d/%m/%Y",
    "MM/DD/YYYY": "%m/%d/%Y",
    "YYYY/MM/DD": "%Y/%m/%d",
    "DD-MON-YYYY": "%d-%b-%Y",
    "DD-MONTH-YYYY": "%d-%M-%Y",
}

PARSE_FORMATS = [
    # DD-MM-YYYY variants (highest priority for international preference)
    "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%d %m %Y",
    # 2-digit year DD-MM
    "%d-%m-%y", "%d/%m/%y",
    # Textual months (day first) - "21 August 2023", "21 Aug 2023", "August 21, 2023", etc.
    "%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y",
    "%d-%b-%Y", "%d-%B-%Y", "%d-%b-%y",
    # MM-DD-YYYY variants
    "%m-%d-%Y", "%m/%d/%Y", "%m.%d.%Y",
    # 2-digit year MM-DD
    "%m-%d-%y", "%m/%d/%y",
    # ISO / Year-first formats
    "%Y-%m-%d", "%Y/%m/%d", "%Y%m%d",
    # With time components
    "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M:%S", "%m-%d-%Y %H:%M:%S",
    "%Y-%m-%d %H:%M", "%d-%m-%Y %H:%M", "%m-%d-%Y %H:%M",
    "%d %B %Y %H:%M", "%B %d, %Y %H:%M",
    # ISO with T/Z
    "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S.%fZ",
]

def detect_date_like_columns(
    engine,
    database: str,
    table_name: str,
    sample_limit: int = 500,
    threshold: float = 0.30,
) -> List[Dict[str, Any]]:
    """
    Scan text/varchar columns to detect which ones contain date-like values.
    
    Samples up to `sample_limit` distinct non-null values per column and tries
    to parse them with PARSE_FORMATS. Returns columns where parseable% >= threshold.
    
    Returns list of dicts with:
        column, data_type, sample_size, parseable_count, parseable_pct,
        dominant_formats, ambiguity_pct, unparseable_samples, recommendation
    """
    try:
        # Get all text/varchar columns
        text_cols = get_text_columns(engine, database, table_name)
        if not text_cols:
            return []
        
        quoted_table = _quote_table(database, table_name)
        results = []
        
        with engine.connect() as conn:
            for col in text_cols:
                quoted_col = _quote_identifier(col)
                
                # Sample distinct non-null values
                sample_query = text(f"""
                    SELECT DISTINCT {quoted_col} as val
                    FROM {quoted_table}
                    WHERE {quoted_col} IS NOT NULL AND TRIM({quoted_col}) != ''
                    LIMIT {sample_limit}
                """)
                sample_result = conn.execute(sample_query)
                values = [row._mapping["val"] for row in sample_result]
                
                if not values:
                    continue
                
                # Try parsing each value with all formats
                format_counts = {}
                parseable = 0
                ambiguous = 0
                unparseable_samples = []
                
                for val in values:
                    val_str = str(val).strip()
                    if not val_str:
                        continue
                    
                    matched_formats = []
                    for fmt in PARSE_FORMATS:
                        try:
                            # Use STR_TO_DATE equivalent in Python for detection
                            from datetime import datetime
                            datetime.strptime(val_str, fmt)
                            matched_formats.append(fmt)
                        except ValueError:
                            continue
                    
                    if matched_formats:
                        parseable += 1
                        if len(matched_formats) > 1:
                            ambiguous += 1
                        for fmt in matched_formats:
                            format_counts[fmt] = format_counts.get(fmt, 0) + 1
                    else:
                        if len(unparseable_samples) < 5:
                            unparseable_samples.append(val_str)
                
                if parseable == 0:
                    continue
                
                parseable_pct = parseable / len(values)
                if parseable_pct < threshold:
                    continue
                
                # Get dominant formats (top 3)
                sorted_formats = sorted(format_counts.items(), key=lambda x: x[1], reverse=True)
                dominant_formats = [
                    {"format": fmt, "count": cnt, "percentage": round(cnt / parseable * 100, 1)}
                    for fmt, cnt in sorted_formats[:3]
                ]
                
                ambiguity_pct = round(ambiguous / parseable * 100, 1) if parseable > 0 else 0
                
                if parseable_pct >= 0.9 and ambiguity_pct < 5:
                    recommendation = "high_confidence"
                elif parseable_pct >= 0.5:
                    recommendation = "mixed_formats"
                else:
                    recommendation = "low_confidence"
                
                results.append({
                    "column": col,
                    "data_type": "text/varchar",
                    "sample_size": len(values),
                    "parseable_count": parseable,
                    "parseable_pct": round(parseable_pct * 100, 1),
                    "dominant_formats": dominant_formats,
                    "ambiguity_pct": ambiguity_pct,
                    "unparseable_samples": unparseable_samples,
                    "recommendation": recommendation,
                })
        
        return results
    
    except Exception as e:
        logger.error(
            "Error detecting date-like columns for '%s': %s",
            table_name,
            str(e),
        )
        return []


def get_date_columns(
    engine,
    database: str,
    working_table_name: str,
) -> list:
    """
    Retrieve all date/date-time column names for a table in the database.
    Only returns native DATE, DATETIME, TIMESTAMP, TIME, YEAR columns.
    """
    try:
        column_query = text("""
            SELECT COLUMN_NAME, DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = :database
              AND TABLE_NAME = :table_name
            ORDER BY ORDINAL_POSITION
            """)
        with engine.connect() as conn:
            result = conn.execute(
                column_query,
                {"database": database, "table_name": working_table_name},
            )
            return [
                row._mapping["COLUMN_NAME"]
                for row in result
                if str(row._mapping["DATA_TYPE"]).lower() in DATE_DATA_TYPES
            ]
    except Exception as e:
        logger.error(
            "Error retrieving date columns for '%s': %s",
            working_table_name,
            str(e),
        )
        return []


def analyze_date_column(
    engine,
    database: str,
    table_name: str,
    column: str,
    limit: int = 10000,
) -> Dict[str, Any]:
    """
    Deep analysis of a single column for date standardization.
    
    Scans up to `limit` rows and provides detailed format distribution,
    ambiguity matrix, row preview, and unparseable categorization.
    """
    try:
        quoted_table = _quote_table(database, table_name)
        quoted_col = _quote_identifier(column)
        
        with engine.connect() as conn:
            # Get all non-null, non-blank values (up to limit)
            query = text(f"""
                SELECT {quoted_col} as val
                FROM {quoted_table}
                WHERE {quoted_col} IS NOT NULL AND TRIM({quoted_col}) != ''
                LIMIT {limit}
            """)
            result = conn.execute(query)
            values = [row._mapping["val"] for row in result]
        
        if not values:
            return {
                "column": column,
                "total_values": 0,
                "format_distribution": {},
                "ambiguity_matrix": {},
                "row_preview": [],
                "unparseable_categories": {"nulls": 0, "blanks": 0, "garbage": []},
                "recommended_parse_formats": [],
            }
        
        # Analyze each value
        format_counts = {}
        ambiguity_matrix = {}
        row_preview = []
        garbage_samples = []
        
        for val in values:
            val_str = str(val).strip()
            if not val_str:
                continue
            
            matched_formats = []
            for fmt in PARSE_FORMATS:
                try:
                    from datetime import datetime
                    parsed = datetime.strptime(val_str, fmt)
                    matched_formats.append(fmt)
                except ValueError:
                    continue
            
            if matched_formats:
                # Use first matched format for preview (priority order)
                primary_fmt = matched_formats[0]
                format_counts[primary_fmt] = format_counts.get(primary_fmt, 0) + 1
                
                try:
                    parsed = datetime.strptime(val_str, primary_fmt)
                    iso_format = parsed.strftime("%Y-%m-%d")
                except ValueError:
                    iso_format = "ERROR"
                
                if len(row_preview) < 50:
                    row_preview.append({
                        "original": val_str,
                        "parsed": iso_format,
                        "matched_formats": matched_formats,
                    })
                
                if len(matched_formats) > 1:
                    ambiguity_matrix[val_str] = matched_formats
            else:
                if len(garbage_samples) < 20:
                    garbage_samples.append(val_str)
        
        # Count nulls and blanks
        with engine.connect() as conn:
            null_query = text(f"SELECT COUNT(*) FROM {quoted_table} WHERE {quoted_col} IS NULL")
            nulls = conn.execute(null_query).scalar() or 0
            
            blank_query = text(f"SELECT COUNT(*) FROM {quoted_table} WHERE {quoted_col} IS NOT NULL AND TRIM({quoted_col}) = ''")
            blanks = conn.execute(blank_query).scalar() or 0
        
        # Recommended parse formats (by frequency)
        recommended = sorted(format_counts.items(), key=lambda x: x[1], reverse=True)
        recommended_formats = [fmt for fmt, _ in recommended]
        
        return {
            "column": column,
            "total_values": len(values),
            "format_distribution": format_counts,
            "ambiguity_matrix": ambiguity_matrix,
            "row_preview": row_preview,
            "unparseable_categories": {
                "nulls": nulls,
                "blanks": blanks,
                "garbage": garbage_samples,
            },
            "recommended_parse_formats": recommended_formats,
        }
    
    except Exception as e:
        logger.error(
            "Error analyzing date column '%s.%s': %s",
            database,
            table_name,
            str(e),
        )
        return {}


def remove_whitespace_workspace(
    engine,
    database: str,
    working_table_name: str,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Remove leading/trailing whitespace and normalize repeated
    whitespace in all text/string columns of the cleaning workspace.

    Only the cleaning workspace is modified.
    The original/source table is never modified.

    Returns:
        (
            success,
            message,
            report
        )

    Report contains:
        - operation
        - total_values_changed
        - columns_affected
        - rows_affected
    """

    try:
        # ---------------------------------------------------------
        # 1. Safety validation
        # ---------------------------------------------------------

        if working_table_name.count(CLEANING_SUFFIX) != 1:
            return (
                False,
                "Refusing to clean a table that is not identified "
                "as a cleaning workspace.",
                {},
            )

        inspector = inspect(engine)

        tables = inspector.get_table_names(schema=database)

        if working_table_name not in tables:
            return (
                False,
                f"Working table '{working_table_name}' not found "
                f"in database '{database}'.",
                {},
            )

        quoted_table = _quote_table(
            database,
            working_table_name,
        )

        # ---------------------------------------------------------
        # 2. Get column metadata
        # ---------------------------------------------------------

        column_query = text("""
            SELECT
                COLUMN_NAME,
                DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = :database
              AND TABLE_NAME = :table_name
            ORDER BY ORDINAL_POSITION
            """)

        with engine.connect() as conn:
            result = conn.execute(
                column_query,
                {
                    "database": database,
                    "table_name": working_table_name,
                },
            )

            columns = [dict(row._mapping) for row in result]

        # ---------------------------------------------------------
        # 3. Identify text columns
        # ---------------------------------------------------------

        text_columns = []

        for column in columns:

            column_name = column["COLUMN_NAME"]
            data_type = str(column["DATA_TYPE"]).lower()

            if data_type in TEXT_DATA_TYPES:
                text_columns.append(column_name)

        # ---------------------------------------------------------
        # 4. No text columns
        # ---------------------------------------------------------

        if not text_columns:

            report = {
                "operation": "Whitespace Cleaning",
                "total_values_changed": 0,
                "columns_affected": [],
                "rows_affected": 0,
            }

            return (
                True,
                "No text/string columns were found. "
                "No whitespace cleaning was required.",
                report,
            )

        # ---------------------------------------------------------
        # 5. Build conditions for affected rows
        # ---------------------------------------------------------

        # A row is considered affected if at least one text column
        # contains whitespace that will actually be changed.

        affected_conditions = []

        for column_name in text_columns:

            quoted_column = _quote_identifier(column_name)

            condition = f"""
                (
                    {quoted_column} IS NOT NULL
                    AND {quoted_column} <> TRIM(
                        REGEXP_REPLACE(
                            {quoted_column},
                            '[[:space:]]+',
                            ' '
                        )
                    )
                )
            """

            affected_conditions.append(condition)

        affected_where = " OR ".join(affected_conditions)

        # ---------------------------------------------------------
        # 6. Process cleaning inside one transaction
        # ---------------------------------------------------------

        column_reports = []
        total_values_changed = 0
        rows_affected = 0

        with engine.begin() as conn:

            # -----------------------------------------------------
            # Count UNIQUE rows that will be affected
            # -----------------------------------------------------

            count_rows_query = text(f"""
                SELECT COUNT(*)
                FROM {quoted_table}
                WHERE {affected_where}
                """)

            rows_affected = conn.execute(count_rows_query).scalar() or 0

            # -----------------------------------------------------
            # Clean each text column
            # -----------------------------------------------------

            for column_name in text_columns:

                quoted_column = _quote_identifier(column_name)

                # Count values that actually need cleaning
                count_values_query = text(f"""
                    SELECT COUNT(*)
                    FROM {quoted_table}
                    WHERE {quoted_column} IS NOT NULL
                      AND {quoted_column} <> TRIM(
                          REGEXP_REPLACE(
                              {quoted_column},
                              '[[:space:]]+',
                              ' '
                          )
                      )
                    """)

                changed_count = conn.execute(count_values_query).scalar() or 0

                if changed_count == 0:
                    continue

                # Apply cleaning directly in MySQL.
                #
                # This preserves:
                # - primary keys
                # - indexes
                # - auto_increment
                # - table structure
                # - column definitions
                #
                update_query = text(f"""
                    UPDATE {quoted_table}
                    SET {quoted_column} =
                        TRIM(
                            REGEXP_REPLACE(
                                {quoted_column},
                                '[[:space:]]+',
                                ' '
                            )
                        )
                    WHERE {quoted_column} IS NOT NULL
                      AND {quoted_column} <> TRIM(
                          REGEXP_REPLACE(
                              {quoted_column},
                              '[[:space:]]+',
                              ' '
                          )
                      )
                    """)

                conn.execute(update_query)

                total_values_changed += changed_count

                column_reports.append(
                    {
                        "column": column_name,
                        "values_changed": changed_count,
                    }
                )

        # ---------------------------------------------------------
        # 7. Build final report
        # ---------------------------------------------------------

        report = {
            "operation": "Whitespace Cleaning",
            "total_values_changed": total_values_changed,
            "columns_affected": column_reports,
            "rows_affected": rows_affected,
        }

        # ---------------------------------------------------------
        # 8. Final message
        # ---------------------------------------------------------

        if total_values_changed == 0:

            message = (
                "Whitespace cleaning completed. " "No whitespace issues were found."
            )

        else:

            message = (
                "Whitespace cleaning completed successfully. "
                f"{total_values_changed} value(s) were cleaned "
                f"across {len(column_reports)} column(s)."
            )

        return (
            True,
            message,
            report,
        )

    except Exception as e:

        logger.error(
            "Error performing whitespace cleaning on '%s': %s",
            working_table_name,
            str(e),
        )

        return (
            False,
            f"Error during whitespace cleaning: {str(e)}",
            {},
        )


def get_text_columns(
    engine,
    database: str,
    working_table_name: str,
) -> list:
    """
    Retrieve all text/string column names for a table in the database.
    """
    try:
        column_query = text("""
            SELECT COLUMN_NAME, DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = :database
              AND TABLE_NAME = :table_name
            ORDER BY ORDINAL_POSITION
            """)
        with engine.connect() as conn:
            result = conn.execute(
                column_query,
                {"database": database, "table_name": working_table_name},
            )
            return [
                row._mapping["COLUMN_NAME"]
                for row in result
                if str(row._mapping["DATA_TYPE"]).lower() in TEXT_DATA_TYPES
            ]
    except Exception as e:
        logger.error(
            "Error retrieving text columns for '%s.%s': %s",
            database,
            working_table_name,
            str(e),
        )
        return []


def format_dates_workspace(
    engine,
    database: str,
    working_table_name: str,
    target_column: str,
    target_format: str,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Validate and preview date formatting for a native date/date-time column in the cleaning workspace.

    For native MySQL DATE/DATETIME/TIMESTAMP columns, the storage format is binary and cannot be changed.
    This operation validates all values, shows a preview of formatted output, and returns a structured report.

    Only the cleaning workspace is analyzed. The original/source table is never modified.

    Returns:
        (
            success,
            message,
            report
        )

    Report contains:
        - operation: "Date Formatting"
        - column: target column name
        - original_format: "native"
        - target_format: selected format string
        - total_examined: total rows examined
        - nulls_skipped: NULL values skipped
        - blanks_skipped: blank/empty values skipped (for string-typed date columns)
        - invalid_unparseable: values that could not be parsed as valid dates
        - values_formatted: 0 for native types (storage unchanged)
        - status: "validated" or "validated (native storage — format is display-only)"
    """
    try:
        # 1. Safety validation: Workspace identification
        if not working_table_name or working_table_name.count(CLEANING_SUFFIX) != 1:
            return (
                False,
                "Refusing to analyze a table that is not identified as a cleaning workspace.",
                {},
            )

        safe_name = _make_safe_table_name(working_table_name)
        if safe_name != working_table_name:
            return (
                False,
                "Refusing to analyze an invalid table identifier.",
                {},
            )

        # 2. Validation: Target format
        if target_format not in FORMAT_MAP:
            return (
                False,
                f"Invalid target format '{target_format}'. Must be one of: {', '.join(FORMAT_MAP.keys())}.",
                {},
            )

        mysql_format = FORMAT_MAP[target_format]

        # 3. Validation: Table existence
        inspector = inspect(engine)
        tables = inspector.get_table_names(schema=database)
        if working_table_name not in tables:
            return (
                False,
                f"Working table '{working_table_name}' not found in database '{database}'.",
                {},
            )

        # 4. Column metadata and type validation
        table_columns_info = inspector.get_columns(working_table_name, schema=database)
        col_info = next((c for c in table_columns_info if c["name"] == target_column), None)

        if not col_info:
            return (
                False,
                f"Column '{target_column}' not found in table '{working_table_name}'.",
                {},
            )

        data_type = _normalize_data_type(col_info.get("type", ""))
        if data_type not in DATE_DATA_TYPES:
            return (
                False,
                f"Column '{target_column}' is not a native date/date-time type (found: {data_type}). "
                f"Only native DATE, DATETIME, TIMESTAMP, TIME, YEAR columns are supported.",
                {},
            )

        quoted_table = _quote_table(database, working_table_name)
        quoted_column = _quote_identifier(target_column)

        # 5. Analyze values in the workspace
        with engine.connect() as conn:
            # Total rows
            total_query = text(f"SELECT COUNT(*) FROM {quoted_table}")
            total_rows = conn.execute(total_query).scalar() or 0

            # NULL count
            null_query = text(f"SELECT COUNT(*) FROM {quoted_table} WHERE {quoted_column} IS NULL")
            null_count = conn.execute(null_query).scalar() or 0

            # For native date types, there are no "blank" strings, but check anyway for safety
            blank_query = text(f"""
                SELECT COUNT(*) FROM {quoted_table} 
                WHERE {quoted_column} IS NOT NULL AND TRIM(CAST({quoted_column} AS CHAR)) = ''
            """)
            blank_count = conn.execute(blank_query).scalar() or 0

            # Check for invalid dates - for native types, MySQL ensures validity
            # But we can check if DATE_FORMAT returns NULL (which indicates invalid)
            invalid_query = text(f"""
                SELECT COUNT(*) FROM {quoted_table}
                WHERE {quoted_column} IS NOT NULL
                  AND DATE_FORMAT({quoted_column}, :fmt) IS NULL
            """)
            invalid_count = conn.execute(invalid_query, {"fmt": mysql_format}).scalar() or 0

            # Preview sample: original + formatted
            preview_query = text(f"""
                SELECT 
                    {quoted_column} AS original,
                    DATE_FORMAT({quoted_column}, :fmt) AS formatted
                FROM {quoted_table}
                WHERE {quoted_column} IS NOT NULL
                LIMIT 20
            """)
            preview_result = conn.execute(preview_query, {"fmt": mysql_format})
            preview_rows = [dict(row._mapping) for row in preview_result]

        valid_count = total_rows - null_count - blank_count - invalid_count

        # 6. Build structured report
        report = {
            "operation": "Date Formatting",
            "column": target_column,
            "original_format": "native",
            "target_format": target_format,
            "total_examined": total_rows,
            "nulls_skipped": null_count,
            "blanks_skipped": blank_count,
            "invalid_unparseable": invalid_count,
            "values_formatted": 0,  # Native types: storage is binary, no format conversion at storage level
            "valid_values": valid_count,
            "preview": preview_rows,
            "status": "validated (native storage — format is display-only)",
        }

        message = (
            f"Date formatting validated for column '{target_column}'. "
            f"{valid_count:,} valid value(s), {null_count:,} NULL(s), {blank_count:,} blank(s), "
            f"{invalid_count:,} invalid. Native MySQL {data_type.upper()} storage is binary — "
            f"display format is applied at query time via DATE_FORMAT()."
        )

        return (True, message, report)

    except Exception as e:
        logger.error(
            "Error performing date formatting validation on '%s.%s' (col: %s): %s",
            database,
            working_table_name,
            target_column,
            str(e),
        )
        return (
            False,
            f"Error during date formatting validation: {str(e)}",
            {},
        )


def apply_date_formatting_workspace(
    engine,
    database: str,
    working_table_name: str,
    target_column: str,
    target_format: str,
    new_column_name: Optional[str] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Apply date formatting by converting a native DATE/DATETIME/TIMESTAMP column
    to a formatted VARCHAR column in the cleaning workspace.

    This creates a new column (or replaces existing) with formatted date strings.
    The original column is preserved unless new_column_name == target_column.

    Only the cleaning workspace is modified. The original/source table is never modified.

    Args:
        target_format: One of FORMAT_MAP keys (e.g., "YYYY-MM-DD", "DD-MON-YYYY")
        new_column_name: Name for the new formatted column. If None, creates
                         "{target_column}_formatted". If same as target_column,
                         replaces the original column (requires ALTER TABLE).

    Returns:
        (success, message, report)
    """
    try:
        # 1. Safety validation: Workspace identification
        if not working_table_name or working_table_name.count(CLEANING_SUFFIX) != 1:
            return (
                False,
                "Refusing to modify a table that is not identified as a cleaning workspace.",
                {},
            )

        safe_name = _make_safe_table_name(working_table_name)
        if safe_name != working_table_name:
            return (
                False,
                "Refusing to modify an invalid table identifier.",
                {},
            )

        # 2. Validation: Target format
        if target_format not in FORMAT_MAP:
            return (
                False,
                f"Invalid target format '{target_format}'. Must be one of: {', '.join(FORMAT_MAP.keys())}.",
                {},
            )

        mysql_format = FORMAT_MAP[target_format]

        # 3. Validation: Table existence
        inspector = inspect(engine)
        tables = inspector.get_table_names(schema=database)
        if working_table_name not in tables:
            return (
                False,
                f"Working table '{working_table_name}' not found in database '{database}'.",
                {},
            )

        # 4. Column metadata and type validation
        table_columns_info = inspector.get_columns(working_table_name, schema=database)
        col_info = next((c for c in table_columns_info if c["name"] == target_column), None)

        if not col_info:
            return (
                False,
                f"Column '{target_column}' not found in table '{working_table_name}'.",
                {},
            )

        data_type = _normalize_data_type(col_info.get("type", ""))
        if data_type not in DATE_DATA_TYPES:
            return (
                False,
                f"Column '{target_column}' is not a native date/date-time type (found: {data_type}). "
                f"Only native DATE, DATETIME, TIMESTAMP, TIME, YEAR columns are supported.",
                {},
            )

        quoted_table = _quote_table(database, working_table_name)
        quoted_column = _quote_identifier(target_column)

        # Determine new column name
        if new_column_name is None:
            new_column_name = f"{target_column}_formatted"
        quoted_new_column = _quote_identifier(new_column_name)

        replace_original = (new_column_name == target_column)

        with engine.begin() as conn:
            if replace_original:
                # Add new column, populate, drop old, rename
                temp_col = f"{target_column}_temp_fmt"
                quoted_temp = _quote_identifier(temp_col)

                # Add temp column
                conn.execute(text(f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_temp} VARCHAR(50)"))
                # Populate with formatted values
                conn.execute(text(f"""
                    UPDATE {quoted_table}
                    SET {quoted_temp} = DATE_FORMAT({quoted_column}, :fmt)
                    WHERE {quoted_column} IS NOT NULL
                """), {"fmt": mysql_format})
                # Drop original column
                conn.execute(text(f"ALTER TABLE {quoted_table} DROP COLUMN {quoted_column}"))
                # Rename temp to original name
                conn.execute(text(f"ALTER TABLE {quoted_table} CHANGE COLUMN {quoted_temp} {quoted_column} VARCHAR(50)"))
            else:
                # Add new column if not exists
                col_names = [c["name"] for c in table_columns_info]
                if new_column_name not in col_names:
                    conn.execute(text(f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_new_column} VARCHAR(50)"))
                # Populate with formatted values
                conn.execute(text(f"""
                    UPDATE {quoted_table}
                    SET {quoted_new_column} = DATE_FORMAT({quoted_column}, :fmt)
                    WHERE {quoted_column} IS NOT NULL
                """), {"fmt": mysql_format})

            # Get count of updated rows
            count_query = text(f"SELECT COUNT(*) FROM {quoted_table} WHERE {quoted_column} IS NOT NULL")
            updated_count = conn.execute(count_query).scalar() or 0

        message = (
            f"Date formatting applied to column '{target_column}'. "
            f"{updated_count:,} value(s) formatted as {target_format} into column '{new_column_name}'."
        )

        report = {
            "operation": "Apply Date Formatting",
            "source_column": target_column,
            "target_column": new_column_name,
            "target_format": target_format,
            "rows_formatted": updated_count,
            "replaced_original": replace_original,
            "status": "completed",
        }

        return (True, message, report)

    except Exception as e:
        logger.error(
            "Error applying date formatting on '%s.%s' (col: %s): %s",
            database,
            working_table_name,
            target_column,
            str(e),
        )
        return (
            False,
            f"Error during date formatting application: {str(e)}",
            {},
        )





def count_blank_values_in_column(
    engine,
    database: str,
    working_table_name: str,
    column_name: str,
) -> int:
    """
    Count rows where column equals empty string '' (excluding NULLs).
    """
    try:
        quoted_table = _quote_table(database, working_table_name)
        quoted_column = _quote_identifier(column_name)

        query = text(f"""
            SELECT COUNT(*) AS cnt
            FROM {quoted_table}
            WHERE {quoted_column} IS NOT NULL
              AND {quoted_column} = ''
            """)
        with engine.connect() as conn:
            result = conn.execute(query)
            return result.scalar() or 0
    except Exception as e:
        logger.error(
            "Error counting blank values in '%s.%s' (col: %s): %s",
            database,
            working_table_name,
            column_name,
            str(e),
        )
        return 0


def scan_blank_and_null_columns(
    engine,
    database: str,
    working_table_name: str,
) -> list:
    """
    Scan all text/string columns in the workspace table and return detailed counts
    for blank/empty strings ('') and SQL NULL values.

    Returns:
        List of dictionaries with keys:
            - column (str): column name
            - blank_count (int): count of empty string values (IS NOT NULL AND col = '')
            - null_count (int): count of NULL values (IS NULL)
            - total_missing (int): blank_count + null_count
            - has_issues (bool): True if total_missing > 0
        Sorted with problematic columns (total_missing > 0, highest first) at the top.
    """
    try:
        text_cols = get_text_columns(engine, database, working_table_name)
        if not text_cols:
            return []

        quoted_table = _quote_table(database, working_table_name)
        select_clauses = []
        for i, col in enumerate(text_cols):
            qcol = _quote_identifier(col)
            select_clauses.append(
                f"SUM(CASE WHEN {qcol} IS NOT NULL AND {qcol} = '' THEN 1 ELSE 0 END) AS `b_{i}`"
            )
            select_clauses.append(
                f"SUM(CASE WHEN {qcol} IS NULL THEN 1 ELSE 0 END) AS `n_{i}`"
            )

        query = text(f"SELECT {', '.join(select_clauses)} FROM {quoted_table}")
        with engine.connect() as conn:
            exec_res = conn.execute(query)
            row = exec_res.first()
            if row is not None:
                if hasattr(row, "_mapping"):
                    row_map = dict(row._mapping)
                else:
                    row_map = dict(row)
            else:
                row_map = {}

        results = []
        for i, col in enumerate(text_cols):
            b_val = int(row_map.get(f"b_{i}") or 0)
            n_val = int(row_map.get(f"n_{i}") or 0)
            tot = b_val + n_val
            results.append(
                {
                    "column": col,
                    "blank_count": b_val,
                    "null_count": n_val,
                    "total_missing": tot,
                    "has_issues": tot > 0,
                }
            )

        # Sort: columns with issues first (descending by total_missing), then clean columns
        results.sort(
            key=lambda x: (not x["has_issues"], -x["total_missing"], x["column"])
        )
        return results

    except Exception as e:
        logger.error(
            "Error scanning blank and null columns in '%s.%s': %s",
            database,
            working_table_name,
            str(e),
        )
        return []


def scan_missing_values(
    engine,
    database: str,
    working_table_name: str,
) -> list:
    """
    Scan ALL supported columns in the workspace table for missing values.

    Returns:
        List of dictionaries with keys:
            - column (str): column name
            - data_type (str): MySQL data type (e.g., 'varchar', 'int', 'date')
            - type_category (str): 'text', 'numeric', 'date', 'boolean', 'unsupported'
            - null_count (int): count of SQL NULL values
            - blank_count (int): count of empty/whitespace strings (text columns only)
            - total_missing (int): null_count + blank_count
            - has_issues (bool): True if total_missing > 0
        Sorted with problematic columns (total_missing > 0, highest first) at the top.
    """
    try:
        # Get all columns with metadata from INFORMATION_SCHEMA
        column_query = text("""
            SELECT
                COLUMN_NAME,
                DATA_TYPE,
                IS_NULLABLE,
                COLUMN_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = :database
              AND TABLE_NAME = :table_name
            ORDER BY ORDINAL_POSITION
            """)

        with engine.connect() as conn:
            result = conn.execute(
                column_query,
                {"database": database, "table_name": working_table_name},
            )
            columns = [dict(row._mapping) for row in result]

        if not columns:
            return []

        # Classify each column
        supported_columns = []
        for col in columns:
            col_name = col["COLUMN_NAME"]
            data_type = str(col["DATA_TYPE"]).lower()
            type_category = classify_column_type(data_type)
            is_nullable = col["IS_NULLABLE"] == "YES"
            column_type = col.get("COLUMN_TYPE", "")

            # Special handling: tinyint(1) is boolean
            if type_category == "boolean" and "tinyint" in data_type:
                # Check if it's tinyint(1)
                if "(1)" in column_type.lower():
                    type_category = "boolean"
                else:
                    type_category = "numeric"

            if type_category != "unsupported" and is_nullable:
                supported_columns.append(
                    {
                        "column": col_name,
                        "data_type": data_type,
                        "type_category": type_category,
                    }
                )
        
        logger.info("Supported nullable columns for %s.%s: %s", database, working_table_name,
                   [(c["column"], c["data_type"], c["type_category"]) for c in supported_columns])

        if not supported_columns:
            return []

        quoted_table = _quote_table(database, working_table_name)
        select_clauses = []

        for i, col_info in enumerate(supported_columns):
            qcol = _quote_identifier(col_info["column"])
            cat = col_info["type_category"]

            # NULL count for all supported types
            select_clauses.append(
                f"SUM(CASE WHEN {qcol} IS NULL THEN 1 ELSE 0 END) AS `n_{i}`"
            )

            # Blank/whitespace count only for text columns
            if cat == "text":
                select_clauses.append(
                    f"SUM(CASE WHEN {qcol} IS NOT NULL AND TRIM({qcol}) = '' THEN 1 ELSE 0 END) AS `b_{i}`"
                )
            else:
                select_clauses.append(f"0 AS `b_{i}`")

        query = text(f"SELECT {', '.join(select_clauses)} FROM {quoted_table}")
        with engine.connect() as conn:
            exec_res = conn.execute(query)
            row = exec_res.first()
            if row is not None:
                if hasattr(row, "_mapping"):
                    row_map = dict(row._mapping)
                else:
                    row_map = dict(row)
            else:
                row_map = {}

        results = []
        for i, col_info in enumerate(supported_columns):
            n_val = int(row_map.get(f"n_{i}") or 0)
            b_val = int(row_map.get(f"b_{i}") or 0)
            tot = n_val + b_val
            results.append(
                {
                    "column": col_info["column"],
                    "data_type": col_info["data_type"],
                    "type_category": col_info["type_category"],
                    "null_count": n_val,
                    "blank_count": b_val,
                    "total_missing": tot,
                    "has_issues": tot > 0,
                }
            )
        
        # Debug log
        logger.info("Missing value scan results for %s.%s: %s", database, working_table_name, 
                   [(r["column"], r["type_category"], r["null_count"], r["blank_count"], r["total_missing"]) for r in results])

        # Sort: columns with issues first (descending by total_missing), then clean columns
        results.sort(
            key=lambda x: (not x["has_issues"], -x["total_missing"], x["column"])
        )
        return results

    except Exception as e:
        logger.error(
            "Error scanning missing values in '%s.%s': %s",
            database,
            working_table_name,
            str(e),
        )
        return []


def replace_blank_values_workspace(
    engine,
    database: str,
    working_table_name: str,
    column_name: str,
    replacement_value: str,
    target_mode: str = "blanks",
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Replace blank/empty string values ('') or NULL values in a specific column of the cleaning workspace
    with a user-selected replacement value.

    Args:
        engine: SQLAlchemy Engine
        database: Database name
        working_table_name: Temporary workspace table name
        column_name: Target text column
        replacement_value: Replacement string
        target_mode: 'blanks' (empty string ''), 'nulls' (SQL NULL), or 'both' (empty string or NULL)

    Safety rules:
    - Only tables containing the exact cleaning suffix (__cleaning_) can be modified.
    - Production/source table is never modified.
    - Column name is quoted safely using MySQL identifier quoting.
    - Replacement value is passed using a parameterized SQL query.

    Returns:
        (
            success,
            message,
            report
        )
    """
    try:
        # 1. Safety validation: Workspace identification
        if not working_table_name or working_table_name.count(CLEANING_SUFFIX) != 1:
            return (
                False,
                "Refusing to clean a table that is not identified as a cleaning workspace.",
                {},
            )

        safe_name = _make_safe_table_name(working_table_name)
        if safe_name != working_table_name:
            return (
                False,
                "Refusing to clean an invalid table identifier.",
                {},
            )

        # 2. Validation: Input arguments (fail fast)
        if not isinstance(column_name, str) or not column_name.strip():
            return (
                False,
                "Column name must be a non-empty string.",
                {},
            )

        if (
            replacement_value is None
            or not isinstance(replacement_value, str)
            or replacement_value == ""
        ):
            return (
                False,
                "Replacement value cannot be empty. Please specify a non-empty replacement string.",
                {},
            )

        # 3. Validation: Table existence
        inspector = inspect(engine)
        tables = inspector.get_table_names(schema=database)
        if working_table_name not in tables:
            return (
                False,
                f"Working table '{working_table_name}' not found in database '{database}'.",
                {},
            )

        # 5. Validation: Column exists and is a text/string column
        column_query = text("""
            SELECT COLUMN_NAME, DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = :database
              AND TABLE_NAME = :table_name
            ORDER BY ORDINAL_POSITION
            """)
        with engine.connect() as conn:
            result = conn.execute(
                column_query,
                {"database": database, "table_name": working_table_name},
            )
            columns = [dict(row._mapping) for row in result]

        col_dict = {
            col["COLUMN_NAME"]: str(col["DATA_TYPE"]).lower() for col in columns
        }

        if column_name not in col_dict:
            return (
                False,
                f"Column '{column_name}' not found in table '{working_table_name}'.",
                {},
            )

        col_type = _normalize_data_type(col_dict[column_name])
        if col_type not in TEXT_DATA_TYPES:
            return (
                False,
                f"Column '{column_name}' is of type '{col_type}', which is not a supported text/string column.",
                {},
            )

        quoted_table = _quote_table(database, working_table_name)
        quoted_column = _quote_identifier(column_name)

        # Determine WHERE filter based on target_mode
        if target_mode == "nulls":
            where_clause = f"{quoted_column} IS NULL"
            op_name = "NULL Value Replacement"
            label = "NULL"
        elif target_mode == "both":
            where_clause = f"({quoted_column} IS NULL OR {quoted_column} = '')"
            op_name = "Blank & NULL Value Replacement"
            label = "blank and NULL"
        else:
            target_mode = "blanks"
            where_clause = f"{quoted_column} IS NOT NULL AND {quoted_column} = ''"
            op_name = "Blank / Empty Value Replacement"
            label = "blank"

        # 6. Count matching values before update
        count_query = text(f"""
            SELECT COUNT(*) AS cnt
            FROM {quoted_table}
            WHERE {where_clause}
            """)

        with engine.connect() as conn:
            count_result = conn.execute(count_query)
            affected_count = count_result.scalar() or 0

        if affected_count == 0:
            report = {
                "operation": op_name,
                "target_mode": target_mode,
                "column": column_name,
                "replacement_value": replacement_value,
                "values_replaced": 0,
                "total_values_changed": 0,
            }
            if target_mode == "blanks":
                zero_msg = f"No blank/empty values found in column '{column_name}'. No values were changed."
            else:
                zero_msg = f"No {label} values found in column '{column_name}'. No values were changed."
            return (
                True,
                zero_msg,
                report,
            )

        # 7. Execute parameterized UPDATE in a transaction
        update_query = text(f"""
            UPDATE {quoted_table}
            SET {quoted_column} = :replacement
            WHERE {where_clause}
            """)

        with engine.begin() as conn:
            conn.execute(
                update_query,
                {"replacement": replacement_value},
            )

        # 8. Build structured report
        report = {
            "operation": op_name,
            "target_mode": target_mode,
            "column": column_name,
            "replacement_value": replacement_value,
            "values_replaced": affected_count,
            "total_values_changed": affected_count,
        }

        if target_mode == "blanks":
            message = (
                f"Successfully replaced {affected_count} blank value(s) in column "
                f"'{column_name}' with '{replacement_value}'."
            )
        else:
            message = (
                f"Successfully replaced {affected_count} {label} value(s) in column "
                f"'{column_name}' with '{replacement_value}'."
            )

        return (
            True,
            message,
            report,
        )

    except Exception as e:
        logger.error(
            "Error replacing blank values in '%s.%s' (col: %s): %s",
            database,
            working_table_name,
            column_name,
            str(e),
        )
        return (
            False,
            f"Error during blank value replacement: {str(e)}",
            {}
        )


def replace_missing_values_workspace(
    engine,
    database: str,
    working_table_name: str,
    column_name: str,
    replacement_value: Any,
    replacement_strategy: str,
    data_type: str,
    type_category: str,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Type-aware replacement of missing values in a specific column of the cleaning workspace.

    Args:
        engine: SQLAlchemy Engine
        database: Database name
        working_table_name: Temporary workspace table name
        column_name: Target column name
        replacement_value: Replacement value (type depends on data_type)
        replacement_strategy: Strategy used ('specific', 'zero', 'mean', 'median', 
                             'current_date', 'current_datetime', 'true', 'false', 'keep_null')
        data_type: MySQL data type from schema (e.g., 'varchar', 'int', 'date')
        type_category: Category from classify_column_type ('text', 'numeric', 'date', 'boolean')

    Returns:
        (success, message, report)
    """
    from datetime import date, datetime

    try:
        # 1. Safety validation: Workspace identification
        if not working_table_name or working_table_name.count(CLEANING_SUFFIX) != 1:
            return (
                False,
                "Refusing to clean a table that is not identified as a cleaning workspace.",
                {},
            )

        safe_name = _make_safe_table_name(working_table_name)
        if safe_name != working_table_name:
            return (
                False,
                "Refusing to clean an invalid table identifier.",
                {},
            )

        # 2. Validation: Input arguments
        if not isinstance(column_name, str) or not column_name.strip():
            return (
                False,
                "Column name must be a non-empty string.",
                {},
            )

        if replacement_strategy == "keep_null":
            return (
                True,
                "No changes made. Strategy is to keep NULL values.",
                {
                    "operation": "Missing Value Cleaning",
                    "strategy": "keep_null",
                    "column": column_name,
                    "data_type": data_type,
                    "type_category": type_category,
                    "values_replaced": 0,
                    "total_values_changed": 0,
                },
            )

        # 3. Validation: Table existence
        inspector = inspect(engine)
        tables = inspector.get_table_names(schema=database)
        if working_table_name not in tables:
            return (
                False,
                f"Working table '{working_table_name}' not found in database '{database}'.",
                {},
            )

        # 4. Get column metadata to verify data type
        column_query = text("""
            SELECT COLUMN_NAME, DATA_TYPE, COLUMN_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = :database
              AND TABLE_NAME = :table_name
            ORDER BY ORDINAL_POSITION
            """)
        with engine.connect() as conn:
            result = conn.execute(
                column_query,
                {"database": database, "table_name": working_table_name},
            )
            columns = [dict(row._mapping) for row in result]

        col_dict = {
            col["COLUMN_NAME"]: {"data_type": str(col["DATA_TYPE"]).lower(), "column_type": col.get("COLUMN_TYPE", "")}
            for col in columns
        }

        if column_name not in col_dict:
            return (
                False,
                f"Column '{column_name}' not found in table '{working_table_name}'.",
                {},
            )

        actual_data_type = col_dict[column_name]["data_type"]
        column_type = col_dict[column_name]["column_type"]

        # 5. Validate replacement value based on type_category
        quoted_table = _quote_table(database, working_table_name)
        quoted_column = _quote_identifier(column_name)

        # Build WHERE clause based on type_category
        if type_category == "text":
            where_clause = f"{quoted_column} IS NULL OR TRIM({quoted_column}) = ''"
            op_name = "Missing Value Cleaning (Text)"
        else:
            where_clause = f"{quoted_column} IS NULL"
            op_name = f"Missing Value Cleaning ({type_category.capitalize()})"

        # Validate and convert replacement value
        validated_value = None
        if type_category == "text":
            if not isinstance(replacement_value, str):
                return (
                    False,
                    f"Replacement value must be a string for text column '{column_name}'.",
                    {},
                )
            validated_value = replacement_value

        elif type_category == "numeric":
            try:
                if "decimal" in actual_data_type or "numeric" in actual_data_type:
                    validated_value = float(replacement_value)
                elif "float" in actual_data_type or "double" in actual_data_type or "real" in actual_data_type:
                    validated_value = float(replacement_value)
                else:
                    # Integer types
                    validated_value = int(float(replacement_value))
            except (ValueError, TypeError):
                return (
                    False,
                    f"Invalid numeric replacement value for column '{column_name}': {replacement_value}",
                    {},
                )

        elif type_category == "date":
            if replacement_strategy == "current_date":
                validated_value = date.today()
            elif isinstance(replacement_value, date):
                validated_value = replacement_value
            elif isinstance(replacement_value, str):
                try:
                    validated_value = datetime.strptime(replacement_value, "%Y-%m-%d").date()
                except ValueError:
                    return (
                        False,
                        f"Invalid date format for column '{column_name}'. Expected YYYY-MM-DD, got: {replacement_value}",
                        {},
                    )
            else:
                return (
                    False,
                    f"Invalid date replacement value for column '{column_name}': {replacement_value}",
                    {},
                )

        elif type_category == "datetime":
            if replacement_strategy == "current_datetime":
                validated_value = datetime.now()
            elif isinstance(replacement_value, datetime):
                validated_value = replacement_value
            elif isinstance(replacement_value, str):
                # Try parsing various datetime formats
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
                    try:
                        validated_value = datetime.strptime(replacement_value, fmt)
                        break
                    except ValueError:
                        continue
                if validated_value is None:
                    return (
                        False,
                        f"Invalid datetime format for column '{column_name}'. Expected YYYY-MM-DD HH:MM:SS, got: {replacement_value}",
                        {},
                    )
            else:
                return (
                    False,
                    f"Invalid datetime replacement value for column '{column_name}': {replacement_value}",
                    {},
                )

        elif type_category == "boolean":
            if replacement_strategy == "true":
                validated_value = 1
            elif replacement_strategy == "false":
                validated_value = 0
            elif isinstance(replacement_value, bool):
                validated_value = 1 if replacement_value else 0
            elif isinstance(replacement_value, (int, str)):
                try:
                    val = int(replacement_value)
                    if val not in (0, 1):
                        return (
                            False,
                            f"Boolean replacement must be 0 or 1 for column '{column_name}', got: {replacement_value}",
                            {},
                        )
                    validated_value = val
                except ValueError:
                    return (
                        False,
                        f"Invalid boolean replacement value for column '{column_name}': {replacement_value}",
                        {},
                    )
            else:
                return (
                    False,
                    f"Invalid boolean replacement value for column '{column_name}': {replacement_value}",
                    {},
                )

        else:
            return (
                False,
                f"Unsupported column type category '{type_category}' for column '{column_name}'.",
                {},
            )

        # 6. Count matching values before update
        count_query = text(f"""
            SELECT COUNT(*) AS cnt
            FROM {quoted_table}
            WHERE {where_clause}
            """)

        with engine.connect() as conn:
            count_result = conn.execute(count_query)
            affected_count = count_result.scalar() or 0

        if affected_count == 0:
            report = {
                "operation": op_name,
                "strategy": replacement_strategy,
                "column": column_name,
                "data_type": data_type,
                "type_category": type_category,
                "replacement_value": str(validated_value) if validated_value is not None else "NULL",
                "values_replaced": 0,
                "total_values_changed": 0,
            }
            return (
                True,
                f"No missing values found in column '{column_name}'. No values were changed.",
                report,
            )

        # 7. Execute parameterized UPDATE in a transaction
        update_query = text(f"""
            UPDATE {quoted_table}
            SET {quoted_column} = :replacement
            WHERE {where_clause}
            """)

        with engine.begin() as conn:
            conn.execute(
                update_query,
                {"replacement": validated_value},
            )

        # 8. Build structured report
        report = {
            "operation": "Missing Value Cleaning",
            "strategy": replacement_strategy,
            "column": column_name,
            "data_type": data_type,
            "type_category": type_category,
            "replacement_value": str(validated_value) if validated_value is not None else "NULL",
            "values_replaced": affected_count,
            "total_values_changed": affected_count,
        }

        message = (
            f"Successfully replaced {affected_count} missing value(s) in column "
            f"'{column_name}' ({type_category}) with '{validated_value}'."
        )

        return (
            True,
            message,
            report,
        )

    except Exception as e:
        logger.error(
            "Error replacing missing values in '%s.%s' (col: %s): %s",
            database,
            working_table_name,
            column_name,
            str(e),
        )
        return (
            False,
            f"Error during missing value replacement: {str(e)}",
            {},
        )


def to_title_case(s: Optional[str]) -> Optional[str]:
    """
    Capitalize the first letter of each word while strictly preserving
    leading, trailing, and intermediate whitespace characters, empty strings, and NULLs.

    Examples:
        'john doe'       -> 'John Doe'
        '  JOHN DOE  '   -> '  John Doe  '
        'o\\'connor'      -> 'O\\'Connor'
        ''               -> ''
        None             -> None
    """
    if s is None:
        return None
    if not isinstance(s, str) or s == "":
        return s
    return re.sub(r"(?<![a-zA-Z])[a-zA-Z]", lambda m: m.group(0).upper(), s.lower())


def count_text_casing_changes(
    engine,
    database: str,
    working_table_name: str,
    column_name: Any,
    case_type: str,
) -> int:
    """
    Count the number of non-null, non-empty values in column_name (single column or list of columns)
    of working_table_name that will actually change if case_type normalization is applied.
    Does NOT modify any data.
    """
    try:
        if not working_table_name or working_table_name.count(CLEANING_SUFFIX) != 1:
            return 0

        # Support multi-column list/tuple
        if isinstance(column_name, (list, tuple)):
            return sum(
                count_text_casing_changes(
                    engine, database, working_table_name, col, case_type
                )
                for col in column_name
                if isinstance(col, str) and col.strip()
            )

        text_cols = get_text_columns(engine, database, working_table_name)
        if column_name not in text_cols:
            return 0

        quoted_table = _quote_table(database, working_table_name)
        quoted_column = _quote_identifier(column_name)

        norm_case = str(case_type).strip().lower()
        is_mysql = getattr(engine.dialect, "name", "") == "mysql"
        binary_col = f"BINARY {quoted_column}" if is_mysql else quoted_column

        if norm_case in ("lowercase", "lower"):
            query = text(f"""
                SELECT COUNT(*) AS cnt
                FROM {quoted_table}
                WHERE {quoted_column} IS NOT NULL
                  AND {quoted_column} != ''
                  AND {binary_col} != LOWER({quoted_column})
            """)
            with engine.connect() as conn:
                return conn.execute(query).scalar() or 0

        elif norm_case in ("uppercase", "upper"):
            query = text(f"""
                SELECT COUNT(*) AS cnt
                FROM {quoted_table}
                WHERE {quoted_column} IS NOT NULL
                  AND {quoted_column} != ''
                  AND {binary_col} != UPPER({quoted_column})
            """)
            with engine.connect() as conn:
                return conn.execute(query).scalar() or 0

        elif norm_case in ("title case", "titlecase", "title"):
            query = text(f"""
                SELECT {quoted_column} AS val, COUNT(*) AS cnt
                FROM {quoted_table}
                WHERE {quoted_column} IS NOT NULL
                  AND {quoted_column} != ''
                GROUP BY {quoted_column}
            """)
            with engine.connect() as conn:
                result = conn.execute(query)
                total_changed = 0
                for row in result:
                    if hasattr(row, "_mapping"):
                        val = row._mapping["val"]
                        cnt = row._mapping["cnt"]
                    else:
                        val = row[0]
                        cnt = row[1]
                    if val is not None and to_title_case(val) != val:
                        total_changed += cnt or 0
                return total_changed

        return 0

    except Exception as e:
        logger.error(
            "Error counting text casing changes in '%s.%s' (col: %s, case: %s): %s",
            database,
            working_table_name,
            column_name,
            case_type,
            str(e),
        )
        return 0


def normalize_text_case_workspace(
    engine,
    database: str,
    working_table_name: str,
    column_name: Any,
    case_type: str,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Normalize text values to lowercase, uppercase, or title case across one or more
    specified text columns of the cleaning workspace in one go.

    Safety rules:
    - Only tables containing the exact cleaning suffix (__cleaning_) can be modified.
    - Production/source tables are never modified.
    - Column names are validated and quoted safely.
    - All column updates are executed inside a single atomic database transaction.

    Returns:
        (
            success: bool,
            message: str,
            report: dict
        )
    """
    try:
        # 1. Safety validation: Workspace identification
        if not working_table_name or working_table_name.count(CLEANING_SUFFIX) != 1:
            return (
                False,
                "Refusing to clean a table that is not identified as a cleaning workspace.",
                {},
            )

        safe_name = _make_safe_table_name(working_table_name)
        if safe_name != working_table_name:
            return (
                False,
                "Refusing to clean an invalid table identifier.",
                {},
            )

        # 2. Validation: Input arguments (single string or list of strings)
        if isinstance(column_name, str):
            if not column_name.strip():
                return (
                    False,
                    "Column name must be a non-empty string.",
                    {},
                )
            target_cols = [column_name.strip()]
        elif isinstance(column_name, (list, tuple)):
            target_cols = [
                c.strip() for c in column_name if isinstance(c, str) and c.strip()
            ]
            if not target_cols:
                return (
                    False,
                    "Please select at least one non-empty column name.",
                    {},
                )
        else:
            return (
                False,
                "Column name must be a string or list of strings.",
                {},
            )

        norm_case = str(case_type).strip().lower()
        if norm_case in ("lowercase", "lower"):
            canonical_case = "lowercase"
        elif norm_case in ("uppercase", "upper"):
            canonical_case = "UPPERCASE"
        elif norm_case in ("title case", "titlecase", "title"):
            canonical_case = "Title Case"
        else:
            return (
                False,
                f"Invalid case format '{case_type}'. Supported options: lowercase, UPPERCASE, Title Case.",
                {},
            )

        # 3. Validation: Table existence
        inspector = inspect(engine)
        tables = inspector.get_table_names(schema=database)
        if working_table_name not in tables:
            return (
                False,
                f"Working table '{working_table_name}' not found in database '{database}'.",
                {},
            )

        # 4. Validation: Column existence and text type
        column_query = text("""
            SELECT COLUMN_NAME, DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = :database
              AND TABLE_NAME = :table_name
            ORDER BY ORDINAL_POSITION
        """)
        with engine.connect() as conn:
            result = conn.execute(
                column_query,
                {"database": database, "table_name": working_table_name},
            )
            columns = [dict(row._mapping) for row in result]

        col_dict = {
            col["COLUMN_NAME"]: str(col["DATA_TYPE"]).lower() for col in columns
        }

        for col in target_cols:
            if col not in col_dict:
                return (
                    False,
                    f"Column '{col}' not found in table '{working_table_name}'.",
                    {},
                )

            col_type = _normalize_data_type(col_dict[col])
            if col_type not in TEXT_DATA_TYPES:
                return (
                    False,
                    f"Column '{col}' is of type '{col_type}', which is not a supported text/string column.",
                    {},
                )

        quoted_table = _quote_table(database, working_table_name)
        is_mysql = getattr(engine.dialect, "name", "") == "mysql"

        # 5. Count changes and prepare update tasks using engine.connect()
        column_reports = []
        total_values_changed = 0
        col_tasks = []

        with engine.connect() as conn:
            for col in target_cols:
                quoted_column = _quote_identifier(col)
                binary_col = f"BINARY {quoted_column}" if is_mysql else quoted_column

                if canonical_case == "lowercase":
                    where_condition = (
                        f"{quoted_column} IS NOT NULL AND {quoted_column} != '' "
                        f"AND {binary_col} != LOWER({quoted_column})"
                    )
                    count_query = text(
                        f"SELECT COUNT(*) FROM {quoted_table} WHERE {where_condition}"
                    )
                    affected_count = conn.execute(count_query).scalar() or 0

                    if affected_count > 0:
                        update_query = text(f"""
                            UPDATE {quoted_table}
                            SET {quoted_column} = LOWER({quoted_column})
                            WHERE {where_condition}
                        """)
                        col_tasks.append(("sql", update_query, None))

                elif canonical_case == "UPPERCASE":
                    where_condition = (
                        f"{quoted_column} IS NOT NULL AND {quoted_column} != '' "
                        f"AND {binary_col} != UPPER({quoted_column})"
                    )
                    count_query = text(
                        f"SELECT COUNT(*) FROM {quoted_table} WHERE {where_condition}"
                    )
                    affected_count = conn.execute(count_query).scalar() or 0

                    if affected_count > 0:
                        update_query = text(f"""
                            UPDATE {quoted_table}
                            SET {quoted_column} = UPPER({quoted_column})
                            WHERE {where_condition}
                        """)
                        col_tasks.append(("sql", update_query, None))

                else:  # Title Case
                    group_query = text(f"""
                        SELECT {quoted_column} AS val, COUNT(*) AS cnt
                        FROM {quoted_table}
                        WHERE {quoted_column} IS NOT NULL
                          AND {quoted_column} != ''
                        GROUP BY {quoted_column}
                    """)
                    res = conn.execute(group_query)
                    to_update = []
                    affected_count = 0
                    for row in res:
                        if hasattr(row, "_mapping"):
                            val = row._mapping["val"]
                            cnt = row._mapping["cnt"]
                        else:
                            val = row[0]
                            cnt = row[1]
                        if val is not None:
                            new_val = to_title_case(val)
                            if new_val != val:
                                to_update.append((val, new_val))
                                affected_count += cnt or 0

                    if affected_count > 0:
                        where_match = (
                            f"BINARY {quoted_column} = :old_val"
                            if is_mysql
                            else f"{quoted_column} = :old_val"
                        )
                        update_stmt = text(f"""
                            UPDATE {quoted_table}
                            SET {quoted_column} = :new_val
                            WHERE {where_match}
                        """)
                        params = [
                            {"new_val": new_v, "old_val": old_v}
                            for old_v, new_v in to_update
                        ]
                        col_tasks.append(("batch", update_stmt, params))

                total_values_changed += affected_count
                column_reports.append(
                    {
                        "column": col,
                        "values_changed": affected_count,
                    }
                )

        # 6. Build structured report
        report = {
            "operation": "Text Casing",
            "column": (
                target_cols[0] if len(target_cols) == 1 else ", ".join(target_cols)
            ),
            "columns": target_cols,
            "case_type": canonical_case,
            "values_changed": total_values_changed,
            "total_values_changed": total_values_changed,
            "columns_affected": column_reports,
        }

        if total_values_changed == 0:
            if len(target_cols) == 1:
                zero_msg = f"All values in column '{target_cols[0]}' are already {canonical_case}. No values were changed."
            else:
                zero_msg = f"All values across the {len(target_cols)} selected column(s) are already in {canonical_case}. No values were changed."
            return (True, zero_msg, report)

        # 7. Execute updates inside one atomic transaction
        with engine.begin() as conn:
            for task_type, stmt, params in col_tasks:
                if task_type == "sql":
                    conn.execute(stmt)
                elif task_type == "batch":
                    conn.execute(stmt, params)

        if len(target_cols) == 1:
            message = (
                f"Successfully normalized {total_values_changed} value(s) in column "
                f"'{target_cols[0]}' to {canonical_case}."
            )
        else:
            message = (
                f"Successfully normalized {total_values_changed} value(s) across "
                f"{len(target_cols)} column(s) to {canonical_case}."
            )

        return (True, message, report)

    except Exception as e:
        logger.error(
            "Error performing text casing normalization on '%s.%s' (col: %s): %s",
            database,
            working_table_name,
            column_name,
            str(e),
        )
        return (
            False,
            f"Error during text casing normalization: {str(e)}",
            {},
        )


def detect_duplicates_workspace(
    engine,
    database: str,
    working_table_name: str,
    duplicate_keys: Any,
    retention_strategy: str = "Keep First",
    preview_limit: Optional[int] = 100,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Detect duplicate records in a cleaning workspace table based on one or more
    user-selected duplicate key columns without modifying any data.

    Returns structured duplicate groups with individual record identifiers to enable
    per-group record-level decision making.

    Safety:
    - Only tables containing the exact cleaning suffix (__cleaning_) can be inspected.
    - Read-only inspection; original and workspace tables are never modified.

    Returns:
        (
            success: bool,
            message: str,
            report: dict
        )
    """
    try:
        # 1. Safety validation: Workspace identification
        if not working_table_name or working_table_name.count(CLEANING_SUFFIX) != 1:
            return (
                False,
                "Refusing to inspect a table that is not identified as a cleaning workspace.",
                {},
            )

        safe_name = _make_safe_table_name(working_table_name)
        if safe_name != working_table_name:
            return (
                False,
                "Refusing to inspect an invalid table identifier.",
                {},
            )

        # 2. Validation: Duplicate key columns
        if isinstance(duplicate_keys, str):
            keys = [duplicate_keys.strip()] if duplicate_keys.strip() else []
        elif isinstance(duplicate_keys, (list, tuple)):
            keys = [
                k.strip() for k in duplicate_keys if isinstance(k, str) and k.strip()
            ]
        else:
            return (
                False,
                "Duplicate key columns must be a string or list of strings.",
                {},
            )

        if not keys:
            return (
                False,
                "Please select at least one duplicate key column.",
                {},
            )

        # 3. Validation: Retention strategy (ordering direction)
        norm_strat = str(retention_strategy).strip().lower()
        if norm_strat in ("keep first", "first"):
            canonical_strat = "Keep First"
        elif norm_strat in ("keep last", "last"):
            canonical_strat = "Keep Last"
        else:
            return (
                False,
                f"Invalid retention strategy '{retention_strategy}'. Choose 'Keep First' or 'Keep Last'.",
                {},
            )

        # 4. Validation: Table existence
        inspector = inspect(engine)
        tables = inspector.get_table_names(schema=database)
        if working_table_name not in tables:
            return (
                False,
                f"Working table '{working_table_name}' not found in database '{database}'.",
                {},
            )

        # 5. Column metadata and PK inspection
        table_columns_info = inspector.get_columns(working_table_name, schema=database)
        table_col_names = [col["name"] for col in table_columns_info]

        for k in keys:
            if k not in table_col_names:
                return (
                    False,
                    f"Column '{k}' not found in table '{working_table_name}'.",
                    {},
                )

        pk_constraint = (
            inspector.get_pk_constraint(working_table_name, schema=database) or {}
        )
        pk_cols = pk_constraint.get("constrained_columns") or []
        has_pk = bool(pk_cols)

        order_dir = "ASC" if canonical_strat == "Keep First" else "DESC"
        if has_pk:
            order_by_cols = [f"{_quote_identifier(c)} {order_dir}" for c in pk_cols]
            warning = None
        else:
            # Deterministic fallback: order by duplicate keys then remaining table columns
            order_cols = list(keys) + [c for c in table_col_names if c not in keys]
            order_by_cols = [f"{_quote_identifier(c)} {order_dir}" for c in order_cols]
            warning = (
                "Table has no Primary Key. Ordering uses available table columns as fallback; "
                "for completely identical rows, row retention order cannot be strictly guaranteed."
            )

        quoted_table = _quote_table(database, working_table_name)
        grp_by_clause = ", ".join([_quote_identifier(c) for c in keys])

        # 6. Aggregate Duplicate Counts
        summary_query = text(f"""
            SELECT
                COUNT(*) AS dup_groups,
                COALESCE(SUM(cnt), 0) AS dup_rows,
                COALESCE(SUM(cnt - 1), 0) AS rows_to_remove
            FROM (
                SELECT {grp_by_clause}, COUNT(*) AS cnt
                FROM {quoted_table}
                GROUP BY {grp_by_clause}
                HAVING COUNT(*) > 1
            ) AS dup_summary
        """)

        with engine.connect() as conn:
            res = conn.execute(summary_query).first()
            if res is not None:
                if hasattr(res, "_mapping"):
                    dup_groups = int(res._mapping.get("dup_groups") or 0)
                    dup_rows = int(res._mapping.get("dup_rows") or 0)
                    rows_to_remove = int(res._mapping.get("rows_to_remove") or 0)
                else:
                    dup_groups = int(res[0] or 0)
                    dup_rows = int(res[1] or 0)
                    rows_to_remove = int(res[2] or 0)
            else:
                dup_groups = 0
                dup_rows = 0
                rows_to_remove = 0

        # 7. Sample Preview and Group Extraction
        preview_rows = []
        groups_map = {}

        if rows_to_remove > 0 and (preview_limit is None or preview_limit > 0):
            order_by_clause = ", ".join(order_by_cols)
            quoted_cols = ", ".join([_quote_identifier(c) for c in table_col_names])

            limit_clause = (
                "LIMIT :limit"
                if (preview_limit is not None and preview_limit > 0)
                else ""
            )
            query_params = (
                {"limit": preview_limit}
                if (preview_limit is not None and preview_limit > 0)
                else {}
            )

            preview_query = text(f"""
                SELECT * FROM (
                    SELECT {quoted_cols},
                           ROW_NUMBER() OVER (
                               PARTITION BY {grp_by_clause}
                               ORDER BY {order_by_clause}
                           ) AS __rn,
                           COUNT(*) OVER (
                               PARTITION BY {grp_by_clause}
                           ) AS __grp_total
                    FROM {quoted_table}
                ) AS ranked
                WHERE __grp_total > 1
                ORDER BY {grp_by_clause}, __rn ASC
                {limit_clause}
            """)

            with engine.connect() as conn:
                preview_res = conn.execute(preview_query, query_params)
                for row in preview_res:
                    row_map = dict(row._mapping if hasattr(row, "_mapping") else row)
                    rn = row_map.pop("__rn")
                    grp_tot = row_map.pop("__grp_total")

                    # Key tuple for grouping (handles None/NULL and blanks)
                    kt = tuple(row_map.get(k) for k in keys)
                    if kt not in groups_map:
                        grp_idx = len(groups_map) + 1
                        groups_map[kt] = {
                            "group_id": f"group_{grp_idx}",
                            "group_num": grp_idx,
                            "key_values": {k: row_map.get(k) for k in keys},
                            "row_count": grp_tot,
                            "default_keep_id": None,
                            "rows": [],
                        }

                    grp_entry = groups_map[kt]

                    # Unique row identifier
                    if has_pk:
                        if len(pk_cols) == 1:
                            row_id = row_map.get(pk_cols[0])
                            lbl_id = f"{pk_cols[0]}: {row_id}"
                        else:
                            row_id = tuple(row_map.get(c) for c in pk_cols)
                            lbl_id = f"PK: {row_id}"
                    else:
                        row_id = rn
                        lbl_id = f"Row #{rn}"

                    # Secondary identifying columns for label
                    other_ident = []
                    for c in table_col_names:
                        if c not in pk_cols and row_map.get(c) is not None:
                            val_str = str(row_map[c])
                            if len(val_str) > 25:
                                val_str = val_str[:22] + "..."
                            other_ident.append(f"{c}: {val_str}")
                            if len(other_ident) >= 3:
                                break

                    display_label = (
                        f"{lbl_id} ({', '.join(other_ident)})"
                        if other_ident
                        else str(lbl_id)
                    )

                    is_default = rn == 1
                    if is_default and grp_entry["default_keep_id"] is None:
                        grp_entry["default_keep_id"] = row_id

                    grp_entry["rows"].append(
                        {
                            "row_id": row_id,
                            "row_data": dict(row_map),
                            "display_label": display_label,
                            "is_default": is_default,
                            "rank": rn,
                        }
                    )

                    # Maintain backward-compatible preview_rows
                    row_copy = dict(row_map)
                    row_copy["__action"] = "Keep" if rn == 1 else "Remove"
                    row_copy["__rank"] = rn
                    row_copy["__group_id"] = grp_entry["group_id"]
                    preview_rows.append(row_copy)

        report = {
            "duplicate_key_columns": keys,
            "duplicate_group_count": dup_groups,
            "duplicate_row_count": dup_rows,
            "rows_to_remove": rows_to_remove,
            "retention_strategy": canonical_strat,
            "has_primary_key": has_pk,
            "primary_key_columns": pk_cols,
            "warning": warning,
            "groups": list(groups_map.values()),
            "preview_rows": preview_rows,
        }

        if rows_to_remove == 0:
            msg = f"No duplicate records detected using duplicate key ({', '.join(keys)})."
        else:
            msg = (
                f"Detected {dup_groups} duplicate group(s) with {dup_rows} total rows "
                f"({rows_to_remove} row(s) to remove)."
            )

        return (True, msg, report)

    except Exception as e:
        logger.error(
            "Error detecting duplicates in '%s.%s' (keys: %s): %s",
            database,
            working_table_name,
            duplicate_keys,
            str(e),
        )
        return (
            False,
            f"Error detecting duplicates: {str(e)}",
            {},
        )


def remove_duplicates_workspace(
    engine,
    database: str,
    working_table_name: str,
    duplicate_keys: Any,
    keep_selections: Optional[Any] = None,
    retention_strategy: str = "Keep First",
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Remove duplicate records from a cleaning workspace table based on one or more
    user-selected duplicate key columns using an atomic transaction and record-level
    KEEP decisions.

    Safety:
    - Only tables containing the exact cleaning suffix (__cleaning_) can be modified.
    - Production/source tables are never modified.
    - Deletions are executed inside an atomic transaction; automatically rolled back on any error.
    - Preserves exactly one row per duplicate group according to the user's KEEP selections.

    Returns:
        (
            success: bool,
            message: str,
            report: dict
        )
    """
    try:
        # Backward-compatibility: if 5th arg is string, treat it as retention_strategy
        if isinstance(keep_selections, str):
            retention_strategy = keep_selections
            keep_selections = None

        # 1. Safety validation: Workspace identification
        if not working_table_name or working_table_name.count(CLEANING_SUFFIX) != 1:
            return (
                False,
                "Refusing to clean a table that is not identified as a cleaning workspace.",
                {},
            )

        safe_name = _make_safe_table_name(working_table_name)
        if safe_name != working_table_name:
            return (
                False,
                "Refusing to clean an invalid table identifier.",
                {},
            )

        # 2. Recalculate/validate duplicate set immediately before deletion
        detect_ok, detect_msg, detect_report = detect_duplicates_workspace(
            engine,
            database,
            working_table_name,
            duplicate_keys,
            retention_strategy=retention_strategy,
            preview_limit=None,  # Fetch all duplicate groups to validate
        )
        if not detect_ok:
            return (False, detect_msg, {})

        keys = detect_report["duplicate_key_columns"]
        dup_groups_count = detect_report["duplicate_group_count"]
        rows_to_remove = detect_report["rows_to_remove"]
        has_pk = detect_report["has_primary_key"]
        pk_cols = detect_report["primary_key_columns"]
        warning = detect_report["warning"]
        detected_groups = detect_report.get("groups", [])
        quoted_table = _quote_table(database, working_table_name)

        # Initial row count before deletion
        with engine.connect() as conn:
            initial_row_count = (
                conn.execute(text(f"SELECT COUNT(*) FROM {quoted_table}")).scalar() or 0
            )

        # If zero duplicates found, return early without modifying workspace
        if rows_to_remove == 0:
            report = {
                "operation": "Duplicate Removal",
                "duplicate_key_columns": keys,
                "retention_strategy": retention_strategy,
                "rows_removed": 0,
                "duplicate_groups": 0,
                "rows_kept": 0,
                "remaining_rows": initial_row_count,
                "has_primary_key": has_pk,
                "warning": warning,
                "group_decisions": [],
            }
            return (
                True,
                f"No duplicate records found for key ({', '.join(keys)}). Workspace was not modified.",
                report,
            )

        # 3. Validate KEEP selections
        if keep_selections is None:
            # Default to deterministic first row of each group
            keep_selections = {
                g["group_id"]: g["default_keep_id"] for g in detected_groups
            }
        elif not isinstance(keep_selections, dict):
            return (
                False,
                "keep_selections must be a dictionary mapping duplicate groups to selected record IDs.",
                {},
            )

        rows_to_remove_ids = []
        rows_to_keep_ids = []
        group_decisions = []

        for g in detected_groups:
            gid = g["group_id"]
            gnum = g["group_num"]

            # Lookup selection by gid, gnum, or str(gnum)
            sel_val = None
            if gid in keep_selections:
                sel_val = keep_selections[gid]
            elif gnum in keep_selections:
                sel_val = keep_selections[gnum]
            elif str(gnum) in keep_selections:
                sel_val = keep_selections[str(gnum)]

            if sel_val is None:
                return (
                    False,
                    f"Missing KEEP selection for duplicate group #{gnum}.",
                    {},
                )

            # Check for multiple selections in one group
            if has_pk and len(pk_cols) == 1 and isinstance(sel_val, (list, set, tuple)):
                return (
                    False,
                    f"Multiple KEEP selections provided for group #{gnum}. Exactly one record must be kept per group.",
                    {},
                )

            # Match sel_val to one of the rows in this group
            matched_row = None
            for r in g["rows"]:
                if r["row_id"] == sel_val or str(r["row_id"]) == str(sel_val):
                    matched_row = r
                    break

            if matched_row is None:
                return (
                    False,
                    f"Selected KEEP record '{sel_val}' was not found in duplicate group #{gnum}.",
                    {},
                )

            rows_to_keep_ids.append(matched_row["row_id"])
            rem_rows = [r for r in g["rows"] if r is not matched_row]
            for r in rem_rows:
                rows_to_remove_ids.append(r["row_id"])

            group_decisions.append(
                {
                    "group_num": gnum,
                    "group_id": gid,
                    "key_values": g["key_values"],
                    "kept_id": matched_row["row_id"],
                    "kept_label": matched_row.get(
                        "display_label", str(matched_row["row_id"])
                    ),
                    "removed_ids": [r["row_id"] for r in rem_rows],
                    "removed_labels": [
                        r.get("display_label", str(r["row_id"])) for r in rem_rows
                    ],
                    "removed_count": len(rem_rows),
                }
            )

        # 4. Execute deletion inside atomic transaction
        inspector = inspect(engine)
        table_columns_info = inspector.get_columns(working_table_name, schema=database)
        table_col_names = [col["name"] for col in table_columns_info]

        with engine.begin() as conn:
            if has_pk:
                if len(pk_cols) == 1:
                    pk_col_q = _quote_identifier(pk_cols[0])
                    for i in range(0, len(rows_to_remove_ids), 500):
                        chunk = rows_to_remove_ids[i : i + 500]
                        placeholders = ", ".join(
                            [f":p_{idx}" for idx in range(len(chunk))]
                        )
                        params = {f"p_{idx}": val for idx, val in enumerate(chunk)}
                        del_stmt = text(
                            f"DELETE FROM {quoted_table} WHERE {pk_col_q} IN ({placeholders})"
                        )
                        conn.execute(del_stmt, params)
                else:
                    for rem_tuple in rows_to_remove_ids:
                        where_parts = []
                        params = {}
                        for idx, c in enumerate(pk_cols):
                            pkey = f"c_{idx}"
                            where_parts.append(f"{_quote_identifier(c)} = :{pkey}")
                            val = (
                                rem_tuple[idx]
                                if isinstance(rem_tuple, (tuple, list))
                                else rem_tuple[c]
                            )
                            params[pkey] = val
                        del_stmt = text(
                            f"DELETE FROM {quoted_table} WHERE {' AND '.join(where_parts)}"
                        )
                        conn.execute(del_stmt, params)

            else:
                # Case B: Table has NO Primary Key
                # Deterministic fallback temporary table deduplication
                order_cols = list(keys) + [c for c in table_col_names if c not in keys]
                order_by_clause = ", ".join(
                    [f"{_quote_identifier(c)} ASC" for c in order_cols]
                )
                quoted_cols = ", ".join([_quote_identifier(c) for c in table_col_names])
                grp_by_clause = ", ".join([_quote_identifier(c) for c in keys])

                is_mysql = getattr(engine.dialect, "name", "") == "mysql"
                temp_tbl_name = f"_tmp_dedup_{uuid.uuid4().hex[:8]}"
                temp_tbl_quoted = _quote_identifier(temp_tbl_name)

                create_kw = (
                    "CREATE TEMPORARY TABLE" if is_mysql else "CREATE TEMP TABLE"
                )
                drop_kw = "DROP TEMPORARY TABLE" if is_mysql else "DROP TABLE"

                # 1. Isolate the rows to keep in temporary table
                conn.execute(text(f"""
                    {create_kw} {temp_tbl_quoted} AS
                    SELECT {quoted_cols}
                    FROM (
                        SELECT {quoted_cols},
                               ROW_NUMBER() OVER (
                                   PARTITION BY {grp_by_clause}
                                   ORDER BY {order_by_clause}
                               ) AS __rn
                        FROM {quoted_table}
                    ) AS __sub
                    WHERE __rn = 1
                """))

                # 2. Clear current workspace table
                conn.execute(text(f"DELETE FROM {quoted_table}"))

                # 3. Re-populate workspace with deduplicated records
                conn.execute(text(f"""
                    INSERT INTO {quoted_table} ({quoted_cols})
                    SELECT {quoted_cols} FROM {temp_tbl_quoted}
                """))

                # 4. Cleanup temporary table
                conn.execute(text(f"{drop_kw} {temp_tbl_quoted}"))

            # 5. Verify post-deletion row count
            final_row_count = (
                conn.execute(text(f"SELECT COUNT(*) FROM {quoted_table}")).scalar() or 0
            )

            actual_removed = initial_row_count - final_row_count
            expected_removed = len(rows_to_remove_ids) if has_pk else rows_to_remove

            if actual_removed != expected_removed:
                raise RuntimeError(
                    f"Row count mismatch: expected to remove {expected_removed} duplicate row(s), "
                    f"but {actual_removed} row(s) were removed. Transaction aborted."
                )

        report = {
            "operation": "Duplicate Removal",
            "duplicate_key_columns": keys,
            "retention_strategy": retention_strategy,
            "rows_removed": actual_removed,
            "duplicate_groups": len(detected_groups),
            "rows_kept": len(detected_groups),
            "remaining_rows": final_row_count,
            "has_primary_key": has_pk,
            "warning": warning,
            "group_decisions": group_decisions,
        }

        message = (
            f"Successfully removed {actual_removed} duplicate row(s) across "
            f"{len(detected_groups)} group(s)."
        )
        return (True, message, report)

    except Exception as e:
        logger.error(
            "Error removing duplicates in '%s.%s' (keys: %s): %s",
            database,
            working_table_name,
            duplicate_keys,
            str(e),
        )
        return (
            False,
            f"Error removing duplicates: {str(e)}",
            {},
        )


def remove_duplicates_by_row_ids(
    engine,
    database: str,
    working_table_name: str,
    duplicate_keys: Any,
    row_actions: Dict[Any, str],
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Remove duplicate records from a cleaning workspace using explicit per-row
    KEEP / REMOVE decisions supplied by the user.

    Unlike remove_duplicates_workspace(), this function:
    - Accepts a flat dict mapping row_id -> "KEEP" or "REMOVE" for every
      duplicate row.
    - Deletes ONLY the rows explicitly marked "REMOVE".
    - Does NOT enforce exactly one KEEP per duplicate group; users may mark
      multiple rows KEEP or multiple rows REMOVE inside a single group.
    - Source table is never modified.
    - Deletion is atomic: wrapped in a single BEGIN/COMMIT transaction; any
      error triggers automatic rollback.

    Args:
        engine:              SQLAlchemy engine bound to the workspace database.
        database:            Database name.
        working_table_name:  Workspace table name (must contain CLEANING_SUFFIX).
        duplicate_keys:      Column(s) used to detect duplicate groups (used only
                             for the audit report; detection is NOT re-run here).
        row_actions:         Dict mapping row_id (PK value or rank int for no-PK
                             tables) -> "KEEP" or "REMOVE".

    Returns:
        (success: bool, message: str, report: dict)
    """
    try:
        # 1. Safety validation
        if not working_table_name or working_table_name.count(CLEANING_SUFFIX) != 1:
            return (
                False,
                "Refusing to clean a table that is not identified as a cleaning workspace.",
                {},
            )

        safe_name = _make_safe_table_name(working_table_name)
        if safe_name != working_table_name:
            return (
                False,
                "Refusing to clean an invalid table identifier.",
                {},
            )

        if not isinstance(row_actions, dict):
            return (
                False,
                "row_actions must be a dict mapping row_id -> 'KEEP' or 'REMOVE'.",
                {},
            )

        # Normalise string values
        normalised_actions: Dict[Any, str] = {}
        for rid, action in row_actions.items():
            a = str(action).strip().upper()
            if a not in ("KEEP", "REMOVE"):
                return (
                    False,
                    f"Invalid action '{action}' for row_id '{rid}'. Use 'KEEP' or 'REMOVE'.",
                    {},
                )
            normalised_actions[rid] = a

        # 2. Resolve rows to delete
        remove_ids = [rid for rid, act in normalised_actions.items() if act == "REMOVE"]
        keep_ids = [rid for rid, act in normalised_actions.items() if act == "KEEP"]

        quoted_table = _quote_table(database, working_table_name)

        # 3. Inspect table metadata
        inspector = inspect(engine)

        tables = inspector.get_table_names(schema=database)
        if working_table_name not in tables:
            return (
                False,
                f"Working table '{working_table_name}' not found in database '{database}'.",
                {},
            )

        table_columns_info = inspector.get_columns(working_table_name, schema=database)
        table_col_names = [col["name"] for col in table_columns_info]

        pk_constraint = (
            inspector.get_pk_constraint(working_table_name, schema=database) or {}
        )
        pk_cols = pk_constraint.get("constrained_columns") or []
        has_pk = bool(pk_cols)

        # 4. Normalise key columns for report
        if isinstance(duplicate_keys, str):
            keys = [duplicate_keys.strip()] if duplicate_keys.strip() else []
        elif isinstance(duplicate_keys, (list, tuple)):
            keys = [
                k.strip() for k in duplicate_keys if isinstance(k, str) and k.strip()
            ]
        else:
            keys = []

        # 5. Capture initial row count
        with engine.connect() as conn:
            initial_row_count = (
                conn.execute(text(f"SELECT COUNT(*) FROM {quoted_table}")).scalar() or 0
            )

        if not remove_ids:
            report = {
                "operation": "Duplicate Removal (Row-Level)",
                "duplicate_key_columns": keys,
                "rows_removed": 0,
                "rows_kept": len(keep_ids),
                "remaining_rows": initial_row_count,
                "has_primary_key": has_pk,
                "row_actions": normalised_actions,
                "group_decisions": [],
            }
            return (
                True,
                "No rows were marked REMOVE. Workspace was not modified.",
                report,
            )

        # 6. Delete rows marked REMOVE inside an atomic transaction
        with engine.begin() as conn:
            if has_pk:
                if len(pk_cols) == 1:
                    pk_col_q = _quote_identifier(pk_cols[0])
                    for i in range(0, len(remove_ids), 500):
                        chunk = remove_ids[i : i + 500]
                        placeholders = ", ".join(
                            [f":p_{idx}" for idx in range(len(chunk))]
                        )
                        params = {f"p_{idx}": val for idx, val in enumerate(chunk)}
                        del_stmt = text(
                            f"DELETE FROM {quoted_table} WHERE {pk_col_q} IN ({placeholders})"
                        )
                        conn.execute(del_stmt, params)
                else:
                    # Composite PK: each remove_id is a tuple/dict
                    for rem_rid in remove_ids:
                        where_parts = []
                        params: Dict[str, Any] = {}
                        for idx, c in enumerate(pk_cols):
                            pkey = f"c_{idx}"
                            where_parts.append(f"{_quote_identifier(c)} = :{pkey}")
                            val = (
                                rem_rid[idx]
                                if isinstance(rem_rid, (tuple, list))
                                else rem_rid[c]
                            )
                            params[pkey] = val
                        del_stmt = text(
                            f"DELETE FROM {quoted_table} WHERE {' AND '.join(where_parts)}"
                        )
                        conn.execute(del_stmt, params)
            else:
                # No PK: use a temporary-table approach, keeping rows NOT in remove set.
                # Since there is no PK, we cannot target individual rows by ID.
                # row_actions keys are rank integers (__rn from detection query).
                # Rebuild the deduplication by keeping only rows whose rank is NOT
                # in the REMOVE set.
                remove_ranks = set(remove_ids)  # ranks to remove

                # Re-fetch all duplicate rows with ranks so we can map rank -> row data
                grp_by_clause = ", ".join([_quote_identifier(c) for c in keys])
                quoted_cols_all = ", ".join(
                    [_quote_identifier(c) for c in table_col_names]
                )
                order_cols = list(keys) + [c for c in table_col_names if c not in keys]
                order_by_clause = ", ".join(
                    [f"{_quote_identifier(c)} ASC" for c in order_cols]
                )

                is_mysql = getattr(engine.dialect, "name", "") == "mysql"
                temp_tbl_name = f"_tmp_dedup_{uuid.uuid4().hex[:8]}"
                temp_tbl_quoted = _quote_identifier(temp_tbl_name)
                create_kw = (
                    "CREATE TEMPORARY TABLE" if is_mysql else "CREATE TEMP TABLE"
                )
                drop_kw = "DROP TEMPORARY TABLE" if is_mysql else "DROP TABLE"

                # Build keep-ranks filter (only needed if remove_ranks is a subset)
                # Strategy: keep all rows except those at the remove ranks WITHIN duplicate groups.
                # Use ROW_NUMBER partitioned by duplicate key; delete rows at those ranks.
                conn.execute(text(f"""
                    {create_kw} {temp_tbl_quoted} AS
                    SELECT {quoted_cols_all}
                    FROM (
                        SELECT {quoted_cols_all},
                               ROW_NUMBER() OVER (
                                   PARTITION BY {grp_by_clause}
                                   ORDER BY {order_by_clause}
                               ) AS __rn,
                               COUNT(*) OVER (
                                   PARTITION BY {grp_by_clause}
                               ) AS __grp_total
                        FROM {quoted_table}
                    ) AS __sub
                    WHERE __grp_total > 1 AND __rn NOT IN ({', '.join(str(r) for r in sorted(remove_ranks))})
                """))

                # Also fetch all non-duplicate rows to preserve
                conn.execute(text(f"""
                    INSERT INTO {temp_tbl_quoted} ({quoted_cols_all})
                    SELECT {quoted_cols_all}
                    FROM (
                        SELECT {quoted_cols_all},
                               COUNT(*) OVER (
                                   PARTITION BY {grp_by_clause}
                               ) AS __grp_total
                        FROM {quoted_table}
                    ) AS __sub2
                    WHERE __grp_total = 1
                """))

                conn.execute(text(f"DELETE FROM {quoted_table}"))
                conn.execute(text(f"""
                    INSERT INTO {quoted_table} ({quoted_cols_all})
                    SELECT {quoted_cols_all} FROM {temp_tbl_quoted}
                """))
                conn.execute(text(f"{drop_kw} {temp_tbl_quoted}"))

            # 7. Verify counts
            final_row_count = (
                conn.execute(text(f"SELECT COUNT(*) FROM {quoted_table}")).scalar() or 0
            )
            actual_removed = initial_row_count - final_row_count

        report = {
            "operation": "Duplicate Removal (Row-Level)",
            "duplicate_key_columns": keys,
            "rows_removed": actual_removed,
            "rows_kept": len(keep_ids),
            "remaining_rows": final_row_count,
            "has_primary_key": has_pk,
            "row_actions": normalised_actions,
            "group_decisions": [],  # Populated by caller for per-group summary
        }

        message = (
            f"Successfully removed {actual_removed} duplicate row(s). "
            f"{len(keep_ids)} row(s) kept."
        )
        return (True, message, report)

    except Exception as e:
        logger.error(
            "Error in remove_duplicates_by_row_ids for '%s.%s': %s",
            database,
            working_table_name,
            str(e),
        )
        return (
            False,
            f"Error removing duplicates: {str(e)}",
            {},
        )


def init_duplicate_row_actions(
    groups: List[Dict[str, Any]],
) -> Dict[Any, str]:
    """
    Initialize duplicate row actions with automatic REMOVE behavior:
    The first record in each duplicate group is set to 'KEEP'.
    All other records in that same duplicate group are automatically set to 'REMOVE'.
    """
    actions: Dict[Any, str] = {}
    for g in groups:
        rows = g.get("rows", [])
        for idx, r in enumerate(rows):
            rid = r["row_id"]
            actions[rid] = "KEEP" if idx == 0 else "REMOVE"
    return actions


def set_group_row_action(
    row_actions: Dict[Any, str],
    group_rows: List[Dict[str, Any]],
    target_row_id: Any,
    new_action: str,
    auto_remove_others: bool = True,
) -> Dict[Any, str]:
    """
    Update a row's KEEP/REMOVE action.

    If auto_remove_others is True and new_action == 'KEEP':
        Automatically marks all OTHER rows in that same duplicate group as 'REMOVE'.
    Otherwise (auto_remove_others is False):
        Updates only target_row_id, allowing multiple KEEP records within the group.
    """
    act = str(new_action).strip().upper()
    if act not in ("KEEP", "REMOVE"):
        raise ValueError(f"Invalid action '{new_action}'. Must be 'KEEP' or 'REMOVE'.")

    updated = dict(row_actions)
    updated[target_row_id] = act

    if auto_remove_others and act == "KEEP":
        for r in group_rows:
            rid = r["row_id"]
            if rid != target_row_id:
                updated[rid] = "REMOVE"

    return updated


def apply_select_all_action(
    row_actions: Dict[Any, str],
    group_row_ids: List[Any],
    select_all: bool,
) -> Dict[Any, str]:
    """
    Apply 'Select All' checkbox action to a duplicate group:
    - If select_all is True: marks ALL rows in group_row_ids as 'REMOVE'.
    - If select_all is False: marks ALL rows in group_row_ids as 'KEEP'.
    - Does not modify rows in other duplicate groups.
    """
    updated = dict(row_actions)
    new_action = "REMOVE" if select_all else "KEEP"
    for rid in group_row_ids:
        updated[rid] = new_action
    return updated


def toggle_row_remove_action(
    row_actions: Dict[Any, str],
    target_row_id: Any,
    is_remove: bool,
) -> Dict[Any, str]:
    """
    Toggle an individual row's checkbox:
    - is_remove == True  -> 'REMOVE'
    - is_remove == False -> 'KEEP'
    - Strictly preserves all other rows without modification.
    """
    updated = dict(row_actions)
    updated[target_row_id] = "REMOVE" if is_remove else "KEEP"
    return updated


def is_group_all_removed(
    row_actions: Dict[Any, str],
    group_row_ids: List[Any],
) -> bool:
    """
    Check if all rows in a duplicate group are marked 'REMOVE'.
    Used to keep the group-level 'Select All' checkbox in sync.
    """
    if not group_row_ids:
        return False
    return all(row_actions.get(rid) == "REMOVE" for rid in group_row_ids)


def format_row_compact_summary(
    row_data: Dict[str, Any],
    pk_cols: Optional[List[str]] = None,
    duplicate_keys: Optional[List[str]] = None,
) -> str:
    """
    Build a compact identifying summary for a duplicate row:
    e.g. 'order_id: 8 | Pooja More | pooja@gmail.com'
    """
    parts = []
    used_cols = set()

    # 1. Primary key column(s) first
    if pk_cols:
        for pk in pk_cols:
            if pk in row_data:
                val = row_data[pk]
                parts.append(f"{pk}: {val}")
                used_cols.add(pk)

    # 2. Duplicate key columns (if not already included in PK)
    if duplicate_keys:
        for k in duplicate_keys:
            if k not in used_cols and k in row_data:
                val = row_data[k]
                val_str = str(val) if val is not None else "NULL"
                parts.append(val_str)
                used_cols.add(k)

    # 3. Add other identifying non-null columns if we have fewer than 3 parts
    for col, val in row_data.items():
        if col not in used_cols and val is not None and str(val).strip():
            val_str = str(val)
            if len(val_str) > 30:
                val_str = val_str[:27] + "..."
            parts.append(val_str)
            used_cols.add(col)
            if len(parts) >= 3:
                break

    if not parts:
        for col, val in list(row_data.items())[:3]:
            parts.append(f"{col}: {val}")

    return " | ".join(parts)


# ============================================================
# RULE-BASED ADVANCED DATE DETECTION & TRANSFORMATION
# ============================================================

DEFAULT_RULE_SAMPLE_PCT = 0.75
DEFAULT_RULE_MAX_SAMPLE = 1000
DEFAULT_RULE_THRESHOLD = 0.80


def _get_pk_column(engine, database: str, table_name: str) -> Optional[str]:
    """Get primary key column name for a table."""
    try:
        inspector = inspect(engine)
        pk_constraint = inspector.get_pk_constraint(table_name, schema=database)
        pk_cols = pk_constraint.get("constrained_columns") or []
        return pk_cols[0] if pk_cols else None
    except Exception:
        return None


def detect_date_columns_rule_based(
    engine,
    database: str,
    table_name: str,
    sample_pct: float = DEFAULT_RULE_SAMPLE_PCT,
    max_sample: int = DEFAULT_RULE_MAX_SAMPLE,
    threshold: float = DEFAULT_RULE_THRESHOLD,
) -> List[Dict[str, Any]]:
    """
    Rule-based date column detection for text/varchar columns.
    
    Scans up to max_sample rows (or sample_pct of total) per column and applies
    date parsing rules. Returns columns where parseable% >= threshold.
    """
    try:
        text_cols = get_text_columns(engine, database, table_name)
        if not text_cols:
            return []
        
        quoted_table = _quote_table(database, table_name)
        pk_col = _get_pk_column(engine, database, table_name)
        pk_select = f", {_quote_identifier(pk_col)}" if pk_col else ""
        
        results = []
        
        with engine.connect() as conn:
            for col in text_cols:
                quoted_col = _quote_identifier(col)
                
                count_query = text(f"SELECT COUNT(*) FROM {quoted_table} WHERE {quoted_col} IS NOT NULL AND TRIM({quoted_col}) != ''")
                total_count = conn.execute(count_query).scalar() or 0
                
                if total_count == 0:
                    continue
                
                sample_size = min(max_sample, int(total_count * sample_pct))
                
                sample_query = text(f"""
                    SELECT {quoted_col} as val{pk_select}
                    FROM {quoted_table}
                    WHERE {quoted_col} IS NOT NULL AND TRIM({quoted_col}) != ''
                    LIMIT {sample_size}
                """)
                sample_result = conn.execute(sample_query)
                values = [(str(row._mapping.get(pk_col, i)) if pk_col else str(i), row._mapping["val"]) 
                          for i, row in enumerate(sample_result)]
                
                if not values:
                    continue
                
                from src.date_rules import analyze_column
                analysis = analyze_column(values)
                analysis.column = col
                
                parseable_pct = analysis.rule_coverage * 100
                
                if parseable_pct < threshold * 100:
                    continue
                
                format_dist = analysis.format_distribution
                sorted_formats = sorted(format_dist.items(), key=lambda x: x[1], reverse=True)
                dominant_formats = [
                    {"format": fmt, "count": cnt, "percentage": round(cnt / sum(format_dist.values()) * 100, 1)}
                    for fmt, cnt in sorted_formats[:5]
                ]
                
                ambiguous_count = len(analysis.escalation_candidates)
                unambiguous_count = len([r for r in analysis.parse_results if r.status == "RESOLVED"])
                
                if parseable_pct >= 95 and ambiguous_count == 0:
                    recommendation = "high_confidence"
                elif parseable_pct >= 80 and ambiguous_count / analysis.sample_size < 0.1:
                    recommendation = "mostly_unambiguous"
                elif len([f for f, c in format_dist.items() if c / analysis.sample_size > 0.1]) > 1:
                    recommendation = "mixed_formats"
                elif ambiguous_count / analysis.sample_size > 0.3:
                    recommendation = "highly_ambiguous"
                else:
                    recommendation = "needs_review"
                
                results.append({
                    "column": col,
                    "data_type": "text/varchar",
                    "sample_size": analysis.sample_size,
                    "parseable_count": len([r for r in analysis.parse_results if r.status == "RESOLVED"]),
                    "parseable_pct": round(parseable_pct, 1),
                    "dominant_formats": dominant_formats,
                    "ambiguous_count": ambiguous_count,
                    "unambiguous_count": unambiguous_count,
                    "two_digit_year_samples": [
                        {"value": r.original, "format": r.format, "parsed_year": r.parsed.year if r.parsed else None,
                         "resolved_year": r.parsed.year if r.parsed else None}
                        for r in analysis.parse_results 
                        if r.parsed and r.parsed.year < 2000 and r.format.endswith("YY")
                    ][:5],
                    "unparseable_samples": [r.original for r in analysis.invalid_records + analysis.non_date_records][:5],
                    "sample_values": [
                        {"original": r.original, "matched_formats": [r.format], "primary_format": r.format}
                        for r in analysis.parse_results[:10]
                    ],
                    "recommendation": recommendation,
                    "confidence": round(analysis.rule_coverage * 100, 1),
                    "mixed_format": len(format_dist) > 1 and any(c / analysis.sample_size > 0.1 for c in format_dist.values()),
                    "column_format": analysis.column_format,
                    "pivot_year": analysis.pivot_year,
                    "rule_coverage": round(analysis.rule_coverage * 100, 1),
                })
        
        return results
    
    except Exception as e:
        logger.error(
            "Error in rule-based date detection for '%s': %s",
            table_name,
            str(e),
        )
        return []


def analyze_column_date_formats_rule_based(
    engine,
    database: str,
    table_name: str,
    column: str,
    sample_pct: float = DEFAULT_RULE_SAMPLE_PCT,
    max_sample: int = DEFAULT_RULE_MAX_SAMPLE,
) -> Dict[str, Any]:
    """
    Deep rule-based analysis of a single column for date transformation.
    """
    try:
        quoted_table = _quote_table(database, table_name)
        quoted_col = _quote_identifier(column)
        pk_col = _get_pk_column(engine, database, table_name)
        pk_select = f", {_quote_identifier(pk_col)}" if pk_col else ""
        
        with engine.connect() as conn:
            count_query = text(f"SELECT COUNT(*) FROM {quoted_table} WHERE {quoted_col} IS NOT NULL AND TRIM({quoted_col}) != ''")
            total_count = conn.execute(count_query).scalar() or 0
            
            if total_count == 0:
                return {
                    "column": column,
                    "total_values": 0,
                    "format_distribution": {},
                    "ambiguity_matrix": {},
                    "unambiguous_values": [],
                    "ambiguous_values": [],
                    "two_digit_year_analysis": [],
                    "row_preview": [],
                    "unparseable_categories": {"nulls": 0, "blanks": 0, "garbage": []},
                    "detected_formats": [],
                    "mixed_format": False,
                    "column_recommendation": {},
                }
            
            sample_size = min(max_sample, int(total_count * sample_pct))
            
            sample_query = text(f"""
                SELECT {quoted_col} as val{pk_select}
                FROM {quoted_table}
                WHERE {quoted_col} IS NOT NULL AND TRIM({quoted_col}) != ''
                LIMIT {sample_size}
            """)
            sample_result = conn.execute(sample_query)
            values = [(str(row._mapping.get(pk_col, i)) if pk_col else str(i), row._mapping["val"]) 
                      for i, row in enumerate(sample_result)]
        
        from src.date_rules import analyze_column, transform_value
        analysis = analyze_column(values)
        analysis.column = column
        
        format_dist = analysis.format_distribution
        sorted_formats = sorted(format_dist.items(), key=lambda x: x[1], reverse=True)
        
        null_query = text(f"SELECT COUNT(*) FROM {quoted_table} WHERE {quoted_col} IS NULL")
        blank_query = text(f"SELECT COUNT(*) FROM {quoted_table} WHERE {quoted_col} IS NOT NULL AND TRIM({quoted_col}) = ''")
        
        with engine.connect() as conn:
            nulls = conn.execute(null_query).scalar() or 0
            blanks = conn.execute(blank_query).scalar() or 0
        
        return {
            "column": column,
            "total_values": analysis.sample_size,
            "format_distribution": format_dist,
            "ambiguity_matrix": {r.original: [r.format] for r in analysis.escalation_candidates},
            "unambiguous_values": [
                {"value": r.original, "format": r.format, "parsed": r.parsed.strftime("%Y-%m-%d") if r.parsed else None}
                for r in analysis.parse_results if r.status == "RESOLVED"
            ],
            "ambiguous_values": [
                {"value": r.original, "interpretations": [{"format": r.format, "description": r.reasoning}], 
                 "confidence": round(r.confidence * 100, 1)}
                for r in analysis.escalation_candidates
            ],
            "two_digit_year_analysis": [
                {"original": r.original, "format": r.format, "parsed_2digit_year": r.parsed.year % 100 if r.parsed else None,
                 "resolved_year": r.parsed.year if r.parsed else None, "full_parsed": r.parsed.strftime("%Y-%m-%d") if r.parsed else None}
                for r in analysis.parse_results if r.parsed and r.parsed.year < 2000 and r.format.endswith("YY")
            ][:20],
            "row_preview": [
                {"original": r.original, "parsed": r.parsed.strftime("%Y-%m-%d") if r.parsed else None,
                 "matched_formats": [r.format], "is_ambiguous": r.status == "ESCALATE",
                 "suggested_format": r.format, "confidence": round(r.confidence * 100, 1)}
                for r in analysis.parse_results[:50]
            ],
            "unparseable_categories": {
                "nulls": nulls,
                "blanks": blanks,
                "garbage": [r.original for r in analysis.invalid_records + analysis.non_date_records][:20],
            },
            "detected_formats": sorted_formats,
            "mixed_format": len(format_dist) > 1 and any(c / analysis.sample_size > 0.1 for c in format_dist.values()),
            "column_recommendation": {
                "format": analysis.column_format,
                "pivot": analysis.pivot_year,
                "confidence": round(analysis.rule_coverage * 100, 1),
                "rules_used": list(set(r.rule_matched for r in analysis.parse_results if r.rule_matched)),
            },
        }
    
    except Exception as e:
        logger.error(
            "Error in rule-based column analysis for '%s.%s': %s",
            database,
            table_name,
            str(e),
        )
        return {}


def transform_advanced_date_column_rule_based(
    engine,
    database: str,
    working_table_name: str,
    column: str,
    target_format: str,
    column_analysis: Dict[str, Any],
    two_digit_pivot: int = 50,
    preserve_time: bool = False,
    new_column_name: str = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Transform a text/varchar column containing dates using rule-based decisions.
    """
    try:
        if not working_table_name or working_table_name.count(CLEANING_SUFFIX) != 1:
            return (
                False,
                "Refusing to modify a table that is not identified as a cleaning workspace.",
                {},
            )
        
        safe_name = _make_safe_table_name(working_table_name)
        if safe_name != working_table_name:
            return (
                False,
                "Refusing to modify an invalid table identifier.",
                {},
            )
        
        if target_format not in ADVANCED_FORMAT_MAP:
            return (
                False,
                f"Invalid target format '{target_format}'.",
                {},
            )
        
        inspector = inspect(engine)
        tables = inspector.get_table_names(schema=database)
        if working_table_name not in tables:
            return (
                False,
                f"Working table '{working_table_name}' not found in database '{database}'.",
                {},
            )
        
        table_columns_info = inspector.get_columns(working_table_name, schema=database)
        col_info = next((c for c in table_columns_info if c["name"] == column), None)
        
        if not col_info:
            return (
                False,
                f"Column '{column}' not found in table '{working_table_name}'.",
                {},
            )
        
        data_type = _normalize_data_type(col_info.get("type", ""))
        if data_type not in TEXT_DATA_TYPES:
            return (
                False,
                f"Column '{column}' is not a text/varchar type (found: {data_type}).",
                {},
            )
        
        quoted_table = _quote_table(database, working_table_name)
        quoted_col = _quote_identifier(column)
        
        if new_column_name is None:
            new_column_name = f"{column}_formatted"
        quoted_new_col = _quote_identifier(new_column_name)
        
        col_names = [c["name"] for c in table_columns_info]
        if new_column_name not in col_names:
            target_col_type = "VARCHAR(30)" if preserve_time else "VARCHAR(20)"
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_new_col} {target_col_type}"))
        
        # Build list of source formats from detected distribution (most frequent first)
        format_dist = column_analysis.get("format_distribution", {})
        sorted_formats = sorted(format_dist.items(), key=lambda x: x[1], reverse=True)
        source_fmts = [ADVANCED_FORMAT_MAP[fmt] for fmt, _ in sorted_formats if fmt in ADVANCED_FORMAT_MAP]
        if not source_fmts:
            source_fmts = ["%d/%m/%Y"]
        # Ensure common fallback formats are present
        common_fallbacks = ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d"]
        for fb in common_fallbacks:
            if fb not in source_fmts:
                source_fmts.append(fb)
        # Add separator variants (slash <-> dash <-> dot) for each format
        expanded_fmts = []
        for fmt in source_fmts:
            variants = {fmt,
                        fmt.replace('-', '/'),
                        fmt.replace('/', '-'),
                        fmt.replace('.', '/'),
                        fmt.replace('/', '.'),
                        fmt.replace('-', '.'),
                        fmt.replace('.', '-')}
            expanded_fmts.extend(v for v in variants if v not in expanded_fmts)
        source_fmts = expanded_fmts
        target_fmt = ADVANCED_FORMAT_MAP[target_format]
        
        # Split formats into four-digit-year (%Y) and two-digit-year (%y only) groups
        four_digit_fmts = [f for f in source_fmts if '%Y' in f and ('%y' not in f)]
        two_digit_fmts = [f for f in source_fmts if '%y' in f and '%Y' not in f]
        
        # Ensure common fallbacks for four-digit
        four_digit_fallbacks = ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d"]
        for fb in four_digit_fallbacks:
            if fb not in four_digit_fmts:
                four_digit_fmts.append(fb)
        # Add separator variants for four-digit
        expanded_four = []
        for fmt in four_digit_fmts:
            variants = {fmt,
                        fmt.replace('-', '/'),
                        fmt.replace('/', '-'),
                        fmt.replace('.', '/'),
                        fmt.replace('/', '.'),
                        fmt.replace('-', '.'),
                        fmt.replace('.', '-')}
            expanded_four.extend(v for v in variants if v not in expanded_four)
        four_digit_fmts = expanded_four
        
        # Separator variants for two-digit
        expanded_two = []
        for fmt in two_digit_fmts:
            variants = {fmt,
                        fmt.replace('-', '/'),
                        fmt.replace('/', '-'),
                        fmt.replace('.', '/'),
                        fmt.replace('/', '.'),
                        fmt.replace('-', '.'),
                        fmt.replace('.', '-')}
            expanded_two.extend(v for v in variants if v not in expanded_two)
        two_digit_fmts = expanded_two
        
        target_fmt = ADVANCED_FORMAT_MAP[target_format]
        
        # Handle preserve_time: if not preserving time, strip time part from target format
        if not preserve_time and ("%H" in target_fmt or "%M" in target_fmt or "%S" in target_fmt):
            # Strip time components (after space)
            mysql_target_fmt = target_fmt.split()[0].replace("%", "%%") if " " in target_fmt else target_fmt.replace("%", "%%")
        else:
            mysql_target_fmt = target_fmt.replace("%", "%%")
        
        # Helper to run a pass using CASE ... WHEN REGEXP ... THEN STR_TO_DATE ... END
        def run_pass(conn, fmt_list):
            """fmt_list = list of Python-format strings like '%d/%m/%Y'."""
            case_parts = []
            for fmt in fmt_list:
                mysql_fmt = fmt.replace("%", "%%")
                regex = _fmt_to_regex(fmt).replace("%", "%%")
                case_parts.append(
                    f"WHEN {quoted_col} REGEXP '{regex}' THEN STR_TO_DATE({quoted_col}, '{mysql_fmt}')"
                )
            case_expr = "CASE " + " ".join(case_parts) + " ELSE NULL END"

            where_clause = (
                f"WHERE {quoted_col} IS NOT NULL "
                f"  AND TRIM({quoted_col}) != '' "
                f"  AND {quoted_new_col} IS NULL "
                f"  AND {case_expr} IS NOT NULL"
            )
            upd = text(f"""
                UPDATE {quoted_table}
                SET {quoted_new_col} = DATE_FORMAT({case_expr}, :target_fmt)
                {where_clause}
            """)
            res = conn.execute(upd, {"target_fmt": mysql_target_fmt})
            return res.rowcount
        
        rows_pass1 = 0
        rows_pass2 = 0
        
        with engine.begin() as conn:
            # Pass 1: four-digit year formats
            if four_digit_fmts:
                rows_pass1 = run_pass(conn, four_digit_fmts)
            
            # Pass 2: two-digit year formats (only rows still NULL)
            if two_digit_fmts:
                rows_pass2 = run_pass(conn, two_digit_fmts)
            
            # Count totals
            count_query = text(f"""
                SELECT COUNT(*) FROM {quoted_table}
                WHERE {quoted_col} IS NOT NULL AND TRIM({quoted_col}) != ''
            """)
            total_rows = conn.execute(count_query).scalar() or 0
            
            # Count failed (still NULL after both passes)
            failed_query = text(f"""
                SELECT COUNT(*) FROM {quoted_table}
                WHERE {quoted_col} IS NOT NULL 
                  AND TRIM({quoted_col}) != ''
                  AND {quoted_new_col} IS NULL
            """)
            failed_rows = conn.execute(failed_query).scalar() or 0
        
        rows_updated = rows_pass1 + rows_pass2
        
        message = (
            f"Rule-based date transformation applied to column '{column}'. "
            f"{rows_updated:,} of {total_rows:,} values formatted as {target_format} "
            f"into column '{new_column_name}' (Pass1 4-digit: {rows_pass1:,}, Pass2 2-digit: {rows_pass2:,})."
        )
        if failed_rows > 0:
            message += f" {failed_rows:,} values could not be parsed."
        
        report = {
            "operation": "Rule-Based Advanced Date Transformation",
            "source_column": column,
            "target_column": new_column_name,
            "source_format": "mixed (4-digit + 2-digit)",
            "target_format": target_format,
            "two_digit_pivot": two_digit_pivot,
            "preserve_time": preserve_time,
            "total_rows": total_rows,
            "rows_transformed": rows_updated,
            "rows_pass1": rows_pass1,
            "rows_pass2": rows_pass2,
            "exceptions": failed_rows,
            "status": "completed",
        }
        
        return (True, message, report)
    
    except Exception as e:
        logger.error(
            "Error in rule-based date transformation on '%s.%s' (col: %s): %s",
            database,
            working_table_name,
            column,
            str(e),
        )
        return (
            False,
            f"Error during rule-based date transformation: {str(e)}",
            {},
        )


# ============================================================
# BOOLEAN / YES-NO DETECTION & NORMALIZATION
# ============================================================

# Canonical sets for boolean detection (case-insensitive, stripped)
_TRUE_VALUES = {
    "true", "t", "yes", "y", "1",
}
_FALSE_VALUES = {
    "false", "f", "no", "n", "0",
}

# Business / contextual pairs recognized when both or strong context are present
_CONTEXTUAL_BOOL_PAIRS = [
    ("active", "inactive"),
    ("enabled", "disabled"),
    ("available", "unavailable"),
    ("present", "absent"),
]

# Column name heuristics for disambiguating numeric 0/1 and boosting/reducing confidence
_POSITIVE_BOOL_NAME_PATTERNS = re.compile(
    r"(?:^|_)(?:is|has|can|should|was|did|will|allow|enable|enabled|active|verified|"
    r"available|deleted|archived|approved|confirmed|valid|published|visible|locked|"
    r"default|primary|required|optional|bool|boolean|flag|opt_in|subscribed)(?:$|_)",
    re.I,
)
_NEGATIVE_BOOL_NAME_PATTERNS = re.compile(
    r"(?:^|_)(?:id|customer_id|product_id|user_id|order_id|account_id|qty|quantity|"
    r"score|count|amount|price|total|age|rank|rating|year|month|day|step|version|num|number|"
    r"index|idx|offset|limit|size|length|width|height|weight)(?:$|_)",
    re.I,
)

# Target formatting pairs (preserving exact uppercase/lowercase conventions)
BOOLEAN_FORMAT_MAP: Dict[str, Tuple[str, str]] = {
    "TRUE_FALSE": ("TRUE", "FALSE"),
    "true_false": ("true", "false"),
    "YES_NO": ("YES", "NO"),
    "yes_no": ("yes", "no"),
    "1_0": ("1", "0"),
    "Y_N": ("Y", "N"),
    "y_n": ("y", "n"),
    "T_F": ("T", "F"),
    "t_f": ("t", "f"),
}


def _normalize_bool_token(val: Any) -> str:
    """Lower-case, strip whitespace, and normalize integer-like floats ('1.0' -> '1')."""
    if val is None:
        return ""
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float)):
        if pd.isna(val):
            return ""
        if float(val).is_integer():
            return str(int(val))
        return str(val).strip().lower()
    s = str(val).strip().lower()
    if s in ("1.0", "+1"):
        return "1"
    if s in ("0.0", "-0", "+0"):
        return "0"
    return s


def _classify_token(tok: str, allow_contextual: bool = False) -> str:
    """Return 'true', 'false', or 'unknown'."""
    if not tok:
        return "null"
    if tok in _TRUE_VALUES:
        return "true"
    if tok in _FALSE_VALUES:
        return "false"
    if allow_contextual:
        for pos, neg in _CONTEXTUAL_BOOL_PAIRS:
            if tok == pos:
                return "true"
            if tok == neg:
                return "false"
    return "unknown"


def _evaluate_column_name_signal(column_name: str) -> str:
    """
    Evaluate whether a column name strongly suggests a Boolean flag ('positive'),
    a non-Boolean measurement/identifier ('negative'), or 'neutral'.
    """
    if not column_name:
        return "neutral"
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(column_name)).lower()
    if _NEGATIVE_BOOL_NAME_PATTERNS.search(snake):
        return "negative"
    if _POSITIVE_BOOL_NAME_PATTERNS.search(snake):
        return "positive"
    return "neutral"


def evaluate_boolean_series(
    column_name: str,
    declared_dtype: str,
    value_counts: Dict[Any, int],
    null_count: int = 0,
) -> Dict[str, Any]:
    """
    Core semantic evaluator that inspects actual column values, unique tokens,
    frequencies, physical datatype, and column name context to determine whether
    a column is Boolean, Boolean-like, Numeric, or Text.

    Never modifies data. Separates NULL/empty values from unrecognized values.
    """
    norm_dtype = _normalize_data_type(declared_dtype)
    is_native_bool_dtype = norm_dtype in ("boolean", "bool", "bit") or "tinyint(1)" in str(declared_dtype).lower()
    name_signal = _evaluate_column_name_signal(column_name)

    non_null_items: List[Tuple[str, int, str]] = []
    extra_empty_count = 0
    for raw_val, cnt in value_counts.items():
        if raw_val is None or (isinstance(raw_val, float) and pd.isna(raw_val)):
            extra_empty_count += int(cnt)
            continue
        raw_str = str(raw_val)
        tok = _normalize_bool_token(raw_val)
        if tok == "":
            extra_empty_count += int(cnt)
            continue
        non_null_items.append((raw_str, int(cnt), tok))

    total_nulls = int(null_count) + extra_empty_count
    total_non_null = sum(cnt for _, cnt, _ in non_null_items)
    total_rows = total_non_null + total_nulls

    if total_non_null == 0:
        return {
            "column": column_name,
            "current_type": str(declared_dtype).upper() if declared_dtype else "VARCHAR",
            "detected_type": "Boolean" if is_native_bool_dtype else "Empty / Null",
            "is_boolean_like": bool(is_native_bool_dtype),
            "confidence": 100.0 if is_native_bool_dtype else 0.0,
            "confidence_level": "HIGH" if is_native_bool_dtype else "NOT_BOOLEAN",
            "recommendation": "high_confidence" if is_native_bool_dtype else "not_boolean",
            "total_rows": total_rows,
            "non_null_count": 0,
            "null_count": total_nulls,
            "unique_count": 0,
            "normalized_unique_count": 0,
            "true_count": 0,
            "false_count": 0,
            "recognized_count": 0,
            "unknown_count": 0,
            "true_representations": [],
            "false_representations": [],
            "unrecognized_values": [],
            "unrecognized_counts": {},
            "value_distribution": {},
            "needs_normalization": False,
            "name_signal": name_signal,
        }

    distinct_tokens = {tok for _, _, tok in non_null_items}
    has_contextual_pair = False
    for pos, neg in _CONTEXTUAL_BOOL_PAIRS:
        if pos in distinct_tokens and neg in distinct_tokens:
            has_contextual_pair = True
            break
        if (pos in distinct_tokens or neg in distinct_tokens) and name_signal == "positive" and len(distinct_tokens) <= 3:
            has_contextual_pair = True
            break

    true_reps: List[str] = []
    false_reps: List[str] = []
    unrecognized_vals: List[str] = []
    unrecognized_counts: Dict[str, int] = {}
    value_distribution: Dict[str, int] = {}

    true_row_count = 0
    false_row_count = 0
    unknown_row_count = 0
    canonical_tokens_seen = set()

    for raw_str, cnt, tok in non_null_items:
        value_distribution[raw_str] = value_distribution.get(raw_str, 0) + cnt
        cls = _classify_token(tok, allow_contextual=has_contextual_pair)
        if cls == "true":
            true_row_count += cnt
            canonical_tokens_seen.add(tok)
            if raw_str not in true_reps:
                true_reps.append(raw_str)
        elif cls == "false":
            false_row_count += cnt
            canonical_tokens_seen.add(tok)
            if raw_str not in false_reps:
                false_reps.append(raw_str)
        else:
            unknown_row_count += cnt
            if raw_str not in unrecognized_vals:
                unrecognized_vals.append(raw_str)
            unrecognized_counts[raw_str] = unrecognized_counts.get(raw_str, 0) + cnt

    recognized_row_count = true_row_count + false_row_count
    recognized_ratio = recognized_row_count / total_non_null if total_non_null > 0 else 0.0
    unique_raw_count = len(value_distribution)
    normalized_unique_count = len(distinct_tokens)

    only_numeric_01 = canonical_tokens_seen.issubset({"0", "1"}) and len(canonical_tokens_seen) > 0

    confidence_score = 0.0
    confidence_level = "NOT_BOOLEAN"
    detected_type = (
        "Text"
        if norm_dtype in TEXT_DATA_TYPES
        else (
            "Numeric"
            if norm_dtype in ("int", "integer", "bigint", "smallint", "tinyint", "decimal", "float", "double", "numeric")
            else str(declared_dtype).upper()
        )
    )
    is_boolean_like = False

    if is_native_bool_dtype:
        is_boolean_like = True
        detected_type = "Boolean"
        confidence_score = round(max(95.0, recognized_ratio * 100.0), 1)
        confidence_level = "HIGH"
    elif recognized_ratio < 0.70 or recognized_row_count == 0:
        is_boolean_like = False
        confidence_score = round(recognized_ratio * 100.0, 1)
        confidence_level = "NOT_BOOLEAN"
    elif only_numeric_01:
        if unknown_row_count > 0 and recognized_ratio < 0.95:
            is_boolean_like = False
            detected_type = "Numeric"
            confidence_score = round(recognized_ratio * 50.0, 1)
            confidence_level = "NOT_BOOLEAN"
        elif name_signal == "negative":
            is_boolean_like = False
            detected_type = "Numeric"
            confidence_score = 35.0
            confidence_level = "LOW"
        elif name_signal == "positive":
            is_boolean_like = True
            detected_type = "Boolean-like"
            confidence_score = round(95.0 * recognized_ratio, 1)
            confidence_level = "HIGH" if recognized_ratio >= 0.95 else "MEDIUM"
        else:
            is_boolean_like = True
            detected_type = "Boolean-like"
            confidence_score = round(82.0 * recognized_ratio, 1)
            confidence_level = "MEDIUM" if recognized_ratio >= 0.90 else "LOW"
    else:
        if unknown_row_count == 0:
            is_boolean_like = True
            detected_type = "Boolean-like"
            if true_row_count > 0 and false_row_count > 0:
                confidence_score = 99.0 if name_signal == "positive" else 96.0
                confidence_level = "HIGH"
            else:
                confidence_score = 92.0 if name_signal == "positive" else 85.0
                confidence_level = "HIGH" if name_signal == "positive" else "MEDIUM"
        elif recognized_ratio >= 0.90:
            is_boolean_like = True
            detected_type = "Boolean-like"
            confidence_score = round(recognized_ratio * 100.0, 1)
            confidence_level = "HIGH" if recognized_ratio >= 0.98 and name_signal == "positive" else "MEDIUM"
        elif recognized_ratio >= 0.75:
            is_boolean_like = True
            detected_type = "Boolean-like"
            confidence_score = round(recognized_ratio * 100.0, 1)
            confidence_level = "LOW"
        else:
            is_boolean_like = False
            confidence_score = round(recognized_ratio * 100.0, 1)
            confidence_level = "NOT_BOOLEAN"

    needs_normalization = False
    if is_boolean_like:
        if len(true_reps) > 1 or len(false_reps) > 1:
            needs_normalization = True
        elif len(true_reps) == 1 and len(false_reps) == 1:
            pair = (true_reps[0], false_reps[0])
            if pair not in set(BOOLEAN_FORMAT_MAP.values()):
                needs_normalization = True

    rec_map = {
        "HIGH": "high_confidence",
        "MEDIUM": "medium_confidence",
        "LOW": "low_confidence",
        "NOT_BOOLEAN": "not_boolean",
    }

    return {
        "column": column_name,
        "current_type": str(declared_dtype).upper() if declared_dtype else "VARCHAR",
        "detected_type": detected_type,
        "is_boolean_like": is_boolean_like,
        "confidence": confidence_score,
        "confidence_level": confidence_level,
        "recommendation": rec_map.get(confidence_level, "not_boolean"),
        "total_rows": total_rows,
        "non_null_count": total_non_null,
        "null_count": total_nulls,
        "unique_count": unique_raw_count,
        "normalized_unique_count": normalized_unique_count,
        "true_count": true_row_count,
        "false_count": false_row_count,
        "recognized_count": recognized_row_count,
        "unknown_count": unknown_row_count,
        "true_representations": true_reps,
        "false_representations": false_reps,
        "unrecognized_values": unrecognized_vals,
        "unrecognized_counts": unrecognized_counts,
        "value_distribution": value_distribution,
        "needs_normalization": needs_normalization,
        "name_signal": name_signal,
    }


def _scan_column_value_counts_db(
    conn,
    quoted_table: str,
    quoted_col: str,
    sample_limit: int = 2000,
) -> Tuple[Dict[Any, int], int]:
    """
    Query distinct values and their exact row frequencies across the column in the database,
    plus exact NULL/empty count.
    """
    null_query = text(
        f"SELECT COUNT(*) FROM {quoted_table} "
        f"WHERE {quoted_col} IS NULL OR TRIM(CAST({quoted_col} AS CHAR)) = ''"
    )
    null_count = int(conn.execute(null_query).scalar() or 0)

    group_query = text(
        f"SELECT CAST({quoted_col} AS CHAR) AS val, COUNT(*) AS cnt "
        f"FROM {quoted_table} "
        f"WHERE {quoted_col} IS NOT NULL AND TRIM(CAST({quoted_col} AS CHAR)) != '' "
        f"GROUP BY CAST({quoted_col} AS CHAR) "
        f"ORDER BY cnt DESC "
        f"LIMIT {int(sample_limit)}"
    )
    rows = conn.execute(group_query).fetchall()
    value_counts: Dict[Any, int] = {}
    for row in rows:
        val = row._mapping["val"]
        cnt = int(row._mapping["cnt"] or 0)
        value_counts[val] = cnt

    return value_counts, null_count


def detect_boolean_like_columns(
    engine,
    database: str,
    table_name: str,
    sample_limit: int = 2000,
    confidence_threshold: float = 0.65,
) -> List[Dict[str, Any]]:
    """
    Scan ALL columns in the table (including VARCHAR/String/Text, Boolean, and 0/1 Numeric)
    by inspecting their actual column values, frequency distributions, and column context.
    Returns a list of detected Boolean and Boolean-like columns with rich metadata.
    """
    try:
        inspector = inspect(engine)
        columns_info = inspector.get_columns(table_name, schema=database)
        if not columns_info:
            return []

        quoted_table = _quote_table(database, table_name)
        results: List[Dict[str, Any]] = []

        with engine.connect() as conn:
            for col_meta in columns_info:
                col_name = col_meta["name"]
                if col_name.startswith("__bool_backup_"):
                    continue

                raw_type = str(col_meta.get("type", "VARCHAR"))
                norm_type = _normalize_data_type(raw_type)

                if norm_type in DATE_DATA_TYPES or norm_type in ("blob", "longblob", "mediumblob", "tinyblob", "binary", "varbinary", "json"):
                    continue

                quoted_col = _quote_identifier(col_name)
                value_counts, null_count = _scan_column_value_counts_db(
                    conn, quoted_table, quoted_col, sample_limit=sample_limit
                )

                eval_res = evaluate_boolean_series(
                    column_name=col_name,
                    declared_dtype=raw_type,
                    value_counts=value_counts,
                    null_count=null_count,
                )

                if not eval_res["is_boolean_like"]:
                    continue

                if (eval_res["confidence"] / 100.0) < confidence_threshold:
                    continue

                results.append({
                    "column": col_name,
                    "current_type": eval_res["current_type"],
                    "detected_type": eval_res["detected_type"],
                    "confidence": eval_res["confidence"],
                    "confidence_level": eval_res["confidence_level"],
                    "recommendation": eval_res["recommendation"],
                    "sample_size": eval_res["non_null_count"],
                    "total_rows": eval_res["total_rows"],
                    "non_null_count": eval_res["non_null_count"],
                    "null_count": eval_res["null_count"],
                    "unique_count": eval_res["unique_count"],
                    "normalized_unique_count": eval_res["normalized_unique_count"],
                    "true_count": eval_res["true_count"],
                    "false_count": eval_res["false_count"],
                    "recognized_count": eval_res["recognized_count"],
                    "unknown_count": eval_res["unknown_count"],
                    "true_representations": eval_res["true_representations"],
                    "false_representations": eval_res["false_representations"],
                    "unrecognized_values": eval_res["unrecognized_values"],
                    "unrecognized_counts": eval_res["unrecognized_counts"],
                    "value_distribution": eval_res["value_distribution"],
                    "needs_normalization": eval_res["needs_normalization"],
                })

        return results

    except Exception as e:
        logger.error(
            "Error detecting boolean-like columns for '%s': %s",
            table_name,
            str(e),
        )
        return []


def analyze_boolean_column(
    engine,
    database: str,
    table_name: str,
    column: str,
    sample_limit: int = 2000,
) -> Dict[str, Any]:
    """
    Deep analysis of a single column for Boolean / Yes-No normalization.
    Returns full value counts, recognized TRUE/FALSE representations,
    unrecognized values, null count, confidence level, and sample preview.
    """
    try:
        inspector = inspect(engine)
        columns_info = inspector.get_columns(table_name, schema=database)
        col_meta = next((c for c in columns_info if c["name"] == column), None)
        raw_type = str(col_meta.get("type", "VARCHAR")) if col_meta else "VARCHAR"

        quoted_table = _quote_table(database, table_name)
        quoted_col = _quote_identifier(column)

        with engine.connect() as conn:
            value_counts, null_count = _scan_column_value_counts_db(
                conn, quoted_table, quoted_col, sample_limit=sample_limit
            )

            eval_res = evaluate_boolean_series(
                column_name=column,
                declared_dtype=raw_type,
                value_counts=value_counts,
                null_count=null_count,
            )

            sample_preview = []
            allow_ctx = any(
                pos in {_normalize_bool_token(k) for k in value_counts}
                and neg in {_normalize_bool_token(k) for k in value_counts}
                for pos, neg in _CONTEXTUAL_BOOL_PAIRS
            )
            for raw_val, cnt in list(value_counts.items())[:30]:
                tok = _normalize_bool_token(raw_val)
                cls = _classify_token(tok, allow_contextual=allow_ctx)
                sample_preview.append({
                    "original": raw_val,
                    "normalized": tok,
                    "classification": cls.upper(),
                    "count": cnt,
                })

            return {
                "column": column,
                "current_type": eval_res["current_type"],
                "detected_type": eval_res["detected_type"],
                "is_boolean_like": eval_res["is_boolean_like"],
                "confidence": eval_res["confidence"],
                "confidence_level": eval_res["confidence_level"],
                "recommendation": eval_res["recommendation"],
                "total_rows": eval_res["total_rows"],
                "total_values": eval_res["non_null_count"],
                "non_null_count": eval_res["non_null_count"],
                "true_count": eval_res["true_count"],
                "false_count": eval_res["false_count"],
                "recognized_count": eval_res["recognized_count"],
                "unknown_count": eval_res["unknown_count"],
                "null_count": eval_res["null_count"],
                "unique_count": eval_res["unique_count"],
                "normalized_unique_count": eval_res["normalized_unique_count"],
                "true_representations": eval_res["true_representations"],
                "false_representations": eval_res["false_representations"],
                "unrecognized_samples": eval_res["unrecognized_values"][:30],
                "unrecognized_counts": eval_res["unrecognized_counts"],
                "value_distribution": eval_res["value_distribution"],
                "sample_values": sample_preview,
                "needs_normalization": eval_res["needs_normalization"],
            }

    except Exception as e:
        logger.error(
            "Error analyzing boolean column '%s.%s': %s",
            database,
            table_name,
            str(e),
        )
        return {}


def resolve_boolean_target_pair(
    target_format: str,
    true_value: str = "TRUE",
    false_value: str = "FALSE",
) -> Tuple[str, str]:
    """Resolve the (true_str, false_str) output pair for a given target_format."""
    if target_format == "custom":
        return (str(true_value), str(false_value))
    if target_format in BOOLEAN_FORMAT_MAP:
        return BOOLEAN_FORMAT_MAP[target_format]
    upper_fmt = target_format.upper()
    if upper_fmt in BOOLEAN_FORMAT_MAP:
        return BOOLEAN_FORMAT_MAP[upper_fmt]
    raise ValueError(f"Invalid target_format '{target_format}'.")


def preview_boolean_normalization(
    engine,
    database: str,
    table_name: str,
    column: str,
    target_format: str = "TRUE_FALSE",
    true_value: str = "TRUE",
    false_value: str = "FALSE",
    unrecognized_action: str = "keep_original",
    manual_mapping: Optional[Dict[str, str]] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    Generate a read-only Before / After preview of Boolean normalization
    without modifying the database.
    """
    analysis = analyze_boolean_column(engine, database, table_name, column)
    if not analysis:
        return {"mapping_summary": [], "row_preview": [], "analysis": {}}

    true_str, false_str = resolve_boolean_target_pair(target_format, true_value, false_value)
    manual_mapping = manual_mapping or {}

    val_dist = analysis.get("value_distribution", {})
    allow_ctx = any(
        pos in {_normalize_bool_token(k) for k in val_dist}
        and neg in {_normalize_bool_token(k) for k in val_dist}
        for pos, neg in _CONTEXTUAL_BOOL_PAIRS
    )

    mapping_summary = []
    for raw_val, cnt in val_dist.items():
        tok = _normalize_bool_token(raw_val)
        cls = _classify_token(tok, allow_contextual=allow_ctx)
        if cls == "true":
            standardized = true_str
            status = "Recognized (TRUE)"
        elif cls == "false":
            standardized = false_str
            status = "Recognized (FALSE)"
        else:
            if raw_val in manual_mapping and manual_mapping[raw_val] in ("TRUE", "FALSE", "NULL", "KEEP"):
                choice = manual_mapping[raw_val]
                if choice == "TRUE":
                    standardized = true_str
                elif choice == "FALSE":
                    standardized = false_str
                elif choice == "NULL":
                    standardized = None
                else:
                    standardized = raw_val
                status = f"Mapped Manually ({choice})"
            elif unrecognized_action == "set_null":
                standardized = None
                status = "Unrecognized → NULL"
            else:
                standardized = raw_val
                status = "Unrecognized (Left Unchanged)"

        mapping_summary.append({
            "Original": raw_val,
            "Standardized": "NULL" if standardized is None else standardized,
            "Logical State": cls.upper(),
            "Count": cnt,
            "Status": status,
        })

    if analysis.get("null_count", 0) > 0:
        mapping_summary.append({
            "Original": "NULL",
            "Standardized": "NULL",
            "Logical State": "NULL",
            "Count": analysis["null_count"],
            "Status": "Preserved as NULL",
        })

    quoted_table = _quote_table(database, table_name)
    quoted_col = _quote_identifier(column)
    row_preview = []
    try:
        with engine.connect() as conn:
            q = text(f"SELECT {quoted_col} AS orig FROM {quoted_table} LIMIT {int(limit)}")
            rows = conn.execute(q).fetchall()
            for r in rows:
                orig = r._mapping["orig"]
                if orig is None or (isinstance(orig, str) and orig.strip() == ""):
                    std = None
                else:
                    orig_s = str(orig)
                    tok = _normalize_bool_token(orig)
                    cls = _classify_token(tok, allow_contextual=allow_ctx)
                    if cls == "true":
                        std = true_str
                    elif cls == "false":
                        std = false_str
                    elif orig_s in manual_mapping:
                        choice = manual_mapping[orig_s]
                        std = true_str if choice == "TRUE" else (false_str if choice == "FALSE" else (None if choice == "NULL" else orig_s))
                    elif unrecognized_action == "set_null":
                        std = None
                    else:
                        std = orig_s
                row_preview.append({
                    "Original": "NULL" if orig is None else str(orig),
                    "Standardized": "NULL" if std is None else str(std),
                })
    except Exception as e:
        logger.warning("Preview row sample failed for '%s': %s", column, str(e))

    return {
        "mapping_summary": mapping_summary,
        "row_preview": row_preview,
        "true_target": true_str,
        "false_target": false_str,
        "analysis": analysis,
    }


def transform_boolean_column(
    engine,
    database: str,
    working_table_name: str,
    column: str,
    target_format: str = "TRUE_FALSE",
    true_value: str = "TRUE",
    false_value: str = "FALSE",
    new_column_name: Optional[str] = None,
    in_place: bool = True,
    unrecognized_action: str = "keep_original",
    manual_mapping: Optional[Dict[str, str]] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Normalize a Boolean-like column into a user-selected format.
    """
    try:
        if not working_table_name or working_table_name.count(CLEANING_SUFFIX) != 1:
            return (False, "Refusing to modify a table that is not identified as a cleaning workspace.", {})
        safe_name = _make_safe_table_name(working_table_name)
        if safe_name != working_table_name:
            return (False, "Refusing to modify an invalid table identifier.", {})

        try:
            true_str, false_str = resolve_boolean_target_pair(target_format, true_value, false_value)
        except ValueError as ve:
            return (False, str(ve), {})

        inspector = inspect(engine)
        tables = inspector.get_table_names(schema=database)
        if working_table_name not in tables:
            return (False, f"Working table '{working_table_name}' not found in database '{database}'.", {})

        table_columns_info = inspector.get_columns(working_table_name, schema=database)
        col_info = next((c for c in table_columns_info if c["name"] == column), None)
        if not col_info:
            return (False, f"Column '{column}' not found in table '{working_table_name}'.", {})

        if new_column_name is not None and new_column_name != column:
            target_col = new_column_name
            modify_in_place = False
        elif not in_place and new_column_name is None:
            target_col = f"{column}_norm"
            modify_in_place = False
        else:
            target_col = column
            modify_in_place = True

        quoted_table = _quote_table(database, working_table_name)
        quoted_col = _quote_identifier(column)
        quoted_target_col = _quote_identifier(target_col)
        backup_col_name = f"__bool_backup_{column}"[:64]
        quoted_backup_col = _quote_identifier(backup_col_name)

        manual_mapping = manual_mapping or {}

        pre_analysis = analyze_boolean_column(engine, database, working_table_name, column)
        val_dist = pre_analysis.get("value_distribution", {})
        allow_ctx = any(
            pos in {_normalize_bool_token(k) for k in val_dist}
            and neg in {_normalize_bool_token(k) for k in val_dist}
            for pos, neg in _CONTEXTUAL_BOOL_PAIRS
        )

        true_tokens = set(_TRUE_VALUES)
        false_tokens = set(_FALSE_VALUES)
        if allow_ctx:
            for pos, neg in _CONTEXTUAL_BOOL_PAIRS:
                true_tokens.add(pos)
                false_tokens.add(neg)

        manual_true_raw: List[str] = []
        manual_false_raw: List[str] = []
        manual_null_raw: List[str] = []
        for raw_k, target_choice in manual_mapping.items():
            if target_choice == "TRUE":
                manual_true_raw.append(raw_k)
            elif target_choice == "FALSE":
                manual_false_raw.append(raw_k)
            elif target_choice == "NULL":
                manual_null_raw.append(raw_k)

        def _sql_quote_literal(val: str) -> str:
            return "'" + str(val).replace("\\", "\\\\").replace("'", "''") + "'"

        true_in_list = ", ".join(_sql_quote_literal(t) for t in sorted(true_tokens))
        false_in_list = ", ".join(_sql_quote_literal(t) for t in sorted(false_tokens))
        norm_sql_expr = f"LOWER(TRIM(CAST({quoted_col} AS CHAR)))"

        when_clauses = [
            f"WHEN {quoted_col} IS NULL OR TRIM(CAST({quoted_col} AS CHAR)) = '' THEN NULL",
            f"WHEN {norm_sql_expr} IN ({true_in_list}) THEN {_sql_quote_literal(true_str)}",
            f"WHEN {norm_sql_expr} IN ({false_in_list}) THEN {_sql_quote_literal(false_str)}",
        ]
        when_clauses.append(f"WHEN {norm_sql_expr} IN ('1.0', '+1') THEN {_sql_quote_literal(true_str)}")
        when_clauses.append(f"WHEN {norm_sql_expr} IN ('0.0', '-0', '+0') THEN {_sql_quote_literal(false_str)}")

        if manual_true_raw:
            m_true_list = ", ".join(_sql_quote_literal(v) for v in manual_true_raw)
            when_clauses.append(f"WHEN CAST({quoted_col} AS CHAR) IN ({m_true_list}) THEN {_sql_quote_literal(true_str)}")
        if manual_false_raw:
            m_false_list = ", ".join(_sql_quote_literal(v) for v in manual_false_raw)
            when_clauses.append(f"WHEN CAST({quoted_col} AS CHAR) IN ({m_false_list}) THEN {_sql_quote_literal(false_str)}")
        if manual_null_raw:
            m_null_list = ", ".join(_sql_quote_literal(v) for v in manual_null_raw)
            when_clauses.append(f"WHEN CAST({quoted_col} AS CHAR) IN ({m_null_list}) THEN NULL")

        if unrecognized_action == "set_null":
            else_clause = "ELSE NULL"
        else:
            else_clause = f"ELSE CAST({quoted_col} AS CHAR)"

        case_expr = "CASE\n    " + "\n    ".join(when_clauses) + f"\n    {else_clause}\nEND"

        with engine.begin() as conn:
            col_names = [c["name"] for c in table_columns_info]

            if modify_in_place:
                if backup_col_name not in col_names:
                    conn.execute(
                        text(f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_backup_col} TEXT NULL")
                    )
                    conn.execute(
                        text(f"UPDATE {quoted_table} SET {quoted_backup_col} = CAST({quoted_col} AS CHAR)")
                    )

                norm_dt = _normalize_data_type(col_info.get("type", ""))
                if norm_dt not in TEXT_DATA_TYPES:
                    conn.execute(
                        text(f"ALTER TABLE {quoted_table} MODIFY COLUMN {quoted_col} VARCHAR(64) NULL")
                    )

                conn.execute(
                    text(
                        f"UPDATE {quoted_table} SET {quoted_col} = NULL "
                        f"WHERE {quoted_col} IS NOT NULL AND TRIM(CAST({quoted_col} AS CHAR)) = ''"
                    )
                )

                update_query = text(f"""
                    UPDATE {quoted_table}
                    SET {quoted_col} = {case_expr}
                    WHERE {quoted_col} IS NOT NULL
                """)
                conn.execute(update_query)
            else:
                if target_col not in col_names:
                    conn.execute(
                        text(f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_target_col} VARCHAR(64) NULL")
                    )
                update_query = text(f"""
                    UPDATE {quoted_table}
                    SET {quoted_target_col} = {case_expr}
                """)
                conn.execute(update_query)

        total_non_null = int(pre_analysis.get("non_null_count", 0))
        recognized_rows = int(pre_analysis.get("recognized_count", 0))
        manually_mapped_rows = sum(
            int(val_dist.get(k, 0))
            for k, v in manual_mapping.items()
            if v in ("TRUE", "FALSE", "NULL")
        )
        rows_converted = recognized_rows + manually_mapped_rows
        unconverted_rows = max(0, total_non_null - rows_converted)

        message = (
            f"Boolean normalization applied to column '{column}'. "
            f"{rows_converted:,} of {total_non_null:,} non-null values standardized to "
            f"'{true_str}' / '{false_str}' in column '{target_col}'."
        )
        if unconverted_rows > 0:
            message += f" {unconverted_rows:,} unrecognized value(s) preserved ({unrecognized_action})."

        report = {
            "operation": "Boolean Normalization",
            "source_column": column,
            "target_column": target_col,
            "in_place": modify_in_place,
            "backup_column": backup_col_name if modify_in_place else None,
            "target_format": target_format,
            "true_target": true_str,
            "false_target": false_str,
            "total_rows": total_non_null,
            "rows_converted": rows_converted,
            "exceptions": unconverted_rows,
            "null_count": int(pre_analysis.get("null_count", 0)),
            "status": "completed",
        }
        return (True, message, report)

    except Exception as e:
        logger.error(
            "Error normalizing boolean column '%s.%s' (col: %s): %s",
            database,
            working_table_name,
            column,
            str(e),
        )
        return (False, f"Error during boolean normalization: {str(e)}", {})


def undo_boolean_normalization(
    engine,
    database: str,
    working_table_name: str,
    column: str,
    target_column: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Revert a previous Boolean normalization on `column` by restoring from
    `__bool_backup_<column>` (if modified in-place) or dropping `target_column`
    (if created as a separate column).
    """
    try:
        if not working_table_name or working_table_name.count(CLEANING_SUFFIX) != 1:
            return (False, "Refusing to modify a non-workspace table.")

        inspector = inspect(engine)
        table_columns_info = inspector.get_columns(working_table_name, schema=database)
        col_names = [c["name"] for c in table_columns_info]

        quoted_table = _quote_table(database, working_table_name)
        backup_col_name = f"__bool_backup_{column}"[:64]

        with engine.begin() as conn:
            if target_column and target_column != column and target_column in col_names:
                quoted_target = _quote_identifier(target_column)
                conn.execute(text(f"ALTER TABLE {quoted_table} DROP COLUMN {quoted_target}"))
                return (True, f"Removed normalized column '{target_column}' and preserved original column '{column}'.")

            if backup_col_name in col_names:
                quoted_col = _quote_identifier(column)
                quoted_backup = _quote_identifier(backup_col_name)
                conn.execute(
                    text(f"UPDATE {quoted_table} SET {quoted_col} = {quoted_backup}")
                )
                conn.execute(
                    text(f"ALTER TABLE {quoted_table} DROP COLUMN {quoted_backup}")
                )
                return (True, f"Reverted column '{column}' to its original pre-normalized values.")

        return (False, f"No backup found to revert for column '{column}'.")

    except Exception as e:
        logger.error("Error reverting boolean normalization on '%s': %s", column, str(e))
        return (False, f"Error reverting boolean normalization: {str(e)}")


# ============================================================
# ADVANCED DATE STANDARDIZATION (DETERMINISTIC RULES 1 & 2)
# ============================================================
from src.advanced_date_standardization import (
    SUPPORTED_OUTPUT_FORMATS as ADV_DATE_OUTPUT_FORMATS,
    ALLOWED_SCAN_PERCENTAGES,
    MONTH_MAPPING,
    validate_date,
    extract_four_digit_year,
    parse_text_month_date,
    parse_numeric_date,
    format_standardized_date,
    parse_and_standardize_record,
    detect_date_like_value,
    get_safe_output_column_name,
    detect_date_columns,
    preview_column_standardization,
    standardize_column,
)
