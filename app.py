"""
app.py

Streamlit entry point for the Automated Data Quality & Anomaly Detection
Pipeline. Wires together ingestion -> profiling -> detection -> cleaning ->
reporting behind a simple upload -> analyze -> review -> download flow.

Run locally:
    streamlit run app.py
"""

from __future__ import annotations

from typing import List

import pandas as pd
import streamlit as st

from src.cleaning import apply_safe_fixes, split_issues_by_fix_strategy
from src.detection import (
    detect_exact_duplicates,
    detect_format_inconsistencies,
    detect_fuzzy_duplicates,
    detect_logical_inconsistencies,
    detect_missing_values,
    detect_outliers_iqr,
    detect_outliers_zscore,
)
from src.ingestion import load_file
from src.profiling import diff_snapshots, profile_dataframe
from src.reporting import (
    build_before_after_summary,
    chart_issues_by_severity,
    chart_issues_by_type,
    chart_missing_by_column,
    chart_outlier_distribution,
    export_cleaned_csv,
    export_report_html,
    summarize_issues,
)

st.set_page_config(page_title="Data Quality Pipeline", page_icon="🔍", layout="wide")

# --------------------------------------------------------------------------
# Sidebar: configuration
# --------------------------------------------------------------------------
st.sidebar.title("⚙️ Configuration")
st.sidebar.caption("Tune detection sensitivity and choose which checks to run.")

run_missing = st.sidebar.checkbox("Detect missing values", value=True)
run_exact_dupes = st.sidebar.checkbox("Detect exact duplicates", value=True)
run_fuzzy_dupes = st.sidebar.checkbox("Detect fuzzy duplicates", value=True)
fuzzy_threshold = st.sidebar.slider(
    "Fuzzy match threshold (%)", min_value=70, max_value=100, value=88, disabled=not run_fuzzy_dupes
)
run_outliers = st.sidebar.checkbox("Detect outliers", value=True)
outlier_method = st.sidebar.radio(
    "Outlier method", ["IQR", "Z-score", "Both"], index=2, disabled=not run_outliers, horizontal=True
)
zscore_threshold = st.sidebar.slider(
    "Z-score threshold", min_value=1.5, max_value=5.0, value=3.0, step=0.1, disabled=not run_outliers
)
run_format = st.sidebar.checkbox("Detect format inconsistencies", value=True)
run_logical = st.sidebar.checkbox("Detect logical inconsistencies", value=True)

st.sidebar.divider()
st.sidebar.caption(
    "Safe fixes (whitespace, casing, date format, exact duplicates) are "
    "always applied automatically. Everything else is flagged for review — "
    "see the README for why."
)

# --------------------------------------------------------------------------
# Main flow: upload
# --------------------------------------------------------------------------
st.title("🔍 Automated Data Quality & Anomaly Detection Pipeline")
st.write(
    "Upload a CSV or Excel file to profile it, detect data quality issues, "
    "auto-fix what's safe to auto-fix, and flag the rest for your review."
)

col_upload, col_demo = st.columns([3, 1])
with col_upload:
    uploaded_file = st.file_uploader("Upload a CSV or XLSX file", type=["csv", "xlsx", "xls"])
with col_demo:
    st.write("")
    st.write("")
    use_demo = st.button("Use demo dataset", use_container_width=True)

if use_demo:
    st.session_state["use_demo"] = True

source = None
if uploaded_file is not None:
    source = uploaded_file
    source_name = uploaded_file.name
elif st.session_state.get("use_demo"):
    source = "data/sample_transactions.csv"
    source_name = "sample_transactions.csv"

if source is None:
    st.info("Upload a file, or click **Use demo dataset** to try it with synthetic financial transaction data.")
    st.stop()

result = load_file(source, filename=source_name)
if not result.success:
    st.error(f"Could not load file: {result.error_message}")
    st.stop()

df_raw = result.dataframe
demo_label = " (demo)" if st.session_state.get("use_demo") and uploaded_file is None else ""
st.success(f"Loaded **{source_name}{demo_label}** — {df_raw.shape[0]} rows × {df_raw.shape[1]} columns.")

with st.expander("Preview raw data"):
    st.dataframe(df_raw.head(20), use_container_width=True)

# Let the user pick which columns matter for certain checks
text_cols = [c for c in df_raw.columns if df_raw[c].dtype == object]
numeric_cols = [c for c in df_raw.columns if pd.api.types.is_numeric_dtype(df_raw[c])]

