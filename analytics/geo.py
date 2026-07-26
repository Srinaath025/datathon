"""
Analytics — Geospatial Module
Hotspot detection, district drill-down, time-based analysis.
"""

import json
from datetime import datetime, timedelta
from collections import defaultdict

from db import get_db


def get_heatmap_data(district_id=None, crime_type=None, time_filter=None):
    """Return lat/lon/intensity points for the heatmap."""
    conn = get_db()
    c = conn.cursor()

    query = "SELECT lat, lon, crime_type, date_time FROM firs WHERE 1=1"
    params = []
    if district_id:
        query += " AND district_id=?"
        params.append(district_id)
    if crime_type:
        query += " AND crime_type=?"
        params.append(crime_type)

    rows = c.execute(query, params).fetchall()
    conn.close()

    points = []
    for r in rows:
        try:
            dt = datetime.fromisoformat(r["date_time"])
        except Exception:
            continue

        # Apply time filter
        if time_filter == "night" and not (dt.hour < 6 or dt.hour >= 20):
            continue
        if time_filter == "day" and not (6 <= dt.hour < 20):
            continue
        if time_filter == "weekend" and dt.weekday() < 5:
            continue
        if time_filter == "weekday" and dt.weekday() >= 5:
            continue

        points.append({"lat": r["lat"], "lon": r["lon"], "intensity": 1})

    return points


def get_district_summary():
    """Return crime counts per district for the choropleth."""
    conn = get_db()
    c = conn.cursor()

    rows = c.execute("""
        SELECT d.district_id, d.name, d.lat, d.lon,
               COUNT(f.fir_id) as total_crimes,
               SUM(CASE WHEN f.crime_type='Murder' THEN 1 ELSE 0 END) as violent_crimes
        FROM districts d
        LEFT JOIN firs f ON d.district_id = f.district_id
        GROUP BY d.district_id
    """).fetchall()
    conn.close()

    result = []
    for r in rows:
        result.append({
            "district_id": r["district_id"],
            "name": r["name"],
            "lat": r["lat"],
            "lon": r["lon"],
            "total_crimes": r["total_crimes"] or 0,
            "violent_crimes": r["violent_crimes"] or 0,
        })
    return result


def get_station_breakdown(district_id):
    """Station-level breakdown for a given district."""
    conn = get_db()
    c = conn.cursor()

    rows = c.execute("""
        SELECT s.station_id, s.name, s.lat, s.lon, s.pending_pct, s.avg_investigation_days,
               COUNT(f.fir_id) as fir_count,
               s.fir_count as total_registered
        FROM stations s
        LEFT JOIN firs f ON s.station_id = f.station_id
        WHERE s.district_id=?
        GROUP BY s.station_id
    """, (district_id,)).fetchall()
    conn.close()

    return [dict(r) for r in rows]


def get_crime_by_hour():
    """Crime distribution by hour of day across all districts."""
    conn = get_db()
    rows = conn.execute("SELECT date_time FROM firs").fetchall()
    conn.close()

    hour_counts = defaultdict(int)
    for r in rows:
        try:
            dt = datetime.fromisoformat(r[0])
            hour_counts[dt.hour] += 1
        except Exception:
            pass

    return [{"hour": h, "count": hour_counts[h]} for h in range(24)]


def get_crime_by_weekday():
    """Crime distribution by day of week."""
    conn = get_db()
    rows = conn.execute("SELECT date_time FROM firs").fetchall()
    conn.close()

    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    day_counts = defaultdict(int)
    for r in rows:
        try:
            dt = datetime.fromisoformat(r[0])
            day_counts[dt.weekday()] += 1
        except Exception:
            pass

    return [{"day": days[i], "count": day_counts[i]} for i in range(7)]


def get_spike_alerts(window_days=30, threshold_multiplier=1.5):
    """Flag districts whose recent crime rate exceeds rolling average by threshold."""
    conn = get_db()
    c = conn.cursor()

    # Get all FIRs with date and district
    rows = c.execute("SELECT district_id, date_time FROM firs").fetchall()
    conn.close()

    district_counts_recent = defaultdict(int)
    district_counts_all = defaultdict(int)

    cutoff = datetime(2025, 1, 1)  # last period vs earlier
    for r in rows:
        try:
            dt = datetime.fromisoformat(r[1])
            district_counts_all[r[0]] += 1
            if dt >= cutoff:
                district_counts_recent[r[0]] += 1
        except Exception:
            pass

    alerts = []
    for did, all_count in district_counts_all.items():
        recent = district_counts_recent.get(did, 0)
        avg = all_count / 3.0  # 3-year average
        if recent > avg * threshold_multiplier:
            alerts.append({
                "district_id": did,
                "recent_count": recent,
                "baseline_avg": round(avg, 1),
                "spike_factor": round(recent / avg, 2),
            })

    return sorted(alerts, key=lambda x: -x["spike_factor"])


def get_crime_type_distribution(district_id=None):
    """Crime type breakdown for charts."""
    conn = get_db()
    query = "SELECT crime_type, COUNT(*) as count FROM firs"
    params = []
    if district_id:
        query += " WHERE district_id=?"
        params.append(district_id)
    query += " GROUP BY crime_type ORDER BY count DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [{"crime_type": r[0], "count": r[1]} for r in rows]
