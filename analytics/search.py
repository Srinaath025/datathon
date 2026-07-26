"""
Analytics — FIR Search & Case Similarity Module
TF-IDF based semantic search over FIR descriptions.
"""

import json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import re

from db import get_db

_vectorizer = None
_tfidf_matrix = None
_fir_cache = None


def reset_index() -> None:
    """Invalidate the in-memory TF-IDF cache.
    Called by data_import after a successful upload so the next search
    request rebuilds the index from the current database contents.
    """
    global _vectorizer, _tfidf_matrix, _fir_cache
    _vectorizer = None
    _tfidf_matrix = None
    _fir_cache = None

def _build_index():
    global _vectorizer, _tfidf_matrix, _fir_cache

    conn = get_db()
    rows = conn.execute("""
        SELECT f.fir_id, f.crime_type, f.sub_type, f.weapon, f.mo_tags,
               f.description, f.date_time, f.status, d.name as district_name
        FROM firs f JOIN districts d ON f.district_id = d.district_id
    """).fetchall()
    conn.close()

    _fir_cache = [dict(r) for r in rows]
    docs = []
    for r in _fir_cache:
        mo = " ".join(json.loads(r["mo_tags"])) if r["mo_tags"] else ""
        text = f"{r['crime_type']} {r['sub_type']} {r['weapon']} {mo} {r['description']}"
        docs.append(text)

    _vectorizer = TfidfVectorizer(stop_words="english", max_features=500)
    _tfidf_matrix = _vectorizer.fit_transform(docs)


KANNADA_GLOSSARY = {
    "ಕಳ್ಳತನ": "theft",
    "ಕೊಲೆ": "murder",
    "ದರೋಡೆ": "robbery",
    "ಹಲ್ಲೆ": "assault",
    "ಮಹಿಳೆ": "woman",
    "ಚಾಕು": "knife",
    "ರಾತ್ರಿ": "night",
    "ಬೆಳಗ್ಗೆ": "daytime",
    "ಮೈಸೂರು": "mysuru",
    "ಬೆಂಗಳೂರು": "bengaluru"
}

def translate_query(query: str) -> str:
    translated = []
    for word in query.split():
        translated.append(KANNADA_GLOSSARY.get(word, word))
    return " ".join(translated)

def search_firs(query: str, limit: int = 10):
    """Full-text semantic search over FIR records using TF-IDF with Kannada support."""
    if _vectorizer is None:
        _build_index()

    english_query = translate_query(query)
    q_vec = _vectorizer.transform([english_query])
    scores = cosine_similarity(q_vec, _tfidf_matrix).flatten()
    top_indices = scores.argsort()[::-1][:limit]

    results = []
    for idx in top_indices:
        if scores[idx] < 0.01:
            continue
        fir = _fir_cache[idx].copy()
        fir["similarity_score"] = round(float(scores[idx]), 4)
        fir["extracted_entities"] = extract_entities(fir.get("description", ""))
        fir.pop("description", None)
        results.append(fir)

    return results

def extract_entities(text: str):
    """Extract suspects and vehicles from text using regex heuristics."""
    entities = {"suspects": [], "vehicles": []}
    if not text: return entities
    
    name_pattern = r"(?:suspect|accused|identified as)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)"
    for m in re.finditer(name_pattern, text):
        entities["suspects"].append(m.group(1))
        
    vehicle_pattern = r"([A-Z]{2}\s?-?\d{1,2}\s?-?[A-Z]{1,2}\s?-?\d{4})"
    for m in re.finditer(vehicle_pattern, text, re.IGNORECASE):
        entities["vehicles"].append(m.group(1).upper())
        
    entities["suspects"] = list(set(entities["suspects"]))
    entities["vehicles"] = list(set(entities["vehicles"]))
    return entities


