"""
Analytics — Criminal Network & Repeat Offender Module
NetworkX graph, repeat-offender scoring, case similarity (TF-IDF).
"""

import json
import networkx as nx
from collections import defaultdict

from db import get_db


def get_network_graph(entity_type: str, entity_id: int, depth: int = 2):
    """
    Build a network graph centred on a given entity.
    Returns nodes and edges in D3-compatible format.
    """
    conn = get_db()
    c = conn.cursor()

    G = nx.Graph()
    visited = set()
    queue = [(entity_type, entity_id)]

    def add_entity_node(etype, eid):
        node_id = f"{etype}_{eid}"
        if node_id not in visited:
            visited.add(node_id)
            if etype == "person":
                row = c.execute("SELECT name, role, prior_fir_count, risk_score FROM persons WHERE person_id=?", (eid,)).fetchone()
                if row:
                    G.add_node(node_id, label=row["name"], entity_type="person",
                               sub_type=row["role"], risk=row["risk_score"],
                               prior_firs=row["prior_fir_count"])
            elif etype == "vehicle":
                row = c.execute("SELECT reg_number, vehicle_type, color FROM vehicles WHERE vehicle_id=?", (eid,)).fetchone()
                if row:
                    G.add_node(node_id, label=row["reg_number"], entity_type="vehicle",
                               sub_type=row["vehicle_type"], color_val=row["color"])
            elif etype == "phone":
                row = c.execute("SELECT number FROM phones WHERE phone_id=?", (eid,)).fetchone()
                if row:
                    G.add_node(node_id, label=row["number"], entity_type="phone", sub_type="phone")

    for _ in range(depth):
        new_queue = []
        for (etype, eid) in queue:
            add_entity_node(etype, eid)
            node_id = f"{etype}_{eid}"

            edges = c.execute("""
                SELECT * FROM relationship_edges
                WHERE (from_entity=? AND from_id=?) OR (to_entity=? AND to_id=?)
            """, (etype, eid, etype, eid)).fetchall()

            for e in edges:
                from_node = f"{e['from_entity']}_{e['from_id']}"
                to_node = f"{e['to_entity']}_{e['to_id']}"

                add_entity_node(e["from_entity"], e["from_id"])
                add_entity_node(e["to_entity"], e["to_id"])

                if not G.has_edge(from_node, to_node):
                    G.add_edge(from_node, to_node, label=e["edge_type"], fir_id=e["fir_id"])
                    new_queue.append((e["from_entity"], e["from_id"]))
                    new_queue.append((e["to_entity"], e["to_id"]))

        queue = new_queue

    conn.close()

    nodes = []
    for n, data in G.nodes(data=True):
        nodes.append({"id": n, **data})

    links = []
    for u, v, data in G.edges(data=True):
        links.append({"source": u, "target": v, **data})

    return {"nodes": nodes, "links": links}


def get_repeat_offenders(min_firs: int = 2, limit: int = 50):
    """
    Return list of repeat offenders with scorecard data.
    """
    conn = get_db()
    c = conn.cursor()

    rows = c.execute("""
        SELECT p.person_id, p.name, p.age, p.gender, p.prior_fir_count,
               p.districts_active, p.mo_pattern, p.risk_score,
               COUNT(fp.fir_id) as fir_count
        FROM persons p
        JOIN fir_persons fp ON p.person_id = fp.person_id AND fp.role='suspect'
        WHERE p.prior_fir_count >= ?
        GROUP BY p.person_id
        ORDER BY p.risk_score DESC
        LIMIT ?
    """, (min_firs, limit)).fetchall()
    conn.close()

    result = []
    for r in rows:
        districts = json.loads(r["districts_active"]) if r["districts_active"] else []
        mo = json.loads(r["mo_pattern"]) if r["mo_pattern"] else []
        result.append({
            "person_id": r["person_id"],
            "name": r["name"],
            "age": r["age"],
            "gender": r["gender"],
            "prior_fir_count": r["prior_fir_count"],
            "fir_count": r["fir_count"],
            "districts_active_count": len(districts),
            "mo_tags": mo,
            "risk_score": r["risk_score"],
            "risk_level": "Critical" if r["risk_score"] >= 80 else
                          "High" if r["risk_score"] >= 60 else
                          "Medium" if r["risk_score"] >= 35 else "Low",
        })
    return result


def get_offender_profile(person_id: int):
    """Full profile for one offender including FIR history and network snippet."""
    conn = get_db()
    c = conn.cursor()

    person = c.execute("SELECT * FROM persons WHERE person_id=?", (person_id,)).fetchone()
    if not person:
        conn.close()
        return None

    firs = c.execute("""
        SELECT f.fir_id, f.crime_type, f.sub_type, f.date_time, f.status, f.district_id,
               d.name as district_name
        FROM fir_persons fp
        JOIN firs f ON fp.fir_id = f.fir_id
        JOIN districts d ON f.district_id = d.district_id
        WHERE fp.person_id=? AND fp.role='suspect'
        ORDER BY f.date_time DESC
    """, (person_id,)).fetchall()
    conn.close()

    districts = json.loads(person["districts_active"]) if person["districts_active"] else []
    mo = json.loads(person["mo_pattern"]) if person["mo_pattern"] else []

    return {
        "person_id": person["person_id"],
        "name": person["name"],
        "age": person["age"],
        "gender": person["gender"],
        "phone": person["phone"],
        "prior_fir_count": person["prior_fir_count"],
        "risk_score": person["risk_score"],
        "districts_active": districts,
        "mo_pattern": mo,
        "fir_history": [dict(f) for f in firs],
    }
