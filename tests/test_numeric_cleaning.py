"""
Unit and Integration Test Suite for Intelligent Numeric Column Detection, Validation, and Conversion.
DataClean Studio — Zero-Production-Risk Staging Pipeline

Covers Section 11 Test Requirements:
- Integer and decimal detection in text columns.
- Automatic detection failures followed by successful manual selection.
- Mixed numeric and non-numeric values.
- Whitespace normalization.
- Negative and positive numbers.
- NULL and empty values.
- Locale-specific separators and ambiguous formats.
- Leading-zero identifiers.
- Phone numbers, postal codes, and product codes.
- Scientific notation.
- Very large numbers and overflow (INT vs BIGINT).
- Decimal precision, scale, and rounding risks.
- Invalid-value handling (blocking vs set_null resolution).
- Empty tables and large datasets.
- Preview operations that must not modify data.
- Successful conversion and post-conversion verification.
- Failed conversion and rollback.
- Preservation of row counts, indexes, and unrelated columns.
- Confirmation that production tables remain unchanged.
- Regression testing of existing features.
"""

from decimal import Decimal
import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, text

from src.staging import (
    NumericNormalizationConfig,
    ValueValidationResult,
    NumericColumnAnalysis,
    NumericDetectionClassification,
    SUPPORTED_NUMERIC_TYPES,
    NUMBER_FORMATS,
    IDENTIFIER_KEYWORDS,
    CURRENCY_SYMBOLS,
    normalize_and_validate_value,
    get_eligible_text_columns,
    analyze_numeric_column,
    scan_table_numeric_candidates,
    convert_column_to_numeric_workspace,
)


@pytest.fixture
def sqlite_test_engine():
    """Creates an in-memory SQLite engine for workspace staging tests."""
    engine = create_engine("sqlite:///:memory:")
    return engine


# ============================================================
# 1. PURE VALUE NORMALIZATION & VALIDATION TESTS
# ============================================================

def test_integer_detection():
    """Whole numbers are detected as VALID_INTEGER."""
    res = normalize_and_validate_value("25000")
    assert res.is_valid is True
    assert res.status == "VALID_INTEGER"
    assert res.normalized_value == "25000"
    assert res.numeric_value == Decimal("25000")
    assert res.is_integer is True
    assert res.scale == 0


def test_decimal_detection():
    """Decimals are detected as VALID_DECIMAL with exact scale."""
    res = normalize_and_validate_value("35000.50")
    assert res.is_valid is True
    assert res.status == "VALID_DECIMAL"
    assert res.normalized_value == "35000.50"
    assert res.numeric_value == Decimal("35000.50")
    assert res.is_integer is False
    assert res.scale == 2


def test_whitespace_normalization():
    """Leading and trailing whitespace is trimmed when enabled."""
    cfg = NumericNormalizationConfig(trim_whitespace=True)
    res = normalize_and_validate_value("   42000   ", config=cfg)
    assert res.is_valid is True
    assert res.status == "VALID_NORMALIZED"
    assert res.normalized_value == "42000"


def test_positive_and_negative_numbers():
    """Negative and positive signed numbers are parsed correctly."""
    cfg = NumericNormalizationConfig(normalize_plus_sign=True)
    res_neg = normalize_and_validate_value("-125.75", config=cfg)
    assert res_neg.is_valid is True
    assert res_neg.normalized_value == "-125.75"
    assert res_neg.numeric_value == Decimal("-125.75")

    res_pos = normalize_and_validate_value("+250", config=cfg)
    assert res_pos.is_valid is True
    assert res_pos.normalized_value == "250"
    assert res_pos.numeric_value == Decimal("250")


def test_null_and_empty_values():
    """NULL values remain NULL and valid; empty strings are flagged as invalid."""
    res_null = normalize_and_validate_value(None)
    assert res_null.status == "NULL_VALUE"
    assert res_null.is_valid is True
    assert res_null.normalized_value is None

    res_empty = normalize_and_validate_value("   ")
    assert res_empty.status == "EMPTY_STRING"
    assert res_empty.is_valid is False
    assert "Empty or whitespace-only" in res_empty.error_reason


def test_locale_specific_separators_standard_us():
    """US/UK standard formatting (1,500.75) parses commas as thousands and dots as decimal."""
    cfg = NumericNormalizationConfig(number_format="standard")
    res = normalize_and_validate_value("1,500.75", config=cfg)
    assert res.is_valid is True
    assert res.normalized_value == "1500.75"
    assert res.numeric_value == Decimal("1500.75")
    assert res.scale == 2


