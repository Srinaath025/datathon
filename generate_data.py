"""
Synthetic Karnataka Crime Dataset Generator
Produces 1000+ FIR records across all 31 Karnataka districts.
Run: python generate_data.py
Output: data/crime_db.sqlite
"""

import sqlite3
import random
import json
import math
import os
from datetime import datetime, timedelta

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ksp_crimeiq.generator")

random.seed(42)
os.makedirs("data", exist_ok=True)

# ─────────────────────────────────────────────────────────────
# REFERENCE DATA
# ─────────────────────────────────────────────────────────────

KARNATAKA_DISTRICTS = [
    {"id": 1,  "name": "Bengaluru Urban",   "lat": 12.9716, "lon": 77.5946, "population_density": 4378, "literacy_rate": 89.0, "urban_pct": 91},
    {"id": 2,  "name": "Bengaluru Rural",   "lat": 13.2000, "lon": 77.5700, "population_density": 315,  "literacy_rate": 78.0, "urban_pct": 28},
    {"id": 3,  "name": "Mysuru",            "lat": 12.2958, "lon": 76.6394, "population_density": 406,  "literacy_rate": 72.5, "urban_pct": 38},
    {"id": 4,  "name": "Mangaluru",         "lat": 12.9141, "lon": 74.8560, "population_density": 430,  "literacy_rate": 88.6, "urban_pct": 42},
    {"id": 5,  "name": "Hubballi-Dharwad",  "lat": 15.3647, "lon": 75.1240, "population_density": 400,  "literacy_rate": 76.2, "urban_pct": 55},
    {"id": 6,  "name": "Belagavi",          "lat": 15.8497, "lon": 74.4977, "population_density": 280,  "literacy_rate": 69.4, "urban_pct": 30},
    {"id": 7,  "name": "Kalaburagi",        "lat": 17.3297, "lon": 76.8343, "population_density": 228,  "literacy_rate": 60.5, "urban_pct": 35},
    {"id": 8,  "name": "Vijayapura",        "lat": 16.8302, "lon": 75.7100, "population_density": 195,  "literacy_rate": 63.2, "urban_pct": 32},
    {"id": 9,  "name": "Ballari",           "lat": 15.1394, "lon": 76.9214, "population_density": 224,  "literacy_rate": 67.3, "urban_pct": 38},
    {"id": 10, "name": "Tumakuru",          "lat": 13.3379, "lon": 77.1173, "population_density": 259,  "literacy_rate": 74.1, "urban_pct": 29},
    {"id": 11, "name": "Shivamogga",        "lat": 13.9299, "lon": 75.5681, "population_density": 190,  "literacy_rate": 79.3, "urban_pct": 31},
    {"id": 12, "name": "Davangere",         "lat": 14.4644, "lon": 75.9218, "population_density": 305,  "literacy_rate": 71.8, "urban_pct": 40},
    {"id": 13, "name": "Hassan",            "lat": 13.0033, "lon": 76.1004, "population_density": 188,  "literacy_rate": 75.6, "urban_pct": 24},
    {"id": 14, "name": "Chikkamagaluru",    "lat": 13.3160, "lon": 75.7760, "population_density": 116,  "literacy_rate": 77.4, "urban_pct": 21},
    {"id": 15, "name": "Kodagu",            "lat": 12.3375, "lon": 75.8069, "population_density": 135,  "literacy_rate": 82.6, "urban_pct": 20},
    {"id": 16, "name": "Udupi",             "lat": 13.3409, "lon": 74.7421, "population_density": 384,  "literacy_rate": 86.2, "urban_pct": 27},
    {"id": 17, "name": "Uttara Kannada",    "lat": 14.7861, "lon": 74.6906, "population_density": 68,   "literacy_rate": 81.4, "urban_pct": 19},
    {"id": 18, "name": "Raichur",           "lat": 16.2120, "lon": 77.3566, "population_density": 183,  "literacy_rate": 55.5, "urban_pct": 28},
    {"id": 19, "name": "Koppal",            "lat": 15.3500, "lon": 76.1547, "population_density": 165,  "literacy_rate": 58.8, "urban_pct": 22},
    {"id": 20, "name": "Gadag",             "lat": 15.4300, "lon": 75.6200, "population_density": 198,  "literacy_rate": 71.3, "urban_pct": 36},
    {"id": 21, "name": "Dharwad",           "lat": 15.4589, "lon": 75.0078, "population_density": 266,  "literacy_rate": 77.9, "urban_pct": 48},
    {"id": 22, "name": "Bagalkot",          "lat": 16.1800, "lon": 75.6966, "population_density": 195,  "literacy_rate": 62.9, "urban_pct": 27},
    {"id": 23, "name": "Chitradurga",       "lat": 14.2251, "lon": 76.3980, "population_density": 135,  "literacy_rate": 67.0, "urban_pct": 25},
    {"id": 24, "name": "Chikkaballapura",   "lat": 13.4339, "lon": 77.7270, "population_density": 262,  "literacy_rate": 74.2, "urban_pct": 22},
    {"id": 25, "name": "Kolar",             "lat": 13.1350, "lon": 78.1290, "population_density": 326,  "literacy_rate": 73.6, "urban_pct": 30},
    {"id": 26, "name": "Ramanagara",        "lat": 12.7157, "lon": 77.2770, "population_density": 280,  "literacy_rate": 72.0, "urban_pct": 26},
    {"id": 27, "name": "Mandya",            "lat": 12.5220, "lon": 76.8950, "population_density": 344,  "literacy_rate": 70.5, "urban_pct": 23},
    {"id": 28, "name": "Chamarajanagara",   "lat": 11.9261, "lon": 76.9439, "population_density": 136,  "literacy_rate": 63.0, "urban_pct": 18},
    {"id": 29, "name": "Yadgir",            "lat": 16.7660, "lon": 77.1380, "population_density": 172,  "literacy_rate": 52.0, "urban_pct": 20},
    {"id": 30, "name": "Bidar",             "lat": 17.9104, "lon": 77.5199, "population_density": 243,  "literacy_rate": 70.5, "urban_pct": 32},
    {"id": 31, "name": "Vijayanagara",      "lat": 15.1700, "lon": 76.5200, "population_density": 156,  "literacy_rate": 66.2, "urban_pct": 27},
]

