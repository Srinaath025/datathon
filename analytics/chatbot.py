"""
KSP CrimeIQ — TF-IDF Case Retrieval Assistant
Vector similarity retrieval over FIR corpus + SQL analytical fallback.
"""

import re
import numpy as np
from db import get_db
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

_VECTORIZER = None
_FIR_MATRIX = None
_FIR_DOCS = []

def _init_rag_pipeline():
    """Build lightweight vector index over all FIR descriptions and MO tags."""
    global _VECTORIZER, _FIR_MATRIX, _FIR_DOCS
    conn = get_db()
    rows = conn.execute("""
        SELECT fir_id, crime_type, sub_type, mo_tags, description, lat, lon
        FROM firs
    """).fetchall()
    conn.close()

    _FIR_DOCS = [dict(r) for r in rows]
    if not _FIR_DOCS:
        return

    corpus = [
        f"{r['crime_type']} {r['sub_type']} {r['mo_tags']} {r['description']}"
        for r in _FIR_DOCS
    ]
    _VECTORIZER = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), max_features=2500)
    _FIR_MATRIX = _VECTORIZER.fit_transform(corpus)

def reset_chatbot_index():
    """Reset vector index for testing or fresh database reloading."""
    global _VECTORIZER, _FIR_MATRIX, _FIR_DOCS
    _VECTORIZER = None
    _FIR_MATRIX = None
    _FIR_DOCS = []

def ask_chatbot(query: str) -> str:
    """
    TF-IDF Case Retrieval Assistant:
    - Structured SQL for quantitative DB stats (counts, top offenders, missing persons)
    - TF-IDF Vector Similarity Search over FIR descriptions for semantic natural language queries
    """
    query_clean = query.lower().strip()
    conn = get_db()

    # Intent 1: Total FIR count
    if "how many crimes" in query_clean or "total crimes" in query_clean or "total fir" in query_clean:
        count = conn.execute("SELECT COUNT(*) FROM firs").fetchone()[0]
        conn.close()
        return f"There are currently {count} total registered FIRs in the system."

    # Intent 2: Top repeat offender
    if "repeat offender" in query_clean or "most wanted" in query_clean:
        offender = conn.execute("""
            SELECT p.name, COUNT(fp.fir_id) as c, p.risk_score
            FROM persons p
            JOIN fir_persons fp ON p.person_id = fp.person_id
            WHERE fp.role = 'suspect'
            GROUP BY p.person_id
            ORDER BY c DESC, p.risk_score DESC LIMIT 1
        """).fetchone()
        conn.close()
        if offender:
            return f"The top repeat offender is {offender['name']} with {offender['c']} linked FIRs (Risk Score: {offender['risk_score']}/100)."
        return "No repeat offenders identified."

    # Intent 3: Missing persons
    if "missing person" in query_clean or "missing count" in query_clean:
        count = conn.execute("SELECT COUNT(*) FROM missing_persons WHERE status='Missing'").fetchone()[0]
        conn.close()
        return f"There are currently {count} active missing persons cases in the state database."

    conn.close()

    # Semantic TF-IDF Vector Search over FIR Corpus
    global _VECTORIZER, _FIR_MATRIX, _FIR_DOCS
    if _VECTORIZER is None or _FIR_MATRIX is None:
        _init_rag_pipeline()

    if _VECTORIZER is None or not _FIR_DOCS:
        return "Retrieval assistant database is empty."

    q_vec = _VECTORIZER.transform([query])
    similarities = cosine_similarity(q_vec, _FIR_MATRIX).flatten()
    top_indices = np.argsort(similarities)[::-1][:3]

    matched_results = []
    for idx in top_indices:
        score = float(similarities[idx])
        if score > 0.1:
            doc = _FIR_DOCS[idx]
            matched_results.append(
                f"• FIR #{doc['fir_id']} ({doc['crime_type']} - {doc['sub_type']}): {doc['description']} [Relevance: {int(score*100)}%]"
            )

    if matched_results:
        return "Found relevant FIR records based on semantic vector search:\n" + "\n".join(matched_results)

    return "I am the KSP CrimeIQ Case Retrieval Assistant. Ask me about total crime counts, repeat offenders, missing persons, or search for specific case details (e.g., 'armed robbery on highway')."