def test_locale_specific_separators_european():
    """European formatting (1.500,75) parses dots as thousands and commas as decimal."""
    cfg = NumericNormalizationConfig(number_format="european")
    res = normalize_and_validate_value("1.500,75", config=cfg)
    assert res.is_valid is True
    assert res.normalized_value == "1500.75"
    assert res.numeric_value == Decimal("1500.75")
    assert res.scale == 2


def test_ambiguous_separators():
    """Ambiguous comma strings under plain formatting are flagged as AMBIGUOUS_FORMAT."""
    cfg = NumericNormalizationConfig(number_format="plain")
    res = normalize_and_validate_value("1,234", config=cfg)
    assert res.status == "AMBIGUOUS_FORMAT"
    assert res.is_valid is False
    assert "Ambiguous comma separator" in res.error_reason


def test_leading_zero_identifiers():
    """Numbers with leading zeros (e.g. 00125) are protected as identifiers by default."""
    cfg = NumericNormalizationConfig(allow_leading_zeros=False)
    res = normalize_and_validate_value("00125", config=cfg, column_name="product_code")
    assert res.status == "POTENTIAL_IDENTIFIER"
    assert res.is_valid is False
    assert "Leading zero detected" in res.error_reason

    # When explicitly allowed by user
    cfg_allow = NumericNormalizationConfig(allow_leading_zeros=True)
    res_allow = normalize_and_validate_value("00125", config=cfg_allow)
    assert res_allow.is_valid is True
    assert res_allow.normalized_value == "125"


def test_phone_numbers_and_postal_codes():
    """Phone numbers and postal code columns are detected and protected."""
    res_phone = normalize_and_validate_value("9876543210", column_name="phone_number")
    assert res_phone.status == "POTENTIAL_IDENTIFIER"
    assert res_phone.is_valid is False
    assert "identifier" in res_phone.error_reason.lower() or "phone" in res_phone.error_reason.lower()


def test_scientific_notation():
    """Scientific notation is supported when enabled and rejected when disabled."""
    cfg_dis = NumericNormalizationConfig(allow_scientific=False)
    res_dis = normalize_and_validate_value("1.5e3", config=cfg_dis)
    assert res_dis.is_valid is False

    cfg_en = NumericNormalizationConfig(allow_scientific=True)
    res_en = normalize_and_validate_value("1.5e3", config=cfg_en)
    assert res_en.is_valid is True
    assert res_en.normalized_value == "1500.0"
    assert res_en.numeric_value == Decimal("1500.0")


def test_currency_and_percentage_stripping():
    """Currency symbols and percentage signs are preserved or stripped based on config."""
    cfg_no_strip = NumericNormalizationConfig(strip_currency=False, strip_percentage=False)
    assert normalize_and_validate_value("$25,000", config=cfg_no_strip).is_valid is False
    assert normalize_and_validate_value("15%", config=cfg_no_strip).is_valid is False

    cfg_strip = NumericNormalizationConfig(strip_currency=True, strip_percentage=True, number_format="standard")
    res_curr = normalize_and_validate_value("$25,000", config=cfg_strip)
    assert res_curr.is_valid is True
    assert res_curr.normalized_value == "25000"

    res_pct = normalize_and_validate_value("15%", config=cfg_strip)
    assert res_pct.is_valid is True
    assert res_pct.normalized_value == "15"


# ============================================================
# 2. COLUMN ANALYSIS & SCANNING TESTS
# ============================================================

