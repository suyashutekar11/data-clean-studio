from typing import Optional, List, Dict, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class ParseResult:
    row_id: str
    original: str
    rule_matched: str
    format: str
    parsed: Optional[datetime]
    confidence: float
    status: str
    ambiguity_type: str = ""
    suggested_interpretation: str = ""
    reasoning: str = ""


@dataclass
class ColumnAnalysis:
    column: str
    total_rows: int
    sample_size: int
    rule_coverage: float
    format_distribution: Dict[str, int]
    column_format: str
    pivot_year: int
    parse_results: List[ParseResult]
    escalation_candidates: List[ParseResult]
    invalid_records: List[ParseResult]
    non_date_records: List[ParseResult]


MONTH_NAMES = {
    'jan': 1, 'january': 1,
    'feb': 2, 'february': 2,
    'mar': 3, 'march': 3,
    'apr': 4, 'april': 4,
    'may': 5,
    'jun': 6, 'june': 6,
    'jul': 7, 'july': 7,
    'aug': 8, 'august': 8,
    'sep': 9, 'sept': 9, 'september': 9,
    'oct': 10, 'october': 10,
    'nov': 11, 'november': 11,
    'dec': 12, 'december': 12,
}

SEPARATOR_PATTERN = re.compile(r'[\-/\.]')
TIMESTAMP_PATTERN = re.compile(r'\s+\d{1,2}:\d{2}(:\d{2})?$')

ISO_PATTERNS = [
    (re.compile(r'^\d{4}-\d{2}-\d{2}$'), '%Y-%m-%d'),
    (re.compile(r'^\d{4}/\d{2}/\d{2}$'), '%Y/%m/%d'),
    (re.compile(r'^\d{4}\.\d{2}\.\d{2}$'), '%Y.%m.%d'),
    (re.compile(r'^\d{8}$'), '%Y%m%d'),
]

TEXT_PATTERNS = [
    # Day Month Year (full month name)
    (re.compile(r'^\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}$'), '%d %B %Y'),
    # Month Day, Year (full month name)
    (re.compile(r'^[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}$'), '%B %d, %Y'),
    # Day Mon Year (abbreviated month)
    (re.compile(r'^\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}$'), '%d %b %Y'),
    # Mon Day, Year (abbreviated month)
    (re.compile(r'^[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}$'), '%b %d, %Y'),
    # Day-Mon-Year
    (re.compile(r'^\d{1,2}-[A-Za-z]{3}-\d{4}$'), '%d-%b-%Y'),
    # Mon-Day-Year
    (re.compile(r'^[A-Za-z]{3}-\d{1,2}-\d{4}$'), '%b-%d-%Y'),
]

def _try_parse(value: str, fmt: str) -> Optional[datetime]:
    try:
        return datetime.strptime(value, fmt)
    except ValueError:
        return None


def _is_valid_date(dt: datetime) -> bool:
    try:
        datetime(dt.year, dt.month, dt.day)
        return True
    except ValueError:
        return False


def _get_month_max_day(year: int, month: int) -> int:
    if month == 2:
        return 29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28
    if month in [4, 6, 9, 11]:
        return 30
    return 31


def rule_iso_format(value: str, row_id: str) -> Optional[ParseResult]:
    clean_value = value.strip()
    for pattern, fmt in ISO_PATTERNS:
        if pattern.match(clean_value):
            parsed = _try_parse(clean_value, fmt)
            if parsed and _is_valid_date(parsed):
                return ParseResult(
                    row_id=row_id,
                    original=value,
                    rule_matched="R1_ISO",
                    format="YYYY-MM-DD" if '-' in fmt else "YYYY/MM/DD" if '/' in fmt else "YYYY.MM.DD" if '.' in fmt else "YYYYMMDD",
                    parsed=parsed,
                    confidence=1.0,
                    status="RESOLVED",
                    reasoning=f"Matched ISO format {fmt}"
                )
    return None


