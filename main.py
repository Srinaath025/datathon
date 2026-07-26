"""
KSP CrimeIQ — Crime Analytics Platform
FastAPI Backend — All REST Endpoints
Run: uvicorn main:app --reload --port 8000
"""

# Load .env before any other module reads os.getenv()
from dotenv import load_dotenv
load_dotenv()

import os
import time
import sqlite3
import asyncio
from typing import Optional
from collections import defaultdict

import logging
from datetime import datetime, timezone

from fastapi import (
    FastAPI, Query, Depends, UploadFile, File, HTTPException,
    status, WebSocket, WebSocketDisconnect, Response, Request
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# ── Auth ────────────────────────────────────────────────────────────────────
from auth import (
    authenticate_user, register_user, create_access_token,
    get_current_user, LoginRequest, SignupRequest, TokenResponse,
    require_roles, DEMO_PASSWORDS
)

# ── Analytics modules ────────────────────────────────────────────────────────
from analytics.geo import (
    get_heatmap_data, get_district_summary, get_station_breakdown,
    get_crime_by_hour, get_crime_by_weekday, get_spike_alerts,
    get_crime_type_distribution
)
from analytics.network import get_network_graph, get_repeat_offenders, get_offender_profile
from analytics.predictive import (
    get_forecast, get_anomalies, get_risk_scores, get_mo_clusters,
    save_officer_override, get_officer_overrides
)
from analytics.socioeconomic import (

    get_socioeconomic_correlation, get_district_ranking,
    get_station_performance, get_crime_calendar, get_sankey_data
)
from analytics.search import search_firs, get_similar_cases, get_investigation_timeline
from analytics.data_import import process_upload, get_data_stats, clear_real_data
from analytics.export import generate_csv_export, generate_pdf_export
from analytics.judicial import get_judicial_funnel
from analytics.predictive import get_bias_audit, log_human_override
from analytics.trafficking import get_trafficking_clusters
from analytics.optimizer import optimize_patrols
from analytics.sentiment import get_station_trust_scores
from analytics.chatbot import ask_chatbot

# ─────────────────────────────────────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="KSP CrimeIQ API",
    description="AI-Driven Crime Analytics Platform",
    version="2.0.0",
)

# Restricted CORS origins
ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "PUT", "OPTIONS"],
    allow_headers=["*"],
)

if os.path.exists("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Configure application logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ksp_crimeiq")

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE & ROLE-BASED ACCESS CONTROL
# ─────────────────────────────────────────────────────────────────────────────
from db import get_db, init_db
init_db()