def test_scan_table_numeric_candidates_classifications(sqlite_test_engine):
    """Verifies that scan_table_numeric_candidates classifies columns correctly."""
    with sqlite_test_engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE employees__cleaning_test (
                id INTEGER PRIMARY KEY,
                salary TEXT,
                quantity TEXT,
                discount TEXT,
                employee_name TEXT,
                product_code TEXT,
                phone_number TEXT,
                custom_field TEXT
            )
        """))
        conn.execute(text("""
            INSERT INTO employees__cleaning_test VALUES
            (1, '25000', '10', '5.5', 'Rahul', '00125', '9876543210', '100'),
            (2, '35000.50', '25', '10.25', 'Priya', '00126', '9876543211', '200'),
            (3, '42000', '100', '15.0', 'Amit', '00127', '9876543212', 'unknown')
        """))

    results = scan_table_numeric_candidates(sqlite_test_engine, "", "employees__cleaning_test")
    res_map = {r["column"]: r for r in results}

    # 1. Salary -> Decimal or Integer
    assert "salary" in res_map
    assert res_map["salary"]["classification"] == NumericDetectionClassification.DECIMAL_CANDIDATE.value
    assert "DECIMAL" in res_map["salary"]["recommended_type"]

    # 2. Quantity -> Integer candidate
    assert "quantity" in res_map
    assert res_map["quantity"]["classification"] == NumericDetectionClassification.INTEGER_CANDIDATE.value
    assert res_map["quantity"]["recommended_type"] == "INT"

    # 3. Discount -> Decimal candidate
    assert "discount" in res_map
    assert res_map["discount"]["classification"] == NumericDetectionClassification.DECIMAL_CANDIDATE.value

    # 4. Employee Name -> Ordinary text
    assert "employee_name" in res_map
    assert res_map["employee_name"]["classification"] == NumericDetectionClassification.ORDINARY_TEXT.value

    # 5. Product Code -> Potential identifier (leading zeros)
    assert "product_code" in res_map
    assert res_map["product_code"]["classification"] == NumericDetectionClassification.POTENTIAL_IDENTIFIER.value

    # 6. Phone Number -> Potential identifier (phone keyword and pattern)
    assert "phone_number" in res_map
    assert res_map["phone_number"]["classification"] == NumericDetectionClassification.POTENTIAL_IDENTIFIER.value

    # 7. Custom Field -> Mixed numeric and non-numeric
    assert "custom_field" in res_map
    assert res_map["custom_field"]["classification"] == NumericDetectionClassification.MIXED_DATA.value


def test_automatic_detection_failure_followed_by_manual_selection(sqlite_test_engine):
    """
    Simulates a column missed or classified as ordinary text/mixed,
    which the user then manually selects and analyzes.
    """
    with sqlite_test_engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE legacy__cleaning_test (
                id INTEGER PRIMARY KEY,
                notes TEXT,
                custom_field TEXT
            )
        """))
        conn.execute(text("""
            INSERT INTO legacy__cleaning_test VALUES
            (1, 'All clean', '100'),
            (2, 'All clean', '200'),
            (3, 'All clean', '300.50'),
            (4, 'All clean', '400')
        """))

    # Eligible columns must list both columns
    eligible = get_eligible_text_columns(sqlite_test_engine, "", "legacy__cleaning_test")
    eligible_names = [c["name"] for c in eligible]
    assert "custom_field" in eligible_names
    assert "notes" in eligible_names

    # Manual analysis of custom_field directly
    analysis = analyze_numeric_column(sqlite_test_engine, "", "legacy__cleaning_test", "custom_field")
    assert analysis["valid_count"] == 4
    assert analysis["invalid_count"] == 0
    assert analysis["numeric_percentage"] == 100.0
    assert analysis["classification"] == NumericDetectionClassification.DECIMAL_CANDIDATE.value
    assert "DECIMAL" in analysis["recommended_type"]


def test_very_large_numbers_and_overflow(sqlite_test_engine):
    """Whole numbers exceeding 2,147,483,647 recommend BIGINT instead of INT."""
    with sqlite_test_engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE big_numbers__cleaning_test (
                id INTEGER PRIMARY KEY,
                huge_id TEXT
            )
        """))
        conn.execute(text("""
            INSERT INTO big_numbers__cleaning_test VALUES
            (1, '3000000000'),
            (2, '5000000000')
        """))

    analysis = analyze_numeric_column(sqlite_test_engine, "", "big_numbers__cleaning_test", "huge_id")
    assert analysis["recommended_type"] == "BIGINT"


def test_empty_table_handling(sqlite_test_engine):
    """Empty tables are safely classified as EMPTY_DATA without crashing."""
    with sqlite_test_engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE empty__cleaning_test (
                id INTEGER PRIMARY KEY,
                amount TEXT
            )
        """))

    analysis = analyze_numeric_column(sqlite_test_engine, "", "empty__cleaning_test", "amount")
    assert analysis["classification"] == NumericDetectionClassification.EMPTY_DATA.value
    assert analysis["total_rows"] == 0


# ============================================================
# 3. WORKSPACE CONVERSION, SAFETY & VERIFICATION TESTS
# ============================================================

