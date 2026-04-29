"""
Vendor Concentration & Resilience Dashboard — "Lens"
Agency 2026 Hackathon — Team 38

Run:
    cd dashboard
    streamlit run app.py
"""

# Load .env BEFORE any other imports that read env vars
from pathlib import Path as _Path
from dotenv import load_dotenv as _load_dotenv
_load_dotenv(_Path(__file__).parent / ".env")

import streamlit as st
import pandas as pd

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="Lens — Transparency Dashboard",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Local imports ─────────────────────────────────────────────────────────────
from utils.data_loader import load_data
from utils.analytics import (
    compute_hhi,
    hhi_label,
    top_n_concentration,
    compute_resilience_score,
    department_summary,
    vendor_market_share,
)
from utils.llm import generate_risk_briefing, generate_accountability_briefs, get_llm_provider_status
from utils.hackathon_data import (
    load_cra_identification,
    load_cra_financials,
    load_fed_grants,
    load_golden_records,
    search_by_bn,
    check_data_sources,
)
from utils.security import run_security_audit
from components.sidebar import render_sidebar
from components.charts import (
    vendor_market_share_chart,
    resilience_gauge,
    department_hhi_chart,
    scenario_comparison_chart,
    funding_sunburst_chart,
)
from components.simulator import simulate_diversification

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .metric-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        border: 1px solid rgba(255,255,255,0.08);
        color: white;
    }
    .metric-label { font-size: 0.78rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }
    .metric-value { font-size: 2rem; font-weight: 700; margin: 0.2rem 0; }
    .metric-sub   { font-size: 0.82rem; color: #64748b; }
    .risk-high   { color: #ef4444; }
    .risk-medium { color: #f59e0b; }
    .risk-low    { color: #10b981; }
    .briefing-box {
        background: #0f172a;
        border-left: 4px solid #6366f1;
        border-radius: 8px;
        padding: 1.2rem 1.5rem;
        color: #e2e8f0;
        font-size: 0.92rem;
        line-height: 1.7;
        white-space: pre-wrap;
    }
    .dossier-card {
        background: linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%);
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        border: 1px solid rgba(99,102,241,0.3);
        color: white;
        margin-bottom: 1rem;
    }
    .security-clean {
        background: #064e3b;
        border-radius: 8px;
        padding: 1rem;
        color: #34d399;
        font-weight: 600;
        text-align: center;
    }
    .security-alert {
        background: #7f1d1d;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        color: #fca5a5;
        margin-bottom: 0.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def get_base_data():
    return load_data()


raw_df, source_label = get_base_data()

# ── Sidebar (filters + data source + health monitor) ─────────────────────────
filtered_df, selected_dept, selected_cat = render_sidebar(raw_df, source_label)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("## 🔍 Lens — Vendor Concentration & Resilience Dashboard")
st.caption(
    f"Analyzing **{len(filtered_df):,}** contracts · "
    f"**{filtered_df['vendor'].nunique()}** vendors · "
    f"**{filtered_df['department'].nunique()}** departments"
)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_overview, tab_dossier, tab_sunburst, tab_analyst, tab_security = st.tabs([
    "📊 Overview",
    "🔎 Golden Record Dossier",
    "☀️ Funding Sunburst",
    "🤖 Strategic Analyst",
    "🔒 Security Audit",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: OVERVIEW (original dashboard)
# ══════════════════════════════════════════════════════════════════════════════
with tab_overview:
    if filtered_df.empty:
        st.warning("No data matches the current filters. Adjust the sidebar selections.")
        st.stop()

    # Core analytics
    hhi = compute_hhi(filtered_df)
    resilience = compute_resilience_score(filtered_df)
    top3 = top_n_concentration(filtered_df, n=3)
    share_df = vendor_market_share(filtered_df)
    total_spend = filtered_df["spend_amount"].sum()

    def _risk_class(score):
        if score >= 60:
            return "risk-low"
        elif score >= 35:
            return "risk-medium"
        return "risk-high"

    # KPI Row
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            f"""<div class="metric-card">
                <div class="metric-label">Total Spend</div>
                <div class="metric-value">${total_spend:,.0f}</div>
                <div class="metric-sub">{len(filtered_df):,} contracts</div>
            </div>""",
            unsafe_allow_html=True,
        )

    with col2:
        hhi_cls = "risk-high" if hhi >= 2500 else "risk-medium" if hhi >= 1500 else "risk-low"
        st.markdown(
            f"""<div class="metric-card">
                <div class="metric-label">HHI Score</div>
                <div class="metric-value {hhi_cls}">{hhi:,.0f}</div>
                <div class="metric-sub">{hhi_label(hhi)}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    with col3:
        r_cls = _risk_class(resilience)
        st.markdown(
            f"""<div class="metric-card">
                <div class="metric-label">Resilience Score</div>
                <div class="metric-value {r_cls}">{resilience}/100</div>
                <div class="metric-sub">{"Low Risk" if resilience >= 60 else "Moderate Risk" if resilience >= 35 else "High Risk"}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    with col4:
        top3_cls = "risk-high" if top3["combined_share_pct"] >= 70 else "risk-medium" if top3["combined_share_pct"] >= 50 else "risk-low"
        st.markdown(
            f"""<div class="metric-card">
                <div class="metric-label">Top-3 Concentration</div>
                <div class="metric-value {top3_cls}">{top3['combined_share_pct']:.1f}%</div>
                <div class="metric-sub">of total spend</div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Charts Row
    chart_col, gauge_col = st.columns([3, 1], gap="large")

    with chart_col:
        chart_title = f"Vendor Market Share — {selected_dept} / {selected_cat}"
        st.plotly_chart(
            vendor_market_share_chart(share_df, title=chart_title),
            use_container_width=True,
        )

    with gauge_col:
        st.plotly_chart(resilience_gauge(resilience), use_container_width=True)
        st.markdown("**Top 3 Vendors**")
        for rank, (vendor, spend, share) in enumerate(top3["vendors"], 1):
            bar_color = "#ef4444" if share >= 40 else "#f59e0b" if share >= 25 else "#10b981"
            st.markdown(
                f"""<div style="margin-bottom:8px">
                    <div style="display:flex;justify-content:space-between;font-size:0.82rem">
                        <span>#{rank} {vendor}</span><span>{share:.1f}%</span>
                    </div>
                    <div style="background:#1e293b;border-radius:4px;height:6px;margin-top:3px">
                        <div style="background:{bar_color};width:{min(share,100):.1f}%;height:6px;border-radius:4px"></div>
                    </div>
                </div>""",
                unsafe_allow_html=True,
            )

    st.divider()

    # Department Overview
    with st.expander("📊 Department-Level HHI Overview", expanded=(selected_dept == "All")):
        dept_summary_df = department_summary(raw_df)
        left, right = st.columns([2, 1])
        with left:
            st.plotly_chart(department_hhi_chart(dept_summary_df), use_container_width=True)
        with right:
            st.markdown("**Department Summary**")
            display_cols = ["department", "total_spend", "vendor_count", "hhi", "resilience_score"]
            fmt_df = dept_summary_df[display_cols].copy()
            fmt_df["total_spend"] = fmt_df["total_spend"].apply(lambda x: f"${x:,.0f}")
            fmt_df["hhi"] = fmt_df["hhi"].apply(lambda x: f"{x:,.0f}")
            fmt_df["resilience_score"] = fmt_df["resilience_score"].apply(lambda x: f"{x:.1f}")
            fmt_df.columns = ["Department", "Total Spend", "Vendors", "HHI", "Resilience"]
            st.dataframe(fmt_df, use_container_width=True, hide_index=True)

    st.divider()

    # AI Risk Briefing
    st.markdown("### 🤖 AI Strategic Risk Briefing")
    llm_info = get_llm_provider_status()
    st.caption(f"Provider: **{llm_info['provider'].upper()}** — click to generate")

    if st.button("⚡ Generate Risk Briefing", type="primary", key="risk_briefing"):
        with st.spinner("Analyzing vendor concentration patterns..."):
            briefing = generate_risk_briefing(
                filtered_df=filtered_df, hhi=hhi, resilience_score=resilience,
                top3=top3, department=selected_dept, category=selected_cat,
            )
        st.markdown(f'<div class="briefing-box">{briefing}</div>', unsafe_allow_html=True)
    else:
        st.info("Click **Generate Risk Briefing** for an AI-powered analysis.")

    st.divider()

    # Scenario Simulator
    st.markdown("### 🔀 Scenario Simulator")
    st.caption("Simulate reallocating 10% of dominant-vendor spend to smaller suppliers.")
    force_diversify = st.toggle("🔄 Force Diversification (10% Reallocation)", value=False)

    if force_diversify:
        sim = simulate_diversification(filtered_df)
        if sim:
            delta_hhi = sim["simulated_hhi"] - sim["original_hhi"]
            delta_score = sim["simulated_score"] - sim["original_score"]
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Original HHI", f"{sim['original_hhi']:,.0f}")
            m2.metric("Simulated HHI", f"{sim['simulated_hhi']:,.0f}", delta=f"{delta_hhi:+,.0f}", delta_color="inverse")
            m3.metric("Original Resilience", f"{sim['original_score']:.1f}")
            m4.metric("Simulated Resilience", f"{sim['simulated_score']:.1f}", delta=f"{delta_score:+.1f}")
            st.markdown(
                f"**${sim['reallocation_amount']:,.0f}** reallocated from "
                f"**{', '.join(sim['dominant_vendors'])}** → "
                f"**{len(sim['small_vendors'])}** smaller vendors"
            )
            st.plotly_chart(
                scenario_comparison_chart(sim["original_df"], sim["simulated_df"]),
                use_container_width=True,
            )
            with st.expander("📋 Reallocation Detail"):
                st.dataframe(sim["reallocation_table"], use_container_width=True, hide_index=True)
        else:
            st.warning("Not enough data to run the simulation.")
    else:
        st.info("Toggle **Force Diversification** above to run the scenario simulation.")

    st.divider()

    # Raw Data Explorer
    with st.expander("🗂️ Raw Data Explorer"):
        st.dataframe(
            filtered_df.sort_values("spend_amount", ascending=False),
            use_container_width=True, hide_index=True,
        )
        csv_bytes = filtered_df.to_csv(index=False).encode()
        st.download_button(
            "⬇️ Download filtered data as CSV",
            data=csv_bytes, file_name="filtered_procurement.csv", mime="text/csv",
        )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: GOLDEN RECORD DOSSIER
# ══════════════════════════════════════════════════════════════════════════════
with tab_dossier:
    st.markdown("### 🔎 Golden Record Dossier")
    st.caption(
        "Cross-dataset entity search. Enter a Business Number (BN) to join "
        "CRA charity data with FED grant records and build a risk profile."
    )

    data_status = check_data_sources()

    bn_input = st.text_input(
        "Business Number (BN)",
        placeholder="e.g. 119058893 or 119058893RR0001",
        help="Enter a 9-digit BN root or full 15-character BN",
    )

    if bn_input:
        with st.spinner("Searching across CRA and FED datasets..."):
            cra_df = load_cra_identification()
            fed_df = load_fed_grants()

            if cra_df.empty and fed_df.empty:
                st.warning(
                    "⚠️ No hackathon data loaded. Download the JSONL data bundle to "
                    "`hackathon/.local-db/data/` to enable cross-dataset search."
                )
                # Show what we'd display with a demo
                st.info(
                    "**Demo mode:** With live data, this would show:\n"
                    "- CRA charity registration details\n"
                    "- Federal grant history\n"
                    "- Cross-dataset risk flags\n"
                    "- Financial profile from T3010 filings"
                )
            else:
                dossier = search_by_bn(bn_input, cra_df, fed_df)

                if "error" in dossier:
                    st.error(dossier["error"])
                else:
                    st.markdown(f"**BN Root:** `{dossier['bn_root']}`")

                    # Risk flags
                    if dossier["risk_flags"]:
                        st.markdown("#### ⚠️ Risk Flags")
                        for flag in dossier["risk_flags"]:
                            st.markdown(f"- {flag}")

                    col_cra, col_fed = st.columns(2)

                    with col_cra:
                        st.markdown("#### 🏛️ CRA Charity Profile")
                        if dossier["cra"]:
                            cra = dossier["cra"]
                            st.markdown(
                                f"""<div class="dossier-card">
                                    <div style="font-size:1.1rem;font-weight:600;margin-bottom:8px">{cra['legal_name']}</div>
                                    <div style="font-size:0.85rem;color:#94a3b8">
                                        BN: {cra['bn']}<br>
                                        Category: {cra['category']} · Designation: {cra['designation']}<br>
                                        Location: {cra['city']}, {cra['province']}<br>
                                        Registered: {cra['registration_date']}<br>
                                        Filing Years: {', '.join(str(y) for y in cra['fiscal_years'])}
                                    </div>
                                </div>""",
                                unsafe_allow_html=True,
                            )
                        else:
                            st.info("No CRA charity record found for this BN.")

                    with col_fed:
                        st.markdown("#### 💰 Federal Grants Profile")
                        if dossier["fed"]:
                            fed = dossier["fed"]
                            st.markdown(
                                f"""<div class="dossier-card">
                                    <div style="font-size:1.1rem;font-weight:600;margin-bottom:8px">{fed['recipient_name']}</div>
                                    <div style="font-size:0.85rem;color:#94a3b8">
                                        Total Grants: ${fed['total_grants']:,.0f}<br>
                                        Grant Count: {fed['grant_count']}<br>
                                        Departments: {', '.join(fed['departments'][:3])}<br>
                                        Programs: {', '.join(fed['programs'][:3])}
                                    </div>
                                </div>""",
                                unsafe_allow_html=True,
                            )

                            if fed["top_grants"]:
                                st.markdown("**Top 5 Grants:**")
                                top_grants_df = pd.DataFrame(fed["top_grants"])
                                if "agreement_value" in top_grants_df.columns:
                                    top_grants_df["agreement_value"] = top_grants_df["agreement_value"].apply(
                                        lambda x: f"${x:,.0f}" if pd.notna(x) else "N/A"
                                    )
                                st.dataframe(top_grants_df, use_container_width=True, hide_index=True)
                        else:
                            st.info("No federal grant records found for this BN.")

    else:
        st.info(
            "Enter a Business Number above to search. Examples of BN formats:\n"
            "- `119058893` (9-digit root)\n"
            "- `119058893RR0001` (full CRA BN)\n\n"
            "The dossier joins CRA T3010 charity filings with federal grant records."
        )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: FUNDING SUNBURST
# ══════════════════════════════════════════════════════════════════════════════
with tab_sunburst:
    st.markdown("### ☀️ Federal Funding Sunburst")
    st.caption("Department → Grant Type → Top Recipient flow visualization")

    fed_df = load_fed_grants()

    if fed_df.empty:
        st.warning(
            "No FED grant data available. Download the hackathon JSONL data bundle "
            "to `hackathon/.local-db/data/fed/` to enable this visualization."
        )
        st.info(
            "**What this shows:** A Plotly Sunburst chart mapping the flow of federal "
            "funding from departments through grant types (Grant/Contribution/Other) "
            "to the top recipients. Hover to see dollar values and percentages."
        )
    else:
        top_n = st.slider("Top N departments to show", 5, 20, 10)
        st.plotly_chart(
            funding_sunburst_chart(fed_df, top_n=top_n),
            use_container_width=True,
        )

        # Summary stats
        originals = fed_df[fed_df.get("is_amendment", True) == False] if "is_amendment" in fed_df.columns else fed_df
        total_val = originals["agreement_value"].sum()
        dept_count = originals["owner_org_title"].nunique()
        recipient_count = originals["recipient_legal_name"].nunique()

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Grant Value", f"${total_val:,.0f}")
        c2.metric("Departments", f"{dept_count:,}")
        c3.metric("Unique Recipients", f"{recipient_count:,}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4: COHERE STRATEGIC ANALYST
# ══════════════════════════════════════════════════════════════════════════════
with tab_analyst:
    st.markdown("### 🤖 Cohere Strategic Analyst")
    llm_info = get_llm_provider_status()

    if llm_info["cohere_active"]:
        st.success("🟣 Cohere Command R+ is active and ready.")
    else:
        st.info(
            f"Current LLM provider: **{llm_info['provider'].upper()}**. "
            "Set `LLM_PROVIDER=cohere` and `COHERE_API_KEY` in `.env` for live Cohere analysis."
        )

    st.caption(
        "Pass the top high-risk entities to the LLM and generate investigative "
        "Accountability Briefs — 3-point memos for each entity."
    )

    # Build high-risk entity list from current data
    st.markdown("#### High-Risk Entity Selection")

    # Use the filtered procurement data to identify high-risk vendors
    if not filtered_df.empty:
        share_df_analyst = vendor_market_share(filtered_df)
        high_risk = share_df_analyst[share_df_analyst["share_pct"] >= 20].head(5)

        if high_risk.empty:
            high_risk = share_df_analyst.head(5)

        entities_for_analysis = []
        for _, row in high_risk.iterrows():
            entities_for_analysis.append({
                "name": row["vendor"],
                "bn": "N/A",
                "fed_total": float(row["spend_amount"]),
                "fed_count": 0,
                "cra_revenue": 0,
                "flags": [
                    f"Market share: {row['share_pct']:.1f}%",
                    "High concentration" if row["share_pct"] >= 30 else "Moderate concentration",
                ],
            })

        st.markdown("**Entities selected for analysis:**")
        for i, e in enumerate(entities_for_analysis, 1):
            flags_str = " · ".join(e["flags"])
            st.markdown(f"{i}. **{e['name']}** — ${e['fed_total']:,.0f} ({flags_str})")

        if st.button("📝 Generate Accountability Briefs", type="primary", key="accountability"):
            with st.spinner("Generating investigative memos..."):
                briefs = generate_accountability_briefs(entities_for_analysis)
            st.markdown(briefs)
        else:
            st.info("Click **Generate Accountability Briefs** to produce investigative memos.")
    else:
        st.warning("No data available. Adjust filters in the sidebar.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5: SECURITY AUDIT
# ══════════════════════════════════════════════════════════════════════════════
with tab_security:
    st.markdown("### 🔒 Security Audit")
    st.caption(
        "Scan the S3 mount and data directories for unencrypted sensitive files, "
        "leaked keys in CSV headers, and credential files."
    )

    scan_col1, scan_col2 = st.columns(2)
    scan_s3 = scan_col1.checkbox("Scan S3 Mount (../data/agency-s3)", value=True)
    scan_hack = scan_col2.checkbox("Scan Hackathon Repo (../hackathon)", value=False)

    if st.button("🔍 Run Security Scan", type="primary", key="security_scan"):
        with st.spinner("Scanning data directories..."):
            report = run_security_audit(scan_s3=scan_s3, scan_hackathon=scan_hack)

        st.markdown(f"**Scanned:** {report.scan_path}")
        st.markdown(f"**Files checked:** {report.files_scanned:,}")

        if report.is_clean:
            st.markdown(
                '<div class="security-clean">✅ CLEAN — No security issues detected</div>',
                unsafe_allow_html=True,
            )
        else:
            # Summary metrics
            s1, s2, s3 = st.columns(3)
            s1.metric("🔴 HIGH", report.high_count)
            s2.metric("🟡 MEDIUM", report.medium_count)
            s3.metric("🟢 LOW", report.low_count)

            # Findings table
            st.markdown("#### Findings")
            for finding in sorted(report.findings, key=lambda f: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[f.severity]):
                severity_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}[finding.severity]
                st.markdown(
                    f"""<div class="security-alert">
                        {severity_icon} <strong>[{finding.severity}]</strong> {finding.category}<br>
                        <span style="font-size:0.82rem">{finding.file_path}</span><br>
                        <span style="font-size:0.82rem;color:#d1d5db">{finding.detail}</span>
                    </div>""",
                    unsafe_allow_html=True,
                )
    else:
        st.info(
            "Click **Run Security Scan** to check data directories for:\n"
            "- 🔑 Unencrypted private keys (.pem, .key, .pfx)\n"
            "- 📋 Leaked API keys/tokens in CSV headers\n"
            "- 🔐 Credential files (.env, credentials.json)\n"
            "- 🕵️ Secret values (AWS keys, GitHub PATs) in data files"
        )
