"""
Fetch data directly from the Open Canada CKAN API and load into local Postgres.

This is the fast-path for hackathon participants who have Postgres running
but haven't downloaded the 13 GB JSONL data bundle yet. It pulls the FED
grants dataset in batches via the datastore_search API.

Usage:
    python -m utils.fetch_opencanada          # fetch 50K records (demo)
    python -m utils.fetch_opencanada --all    # fetch all ~1.3M records
"""

import json
import sys
import urllib.request
import urllib.parse
from pathlib import Path

# FED grants resource UUID from hackathon/FED/config/dataset-inventory.json
FED_RESOURCE_ID = "1d15a62f-5656-49ad-8c88-f40ce689d831"
API_BASE = "https://open.canada.ca/data/en/api/3/action/datastore_search"

# Columns we need for the dashboard (subset of the full schema)
FED_COLUMNS = [
    "_id", "ref_number", "amendment_number", "agreement_type",
    "recipient_type", "recipient_business_number", "recipient_legal_name",
    "recipient_operating_name", "recipient_province", "recipient_city",
    "prog_name_en", "agreement_value", "agreement_start_date",
    "agreement_end_date", "owner_org", "owner_org_title",
]


def fetch_fed_batch(offset: int = 0, limit: int = 10000) -> dict:
    """Fetch a batch of FED grants from the Open Canada API."""
    params = urllib.parse.urlencode({
        "resource_id": FED_RESOURCE_ID,
        "limit": limit,
        "offset": offset,
        "fields": ",".join(FED_COLUMNS),
    })
    url = f"{API_BASE}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "Lens-Dashboard/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("result", {})


def fetch_and_insert_to_postgres(max_records: int = 50000, batch_size: int = 10000):
    """Fetch FED grants from the API and insert into local Postgres."""
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)

    conn_str = "postgresql://sarah@localhost:5432/hackathon"
    conn = psycopg2.connect(conn_str)
    cur = conn.cursor()

    # Check if table already has data
    cur.execute("SELECT COUNT(*) FROM fed.grants_contributions")
    existing = cur.fetchone()[0]
    if existing > 0 and max_records <= existing:
        print(f"fed.grants_contributions already has {existing:,} rows. Skipping fetch.")
        conn.close()
        return existing
    elif existing > 0:
        print(f"fed.grants_contributions has {existing:,} rows. Continuing from offset {existing}...")
        offset = existing
        total_inserted = existing
    else:
        total_inserted = 0
        offset = 0

    while total_inserted < max_records:
        batch_limit = min(batch_size, max_records - total_inserted)
        print(f"  Fetching offset={offset}, limit={batch_limit} ...")

        try:
            result = fetch_fed_batch(offset=offset, limit=batch_limit)
        except Exception as e:
            print(f"  API error at offset {offset}: {e}")
            break

        records = result.get("records", [])
        if not records:
            print(f"  No more records at offset {offset}.")
            break

        # Build INSERT
        insert_cols = [
            "_id", "ref_number", "amendment_number", "agreement_type",
            "recipient_type", "recipient_business_number", "recipient_legal_name",
            "recipient_operating_name", "recipient_province", "recipient_city",
            "prog_name_en", "agreement_value", "agreement_start_date",
            "agreement_end_date", "owner_org", "owner_org_title",
        ]

        values_list = []
        for r in records:
            row = []
            for col in insert_cols:
                val = r.get(col)
                if val == "" or val is None:
                    row.append(None)
                elif col == "_id":
                    row.append(int(val))
                elif col == "agreement_value":
                    try:
                        row.append(float(val))
                    except (ValueError, TypeError):
                        row.append(None)
                else:
                    row.append(str(val) if val is not None else None)
            values_list.append(tuple(row))

        col_names = ", ".join(insert_cols)
        placeholders = ", ".join(["%s"] * len(insert_cols))
        sql = f"INSERT INTO fed.grants_contributions ({col_names}) VALUES ({placeholders}) ON CONFLICT (_id) DO NOTHING"

        try:
            psycopg2.extras.execute_batch(cur, sql, values_list, page_size=1000)
            conn.commit()
            total_inserted += len(records)
            print(f"  Inserted batch: {len(records)} rows (total: {total_inserted:,})")
        except Exception as e:
            conn.rollback()
            print(f"  Insert error: {e}")
            break

        offset += batch_limit

        # Check if we've reached the end
        total_available = result.get("total", 0)
        if offset >= total_available:
            print(f"  Reached end of dataset ({total_available:,} total records)")
            break

    conn.close()
    print(f"\nDone. Inserted {total_inserted:,} FED grant records into local Postgres.")
    return total_inserted


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Fetch FED grants from Open Canada API")
    parser.add_argument("--all", action="store_true", help="Fetch all records (~1.3M)")
    parser.add_argument("--limit", type=int, default=50000, help="Max records to fetch")
    args = parser.parse_args()

    max_recs = 2_000_000 if args.all else args.limit
    print(f"Fetching up to {max_recs:,} FED grant records from Open Canada API...")
    fetch_and_insert_to_postgres(max_records=max_recs)