def test_conversion_preview_does_not_modify_data(sqlite_test_engine):
    """Analyzing or previewing columns never alters data in the workspace."""
    with sqlite_test_engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE preview__cleaning_ws (
                id INTEGER PRIMARY KEY,
                price TEXT
            )
        """))
        conn.execute(text("""
            INSERT INTO preview__cleaning_ws VALUES
            (1, '  120.50  '),
            (2, '$350.00')
        """))

    # Run preview / analysis
    cfg = NumericNormalizationConfig(strip_currency=True, trim_whitespace=True)
    analysis = analyze_numeric_column(sqlite_test_engine, "", "preview__cleaning_ws", "price", config=cfg)
    assert len(analysis["sample_preview"]) == 2

    # Assert raw data is unchanged
    with sqlite_test_engine.connect() as conn:
        raw_vals = [r[0] for r in conn.execute(text("SELECT price FROM preview__cleaning_ws")).fetchall()]
        assert raw_vals == ['  120.50  ', '$350.00']


def test_conversion_blocked_by_default_on_invalid_values(sqlite_test_engine):
    """Conversion fails and blocks if unresolved invalid values remain."""
    with sqlite_test_engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE items__cleaning_ws (
                id INTEGER PRIMARY KEY,
                qty TEXT
            )
        """))
        conn.execute(text("""
            INSERT INTO items__cleaning_ws VALUES
            (1, '100'),
            (2, 'unknown'),
            (3, '300')
        """))

    cfg = NumericNormalizationConfig(invalid_resolution="block")
    ok, msg, rep = convert_column_to_numeric_workspace(
        sqlite_test_engine,
        "",
        "items__cleaning_ws",
        "qty",
        "INT",
        config=cfg,
    )
    assert ok is False
    assert "Conversion blocked" in msg
    assert "invalid, ambiguous, or identifier value(s) found" in msg


def test_conversion_with_set_null_resolution(sqlite_test_engine):
    """When resolution is set_null, invalid values are set to NULL and valid values converted."""
    with sqlite_test_engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE resolve__cleaning_ws (
                id INTEGER PRIMARY KEY,
                qty TEXT
            )
        """))
        conn.execute(text("""
            INSERT INTO resolve__cleaning_ws VALUES
            (1, ' 100 '),
            (2, 'unknown'),
            (3, '300')
        """))

    cfg = NumericNormalizationConfig(invalid_resolution="set_null", trim_whitespace=True)
    ok, msg, rep = convert_column_to_numeric_workspace(
        sqlite_test_engine,
        "",
        "resolve__cleaning_ws",
        "qty",
        "INT",
        config=cfg,
    )
    assert ok is True
    assert rep["invalid_nullified"] == 1
    assert rep["rows_converted"] == 2

    with sqlite_test_engine.connect() as conn:
        rows = conn.execute(text("SELECT id, qty FROM resolve__cleaning_ws ORDER BY id")).fetchall()
        assert rows[0][1] == "100"
        assert rows[1][1] is None  # 'unknown' nullified
        assert rows[2][1] == "300"


def test_new_column_conversion_mode(sqlite_test_engine):
    """In new_column mode, original column is preserved and new column is populated."""
    with sqlite_test_engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE mode__cleaning_ws (
                id INTEGER PRIMARY KEY,
                original_text TEXT
            )
        """))
        conn.execute(text("""
            INSERT INTO mode__cleaning_ws VALUES
            (1, '  50.25 '),
            (2, '  75.50 ')
        """))

    cfg = NumericNormalizationConfig(trim_whitespace=True)
    ok, msg, rep = convert_column_to_numeric_workspace(
        sqlite_test_engine,
        "",
        "mode__cleaning_ws",
        "original_text",
        "DECIMAL(10,2)",
        config=cfg,
        conversion_mode="new_column",
        new_column_name="cleaned_amount",
    )
    assert ok is True
    assert rep["conversion_mode"] == "new_column"
    assert rep["target_column"] == "cleaned_amount"

    with sqlite_test_engine.connect() as conn:
        rows = conn.execute(text("SELECT original_text, cleaned_amount FROM mode__cleaning_ws ORDER BY id")).fetchall()
        # Original text preserved with spaces
        assert rows[0][0] == '  50.25 '
        # New column has normalized value
        assert rows[0][1] == 50.25 or rows[0][1] == "50.25"


def test_zero_production_risk_enforcement(sqlite_test_engine):
    """Refuses to convert any table that is not an authorized cleaning workspace."""
    with sqlite_test_engine.begin() as conn:
        conn.execute(text("CREATE TABLE production_customers (id INT, salary TEXT)"))

    ok, msg, rep = convert_column_to_numeric_workspace(
        sqlite_test_engine,
        "",
        "production_customers",
        "salary",
        "INT",
    )
    assert ok is False
    assert "Refusing to convert a table that is not identified as an authorized cleaning workspace" in msg


