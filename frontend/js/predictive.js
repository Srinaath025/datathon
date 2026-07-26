/* ═══════════════════════════════════════════════════════════
   predictive.js — Predictive Analytics Tab
   Forecast chart, anomaly list, risk score cards, MO clusters
   ═══════════════════════════════════════════════════════════ */

let forecastChart = null;

async function loadPredictive() {
  try {
    const [anomalyRes, riskScores, moClusters] = await Promise.all([
      api('/anomalies?limit=20'),
      api('/risk-score'),
      api('/mo-clusters'),
    ]);
    const anomalies = Array.isArray(anomalyRes) ? anomalyRes : (anomalyRes.anomalies || []);
    const anomalyDiag = Array.isArray(anomalyRes) ? null : anomalyRes.model_diagnostics;
    renderAnomalies(anomalies, anomalyDiag);
    renderRiskScores(riskScores);
    renderMoClusters(moClusters);
    loadForecast();  // Load default forecast
  } catch(e) {
    console.error('Predictive load error:', e);
  }
}

// ─────────────────────────────────────────────────────────────
// FORECAST CHART
// ─────────────────────────────────────────────────────────────
async function loadForecast() {
  const districtId = document.getElementById('forecast-district').value;
  const crimeType  = document.getElementById('forecast-crime-type').value;
  let url = '/forecast?';
  if (districtId) url += 'district_id=' + districtId + '&';
  if (crimeType)  url += 'crime_type=' + encodeURIComponent(crimeType) + '&';

  try {
    const data = await api(url);
    renderForecastChart(data);
  } catch(e) {
    console.error('Forecast error:', e);
  }
}

function renderForecastChart(data) {
  const ctx = document.getElementById('forecastChart');
  if (forecastChart) forecastChart.destroy();

  // Render forecast diagnostics
  if (data.model_diagnostics) {
    const diag = data.model_diagnostics;
    const diagBody = document.getElementById('forecast-diagnostics-body');
    if (diagBody) {
      diagBody.innerHTML =
        '<div><strong>Method:</strong> ' + (diag.validation_method || '6-Fold Rolling Walk-Forward') + '</div>' +
        '<div><strong>Evaluation Scope:</strong> ' + (diag.evaluation_folds || 6) + ' rolling walk-forward folds (last ' + (diag.holdout_period_months || 6) + ' months)</div>' +
        '<div><strong>MAPE Error:</strong> <span style="color:#f59e0b;font-weight:700;">±' + (diag.mape_pct !== null ? diag.mape_pct + '%' : 'N/A') + '</span> | <strong>RMSE:</strong> ' + (diag.rmse !== null ? diag.rmse : 'N/A') + '</div>' +
        '<div style="margin-top:4px;font-style:italic;color:var(--text-muted);">' + (diag.accuracy_caveat || '') + '</div>';
    }
  }



  const allLabels = [...(data.historical_labels || []), ...(data.forecast_labels || [])];
  const hLen = (data.historical || []).length;
  const fLen = (data.forecast || []).length;

  // Build combined datasets
  const historicalFull = [...(data.historical || []), ...Array(fLen).fill(null)];
  const forecastFull   = [...Array(hLen - 1).fill(null), (data.historical || [])[hLen - 1] || null, ...(data.forecast || [])];

  forecastChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: allLabels,
      datasets: [
        {
          label: 'Historical',
          data: historicalFull,
          borderColor: '#3b82f6',
          backgroundColor: 'rgba(59,130,246,0.08)',
          borderWidth: 2.5,
          fill: true,
          tension: 0.35,
          pointBackgroundColor: '#3b82f6',
          pointRadius: 3,
          spanGaps: false,
        },
        {
          label: '6-Month Forecast',
          data: forecastFull,
          borderColor: '#f59e0b',
          backgroundColor: 'rgba(245,158,11,0.06)',
          borderWidth: 2,
          borderDash: [6, 4],
          fill: true,
          tension: 0.35,
          pointBackgroundColor: '#f59e0b',
          pointRadius: 4,
          spanGaps: true,
        }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top' },
        tooltip: {
          callbacks: {
            label: ctx => ' ' + ctx.dataset.label + ': ' + ctx.parsed.y + ' crimes'
          }
        }
      },
      scales: {
        x: { grid: { display: false }, ticks: { maxTicksLimit: 14, maxRotation: 30 } },
        y: { grid: { color: 'rgba(56,120,255,0.07)' }, beginAtZero: true,
             title: { display: true, text: 'Crime Count', color: '#8ba3cc' } }
      },
      animation: { duration: 800 }
    }
  });
}

