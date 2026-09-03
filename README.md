# 🔍 Automated Data Quality & Anomaly Detection Pipeline

A Python + Streamlit tool that profiles a messy CSV/Excel file, detects data
quality issues, automatically fixes the safe ones, flags the rest for human
review, and produces a downloadable cleaned dataset plus a readable report.

![screenshot placeholder](docs/screenshot-placeholder.png)
*(Add a screenshot of the running app here.)*

---

## Problem Statement

Before any report, dashboard, or audit can be trusted, the underlying data
needs to be checked for missing values, duplicates, inconsistent formatting,
and statistical anomalies. Done by hand in a spreadsheet, this is slow,
repetitive, and error-prone — and it's easy to accidentally "fix" something
that shouldn't have been touched (like silently dropping a legitimate large
transaction because it looked like an outlier).

This project automates the *repeatable* parts of that manual review process
while deliberately **not** automating the parts that need human judgment.

## Approach

The pipeline runs in four stages:

1. **Profile** — build a "before" snapshot of the raw data: per-column type,
   % missing, unique values, and summary statistics.
2. **Detect** — run a set of independent, single-purpose detectors (missing
   values, exact/fuzzy duplicates, IQR & z-score outliers, format
   inconsistencies, configurable logical rules), each returning issues in a
   consistent structured format.
3. **Clean** — apply a small set of **safe, unambiguous auto-fixes**
   (whitespace, casing, date formats, exact duplicates) and leave everything
   else flagged for review. See `src/cleaning.py` for the full reasoning
   behind which fixes are safe to automate and which aren't — this decision
   logic is the core design idea of the project, not an afterthought.
4. **Report** — compare before/after snapshots, summarize issues by type,
   column, and severity, generate charts, and export a cleaned CSV and an
   HTML report.

### Why some issues are auto-fixed and others are only flagged

| Auto-fixed (safe, unambiguous) | Flagged only (needs a human) |
|---|---|
| Leading/trailing whitespace | Missing values in critical columns |
| Inconsistent casing | Outliers (could be errors *or* real events) |
| Mixed date formats → ISO | Fuzzy duplicate names (could be different people) |
| Exact duplicate rows | Logical rule violations (e.g. negative amounts) |

The dividing line: auto-fix only when there's essentially one correct
interpretation and low risk in getting it wrong. Flag anything where an
automated fix could silently hide a real problem — which, for financial or
audit-sensitive data, is exactly what you don't want a tool doing quietly in
the background.

## Project Structure

```
dq_pipeline/
├── app.py                     # Streamlit UI entry point
├── requirements.txt
├── README.md
├── data/
│   ├── generate_sample_data.py  # Synthetic messy dataset generator
│   └── sample_transactions.csv  # Generated demo data (~300 rows)
├── src/
│   ├── ingestion.py            # File loading & validation
│   ├── profiling.py            # Before/after snapshot logic
│   ├── detection.py            # All detect_* issue-detection functions
│   ├── cleaning.py             # Safe auto-fix vs. flag-only logic
│   └── reporting.py            # Summaries, Plotly charts, exports
└── tests/
    └── test_detection.py       # pytest unit tests for every detector
```

## How to Run Locally

```bash
# 1. Clone/download this project, then from the project root:
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) Regenerate the synthetic demo dataset
python data/generate_sample_data.py

# 4. Run the tests
pytest tests/ -v

# 5. Launch the app
streamlit run app.py
```

Then open the local URL Streamlit prints (usually `http://localhost:8501`),
upload your own CSV/XLSX, or click **Use demo dataset** to try it instantly
with the included synthetic financial transaction data.

## Deploying to Streamlit Community Cloud (free)

1. Push this project to a public (or private, with an invite) GitHub repo.
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Click **New app**, select your repo/branch, and set the main file path to `app.py`.
4. Click **Deploy**. Streamlit Cloud will install `requirements.txt` and host the app automatically — you'll get a shareable `*.streamlit.app` URL.
5. Any time you push to the connected branch, the deployed app auto-updates.

## Testing

All detection functions have pytest unit tests using small synthetic
DataFrames with known, deliberately-inserted issues (e.g. a DataFrame with 2
known exact duplicates, or a name typo that should trigger a fuzzy-duplicate
match). Run them with:

```bash
pytest tests/ -v
```

## Impact

*(Replace this paragraph with your own 3-4 sentences based on your actual
JLS FMS experience before adding this to a CV/portfolio — that's what makes
it credible rather than a generic tutorial project.)*

In my role as a Data Assistant, I manually reviewed hospital-related
financial datasets in Excel ahead of audits — checking for missing values,
duplicate entries, inconsistent formatting, and unusual transaction amounts
that could indicate errors or required further verification. This project
translates that manual review process into a reusable, automated pipeline:
issues that took hours to spot by scrolling through spreadsheets are now
surfaced in seconds, with a clear, documented line between what's safe to
fix automatically and what genuinely needs a person to look at it — the
same judgment call I was making by hand.

## Tech Stack

Python 3.11+ · pandas · numpy · scipy · rapidfuzz · plotly · streamlit · pytest
