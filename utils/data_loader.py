"""
Data loading utilities for the Vendor Concentration & Resilience Dashboard.
Supports loading from local CSV, S3-mounted path, or uploaded file.
"""

import os
import pandas as pd
import streamlit as st
from pathlib import Path

# Path to the S3 bucket mounted via mount-s3
S3_MOUNT_PATH = Path(__file__).parent.parent.parent / "data" / "agency-s3"
SAMPLE_DATA_PATH = Path(__file__).parent.parent / "sample_data.csv"

REQUIRED_COLUMNS = {"department", "vendor", "spend_amount", "category"}


def _validate_and_clean(df: pd.DataFrame) -> pd.DataFrame:
    """Validate required columns exist and clean the dataframe."""
    missing = REQUIRED_COLUMNS - set(df.columns.str.lower())
    if missing:
        raise ValueError(f"Dataset is missing required columns: {missing}")

    # Normalize column names to lowercase
    df.columns = df.columns.str.lower().str.strip()

    # Coerce spend_amount to numeric, drop unparseable rows
    df["spend_amount"] = pd.to_numeric(df["spend_amount"], errors="coerce")
    df = df.dropna(subset=["spend_amount"])
    df["spend_amount"] = df["spend_amount"].abs()

    # Strip whitespace from string columns
    for col in ["department", "vendor", "category"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    return df


def discover_s3_csvs() -> list[Path]:
    """Return a list of CSV files found in the mounted S3 bucket."""
    if not S3_MOUNT_PATH.exists():
        return []
    return sorted(S3_MOUNT_PATH.rglob("*.csv"))


@st.cache_data(show_spinner="Loading data...")
def load_csv(path: str | Path) -> pd.DataFrame:
    """Load and validate a CSV file from a given path."""
    df = pd.read_csv(path)
    return _validate_and_clean(df)


def load_uploaded_file(uploaded_file) -> pd.DataFrame:
    """Load and validate a CSV from a Streamlit UploadedFile object."""
    df = pd.read_csv(uploaded_file)
    return _validate_and_clean(df)


def load_data() -> tuple[pd.DataFrame, str]:
    """
    Master data loader. Returns (dataframe, source_label).

    Priority:
      1. Files found in the mounted S3 bucket (agency-s3)
      2. Sample data bundled with the app
    """
    s3_files = discover_s3_csvs()

    if s3_files:
        # Use the first CSV found; the sidebar lets users pick among them
        source = str(s3_files[0])
        return load_csv(source), f"S3: {s3_files[0].name}"

    # Fall back to bundled sample data
    return load_csv(SAMPLE_DATA_PATH), "Sample Data (demo)"