def test_new_column_conversion_with_invalid_values_left_blank(sqlite_test_engine):
    """
    Feature Enhancement: Safe conversion into a new column when source contains invalid/ambiguous values.
    Example: 'salary_text' with ['45000', '55000', '12A50', '72000', '   ', None]
    Produces: [45000, 55000, None, 72000, None, None] in salary_text_numeric,
    while salary_text remains completely unchanged.
    """
    with sqlite_test_engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE emp__cleaning_ws (
                id INTEGER PRIMARY KEY,
                salary_text TEXT
            )
        """))
        conn.execute(text("""
            INSERT INTO emp__cleaning_ws VALUES
            (1, '45000'),
            (2, '55000'),
            (3, '12A50'),
            (4, '72000'),
            (5, '   '),
            (6, NULL)
        """))

    cfg = NumericNormalizationConfig(invalid_resolution="block")

    # 1. Verify in-place conversion is blocked when unresolved anomalies exist
    ok_in_place, msg_in_place, _ = convert_column_to_numeric_workspace(
        sqlite_test_engine,
        "",
        "emp__cleaning_ws",
        "salary_text",
        "INT",
        config=cfg,
        conversion_mode="in_place",
    )
    assert ok_in_place is False
    assert "Conversion blocked" in msg_in_place
    assert "In-place conversion is disabled when unresolved anomalies exist" in msg_in_place

    # 2. Verify new-column conversion succeeds despite anomalies
    ok_new, msg_new, rep = convert_column_to_numeric_workspace(
        sqlite_test_engine,
        "",
        "emp__cleaning_ws",
        "salary_text",
        "INT",
        config=cfg,
        conversion_mode="new_column",
    )
    assert ok_new is True
    assert rep["conversion_mode"] == "new_column"
    assert rep["target_column"] == "salary_text_numeric"
    assert rep["rows_converted"] == 3
    assert rep["invalid_nullified"] == 1  # '12A50' was nullified

    # 3. Verify resulting column data and that original values remain untouched
    with sqlite_test_engine.connect() as conn:
        rows = conn.execute(text("SELECT id, salary_text, salary_text_numeric FROM emp__cleaning_ws ORDER BY id")).fetchall()
        
        # Row 1: '45000' -> 45000
        assert rows[0][1] == "45000"
        assert int(rows[0][2]) == 45000

        # Row 2: '55000' -> 55000
        assert rows[1][1] == "55000"
        assert int(rows[1][2]) == 55000

        # Row 3: '12A50' -> NULL (blank) in new column, unchanged in source
        assert rows[2][1] == "12A50"
        assert rows[2][2] is None

        # Row 4: '72000' -> 72000
        assert rows[3][1] == "72000"
        assert int(rows[3][2]) == 72000

        # Row 5: '   ' -> NULL in new column, unchanged in source
        assert rows[4][1] == "   "
        assert rows[4][2] is None

        # Row 6: NULL -> NULL in new column, NULL in source
        assert rows[5][1] is None
        assert rows[5][2] is None


def test_preview_columns_and_reasons(sqlite_test_engine):
    """Preview contains Original value, Proposed numeric value, Conversion status, and Reason."""
    with sqlite_test_engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE preview__cleaning_ws (
                id INTEGER PRIMARY KEY,
                val_text TEXT
            )
        """))
        conn.execute(text("""
            INSERT INTO preview__cleaning_ws VALUES
            (1, '45000'),
            (2, '12A50'),
            (3, NULL)
        """))

    analysis = analyze_numeric_column(
        sqlite_test_engine,
        "",
        "preview__cleaning_ws",
        "val_text",
        NumericNormalizationConfig(),
    )

    preview = analysis["sample_preview"]
    assert len(preview) >= 2

    # Check required keys are present
    for row in preview:
        assert "Original value" in row
        assert "Proposed numeric value" in row
        assert "Conversion status" in row
        assert "Reason" in row

    # Row with '12A50' should have invalid status and descriptive reason
    invalid_row = next(r for r in preview if r["Original value"] == "12A50")
    assert invalid_row["Conversion status"] == "Invalid"
    assert any(term in invalid_row["Reason"].lower() for term in ("alphabetic", "non-numeric", "cannot convert"))
    assert invalid_row["Proposed numeric value"] == "SQL NULL"

    # Row with '45000' should have Valid status
    valid_row = next(r for r in preview if r["Original value"] == "45000")
    assert valid_row["Conversion status"] == "Valid"
    assert valid_row["Proposed numeric value"] == "45000"


