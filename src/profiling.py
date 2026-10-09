from typing import Any, Dict, List, Optional, Tuple
import logging

import pandas as pd
from sqlalchemy import text

logger = logging.getLogger(__name__)


def _quote_identifier(identifier: str) -> str:
    """Safely quote a MySQL identifier."""
    if not isinstance(identifier, str) or not identifier:
        raise ValueError("Identifier must be a non-empty string.")

    return f"`{identifier.replace('`', '``')}`"


def _quote_table(database: str, table_name: str) -> str:
    """Return a fully qualified quoted MySQL table name."""
    return f"{_quote_identifier(database)}." f"{_quote_identifier(table_name)}"


def _get_columns(
    engine,
    database: str,
    table_name: str,
) -> List[Dict[str, Any]]:
    """Get column metadata using INFORMATION_SCHEMA."""
    query = text("""
        SELECT
            COLUMN_NAME,
            DATA_TYPE,
            IS_NULLABLE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = :database
          AND TABLE_NAME = :table_name
        ORDER BY ORDINAL_POSITION
        """)

    with engine.connect() as conn:
        result = conn.execute(
            query,
            {
                "database": database,
                "table_name": table_name,
            },
        )

        return [dict(row._mapping) for row in result]


def profile_table(
    engine,
    database: str,
    table_name: str,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Profile any MySQL table (source or workspace) in read-only mode.

    Returns:
        (
            success,
            message,
            profile
        )
    """
    try:
        columns = _get_columns(
            engine,
            database,
            table_name,
        )

        if not columns:
            return (
                False,
                f"Table '{table_name}' was not found.",
                None,
            )

        quoted_table = _quote_table(
            database,
            table_name,
        )

        # ---------------------------------------------------------
        # Load the table into pandas via read-only SELECT.
        # ---------------------------------------------------------
        query = text(f"SELECT * FROM {quoted_table}")

        with engine.connect() as conn:
            df = pd.read_sql_query(
                query,
                conn,
            )

        row_count = len(df)
        column_count = len(df.columns)

        # ---------------------------------------------------------
        # Duplicate rows
        # ---------------------------------------------------------
        duplicate_row_count = int(df.duplicated(keep=False).sum())

        duplicate_group_count = int(df.duplicated().sum())

        # ---------------------------------------------------------
        # Column-level profiling
        # ---------------------------------------------------------
        column_profiles: List[Dict[str, Any]] = []

        for column in df.columns:
            series = df[column]

            null_count = int(series.isna().sum())

            # Treat empty strings separately from SQL NULL.
            if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(
                series
            ):
                empty_string_count = int(
                    series.fillna("").astype(str).str.strip().eq("").sum() - null_count
                )

                whitespace_issue_count = int(
                    series.dropna()
                    .astype(str)
                    .ne(series.dropna().astype(str).str.strip())
                    .sum()
                )

                unique_count = int(series.dropna().nunique())
            else:
                empty_string_count = 0
                whitespace_issue_count = 0

                unique_count = int(series.dropna().nunique())

            null_percentage = (
                round((null_count / row_count) * 100, 2) if row_count else 0.0
            )

            physical_dtype = str(
                next(
                    (
                        item["DATA_TYPE"]
                        for item in columns
                        if item["COLUMN_NAME"] == column
                    ),
                    str(series.dtype),
                )
            )

            from src.staging import evaluate_boolean_series

            val_counts_dict: Dict[Any, int] = {}
            for k, v in series.dropna().value_counts().items():
                val_counts_dict[k] = int(v)

            bool_eval = evaluate_boolean_series(
                column_name=column,
                declared_dtype=physical_dtype,
                value_counts=val_counts_dict,
                null_count=null_count,
            )

            logical_type = (
                bool_eval["detected_type"]
                if bool_eval["is_boolean_like"]
                else physical_dtype.upper()
            )

            profile: Dict[str, Any] = {
                "Column": column,
                "Data Type": physical_dtype,
                "Logical Type": logical_type,
                "Boolean Confidence": (
                    f"{bool_eval['confidence_level']} ({bool_eval['confidence']}%)"
                    if bool_eval["is_boolean_like"]
                    else "—"
                ),
                "Rows": row_count,
                "Null Count": null_count,
                "Null %": null_percentage,
                "Empty Strings": empty_string_count,
                "Unique Values": unique_count,
                "Whitespace Issues": whitespace_issue_count,
                "_bool_eval": bool_eval,
            }

            # -----------------------------------------------------
            # Numeric statistics
            # -----------------------------------------------------
            if pd.api.types.is_numeric_dtype(series):
                non_null = series.dropna()

                if len(non_null) > 0:
                    profile["Min"] = non_null.min()
                    profile["Max"] = non_null.max()
                    profile["Average"] = round(
                        float(non_null.mean()),
                        4,
                    )
                else:
                    profile["Min"] = None
                    profile["Max"] = None
                    profile["Average"] = None
            else:
                profile["Min"] = None
                profile["Max"] = None
                profile["Average"] = None

            column_profiles.append(profile)

        clean_profiles_for_df = [
            {k: v for k, v in p.items() if k != "_bool_eval"}
            for p in column_profiles
        ]
        column_profile_df = pd.DataFrame(clean_profiles_for_df)

        # ---------------------------------------------------------
        # Findings
        # ---------------------------------------------------------
        findings: List[Dict[str, Any]] = []

        for profile in column_profiles:
            b_eval = profile.get("_bool_eval", {})
            if b_eval.get("is_boolean_like") and b_eval.get("needs_normalization"):
                true_reps = ", ".join(b_eval.get("true_representations", [])[:6])
                false_reps = ", ".join(b_eval.get("false_representations", [])[:6])
                findings.append(
                    {
                        "Type": "Boolean Inconsistency",
                        "Column": profile["Column"],
                        "Count": b_eval.get("recognized_count", 0),
                        "Severity": "Medium",
                        "Description": (
                            f"{profile['Column']} (physical: {profile['Data Type']}) behaves as "
                            f"{b_eval.get('detected_type')} ({b_eval.get('confidence_level')} confidence) "
                            f"with mixed representations (TRUE: [{true_reps}], FALSE: [{false_reps}])."
                        ),
                    }
                )
            if profile["Null Count"] > 0:
                findings.append(
                    {
                        "Type": "Missing Values",
                        "Column": profile["Column"],
                        "Count": profile["Null Count"],
                        "Severity": ("High" if profile["Null %"] >= 20 else "Medium"),
                        "Description": (
                            f"{profile['Column']} contains "
                            f"{profile['Null Count']} NULL value(s) "
                            f"({profile['Null %']}%)."
                        ),
                    }
                )

            if profile["Empty Strings"] > 0:
                findings.append(
                    {
                        "Type": "Empty Values",
                        "Column": profile["Column"],
                        "Count": profile["Empty Strings"],
                        "Severity": "Medium",
                        "Description": (
                            f"{profile['Column']} contains "
                            f"{profile['Empty Strings']} "
                            "empty/blank value(s)."
                        ),
                    }
                )

            if profile["Whitespace Issues"] > 0:
                findings.append(
                    {
                        "Type": "Whitespace",
                        "Column": profile["Column"],
                        "Count": profile["Whitespace Issues"],
                        "Severity": "Low",
                        "Description": (
                            f"{profile['Column']} contains "
                            f"{profile['Whitespace Issues']} "
                            "value(s) with leading/trailing whitespace."
                        ),
                    }
                )

        if duplicate_group_count > 0:
            findings.append(
                {
                    "Type": "Duplicate Rows",
                    "Column": "*",
                    "Count": duplicate_group_count,
                    "Severity": "High",
                    "Description": (
                        f"{duplicate_group_count} duplicate row occurrence(s) "
                        "were detected."
                    ),
                }
            )

        profile = {
            "database": database,
            "table_name": table_name,
            "row_count": row_count,
            "column_count": column_count,
            "duplicate_row_count": duplicate_row_count,
            "duplicate_group_count": duplicate_group_count,
            "column_profiles": column_profile_df,
            "findings": findings,
        }

        return (
            True,
            (f"Profile completed successfully for " f"`{table_name}`."),
            profile,
        )

    except Exception as e:
        logger.error(
            "Error profiling table '%s.%s': %s",
            database,
            table_name,
            str(e),
        )

        return (
            False,
            f"Error profiling table: {str(e)}",
            None,
        )


def profile_source_table(
    engine,
    database: str,
    table_name: str,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Profile an original source table directly in read-only mode.
    Does not modify any source data or create any staging tables.
    """
    return profile_table(engine, database, table_name)


def profile_workspace(
    engine,
    database: str,
    table_name: str,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Profile a cleaning workspace without modifying it.
    """
    return profile_table(engine, database, table_name)
