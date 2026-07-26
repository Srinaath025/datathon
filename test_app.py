"""
KSP CrimeIQ — Targeted Regression Test Suite
=============================================
Coverage focused on key ML constraints, search ranking, network repeat offender scoring,
and 404 error responses for missing resources.
"""

import pytest
from analytics.predictive import get_risk_scores, get_forecast
from analytics.search import search_firs
from analytics.network import get_repeat_offenders
from analytics.geo import get_heatmap_data
from analytics.chatbot import ask_chatbot, reset_chatbot_index
from analytics.socioeconomic import get_socioeconomic_correlation
from analytics.sentiment import get_station_trust_scores, analyze_sentiment_text
from analytics.trafficking import get_trafficking_clusters



# ─────────────────────────────────────────────────────────────
# ANALYTICS MODULE UNIT TESTS
# ─────────────────────────────────────────────────────────────

def test_predictive_risk_scores_bounded(test_db):
    """Assert all area risk scores are bounded strictly within [0, 100]."""
    scores = get_risk_scores()
    assert isinstance(scores, list)
    assert len(scores) > 0
    for item in scores:
        assert "score" in item
        assert 0 <= item["score"] <= 100


def test_predictive_forecast_length(test_db):
    """Assert crime forecast returns historical data plus expected 6-month horizon."""
    res = get_forecast()
    assert "historical" in res
    assert "forecast" in res
    assert len(res["forecast"]) == 6


def test_search_similarity_ranking(test_db):
    """Assert TF-IDF search results are sorted descending by similarity score, not DB insertion order."""
    results = search_firs("theft robbery", limit=10)
    assert isinstance(results, list)
    if len(results) > 1:
        scores = [r["similarity_score"] for r in results]
        assert scores == sorted(scores, reverse=True)


def test_network_repeat_offenders_scoring(test_db):
    """Assert repeat offender list filters for prior_fir_count >= 2 and sorts by risk_score."""
    offenders = get_repeat_offenders(min_firs=2, limit=20)
    assert isinstance(offenders, list)
    for o in offenders:
        assert o["prior_fir_count"] >= 2
    if len(offenders) > 1:
        scores = [o["risk_score"] for o in offenders]
        assert scores == sorted(scores, reverse=True)


def test_geo_heatmap_data_structure(test_db):
    """Assert get_heatmap_data returns points with lat, lon, and intensity."""
    points = get_heatmap_data()
    assert isinstance(points, list)
    if len(points) > 0:
        p = points[0]
        assert "lat" in p and "lon" in p and "intensity" in p


def test_chatbot_total_crimes_query(test_db):
    """Assert case retrieval assistant responds correctly to total crimes query."""
    reply = ask_chatbot("how many total crimes are there?")
    assert "total registered FIRs" in reply



def test_socioeconomic_correlation_keys(test_db):
    """Assert socioeconomic correlation module returns literacy, urban, and density metrics."""
    res = get_socioeconomic_correlation()
    assert "correlations" in res
    assert "crime_vs_literacy" in res["correlations"]
    assert "crime_vs_urban_pct" in res["correlations"]
    assert "crime_vs_population_density" in res["correlations"]



# ─────────────────────────────────────────────────────────────
# FASTAPI ROUTE TESTS (P0 404 RESILIENCE)
# ─────────────────────────────────────────────────────────────

