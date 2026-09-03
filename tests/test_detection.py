"""
test_detection.py

Each test builds a small synthetic DataFrame with a KNOWN, deliberately
inserted issue, then asserts the relevant detect_* function finds exactly
that issue (no more, no less where practical).
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.detection import (
    detect_exact_duplicates,
    detect_format_inconsistencies,
    detect_fuzzy_duplicates,
    detect_logical_inconsistencies,
    detect_missing_values,
    detect_outliers_iqr,
    detect_outliers_zscore,
)


def test_detect_missing_values_finds_known_gaps():
    df = pd.DataFrame({"amount": [10, None, 30], "name": ["A", "B", None]})
    issues = detect_missing_values(df)
    assert len(issues) == 2
    columns_flagged = {issue["column"] for issue in issues}
    assert columns_flagged == {"amount", "name"}
    assert all(issue["issue_type"] == "missing_value" for issue in issues)


def test_detect_missing_values_marks_critical_column_as_high_severity():
    df = pd.DataFrame({"amount": [10, None], "notes": [None, "ok"]})
    issues = detect_missing_values(df, critical_columns=["amount"])
    amount_issue = next(i for i in issues if i["column"] == "amount")
    notes_issue = next(i for i in issues if i["column"] == "notes")
    assert amount_issue["severity"] == "high"
    assert notes_issue["severity"] == "medium"


def test_detect_exact_duplicates_finds_known_duplicates():
    df = pd.DataFrame(
        {
            "id": [1, 2, 3, 2, 1],
            "amount": [100, 200, 300, 200, 100],
        }
    )
    # Rows at index 3 and 4 are exact duplicates of rows 1 and 0.
    issues = detect_exact_duplicates(df)
    flagged_rows = {issue["row_index"] for issue in issues}
    assert flagged_rows == {3, 4}
    assert all(issue["issue_type"] == "exact_duplicate" for issue in issues)


def test_detect_fuzzy_duplicates_catches_near_duplicate_names():
    df = pd.DataFrame({"customer_name": ["John Smith", "Jon Smith", "Completely Different"]})
    issues = detect_fuzzy_duplicates(df, columns=["customer_name"], threshold=80.0)
    assert len(issues) == 1
    assert issues[0]["row_index"] == 1
    assert issues[0]["issue_type"] == "fuzzy_duplicate"


def test_detect_fuzzy_duplicates_ignores_dissimilar_names():
    df = pd.DataFrame({"customer_name": ["John Smith", "Zara Ndlovu"]})
    issues = detect_fuzzy_duplicates(df, columns=["customer_name"], threshold=90.0)
    assert issues == []


def test_detect_outliers_iqr_finds_known_outlier():
    # Tight cluster around 100 plus one extreme value of 10,000.
    df = pd.DataFrame({"amount": [98, 100, 101, 99, 102, 97, 100, 10000]})
    issues = detect_outliers_iqr(df, "amount")
    flagged_rows = {issue["row_index"] for issue in issues}
    assert 7 in flagged_rows
    assert all(issue["issue_type"] == "outlier_iqr" for issue in issues)


def test_detect_outliers_zscore_finds_known_outlier():
    df = pd.DataFrame({"amount": [100, 102, 98, 101, 99, 100, 103, 5000]})
    issues = detect_outliers_zscore(df, "amount", threshold=2.0)
    flagged_rows = {issue["row_index"] for issue in issues}
    assert 7 in flagged_rows


def test_detect_outliers_zscore_no_false_positives_on_uniform_data():
    df = pd.DataFrame({"amount": [100, 100, 100, 100]})
    issues = detect_outliers_zscore(df, "amount")
    assert issues == []


def test_detect_format_inconsistencies_flags_whitespace():
    df = pd.DataFrame({"name": ["Clean Name", "  Padded Name  "]})
    issues = detect_format_inconsistencies(df, "name", expected_format="text")
    whitespace_issues = [i for i in issues if i["issue_type"] == "whitespace"]
    assert len(whitespace_issues) == 1
    assert whitespace_issues[0]["row_index"] == 1


def test_detect_format_inconsistencies_flags_bad_email():
    df = pd.DataFrame({"email": ["good@example.com", "not-an-email"]})
    issues = detect_format_inconsistencies(df, "email", expected_format="email")
    format_issues = [i for i in issues if i["issue_type"] == "format_mismatch"]
    assert len(format_issues) == 1
    assert format_issues[0]["row_index"] == 1


def test_detect_format_inconsistencies_flags_inconsistent_casing():
    df = pd.DataFrame({"status": ["Completed", "completed", "COMPLETED", "Pending"]})
    issues = detect_format_inconsistencies(df, "status", expected_format="text")
    casing_issues = [i for i in issues if i["issue_type"] == "inconsistent_casing"]
    flagged_rows = {i["row_index"] for i in casing_issues}
    assert flagged_rows == {0, 1, 2}


def test_detect_logical_inconsistencies_compare_rule():
    df = pd.DataFrame(
        {
            "start_date": ["2024-01-01", "2024-05-01"],
            "end_date": ["2024-02-01", "2024-04-01"],  # row 1 ends before it starts
        }
    )
    rules = [
        {
            "type": "compare",
            "column_a": "end_date",
            "op": ">",
            "column_b": "start_date",
            "message": "end_date must be after start_date",
        }
    ]
    issues = detect_logical_inconsistencies(df, rules)
    assert len(issues) == 1
    assert issues[0]["row_index"] == 1


def test_detect_logical_inconsistencies_threshold_rule():
    df = pd.DataFrame({"amount": [100, -50, 200, -10]})
    rules = [
        {
            "type": "threshold",
            "column": "amount",
            "op": ">=",
            "value": 0,
            "message": "amount must be >= 0",
        }
    ]
    issues = detect_logical_inconsistencies(df, rules)
    flagged_rows = {issue["row_index"] for issue in issues}
    assert flagged_rows == {1, 3}
