"""
Sidebar component: filters, data source selector, system health monitor, and controls.
"""

import streamlit as st
import pandas as pd
from pathlib import Path
from utils.data_loader import discover_s3_csvs, load_csv, load_uploaded_file, SAMPLE_DATA_PATH
from utils.hackathon_data import check_data_sources
from utils.llm import get_llm_provider_status


def _render_system_health():
    """Render the System Health Monitor / Anti-Stub Check in the sidebar."""
    st.subheader("🩺 System Health")

    data_status = check_data_sources()
    llm_status = get_llm_provider_status()

    # ── Data Authenticity ────────────────────────────────────────────────
    if data_status["has_live_data"]:
        sources = []
        if data_status["s3_csvs"]:
            sources.append(f"S3 ({len(data_status['s3_csvs'])} CSVs)")
        if data_status["hackathon_cra"]:
            sources.append("CRA")
        if data_status["hackathon_fed"]:
            sources.append("FED")
        if data_status["hackathon_ab"]:
            sources.append("AB")
        st.markdown(
            f'<div style="background:#064e3b;border-radius:8px;padding:8px 12px;margin-bottom:8px">'
            f'<span style="color:#34d399;font-weight:600">🟢 LIVE DATA</span><br>'
            f'<span style="color:#a7f3d0;font-size:0.78rem">{", ".join(sources)}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    elif data_status["hackathon_schemas"]:
        st.markdown(
            '<div style="background:#78350f;border-radius:8px;padding:8px 12px;margin-bottom:8px">'
            '<span style="color:#fbbf24;font-weight:600">🟡 SCHEMA ONLY</span><br>'
            '<span style="color:#fde68a;font-size:0.78rem">Hackathon schemas found, no JSONL data</span>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="background:#7f1d1d;border-radius:8px;padding:8px 12px;margin-bottom:8px">'
            '<span style="color:#f87171;font-weight:600">🔴 STUBBED DATA</span><br>'
            '<span style="color:#fca5a5;font-size:0.78rem">Running on local fallback samples</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.warning(
            "⚠️ Dashboard is using sample data. Mount S3 bucket or download "
            "hackathon JSONL data to enable live analysis.",
            icon="⚠️",
        )

    # ── LLM Provider ────────────────────────────────────────────────────
    if llm_status["cohere_active"]:
        st.markdown(
            '<div style="background:#3b0764;border-radius:8px;padding:8px 12px;margin-bottom:8px">'
            '<span style="color:#c084fc;font-weight:600">🟣 COHERE ACTIVE</span><br>'
            '<span style="color:#e9d5ff;font-size:0.78rem">Command R+ ready</span>'
            '</div>',
            unsafe_allow_html=True,
        )
    elif llm_status["is_cohere"] and not llm_status["has_key"]:
        st.markdown(
            '<div style="background:#7f1d1d;border-radius:8px;padding:8px 12px;margin-bottom:8px">'
            '<span style="color:#f87171;font-weight:600">🔴 COHERE — NO KEY</span><br>'
            '<span style="color:#fca5a5;font-size:0.78rem">Set COHERE_API_KEY in .env</span>'
            '</div>',
            unsafe_allow_html=True,
        )
    elif llm_status["provider"] in ("bedrock", "gemini"):
        provider_name = llm_status["provider"].upper()
        st.markdown(
            f'<div style="background:#1e3a5f;border-radius:8px;padding:8px 12px;margin-bottom:8px">'
            f'<span style="color:#60a5fa;font-weight:600">🔵 {provider_name} ACTIVE</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="background:#374151;border-radius:8px;padding:8px 12px;margin-bottom:8px">'
            '<span style="color:#9ca3af;font-weight:600">⚪ PLACEHOLDER LLM</span><br>'
            '<span style="color:#d1d5db;font-size:0.78rem">Set LLM_PROVIDER in .env</span>'
            '</div>',
            unsafe_allow_html=True,
        )

    st.divider()


def render_sidebar(raw_df: pd.DataFrame, source_label: str) -> tuple[pd.DataFrame, str, str]:
    """
    Render the sidebar and return (filtered_df, selected_department, selected_category).
    """
    with st.sidebar:
        st.title("🔍 Lens Dashboard")
        st.caption(f"📂 Source: **{source_label}**")
        st.divider()

        # ── System Health Monitor ────────────────────────────────────────
        _render_system_health()

        # ── Data Source ──────────────────────────────────────────────────
        st.subheader("Data Source")
        s3_files = discover_s3_csvs()

        data_source = st.radio(
            "Choose data source",
            options=["Auto (S3 → Sample)", "Upload CSV"] + (
                [f"S3: {f.name}" for f in s3_files] if s3_files else []
            ),
            index=0,
            label_visibility="collapsed",
        )

        if data_source == "Upload CSV":
            uploaded = st.file_uploader("Upload procurement CSV", type=["csv"])
            if uploaded:
                try:
                    raw_df = load_uploaded_file(uploaded)
                    st.success(f"Loaded {len(raw_df):,} rows")
                except ValueError as e:
                    st.error(str(e))
        elif data_source.startswith("S3: "):
            fname = data_source[4:]
            match = next((f for f in s3_files if f.name == fname), None)
            if match:
                try:
                    raw_df = load_csv(match)
                    st.success(f"Loaded {len(raw_df):,} rows from S3")
                except Exception as e:
                    st.error(str(e))

        st.divider()

        # ── Filters ──────────────────────────────────────────────────────
        st.subheader("Filters")

        departments = ["All"] + sorted(raw_df["department"].unique().tolist())
        selected_dept = st.selectbox("Department", departments)

        categories = ["All"] + sorted(raw_df["category"].unique().tolist())
        selected_cat = st.selectbox("Spend Category", categories)

        st.divider()

        # ── Info ─────────────────────────────────────────────────────────
        st.caption("**HHI Thresholds**")
        st.caption("🟢 < 1,500 — Competitive")
        st.caption("🟡 1,500–2,500 — Moderate")
        st.caption("🔴 > 2,500 — Highly Concentrated")
        st.divider()
        st.caption("Agency 2026 Hackathon · Team 38 · **Lens**")

    # Apply filters
    filtered = raw_df.copy()
    if selected_dept != "All":
        filtered = filtered[filtered["department"] == selected_dept]
    if selected_cat != "All":
        filtered = filtered[filtered["category"] == selected_cat]

    return filtered, selected_dept, selected_cat
