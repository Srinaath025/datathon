"""
KSP CrimeIQ — Spatial Human Trafficking Corridor & Hotspot Detection
Uses DBSCAN density-based spatial clustering on missing person GPS coordinates.
"""

import math
import numpy as np
from sklearn.cluster import DBSCAN
from db import get_db

EARTH_RADIUS_KM = 6371.0

def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes exact haversine distance in kilometers between two GPS coordinates."""
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    return EARTH_RADIUS_KM * 2 * math.asin(math.sqrt(a))

def get_trafficking_clusters(eps_km: float = 40.0, min_samples: int = 3):
    """
    Discovers human trafficking hotspots & corridor vectors automatically using DBSCAN
    spatial density clustering on active missing person cases.
    """
    conn = get_db()
    missing_persons = conn.execute("""
        SELECT mp.id, mp.name, mp.age, mp.gender, mp.lat, mp.lon, d.name as district_name
        FROM missing_persons mp
        LEFT JOIN districts d ON mp.district_id = d.district_id
        WHERE mp.status = 'Missing'
    """).fetchall()

    conn.close()

    if not missing_persons:
        return []

    mp_docs = [dict(r) for r in missing_persons]
    coords_deg = np.array([[m["lat"], m["lon"]] for m in mp_docs])
    coords_rad = np.radians(coords_deg)

    # Convert eps_km to radians for DBSCAN with metric='haversine'
    kms_per_radian = EARTH_RADIUS_KM
    epsilon = eps_km / kms_per_radian

    db = DBSCAN(eps=epsilon, min_samples=min_samples, metric='haversine')
    labels = db.fit_predict(coords_rad)

    clusters_dict = {}
    for idx, label in enumerate(labels):
        if label == -1:
            continue  # Noise point, not part of a cluster

        if label not in clusters_dict:
            clusters_dict[label] = []
        clusters_dict[label].append(mp_docs[idx])

    results = []
    for cluster_id, persons in clusters_dict.items():
        # Compute cluster centroid
        c_lat = float(np.mean([p["lat"] for p in persons]))
        c_lon = float(np.mean([p["lon"] for p in persons]))
        count = len(persons)

        # Primary district names for dynamic corridor lead labeling
        districts_in_cluster = list({p.get("district_name", "Karnataka") for p in persons if p.get("district_name")})
        corridor_label = f"Density Lead #{cluster_id + 1}: {', '.join(districts_in_cluster[:2])} Axis"

        matched_persons = []
        for p in persons:
            dist = _haversine_distance(c_lat, c_lon, p["lat"], p["lon"])
            matched_persons.append({
                "id": p["id"],
                "name": p["name"],
                "age": p["age"],
                "gender": p["gender"],
                "distance_km": round(dist, 1)
            })

        density_label = "High Density Lead" if count >= 8 else ("Moderate Density Lead" if count >= 5 else "Low Density Lead")
        methodology_note = (
            "INVESTIGATIVE METHODOLOGY NOTE: Spatial density clusters are computed via DBSCAN "
            "on missing-person report coordinates. They represent geographic concentrations for "
            "investigative prioritization and human lead follow-up, NOT confirmed human trafficking activity."
        )

        results.append({
            "cluster_id": int(cluster_id),
            "corridor_name": corridor_label,
            "centroid_lat": round(c_lat, 4),
            "centroid_lon": round(c_lon, 4),
            "missing_count": count,
            "density_level": density_label,
            "methodology_note": methodology_note,
            "persons": matched_persons
        })


    return sorted(results, key=lambda x: -x["missing_count"])