with st.expander("Column roles (used to target checks)"):
    critical_cols = st.multiselect(
        "Critical columns (missing values here = high severity)", df_raw.columns.tolist()
    )
    fuzzy_cols = st.multiselect(
        "Text columns to check for fuzzy duplicates", text_cols, default=text_cols[:1] if text_cols else []
    )
    outlier_cols = st.multiselect(
        "Numeric columns to check for outliers", numeric_cols, default=numeric_cols[:1] if numeric_cols else []
    )
    date_cols = st.multiselect(
        "Date columns to standardize", [c for c in df_raw.columns if "date" in c.lower()]
    )
    categorical_cols = st.multiselect(
        "Categorical columns to standardize casing on",
        text_cols,
        default=[c for c in text_cols if c not in fuzzy_cols][:2],
    )

run_clicked = st.button("▶️ Run Analysis", type="primary")

if not run_clicked and "issues" not in st.session_state:
    st.stop()

# --------------------------------------------------------------------------
# Run pipeline
# --------------------------------------------------------------------------
if run_clicked:
    with st.spinner("Profiling and analyzing..."):
        before_profile = profile_dataframe(df_raw)

        issues: List = []
        if run_missing:
            issues += detect_missing_values(df_raw, critical_columns=critical_cols)
        if run_exact_dupes:
            issues += detect_exact_duplicates(df_raw)
        if run_fuzzy_dupes and fuzzy_cols:
            issues += detect_fuzzy_duplicates(df_raw, columns=fuzzy_cols, threshold=fuzzy_threshold)
        if run_outliers:
            for col in outlier_cols:
                if outlier_method in ("IQR", "Both"):
                    issues += detect_outliers_iqr(df_raw, col)
                if outlier_method in ("Z-score", "Both"):
                    issues += detect_outliers_zscore(df_raw, col, threshold=zscore_threshold)
        if run_format:
            for col in text_cols:
                issues += detect_format_inconsistencies(df_raw, col, expected_format="text")
        if run_logical and outlier_cols:
            # Sensible default rule: numeric columns shouldn't be negative.
            # Users can extend this via the custom rules section below.
            default_rules = [
                {
                    "type": "threshold",
                    "column": col,
                    "op": ">=",
                    "value": 0,
                    "message": f"{col} should not be negative",
                }
                for col in outlier_cols
            ]
            issues += detect_logical_inconsistencies(df_raw, default_rules)

        # Custom rules from session state (bonus feature, defined below)
        custom_rules = st.session_state.get("custom_rules", [])
        if custom_rules:
            issues += detect_logical_inconsistencies(df_raw, custom_rules)

        cleaned_df, cleaning_log = apply_safe_fixes(
            df_raw,
            text_columns=[c for c in text_cols if c not in categorical_cols],
            categorical_columns=categorical_cols,
            date_columns=date_cols,
        )
        after_profile = profile_dataframe(cleaned_df)

        st.session_state["issues"] = issues
        st.session_state["cleaned_df"] = cleaned_df
        st.session_state["cleaning_log"] = cleaning_log
        st.session_state["before_profile"] = before_profile
        st.session_state["after_profile"] = after_profile
        st.session_state["df_raw"] = df_raw
        st.session_state["outlier_cols"] = outlier_cols

# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------
issues = st.session_state["issues"]
cleaned_df = st.session_state["cleaned_df"]
cleaning_log = st.session_state["cleaning_log"]
before_profile = st.session_state["before_profile"]
after_profile = st.session_state["after_profile"]
df_raw = st.session_state["df_raw"]
outlier_cols = st.session_state.get("outlier_cols", [])

issue_summary = summarize_issues(issues, len(df_raw))
diff = diff_snapshots(before_profile, after_profile)
full_summary = build_before_after_summary(before_profile, after_profile, issue_summary, cleaning_log.actions)

st.divider()
st.header("Results")

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Rows before", before_profile["n_rows"])
m2.metric("Rows after", after_profile["n_rows"], delta=f"{diff['row_count_delta']}")
m3.metric("Total issues found", issue_summary["total_issues"])
m4.metric("Rows affected", issue_summary["rows_affected"])
m5.metric("% of dataset flagged", f"{issue_summary['pct_rows_affected']}%")

tab_profile, tab_issues, tab_charts, tab_compare, tab_rules = st.tabs(
    ["📋 Profiling", "🚩 Issues", "📊 Charts", "🔁 Before/After", "🧩 Custom Rules"]
)