def rule_month_name(value: str, row_id: str) -> Optional[ParseResult]:
    clean_value = value.strip()
    for pattern, fmt in TEXT_PATTERNS:
        if pattern.match(clean_value):
            parsed = _try_parse(clean_value, fmt)
            if parsed and _is_valid_date(parsed):
                # Determine day-first vs month-first based on format string
                if fmt.lstrip().startswith('%d'):
                    fmt_label = "DD-MMM-YYYY"
                else:
                    fmt_label = "MMM-DD-YYYY"
                return ParseResult(
                    row_id=row_id,
                    original=value,
                    rule_matched="R2_MONTH_NAME",
                    format=fmt_label,
                    parsed=parsed,
                    confidence=1.0,
                    status="RESOLVED",
                    reasoning=f"Matched month name format {fmt}"
                )
    return None


def rule_year_anchor(value: str, row_id: str) -> Optional[ParseResult]:
    clean_value = value.strip()
    parts = SEPARATOR_PATTERN.split(clean_value)
    if len(parts) != 3:
        return None
    
    year_pos = -1
    year_val = None
    for i, part in enumerate(parts):
        if part.isdigit() and len(part) == 4:
            y = int(part)
            if 1900 <= y <= 2099:
                year_pos = i
                year_val = y
                break
    
    if year_pos == -1:
        return None
    
    other_parts = [int(p) for p in parts if p != str(year_val)]
    if len(other_parts) != 2:
        return None
    
    if year_pos == 0:
        fmt = "YYYY-MM-DD"
        day, month = other_parts[1], other_parts[0]
    else:
        day, month = other_parts[0], other_parts[1]
        if day > 12 and month <= 12:
            fmt = "DD-MM-YYYY"
        elif month > 12 and day <= 12:
            fmt = "MM-DD-YYYY"
        else:
            fmt = "DD-MM-YYYY"
    
    try:
        parsed = datetime(year_val, month, day)
        if not _is_valid_date(parsed):
            return ParseResult(
                row_id=row_id,
                original=value,
                rule_matched="R3_YEAR_ANCHOR",
                format=fmt,
                parsed=parsed,
                confidence=0.0,
                status="INVALID",
                reasoning=f"Invalid date: {value}"
            )
        return ParseResult(
            row_id=row_id,
            original=value,
            rule_matched="R3_YEAR_ANCHOR",
            format=fmt,
            parsed=parsed,
            confidence=0.9,
            status="RESOLVED",
            reasoning=f"4-digit year at position {year_pos+1}"
        )
    except ValueError:
        return ParseResult(
            row_id=row_id,
            original=value,
            rule_matched="R3_YEAR_ANCHOR",
            format=fmt,
            parsed=None,
            confidence=0.0,
            status="INVALID",
            reasoning=f"Invalid date: {value}"
        )


def rule_yy_mm_dd(value: str, row_id: str) -> Optional[ParseResult]:
    """Detect YY/MM/DD or YY-MM-DD where first part looks like a year (00-99) 
    and second part 1-12, third 1-31. Prefer when first part >12."""
    clean_value = value.strip()
    parts = SEPARATOR_PATTERN.split(clean_value)
    if len(parts) != 3:
        return None
    if not all(p.isdigit() for p in parts):
        return None
    # Determine separator used
    sep = None
    for ch in clean_value:
        if ch in "-/.":
            sep = ch
            break
    if not sep:
        return None
    # Ensure consistent separator
    if clean_value.count(sep) != 2:
        return None
    # All parts two digits? allow 1-2 digits for year, month, day
    try:
        y = int(parts[0])
        m = int(parts[1])
        d = int(parts[2])
    except ValueError:
        return None
    # Basic ranges
    if not (0 <= y <= 99 and 1 <= m <= 12 and 1 <= d <= 31):
        return None
    # Heuristic: if first part >12, treat as year-first (YY/MM/DD)
    if y > 12:
        fmt = f"YY{sep}MM{sep}DD"
        # Resolve year using pivot later
        parsed = datetime(2000 + y if y < 50 else 1900 + y, m, d)
        if not _is_valid_date(parsed):
            return None
        return ParseResult(
            row_id=row_id,
            original=value,
            rule_matched="R3_YY_MM_DD",
            format=fmt,
            parsed=parsed,
            confidence=0.9,
            status="RESOLVED",
            reasoning=f"Year-first pattern with first part >12"
        )
    return None


