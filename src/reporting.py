"""
reporting.py

Turns raw issue lists + before/after profiling snapshots into:
  - a summary dict (counts, percentages, breakdowns)
  - Plotly charts (missing %, outlier distribution, issues by severity)
  - exportable HTML report and CSV of the cleaned data
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

Issue = Dict[str, Any]


def summarize_issues(issues: List[Issue], total_rows: int) -> Dict[str, Any]:
    """Builds the headline numbers for the report: totals, % of dataset
    affected, and breakdowns by issue type / column / severity.
    """
    affected_rows = {i["row_index"] for i in issues if i["row_index"] is not None}
    by_type = Counter(i["issue_type"] for i in issues)
    by_column = Counter(i["column"] for i in issues if i["column"] is not None)
    by_severity = Counter(i["severity"] for i in issues)

    return {
        "total_issues": len(issues),
        "rows_affected": len(affected_rows),
        "pct_rows_affected": round((len(affected_rows) / total_rows) * 100, 2) if total_rows else 0.0,
        "by_type": dict(by_type),
        "by_column": dict(by_column),
        "by_severity": dict(by_severity),
    }


def build_before_after_summary(
    before_profile: Dict[str, Any],
    after_profile: Dict[str, Any],
    issue_summary: Dict[str, Any],
    cleaning_log_actions: List[str],
) -> Dict[str, Any]:
    """Assembles the full before/after comparison shown at the top of the report."""
    return {
        "rows_before": before_profile["n_rows"],
        "rows_after": after_profile["n_rows"],
        "rows_removed": before_profile["n_rows"] - after_profile["n_rows"],
        "columns": before_profile["n_columns"],
        "issue_summary": issue_summary,
        "cleaning_actions": cleaning_log_actions,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


# --------------------------------------------------------------------------
# Charts
# --------------------------------------------------------------------------

def chart_missing_by_column(profile: Dict[str, Any]) -> go.Figure:
    """Bar chart of % missing values per column."""
    columns = list(profile["columns"].keys())
    pct_missing = [profile["columns"][c]["missing_pct"] for c in columns]
    fig = px.bar(
        x=columns,
        y=pct_missing,
        labels={"x": "Column", "y": "% Missing"},
        title="Missing Values by Column",
    )
    fig.update_layout(yaxis_ticksuffix="%", showlegend=False)
    return fig


def chart_outlier_distribution(df: pd.DataFrame, column: str) -> go.Figure:
    """Box plot showing the distribution of a numeric column, useful for
    visually spotting outliers alongside the IQR/z-score detectors."""
    fig = px.box(df, y=column, points="outliers", title=f"Distribution of '{column}' (outliers highlighted)")
    return fig


def chart_issues_by_severity(issue_summary: Dict[str, Any]) -> go.Figure:
    """Pie chart of issue counts by severity level."""
    severity_counts = issue_summary.get("by_severity", {})
    if not severity_counts:
        fig = go.Figure()
        fig.update_layout(title="Issues by Severity (none found)")
        return fig
    color_map = {"high": "#d62728", "medium": "#ff7f0e", "low": "#2ca02c"}
    labels = list(severity_counts.keys())
    fig = px.pie(
        names=labels,
        values=list(severity_counts.values()),
        title="Issues by Severity",
        color=labels,
        color_discrete_map=color_map,
    )
    return fig


def chart_issues_by_type(issue_summary: Dict[str, Any]) -> go.Figure:
    """Bar chart of issue counts by issue type."""
    by_type = issue_summary.get("by_type", {})
    fig = px.bar(
        x=list(by_type.keys()),
        y=list(by_type.values()),
        labels={"x": "Issue Type", "y": "Count"},
        title="Issues by Type",
    )
    fig.update_layout(showlegend=False)
    return fig


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------

def export_cleaned_csv(df: pd.DataFrame) -> bytes:
    """Serializes the cleaned DataFrame to CSV bytes, ready for download."""
    return df.to_csv(index=False).encode("utf-8")


def export_report_html(summary: Dict[str, Any], issues: List[Issue]) -> bytes:
    """Renders a self-contained HTML summary report (no external assets),
    suitable for downloading and sharing/printing to PDF from a browser.
    """
    issue_summary = summary["issue_summary"]

    def _rows(items: Dict[str, int]) -> str:
        return "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in items.items())

    issues_table_rows = "".join(
        f"<tr><td>{i['row_index'] if i['row_index'] is not None else '-'}</td>"
        f"<td>{i['column'] or '-'}</td><td>{i['issue_type']}</td>"
        f"<td class='sev-{i['severity']}'>{i['severity']}</td><td>{i['details']}</td></tr>"
        for i in issues[:500]  # cap for very large issue lists
    )

    html = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>Data Quality Report</title>
        <style>
            body {{ font-family: -apple-system, Arial, sans-serif; margin: 2rem; color: #1a1a1a; }}
            h1, h2 {{ color: #1a1a1a; }}
            table {{ border-collapse: collapse; width: 100%; margin-bottom: 2rem; }}
            th, td {{ border: 1px solid #ddd; padding: 6px 10px; text-align: left; font-size: 14px; }}
            th {{ background-color: #f4f4f4; }}
            .sev-high {{ color: #d62728; font-weight: bold; }}
            .sev-medium {{ color: #ff7f0e; }}
            .sev-low {{ color: #2ca02c; }}
            .metric {{ display: inline-block; margin-right: 2rem; }}
            .metric .value {{ font-size: 28px; font-weight: bold; }}
        </style>
    </head>
    <body>
        <h1>Data Quality Report</h1>
        <p>Generated: {summary['generated_at']}</p>

        <div>
            <div class="metric"><div class="value">{summary['rows_before']}</div>Rows before</div>
            <div class="metric"><div class="value">{summary['rows_after']}</div>Rows after</div>
            <div class="metric"><div class="value">{summary['rows_removed']}</div>Rows removed</div>
            <div class="metric"><div class="value">{issue_summary['total_issues']}</div>Total issues found</div>
            <div class="metric"><div class="value">{issue_summary['pct_rows_affected']}%</div>Rows affected</div>
        </div>

        <h2>Auto-cleaning actions applied</h2>
        <ul>{"".join(f"<li>{a}</li>" for a in summary['cleaning_actions']) or "<li>No automatic fixes were needed.</li>"}</ul>

        <h2>Issues by Type</h2>
        <table><tr><th>Type</th><th>Count</th></tr>{_rows(issue_summary['by_type'])}</table>

        <h2>Issues by Column</h2>
        <table><tr><th>Column</th><th>Count</th></tr>{_rows(issue_summary['by_column'])}</table>

        <h2>Issues by Severity</h2>
        <table><tr><th>Severity</th><th>Count</th></tr>{_rows(issue_summary['by_severity'])}</table>

        <h2>Detailed Issue List {'(showing first 500)' if len(issues) > 500 else ''}</h2>
        <table>
            <tr><th>Row</th><th>Column</th><th>Issue Type</th><th>Severity</th><th>Details</th></tr>
            {issues_table_rows}
        </table>
    </body>
    </html>
    """
    return html.encode("utf-8")
