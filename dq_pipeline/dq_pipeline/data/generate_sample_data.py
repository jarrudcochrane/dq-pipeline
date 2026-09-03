"""
generate_sample_data.py

Creates a synthetic "messy" financial transaction dataset used for:
  1. Demoing the app end-to-end without needing external/real data.
  2. Providing known, deliberately-inserted issues that the pytest suite
     checks the detection functions against.

Run directly:
    python data/generate_sample_data.py

Produces: data/sample_transactions.csv (~300 rows)
"""

from __future__ import annotations

import random
import string
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

RNG_SEED = 42
N_ROWS = 300
OUTPUT_PATH = Path(__file__).parent / "sample_transactions.csv"

random.seed(RNG_SEED)
np.random.seed(RNG_SEED)

CATEGORIES = ["Travel", "Supplies", "Payroll", "Utilities", "Maintenance", "Consulting"]
STATUSES = ["Completed", "Pending", "Refunded", "Failed"]

FIRST_NAMES = ["John", "Sarah", "Michael", "Priya", "Thabo", "Linda", "David", "Nomvula", "James", "Aisha"]
LAST_NAMES = ["Smith", "Naidoo", "Khumalo", "Botha", "Patel", "Dlamini", "Van Wyk", "Nkosi", "Brown", "Molefe"]


def _random_name() -> str:
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def _random_date(start: datetime, end: datetime) -> datetime:
    delta = end - start
    return start + timedelta(days=random.randint(0, delta.days))


def _format_date_inconsistently(dt: datetime, row_idx: int) -> str:
    """~35% of dates use DD/MM/YYYY, the rest use YYYY-MM-DD (the intended inconsistency)."""
    if row_idx % 3 == 0:
        return dt.strftime("%d/%m/%Y")
    return dt.strftime("%Y-%m-%d")


def generate_base_dataframe(n_rows: int = N_ROWS) -> pd.DataFrame:
    start, end = datetime(2024, 1, 1), datetime(2024, 12, 31)
    rows = []
    for i in range(n_rows):
        amount = round(np.random.normal(loc=1500, scale=450), 2)
        amount = max(amount, 5.0)
        rows.append(
            {
                "transaction_id": f"TXN{10000 + i}",
                "date": _format_date_inconsistently(_random_date(start, end), i),
                "customer_name": _random_name(),
                "amount": amount,
                "category": random.choice(CATEGORIES),
                "status": random.choice(STATUSES),
                "notes": random.choice(
                    ["", "Approved by manager", "Follow up required", "Recurring charge", "One-off expense"]
                ),
            }
        )
    return pd.DataFrame(rows)


def inject_casing_and_whitespace_issues(df: pd.DataFrame) -> pd.DataFrame:
    """Randomly mangles casing in category/status and adds stray whitespace to text fields."""
    idx = df.sample(frac=0.15, random_state=RNG_SEED).index
    for i in idx:
        if random.random() < 0.5:
            df.loc[i, "category"] = df.loc[i, "category"].upper()
        else:
            df.loc[i, "category"] = df.loc[i, "category"].lower()

    idx2 = df.sample(frac=0.1, random_state=RNG_SEED + 1).index
    for i in idx2:
        df.loc[i, "status"] = df.loc[i, "status"].swapcase()

    whitespace_idx = df.sample(n=8, random_state=RNG_SEED + 2).index
    for i in whitespace_idx:
        df.loc[i, "customer_name"] = f"  {df.loc[i, 'customer_name']}  "
    return df


def inject_missing_values(df: pd.DataFrame, target_frac: float = 0.05) -> pd.DataFrame:
    """Scatters missing values (~5% of all cells) across non-ID columns."""
    columns = ["date", "customer_name", "amount", "category", "status", "notes"]
    n_cells = int(len(df) * len(columns) * target_frac)
    for _ in range(n_cells):
        row = random.randrange(len(df))
        col = random.choice(columns)
        df.loc[row, col] = np.nan
    return df


def inject_exact_duplicates(df: pd.DataFrame, n_dupes: int = 10) -> pd.DataFrame:
    """Appends exact copies of randomly chosen rows -> known exact duplicates."""
    dupe_rows = df.sample(n=n_dupes, random_state=RNG_SEED + 3)
    return pd.concat([df, dupe_rows], ignore_index=True)


def inject_fuzzy_duplicates(df: pd.DataFrame, n_fuzzy: int = 5) -> pd.DataFrame:
    """Adds near-duplicate customer names, e.g. 'John Smith' -> 'Jon Smith'."""
    base_rows = df.sample(n=n_fuzzy, random_state=RNG_SEED + 4).copy()

    def _mutate_name(name: str) -> str:
        name = name.strip()
        if " " not in name:
            return name + "x"
        first, last = name.split(" ", 1)
        if len(first) > 3:
            first = first[:-1]  # drop a letter, e.g. "John" -> "Joh"
        else:
            first = first + "n"  # "Jon" style mutation
        return f"{first} {last}"

    base_rows["customer_name"] = base_rows["customer_name"].apply(_mutate_name)
    base_rows["transaction_id"] = [f"TXN{20000 + i}" for i in range(len(base_rows))]
    return pd.concat([df, base_rows], ignore_index=True)


def inject_outliers(df: pd.DataFrame, n_outliers: int = 8) -> pd.DataFrame:
    """Injects extreme amount values, both very high and very low, as known statistical outliers."""
    idx = df.sample(n=n_outliers, random_state=RNG_SEED + 5).index
    for i, row_idx in enumerate(idx):
        df.loc[row_idx, "amount"] = 25000.0 if i % 2 == 0 else -500.0
    return df


def build_sample_dataset() -> pd.DataFrame:
    df = generate_base_dataframe()
    df = inject_casing_and_whitespace_issues(df)
    df = inject_outliers(df)
    df = inject_missing_values(df)
    df = inject_exact_duplicates(df)
    df = inject_fuzzy_duplicates(df)
    df = df.sample(frac=1, random_state=RNG_SEED + 6).reset_index(drop=True)  # shuffle
    return df


def main() -> None:
    df = build_sample_dataset()
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Wrote {len(df)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
