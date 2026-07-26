"""
KSP CrimeIQ — Data Import Module
Supports CSV and Excel uploads to extend or replace the crime database.
Both synthetic and real data can coexist in the same SQLite store.
The 'data_source' column tracks origin of each FIR.
"""

import sqlite3
import json
import os
import random
import math
from datetime import datetime
from typing import Tuple

import pandas as pd

# Import search so we can invalidate its in-memory TF-IDF cache after upload
from analytics.search import reset_index as _reset_search_index
from analytics.predictive import invalidate_model_cache as _invalidate_models



DB_PATH = "data/crime_db.sqlite"

KARNATAKA_DISTRICTS = {
    "bengaluru urban": 1, "bengaluru": 1, "bangalore urban": 1, "bangalore": 1,
    "bengaluru rural": 2, "bangalore rural": 2,
    "mysuru": 3, "mysore": 3,
    "mangaluru": 4, "mangalore": 4,
    "hubballi-dharwad": 5, "hubli-dharwad": 5, "hubli dharwad": 5,
    "belagavi": 6, "belgaum": 6,
    "kalaburagi": 7, "gulbarga": 7,
    "vijayapura": 8, "bijapur": 8,
    "ballari": 9, "bellary": 9,
    "tumakuru": 10, "tumkur": 10,
    "shivamogga": 11, "shimoga": 11,
    "davangere": 12, "davanagere": 12,
    "hassan": 13,
    "chikkamagaluru": 14, "chikmagalur": 14,
    "kodagu": 15, "coorg": 15,
    "udupi": 16,
    "uttara kannada": 17,
    "raichur": 18,
    "koppal": 19,
    "gadag": 20,
    "dharwad": 21,
    "bagalkot": 22,
    "chitradurga": 23,
    "chikkaballapura": 24, "chikballapur": 24,
    "kolar": 25,
    "ramanagara": 26,
    "mandya": 27,
    "chamarajanagara": 28, "chamarajanagar": 28,
    "yadgir": 29,
    "bidar": 30,
    "vijayanagara": 31,
}

CRIME_TYPES = {
    "theft", "assault", "robbery", "cybercrime", "murder",
    "sexual offence", "drugs", "property crime", "economic crime", "abduction"
}

STATUS_MAP = {
    "ui": "Under Investigation", "under investigation": "Under Investigation",
    "cs": "Charge-Sheeted", "charge-sheeted": "Charge-Sheeted", "chargesheeted": "Charge-Sheeted",
    "ct": "Closed-True", "closed-true": "Closed-True", "closed true": "Closed-True",
    "cf": "Closed-False", "closed-false": "Closed-False", "closed false": "Closed-False",
    "pt": "Pending Trial", "pending trial": "Pending Trial", "pending": "Pending Trial",
}

COLUMN_ALIASES = {
    "fir_id": ["fir_id", "fir id", "id", "case_id", "case id"],
    "district": ["district", "district_name", "district name", "dist"],
    "crime_type": ["crime_type", "crime type", "crime", "offence_type", "offence type", "offence"],
    "sub_type": ["sub_type", "sub type", "subtype", "sub-type", "offence_subtype"],
    "date_time": ["date_time", "date time", "datetime", "date", "incident_date", "incident date", "occurrence_date"],
    "lat": ["lat", "latitude"],
    "lon": ["lon", "lng", "longitude"],
    "status": ["status", "case_status", "case status"],
    "weapon": ["weapon", "weapon_used", "weapon used", "arms"],
    "description": ["description", "desc", "details", "narrative", "summary"],
    "mo_tags": ["mo_tags", "mo tags", "modus_operandi", "modus operandi", "mo", "tags"],
}


from db import get_db
_get_db = get_db


def _ensure_data_source_column():
    """Add data_source column to firs table if it doesn't exist."""
    conn = _get_db()
    try:
        conn.execute("ALTER TABLE firs ADD COLUMN data_source TEXT DEFAULT 'synthetic'")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    finally:
        conn.close()


def _normalize_col(df: pd.DataFrame, field: str):
    """Find the first matching alias column in df."""
    aliases = COLUMN_ALIASES.get(field, [field])
    for alias in aliases:
        for col in df.columns:
            if col.lower().strip() == alias.lower():
                return col
    return None


def _resolve_district_id(name: str, conn) -> Tuple[int, int]:
    """Return (district_id, station_id) for a district name."""
    key = name.lower().strip()
    dist_id = KARNATAKA_DISTRICTS.get(key)
    if not dist_id:
        # Try partial match
        for k, v in KARNATAKA_DISTRICTS.items():
            if k in key or key in k:
                dist_id = v
                break
    if not dist_id:
        dist_id = 1  # Default Bengaluru

    stations = conn.execute(
        "SELECT station_id FROM stations WHERE district_id=? LIMIT 5", (dist_id,)
    ).fetchall()
    station_id = random.choice(stations)[0] if stations else 1
    return dist_id, station_id


