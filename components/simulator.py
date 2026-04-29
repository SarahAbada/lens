"""
Scenario Simulator: Force Diversification

Reallocates 10% of spend from the top vendor(s) to smaller vendors,
then recomputes analytics to show the resilience improvement.
"""

import pandas as pd
import numpy as np
from utils.analytics import compute_hhi, compute_resilience_score, vendor_market_share


REALLOCATION_PCT = 0.10  # 10% of top-vendor spend is redistributed


def simulate_diversification(df: pd.DataFrame) -> dict:
    """
    Simulate a 10% budget reallocation from the dominant vendor(s)
    to the bottom 50% of vendors (by spend).

    Returns a dict with:
      simulated_df       – modified spend dataframe (vendor, spend_amount, share_pct)
      original_df        – original vendor spend dataframe
      original_hhi       – float
      simulated_hhi      – float
      original_score     – float
      simulated_score    – float
      reallocation_table – DataFrame describing the transfers
    """
    if df.empty:
        return {}

    share_df = vendor_market_share(df)
    total_spend = share_df["spend_amount"].sum()

    # Identify dominant vendors (top 50% of spend by value)
    cumulative = share_df["spend_amount"].cumsum() / total_spend
    dominant_mask = cumulative.shift(fill_value=0) < 0.50
    dominant_vendors = share_df.loc[dominant_mask, "vendor"].tolist()

    # Identify small vendors (bottom half by spend)
    small_vendors = share_df.loc[~dominant_mask, "vendor"].tolist()

    if not small_vendors:
        # Edge case: only one or two vendors — add a synthetic "New Vendor" entry
        small_vendors = ["New Vendor A", "New Vendor B"]
        new_rows = pd.DataFrame(
            {
                "vendor": small_vendors,
                "spend_amount": [1.0, 1.0],
                "share_pct": [0.0, 0.0],
            }
        )
        share_df = pd.concat([share_df, new_rows], ignore_index=True)

    # Amount to move: 10% of each dominant vendor's spend
    reallocation_amount = (
        share_df.loc[share_df["vendor"].isin(dominant_vendors), "spend_amount"].sum()
        * REALLOCATION_PCT
    )

    # Distribute equally among small vendors
    per_small = reallocation_amount / len(small_vendors)

    simulated = share_df.copy()
    simulated["spend_amount"] = simulated["spend_amount"].astype(float)
    simulated.loc[simulated["vendor"].isin(dominant_vendors), "spend_amount"] *= (
        1 - REALLOCATION_PCT
    )
    simulated.loc[simulated["vendor"].isin(small_vendors), "spend_amount"] += per_small

    # Recompute shares
    new_total = simulated["spend_amount"].sum()
    simulated["share_pct"] = (simulated["spend_amount"] / new_total * 100).round(2)
    simulated = simulated.sort_values("spend_amount", ascending=False).reset_index(drop=True)

    # Build a synthetic df for HHI/resilience recalculation
    def _to_spend_df(vdf):
        return vdf.rename(columns={"spend_amount": "spend_amount"})[["vendor", "spend_amount"]]

    orig_spend_df = _to_spend_df(share_df)
    sim_spend_df = _to_spend_df(simulated)

    original_hhi = compute_hhi(orig_spend_df)
    simulated_hhi = compute_hhi(sim_spend_df)
    original_score = compute_resilience_score(orig_spend_df)
    simulated_score = compute_resilience_score(sim_spend_df)

    # Reallocation summary table
    transfers = []
    for v in dominant_vendors:
        orig_amt = share_df.loc[share_df["vendor"] == v, "spend_amount"].values[0]
        moved = orig_amt * REALLOCATION_PCT
        transfers.append({"From Vendor": v, "Amount Moved ($)": moved})
    for v in small_vendors:
        transfers.append({"To Vendor": v, "Amount Received ($)": per_small})

    realloc_table = pd.DataFrame(
        [
            {
                "Vendor": t.get("From Vendor", t.get("To Vendor")),
                "Direction": "↓ Reduced" if "From Vendor" in t else "↑ Increased",
                "Amount ($)": t.get("Amount Moved ($)", t.get("Amount Received ($)")),
            }
            for t in transfers
        ]
    )

    return {
        "simulated_df": simulated,
        "original_df": share_df,
        "original_hhi": original_hhi,
        "simulated_hhi": simulated_hhi,
        "original_score": original_score,
        "simulated_score": simulated_score,
        "reallocation_table": realloc_table,
        "reallocation_amount": reallocation_amount,
        "dominant_vendors": dominant_vendors,
        "small_vendors": small_vendors,
    }