def rule_unambiguous_daymonth(value: str, row_id: str) -> Optional[ParseResult]:
    clean_value = value.strip()
    parts = SEPARATOR_PATTERN.split(clean_value)
    if len(parts) != 3:
        return None
    
    if not all(p.isdigit() for p in parts):
        return None
    
    nums = [int(p) for p in parts]
    has_4digit = any(len(p) == 4 and 1900 <= int(p) <= 2099 for p in parts)
    if has_4digit:
        return None
    
    pos1, pos2, pos3 = nums
    if pos1 > 12 and pos2 <= 12:
        day, month, year = pos1, pos2, pos3
        fmt = "DD-MM-YY"
        confidence = 0.95
    elif pos2 > 12 and pos1 <= 12:
        month, day, year = pos1, pos2, pos3
        fmt = "MM-DD-YY"
        confidence = 0.95
    else:
        return None
    
    try:
        parsed = datetime(2000 + year if year < 50 else 1900 + year, month, day)
        if not _is_valid_date(parsed):
            return ParseResult(
                row_id=row_id,
                original=value,
                rule_matched="R4_UNAMBIGUOUS",
                format=fmt,
                parsed=parsed,
                confidence=0.0,
                status="INVALID",
                reasoning=f"Invalid date: {value}"
            )
        return ParseResult(
            row_id=row_id,
            original=value,
            rule_matched="R4_UNAMBIGUOUS",
            format=fmt,
            parsed=parsed,
            confidence=confidence,
            status="RESOLVED",
            reasoning=f"Value >12 at position {1 if pos1 > 12 else 2} resolves day/month"
        )
    except ValueError:
        return ParseResult(
            row_id=row_id,
            original=value,
            rule_matched="R4_UNAMBIGUOUS",
            format=fmt,
            parsed=None,
            confidence=0.0,
            status="INVALID",
            reasoning=f"Invalid date: {value}"
        )


def rule_timestamp(value: str, row_id: str) -> Optional[ParseResult]:
    clean_value = value.strip()
    match = TIMESTAMP_PATTERN.search(clean_value)
    if not match:
        return None
    
    date_part = clean_value[:match.start()].strip()
    for pattern, fmt in ISO_PATTERNS:
        if pattern.match(date_part):
            parsed = _try_parse(date_part, fmt)
            if parsed and _is_valid_date(parsed):
                return ParseResult(
                    row_id=row_id,
                    original=value,
                    rule_matched="R7_TIMESTAMP",
                    format="YYYY-MM-DD",
                    parsed=parsed,
                    confidence=1.0,
                    status="RESOLVED",
                    reasoning="Extracted date from timestamp"
                )
    return None


def rule_text_formats(value: str, row_id: str) -> Optional[ParseResult]:
    return rule_month_name(value, row_id)


def parse_value(value: str, row_id: str) -> ParseResult:
    if not value or not value.strip():
        return ParseResult(
            row_id=row_id,
            original=value,
            rule_matched="",
            format="",
            parsed=None,
            confidence=0.0,
            status="NON_DATE",
            reasoning="Empty or null value"
        )
    
    for rule_func in [rule_iso_format, rule_month_name, rule_timestamp, 
                      rule_year_anchor, rule_yy_mm_dd, rule_unambiguous_daymonth]:
        result = rule_func(value, row_id)
        if result:
            return result
    
    return ParseResult(
        row_id=row_id,
        original=value,
        rule_matched="",
        format="",
        parsed=None,
        confidence=0.0,
        status="ESCALATE",
        ambiguity_type="UNRESOLVED",
        reasoning="No rule matched - escalate to AI"
    )


def _infer_column_context(results: List[ParseResult]) -> Tuple[str, int]:
    format_counts = {}
    year_samples = []
    
    for r in results:
        if r.status == "RESOLVED" and r.format:
            format_counts[r.format] = format_counts.get(r.format, 0) + 1
        if r.parsed and r.parsed.year >= 1900:
            year_samples.append(r.parsed.year)
    
    if not format_counts:
        return "DD-MM-YYYY", 50
    
    dominant_format = max(format_counts, key=format_counts.get)
    
    pivot = 50
    if year_samples:
        min_year, max_year = min(year_samples), max(year_samples)
        if max_year - min_year < 100 and min_year >= 2000:
            pivot = 50
        elif max_year - min_year < 100 and max_year <= 1999:
            pivot = 50
    
    return dominant_format, pivot