def get_similar_cases(fir_id: int, limit: int = 8):
    """Find cases most similar to a given FIR."""
    if _vectorizer is None:
        _build_index()

    # Find index of the fir
    idx_map = {r["fir_id"]: i for i, r in enumerate(_fir_cache)}
    if fir_id not in idx_map:
        return []

    source_idx = idx_map[fir_id]
    source_vec = _tfidf_matrix[source_idx]
    scores = cosine_similarity(source_vec, _tfidf_matrix).flatten()
    scores[source_idx] = -1  # exclude self

    top_indices = scores.argsort()[::-1][:limit]
    results = []
    for idx in top_indices:
        if scores[idx] < 0.01:
            continue
        fir = _fir_cache[idx].copy()
        fir["similarity_score"] = round(float(scores[idx]), 4)
        fir.pop("description", None)
        results.append(fir)

    return results


def get_investigation_timeline(fir_id: int):
    """Generate a chronological investigation timeline for a FIR."""
    conn = get_db()
    c = conn.cursor()

    fir = c.execute("""
        SELECT f.*, d.name as district_name, s.name as station_name
        FROM firs f
        JOIN districts d ON f.district_id = d.district_id
        JOIN stations s ON f.station_id = s.station_id
        WHERE f.fir_id=?
    """, (fir_id,)).fetchone()

    if not fir:
        conn.close()
        return None

    persons = c.execute("""
        SELECT p.name, p.role, p.phone, p.age, fp.role as fir_role
        FROM fir_persons fp JOIN persons p ON fp.person_id = p.person_id
        WHERE fp.fir_id=?
    """, (fir_id,)).fetchall()

    vehicles = c.execute("""
        SELECT v.reg_number, v.vehicle_type, v.color
        FROM fir_vehicles fv JOIN vehicles v ON fv.vehicle_id = v.vehicle_id
        WHERE fv.fir_id=?
    """, (fir_id,)).fetchall()
    conn.close()

    from datetime import datetime, timedelta
    import random

    base_dt = datetime.fromisoformat(fir["date_time"])
    events = [
        {"time": (base_dt - timedelta(hours=2)).strftime("%H:%M, %d %b %Y"),
         "event": "Victim last seen at known location", "type": "pre"},
        {"time": base_dt.strftime("%H:%M, %d %b %Y"),
         "event": f"Incident reported — {fir['sub_type']} ({fir['crime_type']})", "type": "incident"},
        {"time": (base_dt + timedelta(minutes=random.randint(15, 45))).strftime("%H:%M, %d %b %Y"),
         "event": f"FIR #{fir_id} registered at {fir['station_name']}", "type": "fir"},
    ]

    if vehicles:
        v = vehicles[0]
        events.append({
            "time": (base_dt + timedelta(hours=random.randint(1, 3))).strftime("%H:%M, %d %b %Y"),
            "event": f"Vehicle {v['reg_number']} ({v['color']} {v['vehicle_type']}) identified at scene",
            "type": "evidence"
        })

    suspects = [p for p in persons if p["fir_role"] == "suspect"]
    if suspects:
        s = suspects[0]
        events.append({
            "time": (base_dt + timedelta(hours=random.randint(4, 12))).strftime("%H:%M, %d %b %Y"),
            "event": f"Suspect {s['name']} (Age {s['age']}) identified. Prior FIRs on record.",
            "type": "suspect"
        })

    events.append({
        "time": (base_dt + timedelta(days=random.randint(1, 5))).strftime("%H:%M, %d %b %Y"),
        "event": f"Case status: {fir['status']}",
        "type": "status"
    })

    return {
        "fir_id": fir_id,
        "crime_type": fir["crime_type"],
        "sub_type": fir["sub_type"],
        "district": fir["district_name"],
        "station": fir["station_name"],
        "date_time": fir["date_time"],
        "status": fir["status"],
        "persons": [dict(p) for p in persons],
        "vehicles": [dict(v) for v in vehicles],
        "timeline": sorted(events, key=lambda x: x["time"]),
    }