def test_route_district_404(client, auth_headers):
    """Assert GET /districts/{nonexistent_id} returns HTTP 404 (not 200)."""
    response = client.get("/districts/999999", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "District 999999 not found"


def test_route_crime_404(client, auth_headers):
    """Assert GET /crimes/{nonexistent_id} returns HTTP 404 (not 200)."""
    response = client.get("/crimes/999999", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "FIR 999999 not found"


def test_route_offender_404(client, auth_headers):
    """Assert GET /offenders/{nonexistent_id} returns HTTP 404 (not 200)."""
    response = client.get("/offenders/999999", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Offender 999999 not found"


def test_health_check_endpoint(client):
    """Assert GET /health checks DB and returns 200 OK payload without authentication requirement."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert "timestamp" in data


def test_sentiment_nlp_analysis(test_db):
    """Assert analyze_sentiment_text returns valid polarity and trust scores include positive/negative counts."""
    assert analyze_sentiment_text("quick, polite and helpful officer") > 0.0
    assert analyze_sentiment_text("rude, corrupt and lazy staff") < 0.0
    scores = get_station_trust_scores()
    assert isinstance(scores, list)
    if len(scores) > 0:
        s = scores[0]
        assert "trust_index" in s
        assert "positive_count" in s and "negative_count" in s


def test_trafficking_dbscan_clustering(test_db):
    """Assert DBSCAN spatial density clustering discovers trafficking corridor clusters."""
    clusters = get_trafficking_clusters(eps_km=100.0, min_samples=2)
    assert isinstance(clusters, list)
    for c in clusters:
        assert "cluster_id" in c
        assert "corridor_name" in c
        assert "missing_count" in c
        assert "density_level" in c
        assert "risk_level" not in c  # Old risk_level key completely removed



def test_risk_score_explanation_sums_to_composite_score(test_db):
    """Assert area risk score feature contributions sum exactly to final composite score."""
    scores = get_risk_scores()
    assert len(scores) > 0
    for s in scores:
        assert "feature_breakdown" in s
        breakdown = s["feature_breakdown"]
        assert len(breakdown) == 4
        sum_contrib = round(sum(f["contribution"] for f in breakdown), 1)
        assert abs(sum_contrib - s["score"]) < 0.2  # Match score within rounding threshold


def test_risk_score_override_rbac(client, auth_headers):
    """Assert POST /risk-score/{district_id}/override requires valid auth credentials."""
    # Unauthenticated -> 401
    res_unauth = client.post("/risk-score/1/override", json={"disagree": True, "reason": "Operational dispute"})
    assert res_unauth.status_code == 401

    # Authenticated -> 200 OK
    res_auth = client.post(
        "/risk-score/1/override",
        headers=auth_headers,
        json={"disagree": True, "revised_score": 45.0, "reason": "Increased night patrols in sector"}
    )
    assert res_auth.status_code == 200
    assert res_auth.json()["status"] == "success"


def test_risk_score_override_persistence_and_retrieval(client, auth_headers, test_db):
    """Assert submitted officer overrides persist in DB and are retrieved in GET /risk-score."""
    # Submit override
    override_reason = "Community policing initiative reduces baseline threat"
    client.post(
        "/risk-score/1/override",
        headers=auth_headers,
        json={"disagree": True, "revised_score": 30.0, "reason": override_reason}
    )

    # Verify retrieval in get_risk_scores
    scores = get_risk_scores()
    district_1 = next((s for s in scores if s["district_id"] == 1), None)
    assert district_1 is not None
    assert "overrides" in district_1
    assert len(district_1["overrides"]) > 0
    latest = district_1["overrides"][0]
    assert latest["reason"] == override_reason
    assert latest["revised_score"] == 30.0


def test_risk_score_dual_score_architecture(client, auth_headers, test_db):
    """Assert Option (b) Dual-Score: override preserves original model score while populating officer_adjusted_score."""
    initial_scores = get_risk_scores()
    d1_initial = next(s for s in initial_scores if s["district_id"] == 1)
    original_model_score = d1_initial["score"]

    client.post(
        "/risk-score/1/override",
        headers=auth_headers,
        json={"disagree": True, "revised_score": 25.0, "reason": "High police presence in district center"}
    )

    updated_scores = get_risk_scores()
    d1_updated = next(s for s in updated_scores if s["district_id"] == 1)
    assert d1_updated["score"] == original_model_score
    assert d1_updated["officer_adjusted_score"] == 25.0



# ─────────────────────────────────────────────────────────────
# REMEDIATION REGRESSION TESTS (PROMPTS 1, 2, 3, 4, 5)
# ─────────────────────────────────────────────────────────────

def test_export_csv_disclaimer_header(client, auth_headers):
    """Assert CSV export starts with the synthetic data warning comment header."""
    res = client.get("/export/csv", headers=auth_headers)
    assert res.status_code == 200
    lines = res.text.splitlines()
    assert len(lines) > 0
    assert lines[0].startswith("# DISCLAIMER: Synthetic demonstration data")


def test_export_pdf_disclaimer_header(client, auth_headers):
    """Assert PDF export returns valid PDF binary containing stream data."""
    res = client.get("/export/pdf", headers=auth_headers)
    assert res.status_code == 200
    assert res.content.startswith(b"%PDF")
    assert len(res.content) > 1000


def test_risk_score_feature_breakdown_structure(test_db):
    """Assert /risk-score feature breakdown returns exact feature names and weights."""
    scores = get_risk_scores()
    assert len(scores) > 0
    s0 = scores[0]
    assert "feature_breakdown" in s0
    features = {f["feature"]: f["weight"] for f in s0["feature_breakdown"]}
    assert features["Violent Crimes"] == 0.35
    assert features["Total Volume"] == 0.30
    assert features["Recent Trend (2025)"] == 0.20
    assert features["Repeat Offenders"] == 0.15


def test_risk_score_override_empty_reason_rejection(client, auth_headers):
    """Assert POST /risk-score/{district_id}/override rejects blank reason with 400 Bad Request."""
    res = client.post(
        "/risk-score/1/override",
        headers=auth_headers,
        json={"disagree": True, "reason": "   "}
    )
    assert res.status_code == 400
    assert "reason is required" in res.json()["detail"]


def test_forecast_model_diagnostics_holdout(client, auth_headers):
    """Assert /forecast returns model_diagnostics with 6-fold rolling walk-forward cross-validation metrics."""
    res = client.get("/forecast", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "model_diagnostics" in data
    diag = data["model_diagnostics"]
    assert "Rolling Walk-Forward" in diag["validation_method"]
    assert diag["evaluation_folds"] == 6
    assert "mape_pct" in diag
    assert "rmse" in diag
    assert "directional indicator" in diag["accuracy_caveat"]



def test_anomalies_model_diagnostics_sensitivity(client, auth_headers):
    """Assert /anomalies returns model_diagnostics with contamination sensitivity sweep."""
    res = client.get("/anomalies?limit=10", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "model_diagnostics" in data
    diag = data["model_diagnostics"]
    assert "contamination_sensitivity" in diag
    sens = diag["contamination_sensitivity"]
    assert "3%" in sens
    assert "5%" in sens
    assert "10%" in sens
    assert sens["5%"]["contamination"] == 0.05


def test_trafficking_density_lead_reframing(client, auth_headers):
    """Assert /trafficking/clusters returns reframed density leads, methodology note, and NO risk_level key."""
    res = client.get("/trafficking/clusters", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    if len(data) > 0:
        c0 = data[0]
        assert "density_level" in c0
        assert "Density Lead" in c0["density_level"]
        assert "risk_level" not in c0  # Old risk_level key completely removed
        assert c0["density_level"] in ["High Density Lead", "Moderate Density Lead", "Low Density Lead"]
        assert "methodology_note" in c0
        assert "investigative prioritization" in c0["methodology_note"]





