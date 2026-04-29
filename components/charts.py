"""
Plotly chart components for the Vendor Concentration & Resilience Dashboard.
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------

PALETTE = px.colors.qualitative.Bold
RISK_RED = "#EF4444"
RISK_AMBER = "#F59E0B"
RISK_GREEN = "#10B981"


def _risk_color(score: float) -> str:
    if score >= 60:
        return RISK_GREEN
    elif score >= 35:
        return RISK_AMBER
    return RISK_RED


# ---------------------------------------------------------------------------
# Vendor Market Share Bar Chart
# ---------------------------------------------------------------------------

def vendor_market_share_chart(share_df: pd.DataFrame, title: str = "Vendor Market Share") -> go.Figure:
    """
    Horizontal bar chart of vendor spend share.
    Top vendors are highlighted; a 40% risk threshold line is drawn.
    """
    if share_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data available", showarrow=False, font_size=16)
        return fig

    # Limit to top 15 for readability
    df = share_df.head(15).copy()
    df = df.sort_values("share_pct", ascending=True)  # ascending for horizontal bar

    colors = [RISK_RED if s >= 40 else PALETTE[i % len(PALETTE)] for i, s in enumerate(df["share_pct"])]

    fig = go.Figure(
        go.Bar(
            x=df["share_pct"],
            y=df["vendor"],
            orientation="h",
            marker_color=colors,
            text=[f"${s:,.0f}<br>{p:.1f}%" for s, p in zip(df["spend_amount"], df["share_pct"])],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Spend: $%{customdata:,.0f}<br>Share: %{x:.1f}%<extra></extra>",
            customdata=df["spend_amount"],
        )
    )

    # 40% risk threshold line
    fig.add_vline(
        x=40,
        line_dash="dash",
        line_color=RISK_RED,
        annotation_text="40% Risk Threshold",
        annotation_position="top right",
        annotation_font_color=RISK_RED,
    )

    fig.update_layout(
        title=dict(text=title, font_size=18),
        xaxis_title="Market Share (%)",
        yaxis_title="",
        xaxis=dict(range=[0, max(df["share_pct"].max() * 1.25, 50)]),
        height=max(350, len(df) * 42),
        margin=dict(l=20, r=120, t=60, b=40),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif"),
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(128,128,128,0.15)")
    fig.update_yaxes(showgrid=False)
    return fig


# ---------------------------------------------------------------------------
# Resilience Score Gauge
# ---------------------------------------------------------------------------

def resilience_gauge(score: float, title: str = "Resilience Score") -> go.Figure:
    """
    Gauge chart showing the Resilience Score (1–100).
    Color zones: red (0–35), amber (35–60), green (60–100).
    """
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=score,
            title={"text": title, "font": {"size": 18}},
            delta={"reference": 50, "increasing": {"color": RISK_GREEN}, "decreasing": {"color": RISK_RED}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "gray"},
                "bar": {"color": _risk_color(score), "thickness": 0.3},
                "bgcolor": "white",
                "borderwidth": 2,
                "bordercolor": "gray",
                "steps": [
                    {"range": [0, 35], "color": "rgba(239,68,68,0.15)"},
                    {"range": [35, 60], "color": "rgba(245,158,11,0.15)"},
                    {"range": [60, 100], "color": "rgba(16,185,129,0.15)"},
                ],
                "threshold": {
                    "line": {"color": "black", "width": 3},
                    "thickness": 0.75,
                    "value": score,
                },
            },
            number={"suffix": "/100", "font": {"size": 36, "color": _risk_color(score)}},
        )
    )
    fig.update_layout(
        height=280,
        margin=dict(l=30, r=30, t=60, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif"),
    )
    return fig


# ---------------------------------------------------------------------------
# HHI Comparison Bar Chart (across departments)
# ---------------------------------------------------------------------------

def department_hhi_chart(summary_df: pd.DataFrame) -> go.Figure:
    """Bar chart comparing HHI across all departments."""
    if summary_df.empty:
        return go.Figure()

    df = summary_df.sort_values("hhi", ascending=False)
    colors = [
        RISK_RED if h >= 2500 else RISK_AMBER if h >= 1500 else RISK_GREEN
        for h in df["hhi"]
    ]

    fig = go.Figure(
        go.Bar(
            x=df["department"],
            y=df["hhi"],
            marker_color=colors,
            text=df["hhi"].apply(lambda h: f"{h:,.0f}"),
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>HHI: %{y:,.0f}<br>",
        )
    )

    # Threshold lines
    for threshold, label, color in [
        (1500, "Moderate (1,500)", RISK_AMBER),
        (2500, "High (2,500)", RISK_RED),
    ]:
        fig.add_hline(
            y=threshold,
            line_dash="dash",
            line_color=color,
            annotation_text=label,
            annotation_position="right",
            annotation_font_color=color,
        )

    fig.update_layout(
        title=dict(text="HHI by Department", font_size=18),
        yaxis_title="HHI Score",
        xaxis_title="",
        height=380,
        margin=dict(l=20, r=100, t=60, b=40),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif"),
    )
    fig.update_yaxes(showgrid=True, gridcolor="rgba(128,128,128,0.15)")
    return fig


# ---------------------------------------------------------------------------
# Scenario Simulator: Before / After Reallocation
# ---------------------------------------------------------------------------

def scenario_comparison_chart(
    original_df: pd.DataFrame,
    simulated_df: pd.DataFrame,
) -> go.Figure:
    """Side-by-side bar chart comparing original vs. diversified vendor spend."""
    orig = original_df.set_index("vendor")["spend_amount"]
    sim = simulated_df.set_index("vendor")["spend_amount"]
    all_vendors = sorted(set(orig.index) | set(sim.index))

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name="Current Spend",
            x=all_vendors,
            y=[orig.get(v, 0) for v in all_vendors],
            marker_color="rgba(99,102,241,0.8)",
        )
    )
    fig.add_trace(
        go.Bar(
            name="After Diversification",
            x=all_vendors,
            y=[sim.get(v, 0) for v in all_vendors],
            marker_color="rgba(16,185,129,0.8)",
        )
    )

    fig.update_layout(
        barmode="group",
        title=dict(text="Scenario: Force Diversification (10% Reallocation)", font_size=18),
        yaxis_title="Spend ($)",
        xaxis_title="",
        height=400,
        margin=dict(l=20, r=20, t=60, b=80),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(tickangle=-30),
    )
    fig.update_yaxes(showgrid=True, gridcolor="rgba(128,128,128,0.15)")
    return fig


# ---------------------------------------------------------------------------
# Funding Sunburst Chart: Department → Category → Top Recipient
# ---------------------------------------------------------------------------

def funding_sunburst_chart(fed_df: pd.DataFrame, top_n: int = 10) -> go.Figure:
    """
    Plotly Sunburst chart: Funding Department → Grant Category → Top Recipient.

    Expects a FED grants DataFrame with columns:
      owner_org_title, agreement_type, recipient_legal_name, agreement_value
    """
    if fed_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No FED grant data available", showarrow=False, font_size=16)
        fig.update_layout(height=400)
        return fig

    # Filter to originals only if is_amendment column exists
    df = fed_df.copy()
    if "is_amendment" in df.columns:
        df = df[df["is_amendment"] == False]

    df = df.dropna(subset=["owner_org_title", "agreement_value"])
    df["agreement_value"] = pd.to_numeric(df["agreement_value"], errors="coerce").fillna(0)
    df = df[df["agreement_value"] > 0]

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No positive-value grants found", showarrow=False, font_size=16)
        fig.update_layout(height=400)
        return fig

    # Map agreement_type to readable labels
    type_map = {"G": "Grant", "C": "Contribution", "O": "Other"}
    df["category"] = df.get("agreement_type", pd.Series(dtype=str)).map(type_map).fillna("Other")

    # Shorten department names for readability
    df["dept_short"] = df["owner_org_title"].str.split("|").str[0].str.strip().str[:40]

    # Get top departments by total value
    top_depts = (
        df.groupby("dept_short")["agreement_value"]
        .sum()
        .nlargest(top_n)
        .index.tolist()
    )
    df = df[df["dept_short"].isin(top_depts)]

    # Get top recipients per department+category
    df["recipient_short"] = df.get(
        "recipient_legal_name", pd.Series(dtype=str)
    ).fillna("Unknown").str[:35]

    # Build sunburst data
    sunburst_data = (
        df.groupby(["dept_short", "category", "recipient_short"])["agreement_value"]
        .sum()
        .reset_index()
    )

    # Keep only top 5 recipients per dept+category to avoid clutter
    sunburst_data = (
        sunburst_data
        .sort_values("agreement_value", ascending=False)
        .groupby(["dept_short", "category"])
        .head(5)
        .reset_index(drop=True)
    )

    fig = px.sunburst(
        sunburst_data,
        path=["dept_short", "category", "recipient_short"],
        values="agreement_value",
        color="agreement_value",
        color_continuous_scale="Viridis",
        title="Federal Funding Flow: Department → Type → Recipient",
    )

    fig.update_layout(
        height=550,
        margin=dict(l=10, r=10, t=50, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif"),
        coloraxis_colorbar=dict(title="Value ($)"),
    )
    fig.update_traces(
        textinfo="label+percent parent",
        hovertemplate="<b>%{label}</b><br>Value: $%{value:,.0f}<br>Share: %{percentParent:.1%}<extra></extra>",
    )

    return fig