CRIME_TYPES = {
    "Theft":           ["House Break-In", "Vehicle Theft", "Pickpocketing", "Shoplifting", "Chain Snatching"],
    "Assault":         ["Simple Hurt", "Grievous Hurt", "Domestic Violence", "Road Rage"],
    "Robbery":         ["Armed Robbery", "Street Robbery", "Bank Robbery", "Mobile Snatching"],
    "Cybercrime":      ["Online Fraud", "Identity Theft", "Phishing", "Cyberstalking"],
    "Murder":          ["Premeditated", "Culpable Homicide", "Attempt to Murder"],
    "Sexual Offence":  ["Molestation", "Eve Teasing", "POCSO"],
    "Drugs":           ["Possession", "Trafficking", "Ganja", "Heroin"],
    "Property Crime":  ["Arson", "Trespass", "Mischief", "Forgery"],
    "Economic Crime":  ["Cheating", "Embezzlement", "Land Fraud", "FEMA Violation"],
    "Abduction":       ["Kidnapping", "Trafficking", "Missing Person"],
}

WEAPONS = ["None", "Knife", "Firearm", "Blunt Object", "Acid", "Vehicle", "Unknown", "Machete", "Stick", "Iron Rod"]

MO_TAGS = [
    "late-night", "daytime", "weekend", "festival-season", "repeat-location",
    "known-to-victim", "stranger", "gang-activity", "solo-offender",
    "weapon-used", "no-weapon", "vehicle-involved", "disguise-used",
    "planned", "opportunistic", "recidivist", "first-time"
]

