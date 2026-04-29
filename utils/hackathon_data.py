"""
Hackathon data loader — connects to the shared hackathon PostgreSQL database
(CRA, FED, AB, general schemas) using the connection string from the hackathon
repo's .env.public files.

Fallback chain:
  1. PostgreSQL via DB_CONNECTION_STRING (from hackathon .env.public / .env)
  2. JSONL files from hackathon/.local-db/data/ (if downloaded)
  3. Empty DataFrame (graceful degradation)

Also provides helpers for the Golden Record Dossier and data-availability checks.
"""

import json
import os
import re
import pandas as pd
import streamlit as st
from pathlib import Path

HACKATHON_ROOT = Path(__file__).parent.parent.parent / "hackathon"
LOCAL_DB_DATA = HACKATHON_ROOT / ".local-db" / "data"
S3_MOUNT = Path(__file__).parent.parent.parent / "data" / "agency-s3"


# ---------------------------------------------------------------------------
# Database connection — reads from hackathon .env.public / .env files
# ---------------------------------------------------------------------------

def _find_db_connection_string() -> str | None:
    """
    Discover the DB_CONNECTION_STRING by checking (in priority order):
      1. Dashboard's own .env  (DB_CONNECTION_STRING)
      2. Environment variable  (DB_CONNECTION_STRING)
      3. hackathon/general/.env.public  then  hackathon/general/.env
      4. hackathon/FED/.env.public      then  hackathon/FED/.env
      5. hackathon/CRA/.env.public      then  hackathon/CRA/.env
      6. Local Postgres default (sarah@localhost/hackathon)
    """
    # Already in environment?
    conn = os.getenv("DB_CONNECTION_STRING")
    if conn and conn.startswith("postgresql"):
        return conn

    # Scan hackathon .env.public and .env files
    search_dirs = ["general", "FED", "CRA", "AB"]
    for subdir in search_dirs:
        for fname in [".env.public", ".env"]:
            env_path = HACKATHON_ROOT / subdir / fname
            if env_path.exists():
                try:
                    with open(env_path, "r") as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("#") or "=" not in line:
                                continue
                            key, _, val = line.partition("=")
                            if key.strip() == "DB_CONNECTION_STRING" and val.strip().startswith("postgresql"):
                                return val.strip()
                except Exception:
                    continue

    # Fallback: local Postgres with the hackathon database
    return "postgresql://sarah@localhost:5432/hackathon"


def _get_pg_connection():
    """Return a psycopg2 connection or None if unavailable."""
    conn_str = _find_db_connection_string()
    if not conn_str:
        return None
    try:
        import psycopg2  # type: ignore
        conn = psycopg2.connect(conn_str)
        return conn
    except ImportError:
        # psycopg2 not installed — try psycopg (v3)
        try:
            import psycopg  # type: ignore
            conn = psycopg.connect(conn_str)
            return conn
        except Exception:
            return None
    except Exception:
        return None


