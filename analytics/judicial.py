from db import get_db

def get_judicial_funnel(district_id=None):
    """Calculates attrition rates at each stage of the justice funnel."""
    conn = get_db()
    c = conn.cursor()
    
    query = "SELECT status, chargesheet_date, trial_start_date, disposal_date, judicial_outcome FROM firs"
    params = []
    if district_id:
        query += " WHERE district_id = ?"
        params.append(district_id)
        
    rows = c.execute(query, params).fetchall()
    conn.close()
    
    funnel = {
        "registered": len(rows),
        "chargesheeted": sum(1 for r in rows if r["chargesheet_date"]),
        "trial_started": sum(1 for r in rows if r["trial_start_date"]),
        "disposed": sum(1 for r in rows if r["disposal_date"]),
        "convicted": sum(1 for r in rows if r["judicial_outcome"] == "Convicted"),
        "acquitted": sum(1 for r in rows if r["judicial_outcome"] == "Acquitted")
    }
    
    return funnel
