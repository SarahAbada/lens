"""
Core analytics for vendor concentration and resilience scoring.

Metrics:
  - HHI  : Herfindahl-Hirschman Index (0–10,000). Higher = more concentrated.
  - Top-3 Concentration: share of spend held by the three largest vendors.
  - Resilience Score: 1–100 inverse of concentration (100 = perfectly diversified).
"""

import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# HHI
# ---------------------------------------------------------------------------

def compute_hhi(df: pd.DataFrame) -> float:
    """
    Compute the Herfindahl-Hirschman Index for a given spend dataframe.

    HHI = Σ (market_share_i * 100)²
    Range: near-0 (perfectly competitive) → 10,000 (monopoly).
    """
    if df.empty or df["spend_amount"].sum() == 0:
        return 0.0

    total = df["spend_amount"].sum()
    shares = df.groupby("vendor")["spend_amount"].sum() / total  # 0–1
    # HHI = sum of squared percentage shares (each share expressed as 0–100)
    hhi = float(((shares * 100) ** 2).sum())
    return round(hhi, 2)


def hhi_label(hhi: float) -> str:
    """Return a human-readable concentration label for an HHI value."""
    if hhi < 1500:
        return "Competitive"
    elif hhi < 2500:
        return "Moderately Concentrated"
    else:
        return "Highly Concentrated"


# ---------------------------------------------------------------------------
# Top-N Concentration
# ---------------------------------------------------------------------------

def top_n_concentration(df: pd.DataFrame, n: int = 3) -> dict:
    """
    Return the top-N vendors by spend and their combined share.

    Returns a dict with keys:
      vendors   – list of (vendor, spend, share_pct) tuples
      combined_share_pct – float
    """
    if df.empty:
        return {"vendors": [], "combined_share_pct": 0.0}

    total = df["spend_amount"].sum()
    by_vendor = (
        df.groupby("vendor")["spend_amount"]
        .sum()
        .sort_values(ascending=False)
        .head(n)
        .reset_index()
    )
    by_vendor["share_pct"] = (by_vendor["spend_amount"] / total * 100).round(2)

    vendors = list(
        zip(by_vendor["vendor"], by_vendor["spend_amount"], by_vendor["share_pct"])
    )
    combined = round(float(by_vendor["share_pct"].sum()), 2)
    return {"vendors": vendors, "combined_share_pct": combined}


# ---------------------------------------------------------------------------
# Resilience Score
# ---------------------------------------------------------------------------

def compute_resilience_score(df: pd.DataFrame) -> float:
    """
    Compute a Resilience Score (1–100).

    Formula:
      score = 100 * (1 - HHI / 10_000)

    A score of 100 means perfectly diversified; 1 means a single vendor
    holds all spend.
    """
    hhi = compute_hhi(df)
    score = 100.0 * (1.0 - hhi / 10_000.0)
    return round(max(1.0, min(100.0, score)), 1)


# ---------------------------------------------------------------------------
# Per-Department Summary
# ---------------------------------------------------------------------------

def department_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a summary DataFrame with one row per department containing:
      total_spend, vendor_count, hhi, resilience_score, top3_share_pct
    """
    rows = []
    for dept, group in df.groupby("department"):
        hhi = compute_hhi(group)
        top3 = top_n_concentration(group, n=3)
        rows.append(
            {
                "department": dept,
                "total_spend": group["spend_amount"].sum(),
                "vendor_count": group["vendor"].nunique(),
                "hhi": hhi,
                "hhi_label": hhi_label(hhi),
                "resilience_score": compute_resilience_score(group),
                "top3_share_pct": top3["combined_share_pct"],
            }
        )
    return pd.DataFrame(rows).sort_values("resilience_score")


# ---------------------------------------------------------------------------
# Vendor Market Share
# ---------------------------------------------------------------------------

def vendor_market_share(df: pd.DataFrame) -> pd.DataFrame:
    """Return vendor spend and share percentage, sorted descending."""
    if df.empty:
        return pd.DataFrame(columns=["vendor", "spend_amount", "share_pct"])

    total = df["spend_amount"].sum()
    result = (
        df.groupby("vendor")["spend_amount"]
        .sum()
        .reset_index()
        .sort_values("spend_amount", ascending=False)
    )
    result["share_pct"] = (result["spend_amount"] / total * 100).round(2)
    return result