def _resolve_ambiguous(results: List[ParseResult], column_format: str, pivot: int) -> List[ParseResult]:
    resolved = []
    for r in results:
        if r.status != "ESCALATE" or r.ambiguity_type != "UNRESOLVED":
            resolved.append(r)
            continue
        
        clean = r.original.strip()
        parts = SEPARATOR_PATTERN.split(clean)
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            nums = [int(p) for p in parts]
            has_4digit = any(len(p) == 4 and 1900 <= int(p) <= 2099 for p in parts)
            
            if not has_4digit:
                if column_format.startswith("DD"):
                    day, month, year = nums[0], nums[1], nums[2]
                else:
                    month, day, year = nums[0], nums[1], nums[2]
                
                try:
                    full_year = 2000 + year if year < pivot else 1900 + year
                    parsed = datetime(full_year, month, day)
                    if _is_valid_date(parsed):
                        r.parsed = parsed
                        r.format = column_format
                        r.confidence = 0.7
                        r.status = "RESOLVED"
                        r.rule_matched = "R5_COLUMN_CONTEXT"
                        r.reasoning = f"Resolved via column context: {column_format}"
                        resolved.append(r)
                        continue
                except ValueError:
                    pass
        
        resolved.append(r)
    return resolved


def _validate_results(results: List[ParseResult]) -> List[ParseResult]:
    validated = []
    for r in results:
        if r.status == "RESOLVED" and r.parsed:
            if not _is_valid_date(r.parsed):
                r.status = "INVALID"
                r.confidence = 0.0
                r.reasoning = "Invalid date (e.g., 31/02/2026)"
            validated.append(r)
        else:
            validated.append(r)
    return validated


def analyze_column(values: List[Tuple[str, str]]) -> ColumnAnalysis:
    parse_results = [parse_value(val, rid) for rid, val in values]
    
    resolved = [r for r in parse_results if r.status == "RESOLVED"]
    escalation = [r for r in parse_results if r.status == "ESCALATE"]
    invalid = [r for r in parse_results if r.status == "INVALID"]
    non_date = [r for r in parse_results if r.status == "NON_DATE"]
    
    format_dist = {}
    for r in resolved:
        format_dist[r.format] = format_dist.get(r.format, 0) + 1
    
    column_format, pivot = _infer_column_context(resolved)
    
    parse_results = _resolve_ambiguous(parse_results, column_format, pivot)
    parse_results = _validate_results(parse_results)
    
    resolved = [r for r in parse_results if r.status == "RESOLVED"]
    escalation = [r for r in parse_results if r.status == "ESCALATE"]
    invalid = [r for r in parse_results if r.status == "INVALID"]
    non_date = [r for r in parse_results if r.status == "NON_DATE"]
    
    rule_coverage = len(resolved) / len(parse_results) if parse_results else 0.0
    
    return ColumnAnalysis(
        column="",
        total_rows=len(values),
        sample_size=len(values),
        rule_coverage=rule_coverage,
        format_distribution=format_dist,
        column_format=column_format,
        pivot_year=pivot,
        parse_results=parse_results,
        escalation_candidates=escalation,
        invalid_records=invalid,
        non_date_records=non_date,
    )


def transform_value(parsed: datetime, target_format: str) -> str:
    fmt_map = {
        "YYYY-MM-DD": "%Y-%m-%d",
        "DD-MM-YYYY": "%d-%m-%Y",
        "MM-DD-YYYY": "%m-%d-%Y",
        "DD/MM/YYYY": "%d/%m/%Y",
        "MM/DD/YYYY": "%m/%d/%Y",
        "YYYY/MM/DD": "%Y/%m/%d",
        "DD.MM.YYYY": "%d.%m.%Y",
        "DD-MMM-YYYY": "%d-%b-%Y",
        "DD-MMM-YY": "%d-%b-%y",
        "MMM-DD-YYYY": "%b-%d-%Y",
    }
    fmt = fmt_map.get(target_format, "%Y-%m-%d")
    return parsed.strftime(fmt)