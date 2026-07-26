"""
Analytics — Socio-Economic Correlation & District Ranking Module
Pearson correlation, transparent weighted ranking, station performance.
"""

import json
import math
from collections import defaultdict

from db import get_db


def _pearson(x, y):
    """Compute Pearson correlation coefficient."""
    n = len(x)
    if n < 2:
        return 0
    mx, my = sum(x) / n, sum(y) / n
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    den = math.sqrt(sum((xi - mx) ** 2 for xi in x) * sum((yi - my) ** 2 for yi in y))
    return round(num / den, 4) if den else 0


def get_socioeconomic_correlation():
    """
    Correlate crime rate (crimes per 1000 pop density) against:
    - population_density
    - literacy_rate
    - urban_pct
    """
    conn = get_db()
    districts = conn.execute("SELECT * FROM districts").fetchall()
    fir_counts = conn.execute(
        "SELECT district_id, COUNT(*) as cnt FROM firs GROUP BY district_id"
    ).fetchall()
    conn.close()

    count_map = {r["district_id"]: r["cnt"] for r in fir_counts}

    data = []
    for d in districts:
        cnt = count_map.get(d["district_id"], 0)
        crime_rate = (cnt / max(d["population_density"], 1)) * 1000
        data.append({
            "district_id": d["district_id"],
            "name": d["name"],
            "crime_rate": round(crime_rate, 2),
            "population_density": d["population_density"],
            "literacy_rate": d["literacy_rate"],
            "urban_pct": d["urban_pct"],
            "total_crimes": cnt,
        })

    crime_rates = [d["crime_rate"] for d in data]
    densities = [d["population_density"] for d in data]
    literacies = [d["literacy_rate"] for d in data]
    urban_pcts = [d["urban_pct"] for d in data]

    return {
        "districts": data,
        "correlations": {
            "crime_vs_population_density": _pearson(crime_rates, densities),
            "crime_vs_literacy": _pearson(crime_rates, literacies),
            "crime_vs_urban_pct": _pearson(crime_rates, urban_pcts),
        },
        "insights": _generate_insights(
            _pearson(crime_rates, densities),
            _pearson(crime_rates, literacies),
            _pearson(crime_rates, urban_pcts),
        ),
    }


def _generate_insights(r_density, r_literacy, r_urban):
    insights = []
    if r_density > 0.4:
        insights.append("Higher population density is significantly correlated with higher crime rates (r={:.2f}). Dense urban areas need prioritized policing.".format(r_density))
    elif r_density < -0.2:
        insights.append("Denser districts show lower crime rates per capita (r={:.2f}), possibly due to better policing infrastructure.".format(r_density))

    if r_literacy < -0.3:
        insights.append("Districts with lower literacy rates tend to have higher crime rates (r={:.2f}). Investment in education may be a long-term crime reduction lever.".format(r_literacy))
    elif r_literacy > 0.2:
        insights.append("Interestingly, higher literacy correlates with increased crime reporting (r={:.2f}), suggesting better access to justice systems.".format(r_literacy))

    if r_urban > 0.3:
        insights.append("More urbanized districts show higher crime rates (r={:.2f}). Urban policing strategies should be strengthened.".format(r_urban))

    if not insights:
        insights.append("No strong linear correlations detected. Crime drivers in Karnataka are likely multi-factorial.")

    return insights


