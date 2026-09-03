"""
detection.py

Each detect_* function inspects a DataFrame for one class of data quality
issue and returns a list of "issue dicts" in a consistent shape:

    {
        "row_index": int | None,   # None for dataset-level issues
        "column": str | None,      # None for row-level issues spanning columns
        "issue_type": str,
        "severity": "low" | "medium" | "high",
        "details": str,
    }

Keeping the schema consistent means the UI, reporting, and cleaning layers
can all consume issues generically (filter by severity, group by column,
count by type) without knowing which detector produced them.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from rapidfuzz import fuzz

Issue = Dict[str, Any]

# --- Regex patterns used by detect_format_inconsistencies -----------------
_FORMAT_PATTERNS = {
    "email": re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
    "phone": re.compile(r"^\+?[0-9\-\s()]{7,15}$"),
    "date_iso": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    "currency": re.compile(r"^-?\$?\d+(,\d{3})*(\.\d{1,2})?$"),
}


def _make_issue(
    row_index: Optional[int],
    column: Optional[str],
    issue_type: str,
    severity: str,
    details: str,
) -> Issue:
    return {
        "row_index": row_index,
        "column": column,
        "issue_type": issue_type,
        "severity": severity,
        "details": details,
    }


def detect_missing_values(df: pd.DataFrame, critical_columns: Optional[List[str]] = None) -> List[Issue]:
    """Flags missing (NaN/None) cells. Missing values in `critical_columns` are
    marked 'high' severity; everywhere else they're 'medium'.

    Args:
        df: DataFrame to check.
        critical_columns: Columns where missingness is especially risky
            (e.g. amount, transaction_id). Defaults to none critical.
    """
    critical = set(critical_columns or [])
    issues: List[Issue] = []
    for col in df.columns:
        missing_rows = df.index[df[col].isna()]
        severity = "high" if col in critical else "medium"
        for row_idx in missing_rows:
            issues.append(
                _make_issue(
                    int(row_idx), col, "missing_value", severity, f"'{col}' is missing a value."
                )
            )
    return issues


def detect_exact_duplicates(df: pd.DataFrame) -> List[Issue]:
    """Flags rows that are exact duplicates of an earlier row (all columns identical)."""
    dup_mask = df.duplicated(keep="first")
    issues: List[Issue] = []
    for row_idx in df.index[dup_mask]:
        issues.append(
            _make_issue(
                int(row_idx),
                None,
                "exact_duplicate",
                "medium",
                "Row is an exact duplicate of a previously seen row.",
            )
        )
    return issues


def detect_fuzzy_duplicates(
    df: pd.DataFrame, columns: List[str], threshold: float = 90.0
) -> List[Issue]:
    """Flags near-duplicate text values in the given columns (e.g. name typos)
    using rapidfuzz token-sort similarity.

    Args:
        df: DataFrame to check.
        columns: Text columns to compare pairwise (e.g. ['customer_name']).
        threshold: Similarity score (0-100) above which two non-identical
            strings are considered likely duplicates. Higher = stricter.
    """
    issues: List[Issue] = []
    for col in columns:
        if col not in df.columns:
            continue
        values = df[col].dropna().astype(str).str.strip()
        seen: List[tuple] = []  # (row_idx, normalized_value)
        for row_idx, value in values.items():
            if not value:
                continue
            for other_idx, other_value in seen:
                if value == other_value:
                    continue  # exact matches are handled by detect_exact_duplicates
                score = fuzz.token_sort_ratio(value, other_value)
                if score >= threshold:
                    issues.append(
                        _make_issue(
                            int(row_idx),
                            col,
                            "fuzzy_duplicate",
                            "medium",
                            f"'{value}' is a likely near-duplicate of '{other_value}' "
                            f"(similarity: {score:.0f}%), seen at row {other_idx}.",
                        )
                    )
                    break
            seen.append((row_idx, value))
    return issues


def detect_outliers_iqr(df: pd.DataFrame, column: str, k: float = 1.5) -> List[Issue]:
    """Flags numeric outliers using the IQR (interquartile range) method:
    any value below Q1 - k*IQR or above Q3 + k*IQR.

    Args:
        df: DataFrame to check.
        column: Numeric column to inspect.
        k: IQR multiplier controlling sensitivity (1.5 is the common default).
    """
    if column not in df.columns or not pd.api.types.is_numeric_dtype(df[column]):
        return []

    series = df[column].dropna()
    if len(series) < 4:
        return []

    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    lower, upper = q1 - k * iqr, q3 + k * iqr

    issues: List[Issue] = []
    outlier_mask = (df[column] < lower) | (df[column] > upper)
    for row_idx in df.index[outlier_mask.fillna(False)]:
        value = df.loc[row_idx, column]
        issues.append(
            _make_issue(
                int(row_idx),
                column,
                "outlier_iqr",
                "medium",
                f"Value {value} is outside the expected IQR range "
                f"[{lower:.2f}, {upper:.2f}].",
            )
        )
    return issues


def detect_outliers_zscore(df: pd.DataFrame, column: str, threshold: float = 3.0) -> List[Issue]:
    """Flags numeric outliers using z-scores: values more than `threshold`
    standard deviations from the column mean.

    Args:
        df: DataFrame to check.
        column: Numeric column to inspect.
        threshold: Z-score cutoff (3.0 is a common default, ~99.7% rule).
    """
    if column not in df.columns or not pd.api.types.is_numeric_dtype(df[column]):
        return []

    series = df[column].dropna()
    if len(series) < 2 or series.std(ddof=0) == 0:
        return []

    mean, std = series.mean(), series.std(ddof=0)
    z_scores = (df[column] - mean) / std

    issues: List[Issue] = []
    outlier_mask = z_scores.abs() > threshold
    for row_idx in df.index[outlier_mask.fillna(False)]:
        z = z_scores.loc[row_idx]
        value = df.loc[row_idx, column]
        issues.append(
            _make_issue(
                int(row_idx),
                column,
                "outlier_zscore",
                "medium",
                f"Value {value} has a z-score of {z:.2f} (threshold: {threshold}).",
            )
        )
    return issues


def detect_format_inconsistencies(
    df: pd.DataFrame, column: str, expected_format: str
) -> List[Issue]:
    """Flags values that don't match an expected format pattern, plus casing
    and whitespace inconsistencies.

    Args:
        df: DataFrame to check.
        column: Column to inspect.
        expected_format: One of "email", "phone", "date_iso", "currency",
            or "text" (checks only whitespace/casing, no regex pattern).
    """
    if column not in df.columns:
        return []

    issues: List[Issue] = []
    series = df[column]
    pattern = _FORMAT_PATTERNS.get(expected_format)

    for row_idx, raw_value in series.items():
        if pd.isna(raw_value):
            continue
        value = str(raw_value)

        if value != value.strip():
            issues.append(
                _make_issue(
                    int(row_idx),
                    column,
                    "whitespace",
                    "low",
                    "Value has leading/trailing whitespace.",
                )
            )

        if pattern is not None and not pattern.match(value.strip()):
            issues.append(
                _make_issue(
                    int(row_idx),
                    column,
                    "format_mismatch",
                    "medium",
                    f"'{value}' does not match expected '{expected_format}' format.",
                )
            )

    # Casing inconsistency: same column, mixed use of upper/lower/title case
    # for what are otherwise the same category of value (checked at column level).
    non_null = series.dropna().astype(str).str.strip()
    if expected_format == "text" and not non_null.empty:
        casings = {v: v.lower() for v in non_null.unique()}
        lower_to_variants: Dict[str, List[str]] = {}
        for original, lowered in casings.items():
            lower_to_variants.setdefault(lowered, []).append(original)
        inconsistent_groups = {k: v for k, v in lower_to_variants.items() if len(v) > 1}
        if inconsistent_groups:
            for row_idx, raw_value in series.items():
                if pd.isna(raw_value):
                    continue
                lowered = str(raw_value).strip().lower()
                if lowered in inconsistent_groups:
                    issues.append(
                        _make_issue(
                            int(row_idx),
                            column,
                            "inconsistent_casing",
                            "low",
                            f"'{raw_value}' casing is inconsistent with other values "
                            f"({', '.join(inconsistent_groups[lowered])}).",
                        )
                    )
    return issues


def detect_logical_inconsistencies(df: pd.DataFrame, rules: List[Dict[str, Any]]) -> List[Issue]:
    """Applies configurable logical/business rules to the DataFrame.

    Each rule dict supports two forms:
      1. Column comparison: {"type": "compare", "column_a": "end_date",
         "op": ">", "column_b": "start_date", "message": "..."}
      2. Column threshold: {"type": "threshold", "column": "amount",
         "op": ">=", "value": 0, "message": "..."}

    Supported ops: ">", ">=", "<", "<=", "==", "!="

    Args:
        df: DataFrame to check.
        rules: List of rule dicts as described above.
    """
    op_funcs = {
        ">": lambda a, b: a > b,
        ">=": lambda a, b: a >= b,
        "<": lambda a, b: a < b,
        "<=": lambda a, b: a <= b,
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
    }

    issues: List[Issue] = []
    for rule in rules:
        rule_type = rule.get("type")
        op = rule.get("op")
        op_func = op_funcs.get(op)
        message = rule.get("message", "Logical rule violated.")
        severity = rule.get("severity", "high")

        if op_func is None:
            continue

        if rule_type == "compare":
            col_a, col_b = rule.get("column_a"), rule.get("column_b")
            if col_a not in df.columns or col_b not in df.columns:
                continue
            a_vals = pd.to_numeric(df[col_a], errors="coerce")
            if not pd.api.types.is_numeric_dtype(df[col_a]):
                a_vals = pd.to_datetime(df[col_a], errors="coerce")
            b_vals = pd.to_numeric(df[col_b], errors="coerce")
            if not pd.api.types.is_numeric_dtype(df[col_b]):
                b_vals = pd.to_datetime(df[col_b], errors="coerce")

            valid_mask = a_vals.notna() & b_vals.notna()
            violation_mask = valid_mask & ~op_func(a_vals, b_vals)
            for row_idx in df.index[violation_mask]:
                issues.append(
                    _make_issue(
                        int(row_idx),
                        f"{col_a}/{col_b}",
                        "logical_inconsistency",
                        severity,
                        f"{message} (row has {col_a}={df.loc[row_idx, col_a]}, "
                        f"{col_b}={df.loc[row_idx, col_b]})",
                    )
                )

        elif rule_type == "threshold":
            col = rule.get("column")
            value = rule.get("value")
            if col not in df.columns:
                continue
            col_vals = pd.to_numeric(df[col], errors="coerce")
            valid_mask = col_vals.notna()
            violation_mask = valid_mask & ~op_func(col_vals, value)
            for row_idx in df.index[violation_mask]:
                issues.append(
                    _make_issue(
                        int(row_idx),
                        col,
                        "logical_inconsistency",
                        severity,
                        f"{message} (value: {df.loc[row_idx, col]})",
                    )
                )
    return issues
