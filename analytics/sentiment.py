"""
KSP CrimeIQ — Citizen Feedback Sentiment & Trust Index Module
Computes NLP sentiment polarity over citizen feedback text per police station.
"""

import re
from db import get_db

# Specialized law enforcement sentiment lexicon
_POSITIVE_WORDS = {
    "helpful", "prompt", "polite", "efficient", "responsive", "safe", "courteous",
    "quick", "professional", "excellent", "good", "reassuring", "supportive",
    "transparent", "honest", "cooperative", "fast", "great", "kind", "respectful"
}
_NEGATIVE_WORDS = {
    "slow", "rude", "corrupt", "unhelpful", "delayed", "bribe", "unprofessional",
    "arrogant", "harassment", "negligent", "ignore", "bias", "lazy", "poor",
    "bad", "terrible", "hostile", "useless", "scam", "threat", "abuse"
}

def analyze_sentiment_text(text: str) -> float:
    """
    Computes a sentiment score in [-1.0, 1.0] for feedback text using lexicon-based NLP.
    """
    if not text:
        return 0.0
    words = re.findall(r"\w+", text.lower())
    if not words:
        return 0.0

    pos_count = sum(1 for w in words if w in _POSITIVE_WORDS)
    neg_count = sum(1 for w in words if w in _NEGATIVE_WORDS)

    total = pos_count + neg_count
    if total == 0:
        return 0.0
    return (pos_count - neg_count) / float(total)

def get_station_trust_scores():
    """
    Evaluates raw citizen feedback text using NLP sentiment analysis
    and computes a 0-100 Trust Index per police station.
    """
    conn = get_db()
    stations = conn.execute("SELECT station_id, name, district_id FROM stations").fetchall()
    feedbacks = conn.execute("SELECT station_id, feedback, sentiment_score FROM citizen_feedback").fetchall()
    conn.close()

    station_metrics = {
        s["station_id"]: {
            "scores": [],
            "positive": 0,
            "neutral": 0,
            "negative": 0
        } for s in stations
    }

    for fb in feedbacks:
        sid = fb["station_id"]
        if sid in station_metrics:
            text = fb["feedback"] or ""
            nlp_polarity = analyze_sentiment_text(text)
            
            # Combine text NLP polarity [-1,1] with numerical score [0,1]
            raw_score = fb["sentiment_score"] if fb["sentiment_score"] is not None else 0.5
            combined = (nlp_polarity + 1.0) / 2.0
            final_score = (combined + raw_score) / 2.0

            station_metrics[sid]["scores"].append(final_score)
            if final_score >= 0.6:
                station_metrics[sid]["positive"] += 1
            elif final_score <= 0.4:
                station_metrics[sid]["negative"] += 1
            else:
                station_metrics[sid]["neutral"] += 1

    results = []
    for s in stations:
        sid = s["station_id"]
        m = station_metrics[sid]
        count = len(m["scores"])
        avg_score = (sum(m["scores"]) / count) if count > 0 else 0.5
        trust_index = round(avg_score * 100, 1)

        results.append({
            "station_id": sid,
            "station_name": s["name"],
            "district_id": s["district_id"],
            "feedback_count": count,
            "positive_count": m["positive"],
            "neutral_count": m["neutral"],
            "negative_count": m["negative"],
            "trust_index": trust_index,
            "status": "Excellent" if trust_index >= 80 else ("Good" if trust_index >= 60 else ("Needs Improvement" if trust_index >= 40 else "Critical"))
        })

    return sorted(results, key=lambda x: -x["trust_index"])
