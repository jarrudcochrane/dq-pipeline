# 🔍 Data Quality Pipeline

<div align="center">

### **Turn messy spreadsheets into a story you can trust.**

A Python-powered data quality tool that profiles messy CSV/Excel files, automatically detects issues, safely fixes what's safe to fix, and flags the rest for human review - all through an interactive dashboard.

🔍 🧹 📊

</div>

## 📌 Overview

Data Quality Pipeline is built around one thing: **turning "is this data actually trustworthy?" into a five-minute answer instead of a two-hour manual review.**

It grew out of manually reviewing hospital-related financial datasets in Excel ahead of audits - checking for missing values, duplicates, inconsistent formatting, and unusual transaction amounts by hand, one column at a time. This project automates that repeatable checking process, while deliberately keeping a human in the loop for anything that needs judgment rather than a rule.

The goal is simple:

> **Upload a file → Profile it → See exactly what's wrong → Fix what's safe → Review what isn't.**

Whether it's a quick sanity check before an audit or a first pass on a new dataset, Data Quality Pipeline makes it easier to answer one important question:

> **"Can I actually trust this data, or does it just look fine?"**

## 🎯 Two Ways to Use It

| | 🧪 `pytest` suite | 🌐 `app.py` dashboard |
|---|---|---|
| **Experience** | Verifies every detector against known issues | Full interactive Streamlit app |
| **Best for** | Confirming the logic is correct | Actually cleaning your data |
| **Output** | Pass/fail test report | Profiling tables, charts, cleaned CSV, HTML report |
| **Data** | Small synthetic DataFrames with planted issues | Any CSV/XLSX you upload, or the built-in demo dataset |

## 🧠 What It Detects

This project goes beyond a quick `.isna().sum()`.

It runs seven independent, single-purpose detectors, each targeting a different class of data quality issue:

- 🕳️ **Missing values** - per-column gaps, with configurable "critical" columns escalated to high severity
- 🧬 **Exact duplicates** - full-row matches, auto-removed
- 👥 **Fuzzy duplicates** - near-identical text (e.g. "John Smith" vs "Jon Smith") via `rapidfuzz` similarity scoring
- 📐 **IQR outliers** - statistical extremes using the interquartile range method
- 📏 **Z-score outliers** - statistical extremes using standard deviations from the mean
- 🔤 **Format inconsistencies** - whitespace, inconsistent casing, and regex mismatches (email, phone, date, currency)
- ⚖️ **Logical inconsistencies** - configurable business rules (e.g. `amount >= 0`, `end_date > start_date`)

Every detector returns issues in the same structured shape - `row_index`, `column`, `issue_type`, `severity`, `details` so the UI, cleaning layer, and reporting layer can all consume them generically.

## 🧹 What Gets Auto-Fixed vs. Flagged

Not everything gets auto-fixed - that's the point.

| ✅ Auto-fixed (safe, unambiguous) | 🚩 Flagged only (needs a human) |
|---|---|
| Leading/trailing whitespace | Missing values in critical columns |
| Inconsistent casing | Outliers (could be errors *or* real events) |
| Mixed date formats → ISO | Fuzzy duplicate names (could be different people) |
| Exact duplicate rows | Logical rule violations (e.g. negative amounts) |

Auto-fixes only apply when there's essentially one correct interpretation and low risk in getting it wrong. Everything else stays visible because for financial or audit-sensitive data, a tool that quietly "fixes" an outlier or merges two similar names is exactly the kind of tool you shouldn't trust. See `src/cleaning.py` for the full reasoning.

## 🌐 Interactive Dashboard

The Streamlit app wraps the whole pipeline in an upload → analyze → review → download flow.

### Dashboard Features

- 📤 **Upload any CSV or XLSX**, or click one button to load the built-in synthetic demo dataset
- ⚙️ **Configurable sidebar** - toggle which checks run, tune the fuzzy-match threshold and z-score threshold, choose IQR vs. z-score vs. both
- 📋 **Full column profiling** - dtype, % missing, unique values, min/max/mean/median for numeric columns
- 🚩 **Filterable issue list** - filter by severity (high/medium/low) or issue type
- 📊 **Interactive Plotly charts** - missing % by column, issues by severity, issues by type, outlier distribution
- 🔁 **Before/after comparison** - side-by-side raw vs. cleaned data, plus a plain-English log of every auto-fix applied
- 🧩 **Custom rule builder** - define your own logical rules from the UI (e.g. "flag if amount > 1,000,000") without touching code
- 📥 **One-click downloads** - cleaned dataset as CSV, full summary as a self-contained HTML report

No manual code editing required to run a full analysis end-to-end.

## 📸 Dashboard Screenshots

### 🔍 Upload & Configuration

<img width="1917" height="967" alt="screenshot-upload" src="https://github.com/user-attachments/assets/72e03076-e50c-415f-a914-74eca03b39b9" />

### 📊 Results Overview

<img width="1912" height="962" alt="screenshot-results" src="https://github.com/user-attachments/assets/c9a8c9da-7d46-4394-bd9d-01b9676020bd" />

