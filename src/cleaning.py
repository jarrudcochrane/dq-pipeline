"""
cleaning.py

Applies the "safe auto-fix" layer, and keeps everything else as flag-only.

DECISION LOGIC (why some things are auto-fixed and others aren't)
-------------------------------------------------------------------
Auto-fixes are only applied when a fix is essentially unambiguous and
reversible in intent -- i.e. there is really only one sensible "correct"
value, and getting it wrong carries low risk:

  - Whitespace (" John " -> "John"): there's no interpretation where the
    surrounding whitespace was intentional data.
  - Casing ("COMPLETED" / "completed" -> "Completed"): standardizing display
    casing doesn't change the meaning of the value.
  - Date formats (mixing "DD/MM/YYYY" and "YYYY-MM-DD" -> ISO "YYYY-MM-DD"):
    once parsed, the underlying date is unambiguous; only its string
    representation changes.
  - Exact duplicate rows: if every single column matches, keeping the repeat
    adds no information and inflates totals/sums.

Everything else is FLAG ONLY, because an automated "fix" could silently
change the meaning or hide something a human needs to see:

  - Missing values in critical columns: imputing (e.g. filling with the
    mean, or a placeholder) can mask a data collection error or, worse,
    misstate a financial figure. A human should decide whether to source
    the real value, exclude the row, or impute deliberately.
  - Outliers: an outlier might be a data entry error OR a legitimate large
    transaction. Auto-removing or capping it could hide fraud or a real
    business event -- exactly the kind of thing an audit needs to see, not
    have quietly cleaned away.
  - Fuzzy duplicates ("Jon Smith" vs "John Smith"): merging these
    automatically risks conflating two different real people. A human
    needs to confirm identity before merging financial records.
  - Logical inconsistencies (e.g. amount < 0, end_date before start_date):
    these often indicate a genuine data problem upstream that needs
    investigating, not just numerically patching over.

This split mirrors how a careful manual reviewer would work: fix the
cosmetic/formatting noise automatically so it doesn't obscure real issues,
but leave anything that touches the *substance* of the data for a human
to review and decide on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

import pandas as pd

Issue = Dict[str, Any]

SAFE_AUTO_FIX_TYPES = {"whitespace", "inconsistent_casing", "date_format", "exact_duplicate"}
FLAG_ONLY_TYPES = {
    "missing_value",
    "outlier_iqr",
    "outlier_zscore",
    "fuzzy_duplicate",
    "logical_inconsistency",
    "format_mismatch",
}


@dataclass
class CleaningLog:
    """Records what was changed during auto-fixing, for the report."""

    actions: List[str] = field(default_factory=list)
    rows_removed: int = 0
    cells_changed: int = 0

    def add(self, message: str) -> None:
        self.actions.append(message)


def strip_whitespace(df: pd.DataFrame, columns: List[str], log: CleaningLog) -> pd.DataFrame:
    """Strips leading/trailing whitespace from text columns."""
    df = df.copy()
    for col in columns:
        if col not in df.columns:
            continue
        text_series = df[col].astype(str)
        mask = df[col].notna() & (text_series != text_series.str.strip())
        changed = int(mask.sum())
        if changed:
            df.loc[df[col].notna(), col] = df.loc[df[col].notna(), col].astype(str).str.strip()
            log.cells_changed += changed
            log.add(f"Stripped whitespace from {changed} value(s) in '{col}'.")
    return df


def standardize_casing(df: pd.DataFrame, columns: List[str], log: CleaningLog) -> pd.DataFrame:
    """Standardizes casing for categorical text columns to Title Case, so
    'COMPLETED' / 'completed' / 'Completed' all collapse to one canonical form.
    """
    df = df.copy()
    for col in columns:
        if col not in df.columns:
            continue
        non_null = df[col].dropna().astype(str)
        titled = non_null.str.strip().str.title()
        changed_mask = non_null != titled
        changed = int(changed_mask.sum())
        if changed:
            df.loc[non_null.index, col] = titled
            log.cells_changed += changed
            log.add(f"Standardized casing for {changed} value(s) in '{col}' (-> Title Case).")
    return df


def standardize_date_formats(df: pd.DataFrame, columns: List[str], log: CleaningLog) -> pd.DataFrame:
    """Parses mixed-format date strings and rewrites them consistently as
    ISO 8601 (YYYY-MM-DD).
    """
    df = df.copy()
    for col in columns:
        if col not in df.columns:
            continue
        original = df[col].astype(str)
        parsed = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
        standardized = parsed.dt.strftime("%Y-%m-%d")
        changed_mask = parsed.notna() & (original != standardized)
        changed = int(changed_mask.sum())
        if changed:
            df.loc[changed_mask, col] = standardized[changed_mask]
            log.cells_changed += changed
            log.add(f"Standardized {changed} date value(s) in '{col}' to YYYY-MM-DD.")
    return df


def remove_exact_duplicates(df: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    """Removes exact duplicate rows, keeping the first occurrence."""
    before = len(df)
    df = df.drop_duplicates(keep="first").reset_index(drop=True)
    removed = before - len(df)
    if removed:
        log.rows_removed += removed
        log.add(f"Removed {removed} exact duplicate row(s).")
    return df


def apply_safe_fixes(
    df: pd.DataFrame,
    text_columns: List[str],
    categorical_columns: List[str],
    date_columns: List[str],
) -> tuple[pd.DataFrame, CleaningLog]:
    """Runs the full safe auto-fix pipeline in a sensible order (formatting
    fixes before duplicate removal, so duplicates are recognized correctly
    even if they only differed by whitespace/casing/date format).

    Args:
        df: Raw (or partially cleaned) DataFrame.
        text_columns: Free-text columns to strip whitespace from.
        categorical_columns: Low-cardinality text columns to standardize casing on.
        date_columns: Columns containing date strings to standardize.

    Returns:
        (cleaned_df, CleaningLog) tuple.
    """
    log = CleaningLog()
    df = strip_whitespace(df, text_columns, log)
    df = standardize_casing(df, categorical_columns, log)
    df = standardize_date_formats(df, date_columns, log)
    df = remove_exact_duplicates(df, log)
    return df, log


def split_issues_by_fix_strategy(issues: List[Issue]) -> tuple[List[Issue], List[Issue]]:
    """Splits a combined issue list into (auto_fixed_types, needs_review_types)
    based on issue_type, using the SAFE_AUTO_FIX_TYPES / FLAG_ONLY_TYPES sets.
    Useful for the reporting/UI layer to show "what was auto-handled" vs.
    "what still needs your attention."
    """
    auto = [i for i in issues if i["issue_type"] in SAFE_AUTO_FIX_TYPES]
    flagged = [i for i in issues if i["issue_type"] in FLAG_ONLY_TYPES]
    other = [i for i in issues if i["issue_type"] not in SAFE_AUTO_FIX_TYPES | FLAG_ONLY_TYPES]
    return auto, flagged + other