// ─────────────────────────────────────────────────────────────
// ANOMALIES
// ─────────────────────────────────────────────────────────────
function renderAnomalies(anomalies, diagnostics) {
  const tag = document.getElementById('anomaly-count-tag');
  tag.textContent = anomalies.length + ' flagged';

  if (diagnostics) {
    const diagBody = document.getElementById('anomaly-diagnostics-body');
    if (diagBody) {
      const sens = diagnostics.contamination_sensitivity || {};
      const sensText = Object.keys(sens).map(k => k + ': ' + sens[k].flagged_count + ' flagged').join(' | ');
      diagBody.innerHTML =
        '<div><strong>Algorithm:</strong> ' + (diagnostics.algorithm || 'Isolation Forest') + '</div>' +
        '<div><strong>Ground Truth:</strong> ' + (diagnostics.ground_truth_status || 'Unsupervised') + '</div>' +
        '<div><strong>Sensitivity Check:</strong> <span style="color:var(--cyan);font-weight:600;">' + (sensText || 'N/A') + '</span></div>';
    }
  }

  const container = document.getElementById('anomaly-list');
  container.innerHTML = anomalies.map(a => {
    const reasons = a.reasons.join('; ');
    const scoreBar = Math.min(100, a.anomaly_score * 100).toFixed(0);
    return '<div style="padding:10px;background:var(--bg-surface);border:1px solid rgba(239,68,68,0.2);border-radius:8px;margin-bottom:6px">' +
      '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">' +
        '<div>' +
          '<span class="mono" style="color:#ef4444">#' + a.fir_id + '</span>' +
          '<span style="font-size:12px;font-weight:600;margin-left:8px">' + a.crime_type + ' — ' + a.sub_type + '</span>' +
        '</div>' +
        '<span class="tag tag-red">Score: ' + a.anomaly_score + '</span>' +
      '</div>' +
      '<div style="font-size:11px;color:var(--text-muted);margin-bottom:6px">' +
        '📍 ' + a.district_name + ' · 🗓️ ' + (a.date_time ? a.date_time.slice(0,10) : '') + ' · ⚔️ ' + a.weapon +
      '</div>' +
      '<div class="gauge-bar-wrap" style="margin-bottom:5px">' +
        '<div class="gauge-bar" style="width:' + scoreBar + '%;background:#ef4444"></div>' +
      '</div>' +
      '<div style="font-size:10px;color:#fca5a5;font-style:italic">⚡ ' + reasons + '</div>' +
    '</div>';
  }).join('');
}


