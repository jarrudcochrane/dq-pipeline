"""
profiling.py

Builds a structured "snapshot" of a DataFrame's shape and per-column
statistics. Used to generate the "before" profile (prior to any cleaning)
and again for the "after" profile, so the two can be diffed in reporting.py.
"""

from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd


def _column_profile(series: pd.Series) -> Dict[str, Any]:
    """Builds the profile dict for a single column."""
    n = len(series)
    missing = int(series.isna().sum())
    profile: Dict[str, Any] = {
        "dtype": str(series.dtype),
        "missing_count": missing,
        "missing_pct": round((missing / n) * 100, 2) if n else 0.0,
        "unique_count": int(series.nunique(dropna=True)),
        "sample_values": series.dropna().astype(str).unique()[:5].tolist(),
    }

    if pd.api.types.is_numeric_dtype(series):
        non_null = series.dropna()
        if not non_null.empty:
            profile.update(
                {
                    "min": float(non_null.min()),
                    "max": float(non_null.max()),
                    "mean": round(float(non_null.mean()), 2),
                    "median": round(float(non_null.median()), 2),
                    "std": round(float(non_null.std()) if len(non_null) > 1 else 0.0, 2),
                }
            )
    return profile


def profile_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
    """Produces a full profiling snapshot for a DataFrame.

    Returns a dict of the form:
        {
            "n_rows": int,
            "n_columns": int,
            "columns": {col_name: {dtype, missing_count, missing_pct,
                                    unique_count, sample_values, [min, max,
                                    mean, median, std for numeric cols]}}
        }

    This snapshot is intentionally plain-dict/JSON-serializable so it can be
    stored, diffed, or rendered in Streamlit without extra transformation.
    """
    return {
        "n_rows": int(len(df)),
        "n_columns": int(len(df.columns)),
        "columns": {col: _column_profile(df[col]) for col in df.columns},
    }


def diff_snapshots(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    """Compares a before/after profiling snapshot pair for the summary report.

    Returns row-count deltas and per-column missing-value deltas, which is
    what the reporting layer needs to show "what changed."
    """
    row_delta = after["n_rows"] - before["n_rows"]
    column_deltas = {}
    for col in before["columns"]:
        if col not in after["columns"]:
            column_deltas[col] = {"status": "removed"}
            continue
        before_missing = before["columns"][col]["missing_pct"]
        after_missing = after["columns"][col]["missing_pct"]
        column_deltas[col] = {
            "missing_pct_before": before_missing,
            "missing_pct_after": after_missing,
            "missing_pct_change": round(after_missing - before_missing, 2),
        }
    return {
        "row_count_before": before["n_rows"],
        "row_count_after": after["n_rows"],
        "row_count_delta": row_delta,
        "rows_removed": max(-row_delta, 0),
        "column_deltas": column_deltas,
    }