with tab_profile:
    st.subheader("Column Profile (before cleaning)")
    profile_rows = []
    for col, stats in before_profile["columns"].items():
        profile_rows.append(
            {
                "column": col,
                "dtype": stats["dtype"],
                "% missing": stats["missing_pct"],
                "unique values": stats["unique_count"],
                "min": stats.get("min", "-"),
                "max": stats.get("max", "-"),
                "mean": stats.get("mean", "-"),
                "median": stats.get("median", "-"),
            }
        )
    st.dataframe(pd.DataFrame(profile_rows), use_container_width=True)

with tab_issues:
    st.subheader("Detected Issues")
    if not issues:
        st.success("No issues detected with the current settings 🎉")
    else:
        col_a, col_b = st.columns(2)
        severity_filter = col_a.multiselect(
            "Filter by severity", ["high", "medium", "low"], default=["high", "medium", "low"]
        )
        type_options = sorted({i["issue_type"] for i in issues})
        type_filter = col_b.multiselect("Filter by issue type", type_options, default=type_options)

        filtered = [i for i in issues if i["severity"] in severity_filter and i["issue_type"] in type_filter]
        st.caption(f"Showing {len(filtered)} of {len(issues)} issues")
        st.dataframe(pd.DataFrame(filtered), use_container_width=True, height=400)

        auto_fixed_types, needs_review = split_issues_by_fix_strategy(issues)
        st.info(
            f"**Auto-fix layer:** {len(cleaning_log.actions)} automatic fix action(s) applied "
            f"(whitespace, casing, dates, exact duplicates). "
            f"**{len(needs_review)} issue(s)** still need human review "
            f"(outliers, fuzzy duplicates, missing critical values, logical inconsistencies)."
        )

with tab_charts:
    st.subheader("Visual Summary")
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(chart_missing_by_column(before_profile), use_container_width=True)
    with c2:
        st.plotly_chart(chart_issues_by_severity(issue_summary), use_container_width=True)

    st.plotly_chart(chart_issues_by_type(issue_summary), use_container_width=True)

    if outlier_cols:
        for col in outlier_cols:
            st.plotly_chart(chart_outlier_distribution(df_raw, col), use_container_width=True)

with tab_compare:
    st.subheader("Before vs. After Cleaning")
    st.write("**Auto-cleaning actions applied:**")
    if cleaning_log.actions:
        for action in cleaning_log.actions:
            st.write(f"- {action}")
    else:
        st.write("_No automatic fixes were needed._")

    col_before, col_after = st.columns(2)
    with col_before:
        st.caption("Before")
        st.dataframe(df_raw.head(15), use_container_width=True)
    with col_after:
        st.caption("After")
        st.dataframe(cleaned_df.head(15), use_container_width=True)

with tab_rules:
    st.subheader("Define a custom logical rule")
    st.caption("Example: flag rows where 'amount' > 1,000,000")
    rc1, rc2, rc3 = st.columns(3)
    rule_column = rc1.selectbox("Column", numeric_cols) if numeric_cols else None
    rule_op = rc2.selectbox("Condition", ["<=", ">=", "<", ">", "==", "!="])
    rule_value = rc3.number_input("Value", value=1000000.0)
    rule_message = st.text_input("Message (shown when this rule is violated)", value="Custom rule violated")

    if st.button("➕ Add rule") and rule_column:
        rules = st.session_state.get("custom_rules", [])
        rules.append(
            {
                "type": "threshold",
                "column": rule_column,
                "op": rule_op,
                "value": rule_value,
                "message": rule_message,
                "severity": "high",
            }
        )
        st.session_state["custom_rules"] = rules
        st.success("Rule added. Click **Run Analysis** again to apply it.")

    if st.session_state.get("custom_rules"):
        st.write("**Active custom rules:**")
        st.json(st.session_state["custom_rules"])
        if st.button("Clear custom rules"):
            st.session_state["custom_rules"] = []

# --------------------------------------------------------------------------
# Downloads
# --------------------------------------------------------------------------
st.divider()
st.subheader("⬇️ Downloads")
dl1, dl2 = st.columns(2)
with dl1:
    st.download_button(
        "Download Cleaned CSV",
        data=export_cleaned_csv(cleaned_df),
        file_name="cleaned_data.csv",
        mime="text/csv",
        use_container_width=True,
    )
with dl2:
    st.download_button(
        "Download Report (HTML)",
        data=export_report_html(full_summary, issues),
        file_name="data_quality_report.html",
        mime="text/html",
        use_container_width=True,
        help="Open the HTML file and use your browser's Print > Save as PDF to get a PDF version.",
    )