def get_district_ranking():
    """
    Transparent district intelligence ranking.
    Formula is shown, not hidden.
    Weights: violent_crime 35% | total_crime 25% | pending_cases 20% | repeat_offenders 10% | investigation_speed 10%
    """
    conn = get_db()
    c = conn.cursor()

    districts = c.execute("SELECT * FROM districts").fetchall()
    violent_types = ("Murder", "Assault", "Robbery", "Abduction", "Sexual Offence")
    placeholders = ",".join("?" * len(violent_types))

    fir_summary = c.execute("""
        SELECT district_id,
               COUNT(*) as total,
               SUM(CASE WHEN crime_type IN ({}) THEN 1 ELSE 0 END) as violent
        FROM firs GROUP BY district_id
    """.format(placeholders), violent_types).fetchall()

    station_stats = c.execute("""
        SELECT district_id, AVG(pending_pct) as avg_pending, AVG(avg_investigation_days) as avg_inv_days
        FROM stations GROUP BY district_id
    """).fetchall()

    offender_counts = c.execute("""
        SELECT district_id, COUNT(*) as cnt FROM persons
        WHERE prior_fir_count >= 3 GROUP BY district_id
    """).fetchall()
    conn.close()

    fir_map = {r["district_id"]: r for r in fir_summary}
    stn_map = {r["district_id"]: r for r in station_stats}
    off_map = {r["district_id"]: r["cnt"] for r in offender_counts}

    max_vals = {
        "total": max((fir_map[d["district_id"]]["total"] if d["district_id"] in fir_map else 0
                      for d in districts), default=1),
        "violent": max((fir_map[d["district_id"]]["violent"] if d["district_id"] in fir_map else 0
                        for d in districts), default=1),
        "pending": max((stn_map[d["district_id"]]["avg_pending"] if d["district_id"] in stn_map else 0
                        for d in districts), default=1),
        "inv_days": max((stn_map[d["district_id"]]["avg_inv_days"] if d["district_id"] in stn_map else 1
                         for d in districts), default=1),
        "offenders": max((off_map.get(d["district_id"], 0) for d in districts), default=1),
    }

    results = []
    for d in districts:
        did = d["district_id"]
        fir = fir_map.get(did, {"total": 0, "violent": 0})
        stn = stn_map.get(did, {"avg_pending": 0, "avg_inv_days": 30})
        off = off_map.get(did, 0)

        # FORMULA (shown to user):
        # score = 0.35*(violent/max_violent) + 0.25*(total/max_total)
        #       + 0.20*(pending/max_pending) + 0.10*(offenders/max_offenders)
        #       + 0.10*(inv_days/max_inv_days)
        w_violent   = 0.35 * (fir["violent"] / max(max_vals["violent"], 1))
        w_total     = 0.25 * (fir["total"]   / max(max_vals["total"], 1))
        w_pending   = 0.20 * ((stn["avg_pending"] or 0) / max(max_vals["pending"], 1))
        w_offenders = 0.10 * (off / max(max_vals["offenders"], 1))
        w_inv       = 0.10 * ((stn["avg_inv_days"] or 30) / max(max_vals["inv_days"], 1))

        composite = round((w_violent + w_total + w_pending + w_offenders + w_inv) * 100, 1)

        results.append({
            "district_id": did,
            "name": d["name"],
            "composite_score": composite,
            "rank": 0,  # filled below
            "total_crimes": fir["total"],
            "violent_crimes": fir["violent"],
            "avg_pending_pct": round(stn["avg_pending"] or 0, 1),
            "avg_investigation_days": round(stn["avg_inv_days"] or 30, 1),
            "repeat_offenders": off,
            "score_breakdown": {
                "violent_crime (35%)": round(w_violent * 100, 2),
                "total_crime (25%)": round(w_total * 100, 2),
                "pending_cases (20%)": round(w_pending * 100, 2),
                "repeat_offenders (10%)": round(w_offenders * 100, 2),
                "investigation_speed (10%)": round(w_inv * 100, 2),
            },
            "formula": "0.35×(violent/max) + 0.25×(total/max) + 0.20×(pending/max) + 0.10×(offenders/max) + 0.10×(inv_days/max)",
        })

    results.sort(key=lambda x: -x["composite_score"])
    for i, r in enumerate(results):
        r["rank"] = i + 1

    return results


def get_station_performance(district_id: int = None):
    """Station-level performance metrics."""
    conn = get_db()
    query = """
        SELECT s.station_id, s.name, s.district_id, d.name as district_name,
               s.pending_pct, s.avg_investigation_days, s.fir_count,
               COUNT(f.fir_id) as actual_firs
        FROM stations s
        JOIN districts d ON s.district_id = d.district_id
        LEFT JOIN firs f ON s.station_id = f.station_id
    """
    params = []
    if district_id:
        query += " WHERE s.district_id=?"
        params.append(district_id)
    query += " GROUP BY s.station_id ORDER BY s.fir_count DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()

    return [dict(r) for r in rows]


def get_crime_calendar():
    """Monthly crime counts by type for the calendar heatmap."""
    conn = get_db()
    rows = conn.execute("SELECT crime_type, date_time FROM firs").fetchall()
    conn.close()

    from collections import defaultdict
    calendar = defaultdict(lambda: defaultdict(int))
    for r in rows:
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(r["date_time"])
            month_key = f"{dt.year}-{dt.month:02d}"
            calendar[month_key][r["crime_type"]] += 1
        except Exception:
            pass

    result = []
    for month, types in sorted(calendar.items()):
        total = sum(types.values())
        result.append({"month": month, "total": total, **types})

    return result


def get_sankey_data():
    """Crime type → District → Station → Status flow for Sankey diagram."""
    conn = get_db()
    rows = conn.execute("""
        SELECT f.crime_type, d.name as district, s.name as station, f.status
        FROM firs f
        JOIN districts d ON f.district_id = d.district_id
        JOIN stations s ON f.station_id = s.station_id
    """).fetchall()
    conn.close()

    # Build Sankey nodes and links
    node_set = {}
    def get_node_id(label, category):
        key = f"{category}::{label}"
        if key not in node_set:
            node_set[key] = {"id": len(node_set), "label": label, "category": category}
        return node_set[key]["id"]

    link_counts = defaultdict(int)
    # Limit: top 5 crime types, top 8 districts for readability
    from collections import Counter
    top_crimes = [x for x, _ in Counter(r["crime_type"] for r in rows).most_common(5)]
    top_districts = [x for x, _ in Counter(r["district"] for r in rows).most_common(8)]

    for r in rows:
        if r["crime_type"] not in top_crimes:
            continue
        if r["district"] not in top_districts:
            continue
        ct_id = get_node_id(r["crime_type"], "crime_type")
        dist_id = get_node_id(r["district"], "district")
        status_id = get_node_id(r["status"], "status")
        link_counts[(ct_id, dist_id)] += 1
        link_counts[(dist_id, status_id)] += 1

    nodes = sorted(node_set.values(), key=lambda x: x["id"])
    links = [{"source": k[0], "target": k[1], "value": v} for k, v in link_counts.items()]

    return {"nodes": nodes, "links": links}