def _query_pg(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Execute a SQL query against the hackathon database and return a DataFrame."""
    conn = _get_pg_connection()
    if conn is None:
        return pd.DataFrame()
    try:
        df = pd.read_sql_query(sql, conn, params=params)
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# JSONL reader (streaming, column-filtered) — fallback when no DB
# ---------------------------------------------------------------------------

def _read_jsonl(path: Path, columns: list[str] | None = None, max_rows: int | None = None) -> pd.DataFrame:
    """Read a JSONL file, optionally selecting only specific columns."""
    if not path.exists():
        return pd.DataFrame()
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if max_rows and i >= max_rows:
                break
            row = json.loads(line)
            if columns:
                row = {k: row.get(k) for k in columns}
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# CRA Identification (charity registry)
# ---------------------------------------------------------------------------

CRA_ID_COLS = ["bn", "fiscal_year", "legal_name", "category", "designation",
               "city", "province", "registration_date"]

@st.cache_data(show_spinner="Loading CRA data...", ttl=3600)
def load_cra_identification() -> pd.DataFrame:
    """Load CRA charity identification data. Tries Postgres first, then JSONL."""
    df = _query_pg("""
        SELECT bn, fiscal_year, legal_name, category, designation,
               city, province, registration_date
        FROM cra.cra_identification
    """)
    if not df.empty:
        df["fiscal_year"] = pd.to_numeric(df["fiscal_year"], errors="coerce")
        return df

    # Fallback: JSONL
    path = LOCAL_DB_DATA / "cra" / "cra_identification.jsonl"
    df = _read_jsonl(path, CRA_ID_COLS)
    if not df.empty:
        df["fiscal_year"] = pd.to_numeric(df["fiscal_year"], errors="coerce")
    return df


@st.cache_data(show_spinner="Loading CRA financials...", ttl=3600)
def load_cra_financials() -> pd.DataFrame:
    """Load CRA financial details (key revenue fields only)."""
    df = _query_pg("""
        SELECT bn, fpe, field_4540, field_4550, field_4560, field_4700,
               field_5100, field_4200
        FROM cra.cra_financial_details
    """)
    if not df.empty:
        return df

    path = LOCAL_DB_DATA / "cra" / "cra_financial_details.jsonl"
    cols = ["bn", "fpe", "field_4540", "field_4550", "field_4560", "field_4700",
            "field_5100", "field_4200"]
    df = _read_jsonl(path, cols)
    if not df.empty:
        for c in cols[2:]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


# ---------------------------------------------------------------------------
# FED Grants
# ---------------------------------------------------------------------------

FED_COLS = ["_id", "recipient_business_number", "recipient_legal_name",
            "agreement_value", "agreement_type", "agreement_start_date",
            "owner_org", "owner_org_title", "prog_name_en", "recipient_type",
            "is_amendment", "recipient_province"]

@st.cache_data(show_spinner="Loading FED grants...", ttl=3600)
def load_fed_grants() -> pd.DataFrame:
    """Load federal grants and contributions. Tries Postgres first, then JSONL."""
    df = _query_pg(f"""
        SELECT {', '.join(FED_COLS)}
        FROM fed.grants_contributions
    """)
    if not df.empty:
        df["agreement_value"] = pd.to_numeric(df["agreement_value"], errors="coerce")
        return df

    # Fallback: JSONL
    path = LOCAL_DB_DATA / "fed" / "grants_contributions.jsonl"
    df = _read_jsonl(path, FED_COLS)
    if not df.empty:
        df["agreement_value"] = pd.to_numeric(df["agreement_value"], errors="coerce")
    return df


# ---------------------------------------------------------------------------
# AB Grants
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Loading AB grants...", ttl=3600)
def load_ab_grants() -> pd.DataFrame:
    """Load Alberta grants. Tries Postgres first, then JSONL."""
    df = _query_pg("""
        SELECT ministry, recipient, program, amount, display_fiscal_year
        FROM ab.ab_grants
    """)
    if not df.empty:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        return df

    path = LOCAL_DB_DATA / "ab" / "ab_grants.jsonl"
    cols = ["ministry", "recipient", "program", "amount", "display_fiscal_year"]
    df = _read_jsonl(path, cols)
    if not df.empty:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    return df


# ---------------------------------------------------------------------------
# Golden Records (entity resolution)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Loading golden records...", ttl=3600)
def load_golden_records() -> pd.DataFrame:
    """Load the entity golden records for cross-dataset search."""
    df = _query_pg("""
        SELECT id, canonical_name, norm_name, entity_type, bn_root,
               bn_variants, dataset_sources, source_link_count,
               cra_profile, fed_profile, ab_profile, confidence, status
        FROM general.entity_golden_records
        LIMIT 100000
    """)
    if not df.empty:
        return df

    path = LOCAL_DB_DATA / "general" / "entity_golden_records.jsonl"
    cols = ["id", "canonical_name", "norm_name", "entity_type", "bn_root",
            "bn_variants", "dataset_sources", "source_link_count",
            "cra_profile", "fed_profile", "ab_profile", "confidence", "status"]
    return _read_jsonl(path, cols)


# ---------------------------------------------------------------------------
# Data availability checks
# ---------------------------------------------------------------------------

def check_data_sources() -> dict:
    """
    Check which data sources are available and return a status dict.
    """
    s3_csvs = []
    if S3_MOUNT.exists():
        s3_csvs = sorted(str(p) for p in S3_MOUNT.rglob("*.csv"))

    # Check Postgres connectivity
    db_conn_str = _find_db_connection_string()
    has_db = False
    if db_conn_str:
        conn = _get_pg_connection()
        if conn:
            has_db = True
            try:
                conn.close()
            except Exception:
                pass

    # Check JSONL files
    cra_jsonl = (LOCAL_DB_DATA / "cra" / "cra_identification.jsonl").exists()
    fed_jsonl = (LOCAL_DB_DATA / "fed" / "grants_contributions.jsonl").exists()
    ab_jsonl = (LOCAL_DB_DATA / "ab" / "ab_grants.jsonl").exists()
    gen_jsonl = (LOCAL_DB_DATA / "general" / "entity_golden_records.jsonl").exists()

    # Check hackathon repo structure exists
    hackathon_schemas = any(
        (HACKATHON_ROOT / d).exists() for d in ["CRA", "FED", "AB"]
    )

    has_live = bool(s3_csvs) or has_db or cra_jsonl or fed_jsonl or ab_jsonl

    return {
        "s3_csvs": s3_csvs,
        "has_db": has_db,
        "db_connection": "connected" if has_db else ("configured" if db_conn_str else "none"),
        "hackathon_cra": has_db or cra_jsonl,
        "hackathon_fed": has_db or fed_jsonl,
        "hackathon_ab": has_db or ab_jsonl,
        "hackathon_general": has_db or gen_jsonl,
        "hackathon_schemas": hackathon_schemas,
        "has_live_data": has_live,
    }


# ---------------------------------------------------------------------------
# BN Search (Golden Record Dossier)
# ---------------------------------------------------------------------------

def extract_bn_root(bn: str) -> str | None:
    """Extract 9-digit root from a BN string."""
    if not bn:
        return None
    cleaned = re.sub(r"\s+", "", bn)
    match = re.match(r"^(\d{9})", cleaned)
    return match.group(1) if match else None


def search_by_bn(bn_query: str, cra_df: pd.DataFrame, fed_df: pd.DataFrame) -> dict:
    """
    Search CRA and FED datasets by Business Number root.
    Returns a dossier dict with CRA charity info and FED grant records.
    """
    root = extract_bn_root(bn_query)
    if not root:
        return {"error": f"Invalid BN format: {bn_query}"}

    result = {"bn_root": root, "cra": None, "fed": None, "risk_flags": []}

    # CRA lookup
    if not cra_df.empty and "bn" in cra_df.columns:
        cra_matches = cra_df[cra_df["bn"].str.startswith(root, na=False)]
        if not cra_matches.empty:
            latest = cra_matches.sort_values("fiscal_year", ascending=False).iloc[0]
            result["cra"] = {
                "bn": latest.get("bn", ""),
                "legal_name": latest.get("legal_name", "Unknown"),
                "category": latest.get("category", ""),
                "designation": latest.get("designation", ""),
                "city": latest.get("city", ""),
                "province": latest.get("province", ""),
                "registration_date": str(latest.get("registration_date", "")),
                "fiscal_years": sorted(cra_matches["fiscal_year"].dropna().unique().tolist()),
            }

    # FED lookup
    if not fed_df.empty and "recipient_business_number" in fed_df.columns:
        fed_matches = fed_df[
            fed_df["recipient_business_number"].str.startswith(root, na=False)
        ]
        if not fed_matches.empty:
            originals = fed_matches[fed_matches.get("is_amendment", True) == False]
            if originals.empty:
                originals = fed_matches
            total_value = originals["agreement_value"].sum()
            grant_count = len(originals)
            departments = originals["owner_org_title"].dropna().unique().tolist()
            programs = originals["prog_name_en"].dropna().unique().tolist()[:10]

            result["fed"] = {
                "total_grants": float(total_value),
                "grant_count": int(grant_count),
                "departments": departments[:10],
                "programs": programs,
                "recipient_name": originals["recipient_legal_name"].mode().iloc[0]
                    if not originals["recipient_legal_name"].mode().empty else "Unknown",
                "top_grants": originals.nlargest(5, "agreement_value")[
                    ["agreement_value", "owner_org_title", "prog_name_en", "agreement_start_date"]
                ].to_dict("records"),
            }

    # Risk flags
    if result["cra"] and result["fed"]:
        fed_total = result["fed"]["total_grants"]
        if fed_total > 1_000_000:
            result["risk_flags"].append(
                f"🔴 High federal funding: ${fed_total:,.0f} across {result['fed']['grant_count']} grants"
            )
        if result["fed"]["grant_count"] > 20:
            result["risk_flags"].append(
                f"🟡 High grant volume: {result['fed']['grant_count']} federal grants"
            )
        if len(result["fed"]["departments"]) == 1:
            result["risk_flags"].append(
                f"🟡 Single-department dependency: all grants from {result['fed']['departments'][0]}"
            )
    elif result["fed"] and not result["cra"]:
        result["risk_flags"].append(
            "🔴 Entity receives federal grants but has NO CRA charity registration"
        )

    return result