def _parse_datetime(val) -> str:
    if pd.isna(val):
        return datetime.now().isoformat()
    if isinstance(val, (datetime,)):
        return val.isoformat()
    try:
        return pd.to_datetime(val).isoformat()
    except Exception:
        return datetime.now().isoformat()


def _normalize_status(val: str) -> str:
    if pd.isna(val) or not val:
        return "Under Investigation"
    key = str(val).lower().strip()
    return STATUS_MAP.get(key, "Under Investigation")


def _normalize_crime_type(val: str) -> str:
    if pd.isna(val) or not val:
        return "Theft"
    val = str(val).strip()
    lower = val.lower()
    for ct in CRIME_TYPES:
        if ct in lower:
            return ct.title()
    return val.title()


def process_upload(file_content: bytes, filename: str) -> dict:
    """
    Parse an uploaded CSV or Excel file and insert FIRs into the database.
    Returns a summary dict with counts and any errors.
    """
    _ensure_data_source_column()

    # Parse file
    try:
        if filename.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(file_content, engine="openpyxl" if filename.endswith(".xlsx") else "xlrd")
        else:
            import io
            df = pd.read_csv(io.BytesIO(file_content), encoding="utf-8", on_bad_lines="skip")
    except Exception as e:
        return {"success": False, "error": f"Could not parse file: {e}", "inserted": 0}

    if df.empty:
        return {"success": False, "error": "File is empty", "inserted": 0}

    # Normalize column names
    df.columns = [str(c).strip() for c in df.columns]

    conn = _get_db()
    try:
        max_id = conn.execute("SELECT MAX(fir_id) FROM firs").fetchone()[0] or 0
        inserted = 0
        errors = []

        for idx, row in df.iterrows():
            try:
                def get(field):
                    col = _normalize_col(df, field)
                    return row[col] if col else None

                # Resolve district
                dist_name = get("district") or "Bengaluru Urban"
                dist_id, station_id = _resolve_district_id(str(dist_name), conn)

                crime_type = _normalize_crime_type(get("crime_type") or "Theft")
                sub_type = str(get("sub_type") or "General") if get("sub_type") else "General"
                date_time = _parse_datetime(get("date_time"))
                status = _normalize_status(get("status"))
                weapon = str(get("weapon") or "Unknown")
                description = str(get("description") or f"FIR imported from {filename}")
                mo_tags = json.dumps(["imported", "real-data"])

                # Coordinates — use district center if not provided
                try:
                    lat = float(get("lat") or 0)
                    lon = float(get("lon") or 0)
                    if lat == 0 or lon == 0:
                        dist_row = conn.execute(
                            "SELECT lat, lon FROM districts WHERE district_id=?", (dist_id,)
                        ).fetchone()
                        if dist_row:
                            lat = dist_row[0] + random.uniform(-0.1, 0.1)
                            lon = dist_row[1] + random.uniform(-0.1, 0.1)
                except Exception:
                    dist_row = conn.execute("SELECT lat, lon FROM districts WHERE district_id=?", (dist_id,)).fetchone()
                    lat = (dist_row[0] if dist_row else 13.0) + random.uniform(-0.1, 0.1)
                    lon = (dist_row[1] if dist_row else 77.0) + random.uniform(-0.1, 0.1)

                max_id += 1
                conn.execute("""
                    INSERT OR IGNORE INTO firs
                    (fir_id, district_id, station_id, crime_type, sub_type, mo_tags,
                     weapon, date_time, lat, lon, status, description, data_source)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'real')
                """, (max_id, dist_id, station_id, crime_type, sub_type, mo_tags,
                      weapon, date_time, lat, lon, status, description))
                inserted += 1

            except Exception as e:
                errors.append(f"Row {idx}: {e}")

        conn.commit()

        # Invalidate TF-IDF cache so newly imported FIRs are searchable
        # immediately without requiring a server restart.
        _reset_search_index()
        # Evict serialised ML models so they are retrained on the new dataset.
        _invalidate_models()

        return {
            "success": True,
            "inserted": inserted,
            "total_rows": len(df),
            "errors": errors[:10],  # cap at 10
            "filename": filename,
        }
    finally:
        conn.close()



def get_data_stats() -> dict:
    """Return breakdown of synthetic vs real FIRs."""
    _ensure_data_source_column()
    conn = _get_db()
    try:
        total = conn.execute("SELECT COUNT(*) FROM firs").fetchone()[0]
        real = conn.execute("SELECT COUNT(*) FROM firs WHERE data_source='real'").fetchone()[0]
        synthetic = total - real
        return {
            "total_firs": total,
            "synthetic_firs": synthetic,
            "real_firs": real,
            "mode": "real" if real > 0 else "synthetic",
        }
    finally:
        conn.close()


def clear_real_data() -> dict:
    """Remove all real (imported) FIRs, keep synthetic data."""
    conn = _get_db()
    try:
        deleted = conn.execute("SELECT COUNT(*) FROM firs WHERE data_source='real'").fetchone()[0]
        conn.execute("DELETE FROM firs WHERE data_source='real'")
        conn.commit()
        return {"success": True, "deleted": deleted}
    finally:
        conn.close()
