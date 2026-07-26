"""
KSP CrimeIQ — Shared Database Utility
=======================================
Single source of truth for SQLite connections.

All analytics modules and main.py must import get_db from here.
This replaces the ~11 duplicate get_db() functions that were
spread across the codebase.

Key guarantees this module provides on every connection:
  • conn.row_factory = sqlite3.Row   (dict-like row access)
  • PRAGMA foreign_keys = ON         (FK constraints enforced)
  • PRAGMA journal_mode = WAL        (better concurrent reads)
"""

import os
import sqlite3

_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_HERE, "data", "crime_db.sqlite")


def get_db() -> sqlite3.Connection:
    """
    Open and return a configured SQLite connection.

    Caller is responsible for calling conn.close() (or using a try/finally).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Enforce FK constraints declared in the schema (SQLite ignores them by default).
    conn.execute("PRAGMA foreign_keys = ON")
    # WAL mode: readers don't block writers, writers don't block readers.
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db() -> None:
    """
    Create database indexes for frequently filtered and joined columns.
    Safe to call multiple times (uses CREATE INDEX IF NOT EXISTS).
    """
    if not os.path.exists(DB_PATH):
        return

    conn = get_db()
    try:
        conn.executescript("""
            CREATE INDEX IF NOT EXISTS idx_firs_district_id ON firs(district_id);
            CREATE INDEX IF NOT EXISTS idx_firs_crime_type ON firs(crime_type);
            CREATE INDEX IF NOT EXISTS idx_firs_date_time ON firs(date_time);
            CREATE INDEX IF NOT EXISTS idx_firs_station_id ON firs(station_id);
            CREATE INDEX IF NOT EXISTS idx_firs_status ON firs(status);

            CREATE INDEX IF NOT EXISTS idx_fir_persons_fir_id ON fir_persons(fir_id);
            CREATE INDEX IF NOT EXISTS idx_fir_persons_person_id ON fir_persons(person_id);
            CREATE INDEX IF NOT EXISTS idx_fir_persons_role ON fir_persons(role);

            CREATE INDEX IF NOT EXISTS idx_fir_vehicles_fir_id ON fir_vehicles(fir_id);
            CREATE INDEX IF NOT EXISTS idx_fir_vehicles_vehicle_id ON fir_vehicles(vehicle_id);

            CREATE INDEX IF NOT EXISTS idx_rel_from ON relationship_edges(from_entity, from_id);
            CREATE INDEX IF NOT EXISTS idx_rel_to ON relationship_edges(to_entity, to_id);
            CREATE INDEX IF NOT EXISTS idx_rel_fir_id ON relationship_edges(fir_id);

            CREATE INDEX IF NOT EXISTS idx_stations_district_id ON stations(district_id);
            CREATE INDEX IF NOT EXISTS idx_persons_district_id ON persons(district_id);
            CREATE INDEX IF NOT EXISTS idx_missing_persons_district_id ON missing_persons(district_id);

            CREATE TABLE IF NOT EXISTS officer_overrides (
                override_id INTEGER PRIMARY KEY AUTOINCREMENT,
                district_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                disagree BOOLEAN NOT NULL DEFAULT 1,
                revised_score REAL,
                reason TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(district_id) REFERENCES districts(district_id)
            );
            CREATE INDEX IF NOT EXISTS idx_officer_overrides_district ON officer_overrides(district_id);
        """)
        conn.commit()
    finally:
        conn.close()