FIRST_NAMES = ["Ravi", "Suresh", "Mahesh", "Priya", "Lakshmi", "Rajesh", "Deepa", "Kiran",
               "Anand", "Sunita", "Venkat", "Meera", "Arun", "Kavya", "Mohan", "Shanti",
               "Ganesh", "Radha", "Krishna", "Nanda", "Prasad", "Usha", "Basavraj", "Geetha",
               "Shivanand", "Manjula", "Prabhu", "Savita", "Nagaraj", "Rekha", "Ashok", "Saroja"]

LAST_NAMES = ["Kumar", "Reddy", "Rao", "Naik", "Gowda", "Patil", "Hegde", "Shetty",
              "Nair", "Sharma", "Singh", "Joshi", "Kulkarni", "Desai", "Iyer",
              "Swamy", "Raju", "Pillai", "Verma", "Mishra", "Bhat", "Kamath"]

STATION_SUFFIXES = ["North", "South", "East", "West", "Central", "Rural", "Town", "City", "Sub-Urban", "Highway"]

VEHICLE_TYPES = ["KA01", "KA02", "KA03", "KA04", "KA05", "KA10", "KA14", "KA21", "KA25", "KA41", "KA50", "KA51"]

FIR_STATUS = ["Under Investigation", "Charge-Sheeted", "Closed-True", "Closed-False", "Pending Trial"]

# ─────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────

def rand_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

def rand_phone():
    prefix = random.choice(["9886", "9845", "9632", "8971", "7204", "6364", "9449", "8867"])
    return f"+91-{prefix}-{random.randint(100000, 999999)}"

def rand_vehicle():
    prefix = random.choice(VEHICLE_TYPES)
    letters = "".join(random.choices("ABCDEFGHJKLMNPRSTUVWXYZ", k=2))
    numbers = random.randint(1000, 9999)
    return f"{prefix}-{letters}-{numbers}"

def rand_point_near(lat, lon, radius_km=0.25):
    """Random lat/lon within radius_km of the given point."""
    dx = random.uniform(-radius_km, radius_km) / 111.0
    dy = random.uniform(-radius_km, radius_km) / (111.0 * math.cos(math.radians(lat)))
    return round(lat + dx, 6), round(lon + dy, 6)

def rand_datetime(start_year=2022, end_year=2025):
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))

# ─────────────────────────────────────────────────────────────
# SCHEMA
# ─────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS districts (
    district_id INTEGER PRIMARY KEY,
    name TEXT,
    lat REAL, lon REAL,
    population_density INTEGER,
    literacy_rate REAL,
    urban_pct INTEGER
);

CREATE TABLE IF NOT EXISTS stations (
    station_id INTEGER PRIMARY KEY,
    district_id INTEGER,
    name TEXT,
    lat REAL, lon REAL,
    fir_count INTEGER DEFAULT 0,
    pending_pct REAL DEFAULT 0,
    avg_investigation_days INTEGER DEFAULT 0,
    FOREIGN KEY(district_id) REFERENCES districts(district_id)
);

CREATE TABLE IF NOT EXISTS persons (
    person_id INTEGER PRIMARY KEY,
    name TEXT,
    age INTEGER,
    gender TEXT,
    role TEXT,
    phone TEXT,
    district_id INTEGER,
    prior_fir_count INTEGER DEFAULT 0,
    districts_active TEXT,
    mo_pattern TEXT,
    risk_score REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS vehicles (
    vehicle_id INTEGER PRIMARY KEY,
    reg_number TEXT,
    vehicle_type TEXT,
    color TEXT,
    linked_fir_ids TEXT
);

CREATE TABLE IF NOT EXISTS phones (
    phone_id INTEGER PRIMARY KEY,
    number TEXT,
    linked_person_ids TEXT
);

CREATE TABLE IF NOT EXISTS firs (
    fir_id INTEGER PRIMARY KEY,
    district_id INTEGER,
    station_id INTEGER,
    crime_type TEXT,
    sub_type TEXT,
    mo_tags TEXT,
    weapon TEXT,
    date_time TEXT,
    lat REAL, lon REAL,
    status TEXT,
    description TEXT,
    chargesheet_date TEXT,
    trial_start_date TEXT,
    disposal_date TEXT,
    judicial_outcome TEXT,
    FOREIGN KEY(district_id) REFERENCES districts(district_id),
    FOREIGN KEY(station_id) REFERENCES stations(station_id)
);

CREATE TABLE IF NOT EXISTS missing_persons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT, age INTEGER, gender TEXT,
    reported_date TEXT, district_id INTEGER, lat REAL, lon REAL,
    status TEXT,
    FOREIGN KEY(district_id) REFERENCES districts(district_id)
);

