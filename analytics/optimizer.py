import numpy as np
from scipy.optimize import linprog
from analytics.predictive import get_risk_scores
from db import get_db

def optimize_patrols(total_units: int = 50):
    """
    Uses Linear Programming to allocate patrol units across districts based on risk scores.
    Objective: Maximize risk coverage.
    Constraints: 
      - Sum of units <= total_units
      - At least 1 unit per district
      - Max units per district proportional to its size/population
    """
    conn = get_db()
    districts = conn.execute("SELECT district_id, name, population_density FROM districts").fetchall()
    conn.close()

    if not districts:
        return []

    # Get risk scores
    risk_data = {r["district_id"]: r["score"] for r in get_risk_scores()}
    
    n = len(districts)
    # Objective coefficients (we want to maximize risk coverage, linprog minimizes, so negative)
    c = [-risk_data.get(d["district_id"], 0) for d in districts]
    
    # Equality constraint: sum(x) = total_units
    A_eq = [[1] * n]
    b_eq = [total_units]
    
    # Bounds: At least 1 unit per district, max based on population density proportion
    total_density = sum(d["population_density"] for d in districts)
    bounds = []
    for d in districts:
        max_units = max(2, int((d["population_density"] / total_density) * total_units * 2))
        bounds.append((1, max_units))

    # Solve LP
    res = linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method='highs')
    
    allocations = []
    if res.success:
        allocs = np.round(res.x).astype(int)
        
        # Adjust rounding errors to match total_units
        diff = total_units - np.sum(allocs)
        if diff > 0:
            allocs[np.argmax(c)] += diff  # Add to highest risk
        elif diff < 0:
            allocs[np.argmin(c)] += diff  # Remove from lowest risk (if negative, it subtracts)
            
        for i, d in enumerate(districts):
            allocations.append({
                "district_id": d["district_id"],
                "district_name": d["name"],
                "risk_score": risk_data.get(d["district_id"], 0),
                "allocated_units": int(allocs[i])
            })
    else:
        # Fallback proportional allocation
        total_risk = sum(risk_data.values())
        for d in districts:
            alloc = max(1, int((risk_data.get(d["district_id"], 0) / total_risk) * total_units))
            allocations.append({
                "district_id": d["district_id"],
                "district_name": d["name"],
                "risk_score": risk_data.get(d["district_id"], 0),
                "allocated_units": alloc
            })

    return sorted(allocations, key=lambda x: -x["allocated_units"])