### 🚩 Issues Tab

<img width="1917" height="962" alt="screenshot-issues" src="https://github.com/user-attachments/assets/7eea993b-8994-4b6a-bbec-56e968aee89b" />


### 📈 Charts Tab\

<img width="1912" height="961" alt="screenshot-charts3" src="https://github.com/user-attachments/assets/f78c2e67-9218-48c0-bc39-b1cd017b6ee7" />


<img width="1917" height="957" alt="screenshot-charts" src="https://github.com/user-attachments/assets/d561bec4-e36e-48c4-b256-98fe61b66d62" />


<img width="1917" height="960" alt="screenshot-charts 2" src="https://github.com/user-attachments/assets/a0a4e348-051b-4f7c-96d6-2e428d1fb185" />



### 🔁 Before/After Tab

<img width="1917" height="966" alt="screenshot-before-after" src="https://github.com/user-attachments/assets/60f04856-3966-43ea-bda4-d4ed8200612b" />

Additional photo

<img width="1917" height="962" alt="Screenshot 2026-09-03 124056" src="https://github.com/user-attachments/assets/417bcee2-2544-4fd5-a371-03c83d8ded18" />


## 🛠️ Tech Stack

| Technology | Purpose |
|---|---|
| 🐍 **Python 3.11+** | Core programming language |
| 🐼 **pandas** | Data loading, profiling and cleaning |
| 🔢 **NumPy** | Numerical calculations |
| 🧮 **SciPy** | Statistical outlier detection |
| 🔤 **RapidFuzz** | Fuzzy string matching for near-duplicate detection |
| ✨ **Plotly** | Interactive charts inside the dashboard |
| 🌐 **Streamlit** | Interactive web dashboard |
| ✅ **pytest** | Unit testing every detection function |

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR-USERNAME/dq-pipeline.git
cd dq-pipeline
```

### 2. Create a Virtual Environment & Install Dependencies

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. (Optional) Regenerate the Synthetic Demo Dataset

```bash
python data/generate_sample_data.py
```

## ✅ Run the Tests

Every detection function is tested against small synthetic DataFrames with known, deliberately-inserted issues:

```bash
pytest tests/ -v
```

## 🌐 Run the Interactive Dashboard

```bash
streamlit run app.py
```

The dashboard will open in your browser, where you can:

- Upload your own file, or click **Use demo dataset** to try it instantly
- Configure which checks run and how sensitive they are
- Review profiling, issues, charts, and the before/after comparison
- Download the cleaned CSV and the HTML report

## 📂 Project Structure

```text
dq-pipeline/
│
├── data/
│   ├── generate_sample_data.py    # Synthetic messy dataset generator
│   └── sample_transactions.csv    # Generated demo data (~300 rows)
│
├── src/
│   ├── ingestion.py                # File loading & validation
│   ├── profiling.py                # Before/after snapshot logic
│   ├── detection.py                # All detect_* issue-detection functions
│   ├── cleaning.py                 # Safe auto-fix vs. flag-only logic
│   └── reporting.py                # Summaries, Plotly charts, exports
│
├── tests/
│   └── test_detection.py           # pytest unit tests for every detector
│
├── docs/
│   └── screenshots (add your own)
│
├── app.py                          # Streamlit dashboard entry point
├── requirements.txt
└── README.md
```

## 🔭 Future Improvements

There are several opportunities to expand the project further:

- 🧠 **Smarter imputation suggestions**
  - Suggest (never auto-apply) sensible fill values for missing data, shown alongside the flag

- 📑 **PDF export**
  - Generate the report directly as PDF instead of relying on browser print-to-PDF

- 🗂️ **Multi-file / batch mode**
  - Run the same checks across several files at once and compare results

- 🔌 **Database connectors**
  - Pull data directly from a database or warehouse instead of only file uploads

- ☁️ **Cloud deployment**
  - Deploy the dashboard to Streamlit Community Cloud for access from anywhere

- 📱 **Mobile-friendly layout**
  - Optimise the dashboard for quick checks on smaller screens

## 🎯 The Goal

Data Quality Pipeline was built to turn manual, error-prone spreadsheet review into something repeatable.

Not just:

> *"How many rows does this file have?"*

But:

> **What's actually wrong with this data?**

> **What can I safely fix automatically?**

> **What genuinely needs a second pair of eyes before it goes into a report or an audit?**

## 💡 Impact

In my role as a Data Assistant, I manually reviewed hospital-related financial datasets in Excel ahead of audits checking for missing values, duplicate entries, inconsistent formatting, and unusual transaction amounts that could indicate errors or required further verification. This project translates that manual review process into a reusable, automated pipeline issues that took hours to spot by scrolling through spreadsheets are now surfaced in seconds, with a clear, documented line between what's safe to fix automatically and what genuinely needs a person to look at it — the same judgment call I was making by hand.

<div align="center">

## 🔍 **Upload. Detect. Clean. Trust.**

*Because bad data doesn't announce itself — the pipeline just makes sure it can't hide.*

🔍 🧹 📊

<br>

### **Developed by Jarrud Cochrane**

</div>