// ─────────────────────────────────────────────────────────────
// RISK SCORES
// ─────────────────────────────────────────────────────────────
function renderRiskScores(scores) {
  const container = document.getElementById('risk-scores-grid');
  container.innerHTML = scores.map(s => {
    const color = riskColor(s.score);
    const cls = riskClass(s.score);
    const stars = starsHtml(s.stars);

    // Feature contributions HTML
    const breakdownHtml = (s.feature_breakdown || []).map(f =>
      '<div style="font-size:10px; display:flex; justify-content:space-between; margin-bottom:2px; color:var(--text-secondary);">' +
        '<span>' + f.feature + ' (' + (f.weight * 100) + '%)</span>' +
        '<span><strong>+' + f.contribution + ' pts</strong> (' + f.percent_impact + '%)</span>' +
      '</div>' +
      '<div style="height:3px; background:rgba(255,255,255,0.08); border-radius:2px; margin-bottom:6px; overflow:hidden;">' +
        '<div style="height:100%; width:' + Math.min(100, f.percent_impact) + '%; background:' + color + ';"></div>' +
      '</div>'
    ).join('');

    // Overrides badges
    const overridesCount = (s.overrides || []).length;
    const latestOverride = overridesCount > 0 ? s.overrides[0] : null;
    const overrideBadge = latestOverride ?
      '<div style="margin-top:8px; padding:6px 8px; background:rgba(245,158,11,0.12); border-left:3px solid #f59e0b; border-radius:4px; font-size:10px; color:#fef08a;">' +
        '⚠️ <strong>Challenged by ' + latestOverride.username + '</strong>: "' + latestOverride.reason + '"' +
        (latestOverride.revised_score !== null ? ' (Proposed: ' + latestOverride.revised_score + ')' : '') +
      '</div>' : '';

    const adjustedBadge = s.officer_adjusted_score !== null ?
      '<div style="font-size:11px; font-weight:700; color:#f59e0b; background:rgba(245,158,11,0.15); padding:3px 8px; border-radius:4px; border:1px solid rgba(245,158,11,0.3); margin-left:8px;">' +
        '👮 Officer-Adjusted: ' + s.officer_adjusted_score +
      '</div>' : '';

    return '<div class="risk-card" style="display:flex; flex-direction:column; justify-space-between;">' +
      '<div style="display:flex;justify-content:space-between;align-items:flex-start">' +
        '<div class="risk-district">' + s.name + '</div>' +
        '<div style="font-size:13px;color:#f59e0b">' + stars + '</div>' +
      '</div>' +
      '<div class="risk-score-row" style="display:flex; align-items:baseline; gap:6px;">' +
        '<div class="risk-number ' + cls + '">' + s.score + '</div>' +
        '<div style="font-size:10px; color:var(--text-muted); text-transform:uppercase; font-weight:600;">(Model Score)</div>' +
        adjustedBadge +
      '</div>' +
      '<div style="margin-top:4px;font-size:11px;color:var(--text-secondary);display:flex;gap:12px;margin-bottom:10px">' +
        '<span>Total: ' + (s.total_crimes || 0) + '</span>' +
        '<span>Violent: ' + (s.violent_crimes || 0) + '</span>' +
      '</div>' +
      '<div class="risk-bar-wrap" style="margin-bottom:10px;">' +
        '<div class="risk-bar" style="width:' + s.score + '%;background:' + color + '"></div>' +
      '</div>' +
      '<div style="margin-bottom:10px; background:var(--bg-surface); padding:8px; border-radius:6px; border:1px solid var(--border);">' +
        '<div style="font-size:10px; font-weight:700; color:var(--text-muted); margin-bottom:6px; text-transform:uppercase; letter-spacing:0.05em;">Feature Weight Contribution</div>' +
        breakdownHtml +
      '</div>' +
      '<div class="risk-justification" style="margin-bottom:8px;">Insight: ' + s.justification + '</div>' +
      overrideBadge +

      '<button class="btn btn-ghost btn-sm" style="margin-top:10px; width:100%; font-size:11px; color:#fca5a5; border:1px dashed rgba(239,68,68,0.4);" onclick="submitRiskScoreOverride(' + s.district_id + ', \'' + s.name.replace(/'/g, "\\'") + '\')">' +
        '✏️ Challenge / Override Score' +
      '</button>' +
    '</div>';
  }).join('');
}

async function submitRiskScoreOverride(districtId, districtName) {
  const reason = prompt(`Submit Officer Challenge / Operational Context for ${districtName}:\nState your operational reason for disputing or contextualizing this score:`);
  if (!reason || !reason.trim()) return;

  const revised = prompt(`(Optional) Enter your proposed revised risk score (0-100), or leave blank:`);
  let revisedScore = null;
  if (revised && !isNaN(parseFloat(revised))) {
    revisedScore = parseFloat(revised);
  }

  try {
    const token = localStorage.getItem('token');
    const res = await fetch(`/risk-score/${districtId}/override`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        disagree: true,
        revised_score: revisedScore,
        reason: reason.trim()
      })
    });
    if (res.ok) {
      alert(`Officer override for ${districtName} logged successfully in audit trail.`);
      if (typeof loadPredictiveModule === 'function') loadPredictiveModule();
    } else {
      const err = await res.json();
      alert(`Error submitting override: ${err.detail || 'Authorization failed'}`);
    }
  } catch (e) {
    alert(`Failed to connect to server.`);
  }
}


// ─────────────────────────────────────────────────────────────
// MO CLUSTERS
// ─────────────────────────────────────────────────────────────
function renderMoClusters(clusters) {
  const container = document.getElementById('mo-cluster-list');
  const colors = ['#3b82f6','#8b5cf6','#f59e0b','#ef4444','#10b981','#06b6d4'];
  const maxSize = Math.max(...clusters.map(c => c.size), 1);

  container.innerHTML = clusters.map((c, i) => {
    const color = colors[i % colors.length];
    const pct = Math.round((c.size / maxSize) * 100);
    return '<div style="padding:10px;background:var(--bg-surface);border:1px solid var(--border);border-radius:8px;margin-bottom:6px">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">' +
        '<div style="font-size:12px;font-weight:700">' + c.name + '</div>' +
        '<span class="tag tag-blue">' + c.size + ' cases</span>' +
      '</div>' +
      '<div class="gauge-bar-wrap" style="margin-bottom:6px">' +
        '<div class="gauge-bar" style="width:' + pct + '%;background:' + color + '"></div>' +
      '</div>' +
      '<div style="font-size:11px;color:var(--text-muted)">Dominant: <strong style="color:' + color + '">' + c.dominant_crime_type + '</strong></div>' +
      '<div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:6px">' +
        c.sample_firs.slice(0,3).map(f =>
          '<span class="tag tag-grey" title="' + f.crime_type + '">#' + f.fir_id + '</span>'
        ).join('') +
      '</div>' +
    '</div>';
  }).join('');
}