CREATE TABLE IF NOT EXISTS human_overrides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fir_id INTEGER, action TEXT, reason TEXT, timestamp TEXT
);

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


CREATE TABLE IF NOT EXISTS citizen_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id INTEGER, feedback TEXT, sentiment_score REAL,
    FOREIGN KEY(station_id) REFERENCES stations(station_id)
);

CREATE TABLE IF NOT EXISTS fir_persons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fir_id INTEGER,
    person_id INTEGER,
    role TEXT,
    FOREIGN KEY(fir_id) REFERENCES firs(fir_id),
    FOREIGN KEY(person_id) REFERENCES persons(person_id)
);

CREATE TABLE IF NOT EXISTS fir_vehicles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fir_id INTEGER,
    vehicle_id INTEGER,
    FOREIGN KEY(fir_id) REFERENCES firs(fir_id),
    FOREIGN KEY(vehicle_id) REFERENCES vehicles(vehicle_id)
);

CREATE TABLE IF NOT EXISTS relationship_edges (
    edge_id INTEGER PRIMARY KEY,
    from_entity TEXT,
    from_id INTEGER,
    to_entity TEXT,
    to_id INTEGER,
    edge_type TEXT,
    fir_id INTEGER
);

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
"""

# ─────────────────────────────────────────────────────────────
# GENERATORS
# ─────────────────────────────────────────────────────────────

def generate_stations(districts):
    stations = []
    sid = 1
    for d in districts:
        n_stations = random.randint(3, 8)
        for i in range(n_stations):
            suffix = random.choice(STATION_SUFFIXES)
            lat, lon = rand_point_near(d["lat"], d["lon"], radius_km=15)
            stations.append({
                "station_id": sid,
                "district_id": d["id"],
                "name": f"{d['name']} {suffix} PS",
                "lat": lat, "lon": lon,
                "fir_count": 0,
                "pending_pct": round(random.uniform(15, 60), 1),
                "avg_investigation_days": random.randint(18, 90),
            })
            sid += 1
    return stations

def generate_persons(n=400):
    persons = []
    roles_dist = ["suspect"] * 5 + ["victim"] * 4 + ["witness"] * 3
    for i in range(1, n + 1):
        prior = random.choices([0, 1, 2, 3, 4, 5, 8, 12], weights=[40, 20, 15, 10, 7, 4, 3, 1])[0]
        districts_active = random.sample(range(1, 32), k=min(prior + 1, 5)) if prior > 0 else [random.randint(1, 31)]
        mo = random.sample(MO_TAGS, k=random.randint(1, 4))
        risk = min(100, prior * 12 + random.uniform(0, 20))
        persons.append({
            "person_id": i,
            "name": rand_name(),
            "age": random.randint(16, 65),
            "gender": random.choice(["Male", "Male", "Male", "Female"]),
            "role": random.choice(roles_dist),
            "phone": rand_phone(),
            "district_id": random.choice(districts_active),
            "prior_fir_count": prior,
            "districts_active": json.dumps(districts_active),
            "mo_pattern": json.dumps(mo),
            "risk_score": round(risk, 1),
        })
    return persons

def generate_vehicles(n=200):
    colors = ["White", "Black", "Silver", "Red", "Blue", "Grey", "Brown", "Green"]
    types = ["Motorcycle", "Car", "Auto-Rickshaw", "Truck", "Van", "SUV"]
    vehicles = []
    for i in range(1, n + 1):
        vehicles.append({
            "vehicle_id": i,
            "reg_number": rand_vehicle(),
            "vehicle_type": random.choice(types),
            "color": random.choice(colors),
            "linked_fir_ids": json.dumps([]),
        })
    return vehicles

def generate_phones(n=300):
    phones = []
    for i in range(1, n + 1):
        phones.append({
            "phone_id": i,
            "number": rand_phone(),
            "linked_person_ids": json.dumps([]),
        })
    return phones

def generate_firs(districts, stations, n=1200):
    firs = []
    crime_types_list = list(CRIME_TYPES.keys())

    # Weight urban districts to have more crimes
    district_weights = [d["population_density"] for d in districts]
    total_w = sum(district_weights)
    district_weights = [w / total_w for w in district_weights]

    for i in range(1, n + 1):
        d = random.choices(districts, weights=district_weights)[0]
        st_pool = [s for s in stations if s["district_id"] == d["id"]]
        st = random.choice(st_pool) if st_pool else stations[0]

        ct = random.choice(crime_types_list)
        sub = random.choice(CRIME_TYPES[ct])
        weapon = random.choice(WEAPONS)
        mo = random.sample(MO_TAGS, k=random.randint(2, 5))
        dt = rand_datetime()
        lat, lon = rand_point_near(d["lat"], d["lon"], radius_km=20)

        hour = dt.hour
        if hour < 6 or hour >= 22:
            if "late-night" not in mo:
                mo.append("late-night")
        elif 6 <= hour < 18:
            if "daytime" not in mo:
                mo.append("daytime")

        if dt.weekday() >= 5 and "weekend" not in mo:
            mo.append("weekend")

        month = dt.month
        if month in [10, 11, 12, 1] and "festival-season" not in mo:
            mo.append("festival-season")

        desc_templates = [
            f"Complainant reported {sub.lower()} incident. Accused used {weapon.lower()} during the act.",
            f"FIR registered for {ct.lower()} ({sub}). Incident occurred near {st['name']} jurisdiction.",
            f"Victim reported {sub} at the stated location. Preliminary investigation underway.",
            f"Station received complaint regarding {ct.lower()}. Sub-type: {sub}. Weapon: {weapon}.",
            f"Case of {sub} filed. Accused fled the scene. Witnesses present at location.",
        ]

        c_date, t_date, d_date, j_outcome = None, None, None, "Pending"
        if random.random() < 0.7:
            c_date = (dt + timedelta(days=random.randint(15, 60))).isoformat()
            if random.random() < 0.6:
                t_date = (datetime.fromisoformat(c_date) + timedelta(days=random.randint(30, 180))).isoformat()
                if random.random() < 0.5:
                    d_date = (datetime.fromisoformat(t_date) + timedelta(days=random.randint(60, 300))).isoformat()
                    j_outcome = random.choice(["Convicted", "Acquitted", "Compromised"])

        firs.append({
            "fir_id": i,
            "district_id": d["id"],
            "station_id": st["station_id"],
            "crime_type": ct,
            "sub_type": sub,
            "mo_tags": json.dumps(mo),
            "weapon": weapon,
            "date_time": dt.isoformat(),
            "lat": lat,
            "lon": lon,
            "status": random.choice(FIR_STATUS),
            "description": random.choice(desc_templates),
            "chargesheet_date": c_date,
            "trial_start_date": t_date,
            "disposal_date": d_date,
            "judicial_outcome": j_outcome,
        })
    return firs

def generate_fir_persons(firs, persons):
    links = []
    suspect_pool = [p for p in persons if p["role"] == "suspect"]
    victim_pool = [p for p in persons if p["role"] == "victim"]
    witness_pool = [p for p in persons if p["role"] == "witness"]

    for fir in firs:
        # 1-3 suspects
        for p in random.sample(suspect_pool, k=min(random.randint(1, 3), len(suspect_pool))):
            links.append({"fir_id": fir["fir_id"], "person_id": p["person_id"], "role": "suspect"})
        # 1-2 victims
        for p in random.sample(victim_pool, k=min(random.randint(1, 2), len(victim_pool))):
            links.append({"fir_id": fir["fir_id"], "person_id": p["person_id"], "role": "victim"})
        # 0-2 witnesses
        if random.random() > 0.4:
            for p in random.sample(witness_pool, k=min(random.randint(1, 2), len(witness_pool))):
                links.append({"fir_id": fir["fir_id"], "person_id": p["person_id"], "role": "witness"})
    return links

def generate_fir_vehicles(firs, vehicles):
    links = []
    for fir in firs:
        if random.random() > 0.6:  # 40% of FIRs involve a vehicle
            v = random.choice(vehicles)
            links.append({"fir_id": fir["fir_id"], "vehicle_id": v["vehicle_id"]})
    return links

def generate_edges(fir_persons, fir_vehicles, phones):
    edges = []
    eid = 1

    # Group by fir
    fir_to_persons = {}
    for fp in fir_persons:
        fir_to_persons.setdefault(fp["fir_id"], []).append(fp)

    fir_to_vehicles = {}
    for fv in fir_vehicles:
        fir_to_vehicles.setdefault(fv["fir_id"], []).append(fv)

    for fir_id, fps in fir_to_persons.items():
        persons_in_fir = fps
        vehicles_in_fir = fir_to_vehicles.get(fir_id, [])

        # Person-Person edges (suspects linked to victims)
        suspects = [p for p in persons_in_fir if p["role"] == "suspect"]
        victims = [p for p in persons_in_fir if p["role"] == "victim"]
        for s in suspects:
            for v in victims:
                edges.append({
                    "edge_id": eid, "from_entity": "person", "from_id": s["person_id"],
                    "to_entity": "person", "to_id": v["person_id"],
                    "edge_type": "suspect_of", "fir_id": fir_id
                })
                eid += 1

        # Person-Vehicle edges
        for p in suspects:
            for fv in vehicles_in_fir:
                edges.append({
                    "edge_id": eid, "from_entity": "person", "from_id": p["person_id"],
                    "to_entity": "vehicle", "to_id": fv["vehicle_id"],
                    "edge_type": "used_vehicle", "fir_id": fir_id
                })
                eid += 1

        # Person-Phone edges (random phone links)
        for p in suspects:
            phone = random.choice(phones)
            edges.append({
                "edge_id": eid, "from_entity": "person", "from_id": p["person_id"],
                "to_entity": "phone", "to_id": phone["phone_id"],
                "edge_type": "uses_phone", "fir_id": fir_id
            })
            eid += 1

    return edges

def update_station_fir_counts(stations, firs):
    counts = {}
    for f in firs:
        counts[f["station_id"]] = counts.get(f["station_id"], 0) + 1
    for s in stations:
        s["fir_count"] = counts.get(s["station_id"], 0)
    return stations

def generate_missing_persons(districts):
    mps = []
    for i in range(1, 151):
        d = random.choice(districts)
        lat, lon = rand_point_near(d["lat"], d["lon"], radius_km=30)
        mps.append({
            "id": i,
            "name": rand_name(),
            "age": random.randint(12, 45),
            "gender": random.choice(["Male", "Female"]),
            "reported_date": rand_datetime().isoformat(),
            "district_id": d["id"],
            "lat": lat, "lon": lon,
            "status": random.choice(["Missing", "Missing", "Recovered"])
        })
    return mps

def generate_citizen_feedback(stations):
    feedbacks = []
    fid = 1
    texts = ["Police were very helpful", "Took too long to register FIR", "Station was crowded but handled well", "Officer demanded bribe", "Professional conduct", "Refused to file my complaint initially"]
    for s in stations:
        for _ in range(random.randint(1, 5)):
            txt = random.choice(texts)
            score = 1.0 if "helpful" in txt or "Professional" in txt else (0.2 if "bribe" in txt or "Refused" in txt else 0.5)
            feedbacks.append({
                "id": fid,
                "station_id": s["station_id"],
                "feedback": txt,
                "sentiment_score": score
            })
            fid += 1
    return feedbacks

# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    logger.info("KSP Datathon -- Synthetic Data Generator started")

    logger.info("Generating stations...")
    stations = generate_stations(KARNATAKA_DISTRICTS)

    logger.info("Generating persons (400)...")
    persons = generate_persons(400)

    logger.info("Generating vehicles (200)...")
    vehicles = generate_vehicles(200)

    logger.info("Generating phones (300)...")
    phones = generate_phones(300)

    logger.info("Generating FIRs (1200)...")
    firs = generate_firs(KARNATAKA_DISTRICTS, stations, n=1200)

    logger.info("Generating FIR-Person links...")
    fir_persons = generate_fir_persons(firs, persons)

    logger.info("Generating FIR-Vehicle links...")
    fir_vehicles = generate_fir_vehicles(firs, vehicles)

    logger.info("Generating relationship edges...")
    edges = generate_edges(fir_persons, fir_vehicles, phones)

    logger.info("Updating station FIR counts...")
    stations = update_station_fir_counts(stations, firs)

    logger.info("Generating Missing Persons & Feedback...")
    missing = generate_missing_persons(KARNATAKA_DISTRICTS)
    feedback = generate_citizen_feedback(stations)

    logger.info("Writing to SQLite database...")
    db_path = "data/crime_db.sqlite"
    if os.path.exists(db_path): os.remove(db_path)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.executescript(SCHEMA)

    c.executemany("INSERT INTO districts VALUES (:id,:name,:lat,:lon,:population_density,:literacy_rate,:urban_pct)",
                  KARNATAKA_DISTRICTS)
    c.executemany("INSERT INTO stations VALUES (:station_id,:district_id,:name,:lat,:lon,:fir_count,:pending_pct,:avg_investigation_days)",
                  stations)
    c.executemany("INSERT INTO persons VALUES (:person_id,:name,:age,:gender,:role,:phone,:district_id,:prior_fir_count,:districts_active,:mo_pattern,:risk_score)",
                  persons)
    c.executemany("INSERT INTO vehicles VALUES (:vehicle_id,:reg_number,:vehicle_type,:color,:linked_fir_ids)",
                  vehicles)
    c.executemany("INSERT INTO phones VALUES (:phone_id,:number,:linked_person_ids)",
                  phones)
    c.executemany("INSERT INTO firs VALUES (:fir_id,:district_id,:station_id,:crime_type,:sub_type,:mo_tags,:weapon,:date_time,:lat,:lon,:status,:description,:chargesheet_date,:trial_start_date,:disposal_date,:judicial_outcome)",
                  firs)
    c.executemany("INSERT INTO fir_persons(fir_id,person_id,role) VALUES (:fir_id,:person_id,:role)",
                  fir_persons)
    c.executemany("INSERT INTO fir_vehicles(fir_id,vehicle_id) VALUES (:fir_id,:vehicle_id)",
                  fir_vehicles)
    c.executemany("INSERT INTO relationship_edges VALUES (:edge_id,:from_entity,:from_id,:to_entity,:to_id,:edge_type,:fir_id)",
                  edges)

    c.executemany("INSERT INTO missing_persons VALUES (:id,:name,:age,:gender,:reported_date,:district_id,:lat,:lon,:status)", missing)
    c.executemany("INSERT INTO citizen_feedback VALUES (:id,:station_id,:feedback,:sentiment_score)", feedback)

    conn.commit()
    conn.close()

    logger.info(f"Database successfully written to {db_path} (Districts: {len(KARNATAKA_DISTRICTS)}, Stations: {len(stations)}, Persons: {len(persons)}, FIRs: {len(firs)}, Vehicles: {len(vehicles)}, Phones: {len(phones)}, Edges: {len(edges)})")


if __name__ == "__main__":
    main()
