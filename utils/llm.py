"""
LLM integration for Strategic Risk Briefings and Accountability Briefs.

Supports:
  - Amazon Bedrock (Claude 3 Sonnet) via boto3
  - Google Gemini via google-generativeai
  - Cohere (hackathon North SDK at zkrx5.democloud.cohere.com)
  - Offline placeholder (no API key required)

Set LLM_PROVIDER in .env to "bedrock", "gemini", "cohere", or "placeholder" (default).
For Cohere: set COHERE_API_KEY to your authToken from the hackathon demo cloud.
"""

import os
import json
import textwrap
import pandas as pd

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "placeholder").lower()
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")
BEDROCK_REGION = os.getenv("AWS_REGION", "us-east-1")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
COHERE_API_KEY = os.getenv("COHERE_API_KEY", "")
COHERE_MODEL = os.getenv("COHERE_MODEL", "command-r-plus")


# ---------------------------------------------------------------------------
# Prompt builder — Risk Briefing
# ---------------------------------------------------------------------------

def _build_prompt(
    filtered_df: pd.DataFrame,
    hhi: float,
    resilience_score: float,
    top3: dict,
    department: str,
    category: str,
) -> str:
    top3_lines = "\n".join(
        f"  {i+1}. {v[0]}: ${v[1]:,.0f} ({v[2]:.1f}%)"
        for i, v in enumerate(top3["vendors"])
    )
    vendor_count = filtered_df["vendor"].nunique()
    total_spend = filtered_df["spend_amount"].sum()

    return textwrap.dedent(f"""
        You are a government procurement risk analyst. Analyze the following vendor
        concentration data and produce a concise Strategic Risk Briefing (3–5 bullet points).

        FILTER CONTEXT
        --------------
        Department  : {department}
        Category    : {category}
        Total Spend : ${total_spend:,.0f}
        Vendor Count: {vendor_count}

        CONCENTRATION METRICS
        ---------------------
        HHI Score         : {hhi:.0f} / 10,000
        Resilience Score  : {resilience_score:.1f} / 100
        Top-3 Combined    : {top3['combined_share_pct']:.1f}%

        TOP VENDORS
        -----------
        {top3_lines}

        INSTRUCTIONS
        ------------
        - Identify the primary concentration risk.
        - Flag any single-vendor dependency (>40% share).
        - Recommend 2–3 concrete diversification actions.
        - Note any supply-chain resilience concerns.
        - Keep the tone professional and actionable.
        - Format as bullet points starting with "•".
    """).strip()


# ---------------------------------------------------------------------------
# Prompt builder — Accountability Brief (Cohere feature)
# ---------------------------------------------------------------------------

def _build_accountability_prompt(entities: list[dict]) -> str:
    """Build a prompt for Cohere to generate investigative memos."""
    entity_lines = []
    for i, e in enumerate(entities[:5], 1):
        entity_lines.append(
            f"  {i}. {e.get('name', 'Unknown')} (BN: {e.get('bn', 'N/A')})\n"
            f"     - Federal Grants: ${e.get('fed_total', 0):,.0f} ({e.get('fed_count', 0)} grants)\n"
            f"     - CRA Revenue: ${e.get('cra_revenue', 0):,.0f}\n"
            f"     - Risk Flags: {', '.join(e.get('flags', ['None']))}"
        )

    return textwrap.dedent(f"""
        You are an investigative analyst for a government accountability hackathon.
        Draft a 3-point investigative memo for EACH of the following high-risk entities.

        Each memo should:
        1. Summarize the entity's funding profile and why it warrants scrutiny.
        2. Identify specific red flags (concentration, sole-source dependency,
           discrepancy between CRA filings and federal grant records).
        3. Recommend concrete next steps for investigation.

        HIGH-RISK ENTITIES
        ------------------
        {chr(10).join(entity_lines)}

        FORMAT
        ------
        For each entity, output:
        ## [Entity Name]
        **1. Profile Summary:** ...
        **2. Red Flags:** ...
        **3. Recommended Actions:** ...

        Keep each memo to 3–5 sentences per point. Be specific and cite the numbers.
    """).strip()


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------

def _call_bedrock(prompt: str) -> str:
    try:
        import boto3  # type: ignore

        client = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 512,
                "messages": [{"role": "user", "content": prompt}],
            }
        )
        response = client.invoke_model(modelId=BEDROCK_MODEL_ID, body=body)
        result = json.loads(response["body"].read())
        return result["content"][0]["text"]
    except Exception as exc:
        return f"⚠️ Bedrock call failed: {exc}\n\n{_placeholder_briefing(prompt)}"


def _call_gemini(prompt: str) -> str:
    try:
        import google.generativeai as genai  # type: ignore

        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)
        return response.text
    except Exception as exc:
        return f"⚠️ Gemini call failed: {exc}\n\n{_placeholder_briefing(prompt)}"