@app.get("/health", tags=["System"])
def health_check():
    """Health check endpoint verifying database connectivity."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        conn.close()
        return {
            "status": "ok",
            "database": "connected",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "unhealthy", "database": "disconnected", "error": str(e)}
        )

# Granular RBAC shorthands matching product story & frontend tabs
AUTH_ANY = Depends(require_roles(["commander", "analyst", "sho", "investigator"]))

AUTH_COMMANDER_ANALYST = Depends(require_roles(["commander", "analyst"]))
AUTH_GEO_PRED_ADV = Depends(require_roles(["commander", "analyst", "sho", "investigator"]))
AUTH_NETWORK = Depends(require_roles(["commander", "analyst", "investigator"]))

# ─────────────────────────────────────────────────────────────────────────────
# RATE LIMITER FOR LOGIN
# ─────────────────────────────────────────────────────────────────────────────
_FAILED_LOGIN_ATTEMPTS = defaultdict(list)

def enforce_login_rate_limit(client_ip: str):
    now = time.time()
    attempts = [t for t in _FAILED_LOGIN_ATTEMPTS[client_ip] if now - t < 60]
    _FAILED_LOGIN_ATTEMPTS[client_ip] = attempts
    if len(attempts) >= 5:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please wait 60 seconds before trying again."
        )

def record_failed_login(client_ip: str):
    _FAILED_LOGIN_ATTEMPTS[client_ip].append(time.time())

# ─────────────────────────────────────────────────────────────────────────────
# PAGES  (public)
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def serve_index():
    with open("frontend/index.html", encoding="utf-8") as f:
        return f.read()

@app.get("/login", response_class=HTMLResponse, include_in_schema=False)
def serve_login():
    with open("frontend/login.html", encoding="utf-8") as f:
        return f.read()

# ─────────────────────────────────────────────────────────────────────────────
# AUTH  (public / rate-limited)
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/auth/login", response_model=TokenResponse, tags=["Auth"])
def login(req: LoginRequest, request: Request):
    client_ip = request.client.host if request.client else "127.0.0.1"
    enforce_login_rate_limit(client_ip)

    user = authenticate_user(req.username, req.password)
    if not user:
        record_failed_login(client_ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid username or password")
    token = create_access_token({"sub": user["username"], "role": user["role"]})
    return TokenResponse(
        access_token=token,
        user={k: user[k] for k in ("username","display_name","role","role_label","badge","avatar_color")},
    )

@app.post("/auth/signup", response_model=TokenResponse, tags=["Auth"])
def signup(req: SignupRequest):
    try:
        user = register_user(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    token = create_access_token({"sub": user["username"], "role": user["role"]})
    return TokenResponse(
        access_token=token,
        user={k: user[k] for k in ("username","display_name","role","role_label","badge","avatar_color")},
    )

@app.get("/auth/me", tags=["Auth"])
def auth_me(current_user: dict = AUTH_ANY):
    return {k: current_user[k] for k in ("username","display_name","role","role_label","badge","avatar_color")}

@app.get("/auth/users", tags=["Auth"])
def auth_users():
    """Returns demo accounts and active generated credentials for UI quick-fill."""
    conn = get_db()
    rows = conn.execute("SELECT username, role, role_label, display_name, badge FROM users WHERE username IN ('admin','investigator','sho')").fetchall()
    conn.close()
    return [
        {
            "username": r["username"],
            "password": DEMO_PASSWORDS.get(r["username"], ""),
            "role": r["role"],
            "role_label": r["role_label"],
            "display_name": r["display_name"],
            "badge": r["badge"]
        }
        for r in rows
    ]

# ─────────────────────────────────────────────────────────────────────────────
# DATA MANAGEMENT  (Commander, Analyst)
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/data/upload", tags=["Data Management"])
async def upload_data(
    file: UploadFile = File(...),
    _: dict = AUTH_COMMANDER_ANALYST,
):
    """Upload a CSV or Excel file to import real crime data."""
    allowed = {".csv", ".xlsx", ".xls"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}. Use CSV or Excel.")
    content = await file.read()
    result = process_upload(content, file.filename)
    return result

@app.get("/data/stats", tags=["Data Management"])
def data_stats(_: dict = AUTH_ANY):
    """Breakdown of synthetic vs real imported FIRs."""
    return get_data_stats()

@app.delete("/data/clear-real", tags=["Data Management"])
def clear_real(_: dict = AUTH_COMMANDER_ANALYST):
    """Remove all real (imported) FIRs, keeping synthetic data."""
    return clear_real_data()

# ─────────────────────────────────────────────────────────────────────────────
# CORE DATA  (All Roles)
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/stats", tags=["Core Data"])
def platform_stats(_: dict = AUTH_ANY):
    conn = get_db()
    c = conn.cursor()
    stats = {
        "total_firs":      c.execute("SELECT COUNT(*) FROM firs").fetchone()[0],
        "total_districts": c.execute("SELECT COUNT(*) FROM districts").fetchone()[0],
        "total_stations":  c.execute("SELECT COUNT(*) FROM stations").fetchone()[0],
        "total_persons":   c.execute("SELECT COUNT(*) FROM persons").fetchone()[0],
        "total_vehicles":  c.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0],
        "total_edges":     c.execute("SELECT COUNT(*) FROM relationship_edges").fetchone()[0],
        "pending_cases":   c.execute("SELECT COUNT(*) FROM firs WHERE status='Under Investigation'").fetchone()[0],
        "crime_types":     c.execute("SELECT COUNT(DISTINCT crime_type) FROM firs").fetchone()[0],
    }
    conn.close()
    return stats

@app.get("/districts", tags=["Core Data"])
def list_districts(_: dict = AUTH_ANY):
    conn = get_db()
    rows = conn.execute("SELECT * FROM districts").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/districts/{district_id}", tags=["Core Data"])
def get_district(district_id: int, _: dict = AUTH_ANY):
    conn = get_db()
    row = conn.execute("SELECT * FROM districts WHERE district_id=?", (district_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"District {district_id} not found")
    return dict(row)

@app.get("/stations", tags=["Core Data"])
def list_stations(district_id: Optional[int] = None, _: dict = AUTH_ANY):
    conn = get_db()
    if district_id:
        rows = conn.execute("SELECT * FROM stations WHERE district_id=?", (district_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM stations").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/crimes", tags=["Core Data"])
def list_crimes(
    district_id: Optional[int] = None,
    crime_type:  Optional[str] = None,
    status:      Optional[str] = None,
    limit: int   = Query(100, le=500),
    offset: int  = 0,
    _: dict      = AUTH_ANY,
):
    conn = get_db()
    q = """
        SELECT f.*, d.name as district_name, s.name as station_name
        FROM firs f
        JOIN districts d ON f.district_id = d.district_id
        JOIN stations  s ON f.station_id  = s.station_id
        WHERE 1=1
    """
    params = []
    if district_id: q += " AND f.district_id=?"; params.append(district_id)
    if crime_type:  q += " AND f.crime_type=?";  params.append(crime_type)
    if status:      q += " AND f.status=?";       params.append(status)
    q += " ORDER BY f.date_time DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/crimes/{fir_id}", tags=["Core Data"])
def get_crime(fir_id: int, _: dict = AUTH_ANY):
    conn = get_db()
    row = conn.execute("""
        SELECT f.*, d.name as district_name, s.name as station_name
        FROM firs f
        JOIN districts d ON f.district_id = d.district_id
        JOIN stations  s ON f.station_id  = s.station_id
        WHERE f.fir_id=?
    """, (fir_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"FIR {fir_id} not found")
    return dict(row)

@app.get("/offenders", tags=["Core Data"])
def list_offenders(min_firs: int = 2, limit: int = 50, _: dict = AUTH_ANY):
    return get_repeat_offenders(min_firs=min_firs, limit=limit)

@app.get("/offenders/{person_id}", tags=["Core Data"])
def get_offender(person_id: int, _: dict = AUTH_ANY):
    profile = get_offender_profile(person_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Offender {person_id} not found")
    return profile

# ─────────────────────────────────────────────────────────────────────────────
# GEOSPATIAL  (Commander, Analyst, SHO)
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/heatmap-data", tags=["Geospatial"])
def heatmap(
    district_id: Optional[int] = None,
    crime_type:  Optional[str] = None,
    time_filter: Optional[str] = None,
    _: dict      = AUTH_GEO_PRED_ADV,
):
    return get_heatmap_data(district_id=district_id, crime_type=crime_type, time_filter=time_filter)

@app.get("/district-summary", tags=["Geospatial"])
def district_summary(_: dict = AUTH_GEO_PRED_ADV):
    return get_district_summary()

@app.get("/station-breakdown/{district_id}", tags=["Geospatial"])
def station_breakdown(district_id: int, _: dict = AUTH_GEO_PRED_ADV):
    return get_station_breakdown(district_id)

@app.get("/crime-by-hour", tags=["Geospatial"])
def crime_by_hour(_: dict = AUTH_GEO_PRED_ADV):
    return get_crime_by_hour()

@app.get("/crime-by-weekday", tags=["Geospatial"])
def crime_by_weekday(_: dict = AUTH_GEO_PRED_ADV):
    return get_crime_by_weekday()

@app.get("/spike-alerts", tags=["Geospatial"])
def spike_alerts(_: dict = AUTH_GEO_PRED_ADV):
    return get_spike_alerts()

@app.get("/crime-type-distribution", tags=["Geospatial"])
def crime_type_distribution(district_id: Optional[int] = None, _: dict = AUTH_GEO_PRED_ADV):
    return get_crime_type_distribution(district_id=district_id)

# ─────────────────────────────────────────────────────────────────────────────
# NETWORK  (Commander, Analyst, Investigator)
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/network/{entity_type}/{entity_id}", tags=["Network"])
def network_graph(entity_type: str, entity_id: int, depth: int = 2, _: dict = AUTH_NETWORK):
    return get_network_graph(entity_type, entity_id, depth=depth)

# ─────────────────────────────────────────────────────────────────────────────
# PREDICTIVE  (Commander, Analyst, SHO)
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/forecast", tags=["Predictive"])
def forecast(district_id: Optional[int] = None, crime_type: Optional[str] = None, _: dict = AUTH_GEO_PRED_ADV):
    return get_forecast(district_id=district_id, crime_type=crime_type)

@app.get("/anomalies", tags=["Predictive"])
def anomalies(limit: int = 30, _: dict = AUTH_GEO_PRED_ADV):
    return get_anomalies(limit=limit)

@app.get("/risk-score", tags=["Predictive"], summary="District Risk Scores (Dual-Score Architecture)")
def risk_scores(_: dict = AUTH_GEO_PRED_ADV):
    """
    Returns district composite risk scores with linear feature weight breakdowns.
    Dual-Score Architecture: Model-computed score ('score') is preserved for mathematical auditability;
    human officer overrides do not alter the baseline model score, but surface an explicit 'officer_adjusted_score'
    field alongside the audit trail.
    """
    return get_risk_scores()

class RiskScoreOverrideRequest(BaseModel):
    disagree: bool = True
    revised_score: Optional[float] = None
    reason: str

@app.post("/risk-score/{district_id}/override", tags=["Predictive"], summary="Log Officer Score Override")
def post_risk_score_override(
    district_id: int,
    req: RiskScoreOverrideRequest,
    current_user: dict = AUTH_GEO_PRED_ADV
):
    """
    Log an officer challenge or operational context override for a district risk score.
    Overrides are recorded in the officer_overrides audit log and surface a distinct 'officer_adjusted_score'
    field without mutating the underlying model-computed baseline score.
    """
    if not req.reason or not req.reason.strip():
        raise HTTPException(status_code=400, detail="Explanation/reason is required for score override.")
    save_officer_override(
        district_id=district_id,
        username=current_user.get("username", "officer"),
        disagree=req.disagree,
        revised_score=req.revised_score,
        reason=req.reason.strip()
    )
    return {"status": "success", "message": "Officer override recorded successfully."}


@app.get("/risk-score/{district_id}/overrides", tags=["Predictive"])
def get_district_risk_score_overrides(
    district_id: int,
    _: dict = AUTH_GEO_PRED_ADV
):
    return get_officer_overrides(district_id=district_id)

@app.get("/mo-clusters", tags=["Predictive"])

def mo_clusters(n_clusters: int = 6, _: dict = AUTH_GEO_PRED_ADV):
    return get_mo_clusters(n_clusters=n_clusters)

# ─────────────────────────────────────────────────────────────────────────────
# SOCIO-ECONOMIC  (Commander, Analyst)
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/correlation", tags=["Socio-Economic"])
def correlation(_: dict = AUTH_COMMANDER_ANALYST):
    return get_socioeconomic_correlation()

@app.get("/district-rank", tags=["Socio-Economic"])
def district_rank(_: dict = AUTH_COMMANDER_ANALYST):
    return get_district_ranking()

@app.get("/station-performance", tags=["Socio-Economic"])
def station_performance(district_id: Optional[int] = None, _: dict = AUTH_COMMANDER_ANALYST):
    return get_station_performance(district_id=district_id)

@app.get("/crime-calendar", tags=["Socio-Economic"])
def crime_calendar(_: dict = AUTH_COMMANDER_ANALYST):
    return get_crime_calendar()

@app.get("/sankey", tags=["Socio-Economic"])
def sankey(_: dict = AUTH_COMMANDER_ANALYST):
    return get_sankey_data()

# ─────────────────────────────────────────────────────────────────────────────
# SEARCH & INVESTIGATION  (All Roles)
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/search", tags=["Search"])
def fir_search(q: str = Query(..., min_length=2), limit: int = 10, _: dict = AUTH_ANY):
    return search_firs(q, limit=limit)

@app.get("/similar-cases/{fir_id}", tags=["Search"])
def similar_cases(fir_id: int, limit: int = 8, _: dict = AUTH_ANY):
    return get_similar_cases(fir_id, limit=limit)

@app.get("/investigation-timeline/{fir_id}", tags=["Search"])
def investigation_timeline(fir_id: int, _: dict = AUTH_ANY):
    return get_investigation_timeline(fir_id)

# ─────────────────────────────────────────────────────────────────────────────
# ADVANCED MODULES  (Commander, Analyst, SHO)
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/judicial/funnel", tags=["Advanced"])
def judicial_funnel(district_id: Optional[int] = None, _: dict = AUTH_GEO_PRED_ADV):
    return get_judicial_funnel(district_id=district_id)

@app.get("/audit/bias", tags=["Advanced"])
def audit_bias(_: dict = AUTH_GEO_PRED_ADV):
    return get_bias_audit()

class OverrideRequest(BaseModel):
    action: str
    reason: str

@app.post("/audit/override/{fir_id}", tags=["Advanced"])
def audit_override(fir_id: int, req: OverrideRequest, _: dict = AUTH_GEO_PRED_ADV):
    return log_human_override(fir_id, req.action, req.reason)

@app.get("/trafficking/clusters", tags=["Advanced"])
def trafficking_clusters(_: dict = AUTH_GEO_PRED_ADV):
    return get_trafficking_clusters()

@app.get("/optimize-patrols", tags=["Advanced"])
def patrols_optimizer(total_units: int = 50, _: dict = AUTH_GEO_PRED_ADV):
    return optimize_patrols(total_units=total_units)

@app.get("/sentiment/trust-score", tags=["Advanced"])
def sentiment_trust_score(_: dict = AUTH_GEO_PRED_ADV):
    return get_station_trust_scores()

class ChatRequest(BaseModel):
    query: str

@app.post("/chat", tags=["Retrieval Assistant"], summary="TF-IDF Case Retrieval Assistant")
def chat_endpoint(req: ChatRequest, _: dict = AUTH_ANY):

    response = ask_chatbot(req.query)
    return {"response": response}

# ─────────────────────────────────────────────────────────────────────────────
# EXPORT  (Commander, Analyst) & WEBSOCKETS
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/export/csv", tags=["Export"])
def export_csv(_: dict = AUTH_COMMANDER_ANALYST):
    csv_data = generate_csv_export()
    return Response(content=csv_data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=district_summary.csv"})

@app.get("/export/pdf", tags=["Export"])
def export_pdf(_: dict = AUTH_COMMANDER_ANALYST):
    pdf_data = generate_pdf_export()
    return Response(content=pdf_data, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=district_summary.pdf"})

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

@app.websocket("/ws/alerts")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    # Catalyst provides the port via this environment variable
    port = int(os.environ.get("X_ZOHO_CATALYST_LISTEN_PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