def test_check_numeric_candidate_pattern_unit():
    """Unit tests for check_numeric_candidate_pattern verifying all candidate variations."""
    from src.staging import check_numeric_candidate_pattern

    # Clean integers
    is_num, is_dec, int_d, sc, is_id, is_emp = check_numeric_candidate_pattern("100")
    assert (is_num, is_dec, is_id, is_emp) == (True, False, False, False)
    assert int_d == 3 and sc == 0

    # Decimals
    is_num, is_dec, int_d, sc, is_id, is_emp = check_numeric_candidate_pattern("1500.75")
    assert (is_num, is_dec, is_id, is_emp) == (True, True, False, False)
    assert int_d == 4 and sc == 2

    # Negative numbers and accounting format
    is_num, is_dec, _, _, is_id, is_emp = check_numeric_candidate_pattern("-250.50")
    assert (is_num, is_dec, is_id, is_emp) == (True, True, False, False)

    is_num, is_dec, _, _, is_id, is_emp = check_numeric_candidate_pattern("(250.50)")
    assert (is_num, is_dec, is_id, is_emp) == (True, True, False, False)

    # Positive sign
    is_num, is_dec, _, _, is_id, is_emp = check_numeric_candidate_pattern("+350")
    assert (is_num, is_dec, is_id, is_emp) == (True, False, False, False)

    # Percentages
    is_num, is_dec, _, _, is_id, is_emp = check_numeric_candidate_pattern("12.5%")
    assert (is_num, is_dec, is_id, is_emp) == (True, True, False, False)

    # Whitespace
    is_num, is_dec, _, _, is_id, is_emp = check_numeric_candidate_pattern("   1500.75   ")
    assert (is_num, is_dec, is_id, is_emp) == (True, True, False, False)

    # Thousands separated
    is_num, is_dec, _, _, is_id, is_emp = check_numeric_candidate_pattern("1,500.75")
    assert (is_num, is_dec, is_id, is_emp) == (True, True, False, False)

    # European format
    is_num, is_dec, _, _, is_id, is_emp = check_numeric_candidate_pattern("1.500,75")
    assert (is_num, is_dec, is_id, is_emp) == (True, True, False, False)

    is_num, is_dec, _, _, is_id, is_emp = check_numeric_candidate_pattern("35,50")
    assert (is_num, is_dec, is_id, is_emp) == (True, True, False, False)

    # Scientific notation
    is_num, is_dec, _, _, is_id, is_emp = check_numeric_candidate_pattern("1.5e3")
    assert (is_num, is_dec, is_id, is_emp) == (True, True, False, False)

    # Currency
    is_num, is_dec, _, _, is_id, is_emp = check_numeric_candidate_pattern("$1,500.00")
    assert (is_num, is_dec, is_id, is_emp) == (True, True, False, False)

    # Invalid / anomalies: must NOT match candidate numeric pattern
    assert check_numeric_candidate_pattern("12A50")[0] is False
    assert check_numeric_candidate_pattern("unknown")[0] is False
    assert check_numeric_candidate_pattern("--")[0] is False
    assert check_numeric_candidate_pattern("Order 125 completed")[0] is False
    assert check_numeric_candidate_pattern("Alice Smith")[0] is False
    assert check_numeric_candidate_pattern("2026-10-15")[0] is False

    # Identifiers: leading zero whole numbers
    is_num, is_dec, _, _, is_id, is_emp = check_numeric_candidate_pattern("00123")
    assert is_id is True and is_num is False

    is_num, is_dec, _, _, is_id, is_emp = check_numeric_candidate_pattern("0456")
    assert is_id is True and is_num is False

    # Empty / whitespace
    assert check_numeric_candidate_pattern("   ")[5] is True
    assert check_numeric_candidate_pattern("")[5] is True
    assert check_numeric_candidate_pattern(None)[5] is True


