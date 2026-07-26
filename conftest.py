"""
pytest configuration and shared fixtures for KSP CrimeIQ test suite.
Spins up a temporary SQLite database initialized with generate_data.py schema
and seed generator, overriding db.DB_PATH so production database is untouched.
"""

from dotenv import load_dotenv
load_dotenv()

import os
import sqlite3
import pytest
from fastapi.testclient import TestClient

import db
from auth import create_access_token, _ensure_users_table, _seed_default_users
from generate_data import (
    SCHEMA, KARNATAKA_DISTRICTS, generate_stations, generate_persons,
    generate_vehicles, generate_phones, generate_firs, generate_fir_persons,
    generate_fir_vehicles, generate_edges, update_station_fir_counts,
    generate_missing_persons, generate_citizen_feedback
)
from analytics.search import reset_index
from analytics.predictive import invalidate_model_cache
from main import app


@pytest.fixture(scope="session", autouse=True)
def test_db(tmp_path_factory):
    """Create a temporary test database populated with synthetic data."""
    tmp_dir = tmp_path_factory.mktemp("db")
    test_db_path = str(tmp_dir / "test_crime_db.sqlite")

    # Override db module DB_PATH before schema/seeding
    db.DB_PATH = test_db_path

    # Generate small dataset for testing
    stations = generate_stations(KARNATAKA_DISTRICTS)
    persons = generate_persons(100)
    vehicles = generate_vehicles(50)
    phones = generate_phones(50)
    firs = generate_firs(KARNATAKA_DISTRICTS, stations, n=300)
    fir_persons = generate_fir_persons(firs, persons)
    fir_vehicles = generate_fir_vehicles(firs, vehicles)
    edges = generate_edges(fir_persons, fir_vehicles, phones)
    stations = update_station_fir_counts(stations, firs)
    missing = generate_missing_persons(KARNATAKA_DISTRICTS)
    feedback = generate_citizen_feedback(stations)

    conn = sqlite3.connect(test_db_path)
    c = conn.cursor()
    c.executescript(SCHEMA)

    c.executemany("INSERT INTO districts VALUES (:id,:name,:lat,:lon,:population_density,:literacy_rate,:urban_pct)", KARNATAKA_DISTRICTS)
    c.executemany("INSERT INTO stations VALUES (:station_id,:district_id,:name,:lat,:lon,:fir_count,:pending_pct,:avg_investigation_days)", stations)
    c.executemany("INSERT INTO persons VALUES (:person_id,:name,:age,:gender,:role,:phone,:district_id,:prior_fir_count,:districts_active,:mo_pattern,:risk_score)", persons)
    c.executemany("INSERT INTO vehicles VALUES (:vehicle_id,:reg_number,:vehicle_type,:color,:linked_fir_ids)", vehicles)
    c.executemany("INSERT INTO phones VALUES (:phone_id,:number,:linked_person_ids)", phones)
    c.executemany("INSERT INTO firs VALUES (:fir_id,:district_id,:station_id,:crime_type,:sub_type,:mo_tags,:weapon,:date_time,:lat,:lon,:status,:description,:chargesheet_date,:trial_start_date,:disposal_date,:judicial_outcome)", firs)
    c.executemany("INSERT INTO fir_persons(fir_id,person_id,role) VALUES (:fir_id,:person_id,:role)", fir_persons)
    c.executemany("INSERT INTO fir_vehicles(fir_id,vehicle_id) VALUES (:fir_id,:vehicle_id)", fir_vehicles)
    c.executemany("INSERT INTO relationship_edges VALUES (:edge_id,:from_entity,:from_id,:to_entity,:to_id,:edge_type,:fir_id)", edges)
    c.executemany("INSERT INTO missing_persons VALUES (:id,:name,:age,:gender,:reported_date,:district_id,:lat,:lon,:status)", missing)
    c.executemany("INSERT INTO citizen_feedback VALUES (:id,:station_id,:feedback,:sentiment_score)", feedback)

    conn.commit()
    conn.close()

    _ensure_users_table()
    _seed_default_users()
    reset_index()

    invalidate_model_cache()


    yield test_db_path

    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except Exception:
            pass


@pytest.fixture
def auth_headers():
    """Return Authorization header with a valid JWT token."""
    token = create_access_token({"sub": "admin", "role": "commander"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client():
    """FastAPI TestClient instance."""
    return TestClient(app)
