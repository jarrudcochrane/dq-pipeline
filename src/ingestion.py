"""
ingestion.py

Handles loading user-uploaded CSV/XLSX files into a clean, standardized
pandas DataFrame, and fails gracefully (with a readable error) rather than
crashing on malformed input.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Optional, Union

import pandas as pd

SUPPORTED_EXTENSIONS = (".csv", ".xlsx", ".xls")


class IngestionError(Exception):
    """Raised when a file cannot be parsed into a usable DataFrame."""


@dataclass
class IngestionResult:
    """Wraps a load attempt so the caller can check success without a try/except."""

    success: bool
    dataframe: Optional[pd.DataFrame] = None
    error_message: Optional[str] = None
    original_columns: Optional[list] = None


def standardize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Strips whitespace and lowercases/snake-cases column names for consistent access.

    Example: "  Customer Name " -> "customer_name"
    """
    new_columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace(r"\s+", "_", regex=True)
        .str.replace(r"[^a-z0-9_]", "", regex=True)
    )
    df = df.copy()
    df.columns = new_columns
    return df


def _read_csv(file_obj: Union[str, io.BytesIO]) -> pd.DataFrame:
    try:
        return pd.read_csv(file_obj)
    except UnicodeDecodeError:
        # Retry with a more permissive encoding before giving up.
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)
        return pd.read_csv(file_obj, encoding="latin1")


def _read_excel(file_obj: Union[str, io.BytesIO]) -> pd.DataFrame:
    return pd.read_excel(file_obj, engine="openpyxl")


def load_file(file_obj: Union[str, io.BytesIO], filename: Optional[str] = None) -> IngestionResult:
    """Loads a CSV or XLSX file into a DataFrame with standardized column names.

    Args:
        file_obj: A file path (str) or an in-memory buffer (e.g. Streamlit's
            UploadedFile, which behaves like a BytesIO object).
        filename: Original filename, used to detect the extension when
            `file_obj` isn't a plain path (e.g. Streamlit uploads).

    Returns:
        An IngestionResult. Check `.success` before using `.dataframe`.
    """
    name = filename or (file_obj if isinstance(file_obj, str) else "")
    lower_name = name.lower()

    if not lower_name.endswith(SUPPORTED_EXTENSIONS):
        return IngestionResult(
            success=False,
            error_message=(
                f"Unsupported file type for '{name}'. "
                f"Please upload one of: {', '.join(SUPPORTED_EXTENSIONS)}"
            ),
        )

    try:
        if lower_name.endswith(".csv"):
            df = _read_csv(file_obj)
        else:
            df = _read_excel(file_obj)
    except pd.errors.EmptyDataError:
        return IngestionResult(success=False, error_message="The file appears to be empty.")
    except pd.errors.ParserError as exc:
        return IngestionResult(success=False, error_message=f"Could not parse file: {exc}")
    except Exception as exc:  # noqa: BLE001 - surface any parser failure as a friendly message
        return IngestionResult(success=False, error_message=f"Failed to read file: {exc}")

    if df.empty:
        return IngestionResult(success=False, error_message="The file was read but contains no rows.")

    original_columns = list(df.columns)
    df = standardize_column_names(df)

    return IngestionResult(success=True, dataframe=df, original_columns=original_columns)