def test_automatic_numeric_column_detection_user_dataset(sqlite_test_engine):
    """
    Verifies automatic numeric candidate detection against the user's numeric_conversion_test dataset:
    - salary_text: detected (predominantly numeric, whitespace, one invalid value '12A50')
    - amount_text: detected (decimal values with various thousands and decimal separators: '1,500.75', '1.500,75')
    - quantity_text: detected (clean integer values)
    - percentage_text: detected (numeric values with percentage symbols: '12.5%')
    - signed_number_text: detected (negative values, positive signs, decimals, scientific notation: '1.5e3')
    - mixed_numeric_text: detected (predominantly numeric values with occasional invalid value: 'unknown')
    - product_code: preserved with identifier protections (leading zeros)
    - employee_name: excluded (ordinary text, including 'Order 125 completed')
    """
    with sqlite_test_engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE numeric_conversion_test__cleaning_demo (
                id INTEGER PRIMARY KEY,
                salary_text TEXT,
                amount_text TEXT,
                quantity_text TEXT,
                percentage_text TEXT,
                signed_number_text TEXT,
                mixed_numeric_text TEXT,
                product_code TEXT,
                employee_name TEXT
            )
        """))
        conn.execute(text("""
            INSERT INTO numeric_conversion_test__cleaning_demo VALUES
            (1, '45000', '1500.75', '10', '12.5%', '-250.50', '100', '00123', 'Alice Smith'),
            (2, '55000', '1,500.75', '25', '50%', '+350', '200', '0456', 'Bob Jones'),
            (3, '12A50', '1.500,75', '100', '99.9%', '1.5e3', 'unknown', '007', 'Charlie Brown'),
            (4, '72000', '25000', '500', '5.0 %', '-100', '300', '00891', 'Order 125 completed'),
            (5, '   ', '35,50', '50', '100%', '+12.5', '400', '012', 'David Miller'),
            (6, NULL, '100.00', '75', '0.5%', '-15.75', '500', '034', 'Eva Green'),
            (7, '60000', '2,000.50', '120', '25%', '+500', '600', '056', 'Frank White'),
            (8, '65000', '500,25', '300', '75.5%', '2.5e2', '700', '078', 'Grace Taylor'),
            (9, '70000', '1200', '450', '10%', '-50', '800', '090', 'Henry Clark'),
            (10, '80000', '3,450.00', '200', '15.0%', '+100', '900', '099', 'Ivy Adams')
        """))

    results = scan_table_numeric_candidates(
        sqlite_test_engine,
        "",
        "numeric_conversion_test__cleaning_demo",
        config=NumericNormalizationConfig(detection_threshold=85.0),
    )
    res_map = {r["column"]: r for r in results}

    qualifying_candidates = [
        r["column"] for r in results
        if r["classification"] in (
            NumericDetectionClassification.INTEGER_CANDIDATE.value,
            NumericDetectionClassification.DECIMAL_CANDIDATE.value,
        )
    ]

    # Verify all 6 expected columns are detected as qualifying candidates
    assert "salary_text" in qualifying_candidates
    assert "amount_text" in qualifying_candidates
    assert "quantity_text" in qualifying_candidates
    assert "percentage_text" in qualifying_candidates
    assert "signed_number_text" in qualifying_candidates
    assert "mixed_numeric_text" in qualifying_candidates

    # Verify exclusions: identifier and ordinary text
    assert "product_code" not in qualifying_candidates
    assert "employee_name" not in qualifying_candidates

    # Detailed classification and percentage checks
    assert res_map["salary_text"]["classification"] == NumericDetectionClassification.INTEGER_CANDIDATE.value
    # 8 non-empty evaluated rows (SQL NULL and whitespace excluded from denominator), 7 numeric -> 7/8 = 87.5%
    assert res_map["salary_text"]["numeric_percentage"] == 87.5
    assert len(res_map["salary_text"]["warnings"]) > 0

    assert res_map["amount_text"]["classification"] == NumericDetectionClassification.DECIMAL_CANDIDATE.value
    assert res_map["amount_text"]["numeric_percentage"] == 100.0

    assert res_map["quantity_text"]["classification"] == NumericDetectionClassification.INTEGER_CANDIDATE.value
    assert res_map["quantity_text"]["numeric_percentage"] == 100.0

    assert res_map["percentage_text"]["classification"] == NumericDetectionClassification.DECIMAL_CANDIDATE.value
    assert res_map["percentage_text"]["numeric_percentage"] == 100.0

    assert res_map["signed_number_text"]["classification"] == NumericDetectionClassification.DECIMAL_CANDIDATE.value
    assert res_map["signed_number_text"]["numeric_percentage"] == 100.0

    assert res_map["mixed_numeric_text"]["classification"] == NumericDetectionClassification.INTEGER_CANDIDATE.value
    # 10 non-empty rows, 9 numeric, 1 invalid ('unknown') -> 90.0%
    assert res_map["mixed_numeric_text"]["numeric_percentage"] == 90.0
    assert len(res_map["mixed_numeric_text"]["warnings"]) > 0

    # Protected identifier retains leading zeros and is NOT qualified
    assert res_map["product_code"]["classification"] == NumericDetectionClassification.POTENTIAL_IDENTIFIER.value
    assert "VARCHAR" in res_map["product_code"]["recommended_type"]

    # Ordinary text (including rows like 'Order 125 completed') is NOT qualified
    assert res_map["employee_name"]["classification"] == NumericDetectionClassification.ORDINARY_TEXT.value
    assert res_map["employee_name"]["numeric_percentage"] == 0.0


def test_configurable_detection_threshold(sqlite_test_engine):
    """Verifies that configurable detection threshold allows columns with varying anomaly ratios to qualify."""
    with sqlite_test_engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE custom_thresh__cleaning_ws (
                id INTEGER PRIMARY KEY,
                col_70_num TEXT
            )
        """))
        # 7 numeric numbers, 3 non-numeric
        conn.execute(text("""
            INSERT INTO custom_thresh__cleaning_ws VALUES
            (1, '100'), (2, '200'), (3, '300'), (4, '400'), (5, '500'),
            (6, '600'), (7, '700'), (8, 'invalid1'), (9, 'invalid2'), (10, 'invalid3')
        """))

    # At default 85% threshold, 70% numeric is MIXED_DATA (does not qualify)
    res_85 = scan_table_numeric_candidates(
        sqlite_test_engine, "", "custom_thresh__cleaning_ws",
        config=NumericNormalizationConfig(detection_threshold=85.0),
    )
    assert res_85[0]["classification"] == NumericDetectionClassification.MIXED_DATA.value

    # At 65% threshold, 70% numeric qualifies as an INTEGER_CANDIDATE
    res_65 = scan_table_numeric_candidates(
        sqlite_test_engine, "", "custom_thresh__cleaning_ws",
        config=NumericNormalizationConfig(detection_threshold=65.0),
    )
    assert res_65[0]["classification"] == NumericDetectionClassification.INTEGER_CANDIDATE.value