def _call_cohere(prompt: str) -> str:
    """Call Cohere via the hackathon North SDK (zkrx5.democloud.cohere.com)."""
    try:
        import north  # type: ignore

        client = north.NorthClient(
            auth_token=COHERE_API_KEY,
            base_url="https://zkrx5.democloud.cohere.com",
        )
        response = client.chat(
            messages=[{"role": "user", "content": prompt}],
        )
        # Extract text from the response
        if hasattr(response, "messages") and response.messages:
            last_msg = response.messages[-1]
            if hasattr(last_msg, "content"):
                content = last_msg.content
                if isinstance(content, str):
                    return content
                elif isinstance(content, list):
                    texts = []
                    for block in content:
                        if hasattr(block, "text"):
                            texts.append(block.text)
                        elif isinstance(block, dict) and "text" in block:
                            texts.append(block["text"])
                        elif isinstance(block, str):
                            texts.append(block)
                    return "\n".join(texts) if texts else str(content)
                return str(content)
        if hasattr(response, "text"):
            return response.text
        if hasattr(response, "message") and hasattr(response.message, "content"):
            content = response.message.content
            if isinstance(content, list) and content:
                return content[0].text if hasattr(content[0], "text") else str(content[0])
            return str(content)
        return str(response)
    except Exception as exc:
        return f"⚠️ Cohere call failed: {exc}\n\n{_placeholder_briefing(prompt)}"


def _placeholder_briefing(prompt: str) -> str:
    """
    Deterministic placeholder that returns a realistic-looking briefing
    without any API call.
    """
    return textwrap.dedent("""
        • **High Concentration Risk Detected** — The top 3 vendors account for a
          disproportionate share of total spend, creating significant single-point
          failure exposure if any vendor experiences disruption.

        • **Single-Vendor Dependency** — At least one vendor exceeds the 40% spend
          threshold, which violates best-practice diversification guidelines and
          increases negotiation leverage risk.

        • **Recommended Action 1** — Initiate a competitive re-solicitation for the
          largest contract at next renewal, targeting a minimum of 3 qualified bidders
          to reduce incumbent lock-in.

        • **Recommended Action 2** — Allocate 10–15% of the next budget cycle to
          pre-qualified small/medium vendors to build a resilient supplier pipeline.

        • **Recommended Action 3** — Establish quarterly vendor performance reviews
          with explicit diversification KPIs tied to procurement officer evaluations.

        *(This briefing was generated by the offline placeholder. Set LLM_PROVIDER
        to bedrock, gemini, or cohere in your .env file to enable live AI analysis.)*
    """).strip()


def _placeholder_accountability(entities: list[dict]) -> str:
    """Placeholder accountability brief when no LLM is configured."""
    lines = []
    for e in entities[:5]:
        name = e.get("name", "Unknown Entity")
        fed = e.get("fed_total", 0)
        cra = e.get("cra_revenue", 0)
        flags = e.get("flags", [])
        lines.append(textwrap.dedent(f"""
            ## {name}
            **1. Profile Summary:** This entity received ${fed:,.0f} in federal grants
            and reported ${cra:,.0f} in CRA revenue. It warrants scrutiny due to the
            scale of public funding relative to its operational profile.

            **2. Red Flags:** {'; '.join(flags) if flags else 'Concentration risk detected — entity appears across multiple funding streams with limited diversification.'}

            **3. Recommended Actions:** Cross-reference CRA T3010 filings against
            federal disbursement records. Verify that reported federal revenue
            (field_4540) aligns with actual grant values. Review board composition
            for potential conflicts of interest.
        """).strip())

    header = "*(Placeholder — set LLM_PROVIDER=cohere for live Cohere Command R+ analysis)*\n\n"
    return header + "\n\n---\n\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_llm_provider_status() -> dict:
    """Return the current LLM provider status for the sidebar."""
    return {
        "provider": LLM_PROVIDER,
        "is_cohere": LLM_PROVIDER == "cohere",
        "cohere_active": LLM_PROVIDER == "cohere" and bool(COHERE_API_KEY),
        "has_key": bool(COHERE_API_KEY) if LLM_PROVIDER == "cohere" else True,
    }


def generate_risk_briefing(
    filtered_df: pd.DataFrame,
    hhi: float,
    resilience_score: float,
    top3: dict,
    department: str = "All",
    category: str = "All",
) -> str:
    """
    Generate a Strategic Risk Briefing for the current filter context.
    Dispatches to the configured LLM provider or falls back to the placeholder.
    """
    prompt = _build_prompt(filtered_df, hhi, resilience_score, top3, department, category)

    if LLM_PROVIDER == "bedrock":
        return _call_bedrock(prompt)
    elif LLM_PROVIDER == "gemini":
        return _call_gemini(prompt)
    elif LLM_PROVIDER == "cohere":
        return _call_cohere(prompt)
    else:
        return _placeholder_briefing(prompt)


def generate_accountability_briefs(entities: list[dict]) -> str:
    """
    Generate investigative Accountability Briefs for high-risk entities.
    Uses Cohere Command R+ when available, otherwise placeholder.
    """
    prompt = _build_accountability_prompt(entities)

    if LLM_PROVIDER == "cohere" and COHERE_API_KEY:
        return _call_cohere(prompt)
    elif LLM_PROVIDER == "bedrock":
        return _call_bedrock(prompt)
    elif LLM_PROVIDER == "gemini":
        return _call_gemini(prompt)
    else:
        return _placeholder_accountability(entities)