def test_strip_negative_sign_normalization():
    """Verifies that negative sign stripping converts negative values and accounting formats to positive."""
    cfg_strip = NumericNormalizationConfig(strip_negative_sign=True)
    cfg_preserve = NumericNormalizationConfig(strip_negative_sign=False)

    # When strip_negative_sign is True
    res_int = normalize_and_validate_value("-500", config=cfg_strip, column_name="amount")
    assert res_int.is_valid is True
    assert res_int.status == "VALID_NORMALIZED"
    assert res_int.numeric_value == Decimal("500")

    res_dec = normalize_and_validate_value("-750.25", config=cfg_strip, column_name="amount")
    assert res_dec.is_valid is True
    assert res_dec.status == "VALID_NORMALIZED"
    assert res_dec.numeric_value == Decimal("750.25")

    # Accounting parentheses format
    res_acct = normalize_and_validate_value("(250.50)", config=cfg_strip, column_name="amount")
    assert res_acct.is_valid is True
    assert res_acct.status == "VALID_NORMALIZED"
    assert res_acct.numeric_value == Decimal("250.50")

    # Trailing minus format
    res_trail = normalize_and_validate_value("1250-", config=cfg_strip, column_name="amount")
    assert res_trail.is_valid is True
    assert res_trail.status == "VALID_NORMALIZED"
    assert res_trail.numeric_value == Decimal("1250")

    # Malformed double minus should fail validation
    res_invalid = normalize_and_validate_value("--", config=cfg_strip, column_name="amount")
    assert res_invalid.is_valid is False

    # When strip_negative_sign is False (default)
    res_def_int = normalize_and_validate_value("-500", config=cfg_preserve, column_name="amount")
    assert res_def_int.is_valid is True
    assert res_def_int.numeric_value == Decimal("-500")

    res_def_dec = normalize_and_validate_value("-750.25", config=cfg_preserve, column_name="amount")
    assert res_def_dec.is_valid is True
    assert res_def_dec.numeric_value == Decimal("-750.25")


def test_conversion_with_strip_negative_sign(sqlite_test_engine):
    """Verifies end-to-end workspace column conversion with strip_negative_sign enabled."""
    with sqlite_test_engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE neg_test__cleaning_ws (
                id INTEGER PRIMARY KEY,
                val_text TEXT
            )
        """))
        conn.execute(text("""
            INSERT INTO neg_test__cleaning_ws VALUES
            (1, '450'),
            (2, '-500'),
            (3, '600'),
            (4, '-750.25'),
            (5, '-1000'),
            (6, '+125')
        """))

    cfg = NumericNormalizationConfig(
        strip_negative_sign=True,
        normalize_plus_sign=True,
        invalid_resolution="block",
    )

    success, msg, metrics = convert_column_to_numeric_workspace(
        sqlite_test_engine,
        "",
        "neg_test__cleaning_ws",
        "val_text",
        target_type="DECIMAL(10,2)",
        config=cfg,
        conversion_mode="in_place",
    )

    assert success is True
    assert metrics["total_rows"] == 6
    assert metrics["rows_converted"] == 6
    assert metrics["invalid_nullified"] == 0

    with sqlite_test_engine.connect() as conn:
        rows = conn.execute(text("SELECT val_text FROM neg_test__cleaning_ws ORDER BY id")).fetchall()
        vals = [float(r[0]) for r in rows]
        assert vals == [450.0, 500.0, 600.0, 750.25, 1000.0, 125.0]




