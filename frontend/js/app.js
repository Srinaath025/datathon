/* ═══════════════════════════════════════════════════════════
   app.js — Core routing, shared utilities, global search,
             overview tab data loading
   ═══════════════════════════════════════════════════════════ */

const API = '';  // Same-origin FastAPI

// ─────────────────────────────────────────────────────────────
// CHART.JS DEFAULTS
// ─────────────────────────────────────────────────────────────
Chart.defaults.color = '#8ba3cc';
Chart.defaults.borderColor = 'rgba(56,120,255,0.12)';
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.font.size = 11;
Chart.defaults.plugins.legend.labels.boxWidth = 10;
Chart.defaults.plugins.legend.labels.padding = 14;
Chart.defaults.plugins.tooltip.backgroundColor = '#121e36';
Chart.defaults.plugins.tooltip.borderColor = 'rgba(56,120,255,0.3)';
Chart.defaults.plugins.tooltip.borderWidth = 1;
Chart.defaults.plugins.tooltip.titleColor = '#f0f6ff';
Chart.defaults.plugins.tooltip.bodyColor = '#8ba3cc';
Chart.defaults.plugins.tooltip.padding = 10;

// ─────────────────────────────────────────────────────────────
// AUTH HELPERS
// ─────────────────────────────────────────────────────────────
function getToken()  { return localStorage.getItem('ksp_token') || ''; }
function getUser()   { try { return JSON.parse(localStorage.getItem('ksp_user') || '{}'); } catch { return {}; } }
function logout() {
  localStorage.removeItem('ksp_token');
  localStorage.removeItem('ksp_user');
  window.location.href = '/login';
}

async function exportData(format) {
  try {
    const r = await fetch(API + '/export/' + format, {
      headers: { 'Authorization': 'Bearer ' + getToken() }
    });
    if (!r.ok) throw new Error('Export failed: ' + r.status + ' - Check if role permitted');
    const blob = await r.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'district_summary.' + format;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } catch (e) {
    alert(e.message);
  }
}


// ─────────────────────────────────────────────────────────────
// SHARED FETCH UTILITY  (always sends Bearer token)
// ─────────────────────────────────────────────────────────────
async function api(path, options = {}) {
  const token = getToken();
  const headers = { ...options.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const r = await fetch(API + path, { ...options, headers });
  if (r.status === 401) {
    logout();
    throw new Error('Unauthenticated');
  }
  if (!r.ok) throw new Error(`API error: ${r.status} ${path}`);
  return r.json();
}

// ─────────────────────────────────────────────────────────────
// SHARED COLOR HELPERS
// ─────────────────────────────────────────────────────────────
const PALETTE = [
  '#3b82f6','#8b5cf6','#06b6d4','#f59e0b','#ef4444',
  '#10b981','#f97316','#ec4899','#6366f1','#14b8a6'
];
function riskColor(score) {
  if (score >= 80) return '#ef4444';
  if (score >= 60) return '#f97316';
  if (score >= 35) return '#f59e0b';
  return '#10b981';
}
function riskClass(score) {
  if (score >= 80) return 'critical';
  if (score >= 60) return 'high';
  if (score >= 35) return 'medium';
  return 'low';
}
function starsHtml(n) {
  return '★'.repeat(n) + '☆'.repeat(5 - n);
}

// ─────────────────────────────────────────────────────────────
// TAB ROUTING
// ─────────────────────────────────────────────────────────────
const tabLoaded = {};

document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', () => {
    const tab = item.dataset.tab;
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    item.classList.add('active');
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.getElementById(`tab-${tab}`).classList.add('active');

    if (!tabLoaded[tab]) {
      tabLoaded[tab] = true;
      switch(tab) {
        case 'overview':   loadOverview(); break;
        case 'geo':        loadGeo(); break;
        case 'network':    loadNetwork(); break;
        case 'predictive': loadPredictive(); break;
        case 'socio':      loadSocio(); break;
        case 'advanced':   loadAdvanced(); break;
        case 'datamgr':    loadDataStats(); break;
        case 'search':     break;
        case 'timeline':   break;
      }
    }
  });
});

// ─────────────────────────────────────────────────────────────
// ROLE SELECTOR
// ─────────────────────────────────────────────────────────────
const ROLE_MESSAGES = {
  investigator: 'Welcome, Investigator — Case-level lookups and network analysis enabled.',
  sho:          'Welcome, Station House Officer — Local hotspot and repeat-offender view.',
  commander:    'Welcome, District Commander — Risk scores, resource allocation, district ranking.',
  analyst:      'Welcome, SCRB Analyst — Cross-district trends, anomaly flags, correlations.',
};


// ─────────────────────────────────────────────────────────────
// AUTH GUARD + USER DISPLAY
// ─────────────────────────────────────────────────────────────
(async function initAuth() {
  const token = getToken();
  if (!token) { window.location.href = '/login'; return; }

  // Verify token is still valid
  try {
    const res = await fetch('/auth/me', { headers: { Authorization: `Bearer ${token}` } });
    if (!res.ok) { logout(); return; }
    const user = await res.json();
    localStorage.setItem('ksp_user', JSON.stringify(user));
    renderUserTopbar(user);
    initWebSockets();
  } catch(e) {
    logout();
  }
})();

let ws;
function initWebSockets() {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.host; 
    ws = new WebSocket(`${wsProtocol}//${wsHost}/ws/alerts`);
    ws.onmessage = (event) => {
        const toast = document.createElement('div');
        toast.style = "background: rgba(239, 68, 68, 0.9); color: white; padding: 12px 20px; border-radius: 8px; font-size: 13px; font-weight: bold; box-shadow: 0 4px 12px rgba(0,0,0,0.5); display: flex; align-items: center; gap: 8px;";
        toast.innerHTML = `<span>🚨</span> <span>${event.data}</span>`;
        const container = document.getElementById('toast-container');
        if (container) {
            container.appendChild(toast);
            setTimeout(() => toast.remove(), 5000);
        }
    };
}

function renderUserTopbar(user) {
  const el = document.getElementById('topbar-user-info');
  if (!el) return;
  el.innerHTML = `
    <div style="display:flex;align-items:center;gap:8px">
      <div style="width:28px;height:28px;border-radius:50%;background:${user.avatar_color || '#3b82f6'};
                  display:flex;align-items:center;justify-content:center;font-weight:700;font-size:12px">
        ${(user.display_name||'?').charAt(0)}
      </div>
      <div style="line-height:1.3">
        <div style="font-size:12px;font-weight:600">${user.display_name || user.username}</div>
        <div style="font-size:10px;color:var(--text-muted)">${user.badge || ''}</div>
      </div>
      <button onclick="logout()" style="margin-left:8px;background:rgba(239,68,68,0.12);border:1px solid rgba(239,68,68,0.3);
              color:#fca5a5;border-radius:6px;padding:4px 10px;font-size:11px;cursor:pointer;font-family:inherit"
              title="Logout">Logout</button>
    </div>
  `;

  // Display static role instead of select
  const roleDisplay = document.getElementById('role-display');
  const roleNames = { investigator: 'Investigator', sho: 'Station House Officer', commander: 'District Commander', analyst: 'SCRB Analyst' };
  if (roleDisplay && user.role) roleDisplay.textContent = roleNames[user.role] || user.role;
  const sub = document.getElementById('overview-role-subtitle');
  if (sub) sub.textContent = ROLE_MESSAGES[user.role] || '';


  // Apply Role-Based Nav Filtering
  document.querySelectorAll('[data-role-req]').forEach(el => {
    const roles = el.getAttribute('data-role-req').split(',');
    if (!roles.includes(user.role)) {
      el.style.display = 'none';
      if (el.classList.contains('active')) {
        document.querySelector('.nav-item[data-role-req*="'+user.role+'"]').click();
      }
    } else {
      el.style.display = '';
    }
  });
}

// ─────────────────────────────────────────────────────────────
// THEME TOGGLE
// ─────────────────────────────────────────────────────────────
function toggleTheme() {
  document.body.classList.toggle('light-theme');
  const isLight = document.body.classList.contains('light-theme');
  localStorage.setItem('ksp_theme', isLight ? 'light' : 'dark');
  const btn = document.getElementById('theme-btn');
  if (btn) btn.textContent = isLight ? '☀️' : '🌙';
}

// Init theme on load
if (localStorage.getItem('ksp_theme') === 'light') {
  document.body.classList.add('light-theme');
  const btn = document.getElementById('theme-btn');
  if (btn) btn.textContent = '☀️';
}

// ─────────────────────────────────────────────────────────────
// GLOBAL SEARCH
// ─────────────────────────────────────────────────────────────
let searchTimeout;
const searchInput = document.getElementById('global-search');
const dropdown = document.getElementById('search-results-dropdown');

searchInput.addEventListener('input', () => {
  clearTimeout(searchTimeout);
  const q = searchInput.value.trim();
  if (q.length < 3) { dropdown.style.display = 'none'; return; }
  searchTimeout = setTimeout(async () => {
    try {
      const results = await api(`/search?q=${encodeURIComponent(q)}&limit=6`);
      renderSearchDropdown(results);
    } catch(e) {}
  }, 300);
});

document.addEventListener('click', e => {
  if (!e.target.closest('.topbar-center')) dropdown.style.display = 'none';
});

function renderSearchDropdown(results) {
  if (!results.length) { dropdown.style.display = 'none'; return; }
  dropdown.innerHTML = results.map(r => {
    let entitiesHtml = '';
    if (r.extracted_entities) {
      const suspects = r.extracted_entities.suspects.join(', ');
      const vehicles = r.extracted_entities.vehicles.join(', ');
      if (suspects) entitiesHtml += `<div><span style="color:#ef4444">Suspects:</span> ${suspects}</div>`;
      if (vehicles) entitiesHtml += `<div><span style="color:#3b82f6">Vehicles:</span> ${vehicles}</div>`;
    }
    return `
    <div class="search-result-item" onclick="openFirTimeline(${r.fir_id})">
      <div class="fir-id">FIR #${r.fir_id} · ${(r.similarity_score * 100).toFixed(0)}% match</div>
      <div class="crime-label">${r.crime_type} — ${r.sub_type}</div>
      <div class="meta">${r.district_name} · ${r.date_time ? r.date_time.slice(0,10) : ''} · ${r.status}</div>
      ${entitiesHtml ? `<div style="font-size:10px; margin-top:4px;">${entitiesHtml}</div>` : ''}
    </div>
  `}).join('');
  dropdown.style.display = 'block';
}

function openFirTimeline(firId) {
  dropdown.style.display = 'none';
  searchInput.value = '';
  // Navigate to timeline tab
  document.querySelector('[data-tab="timeline"]').click();
  document.getElementById('timeline-fir-id').value = firId;
  loadTimeline();
}

// ─────────────────────────────────────────────────────────────
// OVERVIEW TAB
// ─────────────────────────────────────────────────────────────
let overviewCharts = {};

async function loadOverview() {
  try {
    const [stats, districtSummary, hourData, weekdayData, spikeAlerts, crimeTypeDist] = await Promise.all([
      api('/stats'),
      api('/district-summary'),
      api('/crime-by-hour'),
      api('/crime-by-weekday'),
      api('/spike-alerts'),
      api('/crime-type-distribution'),
    ]);

    // Stats cards
    document.getElementById('stat-firs').textContent = stats.total_firs.toLocaleString();
    document.getElementById('stat-pending').textContent = stats.pending_cases.toLocaleString();
    document.getElementById('stat-districts').textContent = stats.total_districts;
    // Offender count loaded separately
    api('/offenders?min_firs=3&limit=500').then(data => {
      document.getElementById('stat-offenders').textContent = data.length;
    });

    // Spike alerts
    renderSpikeAlerts(spikeAlerts);

    // Crime type donut
    renderCrimeTypeChart(crimeTypeDist);

    // Hour chart
    renderHourChart(hourData);

    // Weekday bar
    renderWeekdayChart(weekdayData);

    // Top districts
    renderTopDistricts(districtSummary);

    // Populate district dropdowns across all tabs
    populateDistrictDropdowns(districtSummary);

  } catch(e) {
    console.error(e);
  }
}

// ─────────────────────────────────────────────────────────────
// ADVANCED TAB
// ─────────────────────────────────────────────────────────────
async function loadAdvanced() {
  try {
    const [funnel, audit, traffic, sentiment] = await Promise.all([
      api('/judicial/funnel'),
      api('/audit/bias'),
      api('/trafficking/clusters'),
      api('/sentiment/trust-score')
    ]);

    // Funnel
    document.getElementById('judicial-funnel-container').innerHTML = `
      <div style="display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid var(--border)"><span>Registered FIRs:</span> <b>${funnel.registered}</b></div>
      <div style="display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid var(--border)"><span>Charge-Sheeted:</span> <b>${funnel.chargesheeted} (${Math.round((funnel.chargesheeted/funnel.registered)*100)}%)</b></div>
      <div style="display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid var(--border)"><span>Trial Started:</span> <b>${funnel.trial_started}</b></div>
      <div style="display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid var(--border)"><span>Convicted:</span> <b style="color:#10b981">${funnel.convicted}</b></div>
      <div style="display:flex; justify-content:space-between; padding:8px 0"><span>Acquitted:</span> <b style="color:#ef4444">${funnel.acquitted}</b></div>
    `;

    // Audit
    document.getElementById('bias-audit-container').innerHTML = `
      <div style="margin-bottom:12px; font-size:14px;"><b>Status:</b> <span class="tag tag-green">${audit.status}</span></div>
      <div style="margin-bottom:12px"><b>Literacy vs Risk Correlation:</b> ${audit.correlations.literacy_rate_vs_risk_score}</div>
      <div style="margin-bottom:12px"><b>Urban vs Risk Correlation:</b> ${audit.correlations.urban_pct_vs_risk_score}</div>
      <div style="color:var(--text-muted); line-height: 1.5">${audit.interpretation}</div>
    `;

    // Trafficking / Missing Persons Spatial Density Leads
    const methodNote = (traffic.length && traffic[0].methodology_note)
      ? `<div style="font-size:11px; color:var(--text-sec); background:rgba(59,130,246,0.1); border-left:3px solid #3b82f6; padding:8px 10px; border-radius:4px; margin-bottom:12px;">
           ℹ️ <b>Investigative Lead Note:</b> ${traffic[0].methodology_note}
         </div>`
      : '';

    document.getElementById('trafficking-container').innerHTML = methodNote + (traffic.length ? traffic.map(t => `
      <div style="padding:12px; border:1px solid var(--border); border-radius:6px; margin-bottom:12px; background:var(--bg-card)">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px">
          <div style="font-weight:bold; font-size:13px; color:var(--text-primary)">🔍 ${t.corridor_name}</div>
          <span class="tag ${t.density_level.includes('High') ? 'tag-blue' : 'tag-grey'}">${t.density_level}</span>
        </div>
        <div style="font-size:12px; color:var(--text-sec)">Missing Person Reports in Density Cluster: <b>${t.missing_count}</b></div>
      </div>
    `).join('') : '<div>No spatial density clusters detected.</div>');


    // Sentiment
    document.getElementById('sentiment-container').innerHTML = sentiment.slice(0, 10).map(s => `
      <div style="display:flex; justify-content:space-between; align-items:center; padding:10px 0; border-bottom:1px solid var(--border)">
        <span style="font-size:14px">${s.station_name}</span>
        <span class="tag ${s.trust_index >= 60 ? 'tag-green' : 'tag-red'}">${s.trust_index} / 100 (${s.status})</span>
      </div>
    `).join('');

    // Load default patrol allocation
    runPatrolOptimizer();

  } catch(e) {
    console.error(e);
  }
}

async function runPatrolOptimizer() {
  const units = document.getElementById('patrol-units').value;
  try {
    const alloc = await api('/optimize-patrols?total_units=' + units);
    document.getElementById('patrol-container').innerHTML = alloc.map(a => `
      <div style="display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid var(--border)">
        <span style="font-size:14px">${a.district_name}</span>
        <b style="color:var(--text); background:rgba(56,120,255,0.1); padding:4px 8px; border-radius:4px;">${a.allocated_units} units</b>
      </div>
    `).join('');
  } catch(e) {
    console.error(e);
  }
}

function renderSpikeAlerts(alerts) {
  const container = document.getElementById('spike-alerts-container');
  if (!alerts.length) { container.innerHTML = ''; return; }
  const top = alerts.slice(0, 3);
  container.innerHTML = top.map(a => `
    <div class="alert-banner ${a.spike_factor > 2 ? 'danger' : 'warning'}">
      <span>🚨</span>
      <span><strong>District Alert:</strong> District #${a.district_id} showing ${a.spike_factor}× spike above baseline (${a.recent_count} crimes vs avg ${a.baseline_avg})</span>
    </div>
  `).join('');
}

function renderCrimeTypeChart(data) {
  const ctx = document.getElementById('crimeTypeChart');
  if (overviewCharts.crimeType) overviewCharts.crimeType.destroy();
  overviewCharts.crimeType = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: data.map(d => d.crime_type),
      datasets: [{
        data: data.map(d => d.count),
        backgroundColor: PALETTE,
        borderWidth: 0,
        hoverOffset: 8,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'right' },
        tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${ctx.parsed.toLocaleString()}` } }
      },
      cutout: '65%',
      animation: { animateRotate: true, duration: 800 }
    }
  });
}

function renderHourChart(data) {
  const ctx = document.getElementById('crimeHourChart');
  if (overviewCharts.hour) overviewCharts.hour.destroy();
  const gradient = ctx.getContext('2d').createLinearGradient(0, 0, 0, 260);
  gradient.addColorStop(0, 'rgba(59,130,246,0.5)');
  gradient.addColorStop(1, 'rgba(59,130,246,0.02)');

  overviewCharts.hour = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.map(d => `${d.hour}:00`),
      datasets: [{
        data: data.map(d => d.count),
        backgroundColor: data.map(d => {
          if (d.hour < 6 || d.hour >= 20) return 'rgba(239,68,68,0.7)';
          return 'rgba(59,130,246,0.6)';
        }),
        borderRadius: 3,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { maxTicksLimit: 8 } },
        y: { grid: { color: 'rgba(56,120,255,0.07)' }, beginAtZero: true }
      },
      animation: { duration: 700 }
    }
  });
}

function renderWeekdayChart(data) {
  const ctx = document.getElementById('crimeWeekdayChart');
  if (overviewCharts.weekday) overviewCharts.weekday.destroy();
  overviewCharts.weekday = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.map(d => d.day),
      datasets: [{
        data: data.map(d => d.count),
        backgroundColor: data.map((d, i) => i >= 5 ? 'rgba(239,68,68,0.65)' : 'rgba(59,130,246,0.6)'),
        borderRadius: 4,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false } },
        y: { grid: { color: 'rgba(56,120,255,0.07)' }, beginAtZero: true }
      },
      animation: { duration: 700 }
    }
  });
}

function renderTopDistricts(data) {
  const sorted = [...data].sort((a, b) => b.total_crimes - a.total_crimes).slice(0, 10);
  const max = sorted[0]?.total_crimes || 1;
  const container = document.getElementById('top-districts-list');
  container.innerHTML = sorted.map((d, i) => `
    <div style="padding:8px 4px;border-bottom:1px solid rgba(56,120,255,0.07)">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px">
        <div style="font-size:12px;font-weight:600">${i+1}. ${d.name}</div>
        <div style="font-size:12px;font-family:var(--font-mono);color:var(--blue-primary)">${d.total_crimes}</div>
      </div>
      <div class="gauge-bar-wrap">
        <div class="gauge-bar" style="width:${(d.total_crimes/max)*100}%;background:${i<3?'#ef4444':i<6?'#f59e0b':'#3b82f6'}"></div>
      </div>
    </div>
  `).join('');
}

function populateDistrictDropdowns(districtData) {
  const selects = ['geo-district-filter', 'station-district-select', 'forecast-district'];
  selects.forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    const existing = el.innerHTML;
    const options = districtData.map(d =>
      `<option value="${d.district_id}">${d.name}</option>`
    ).join('');
    el.innerHTML = el.options[0].outerHTML + options;
  });
}

// ─────────────────────────────────────────────────────────────
// TIMELINE TAB
// ─────────────────────────────────────────────────────────────
async function loadTimeline() {
  const firId = parseInt(document.getElementById('timeline-fir-id').value);
  if (!firId) return;

  const container = document.getElementById('timeline-content');
  container.innerHTML = '<div class="loader-wrap"><div class="spinner"></div> Loading timeline...</div>';

  try {
    const data = await api(`/investigation-timeline/${firId}`);
    renderTimeline(data, container);
  } catch(e) {
    container.innerHTML = `<div class="card"><div style="color:var(--red);padding:20px">FIR #${firId} not found.</div></div>`;
  }
}

function renderTimeline(data, container) {
  const persons = data.persons || [];
  const suspects = persons.filter(p => p.fir_role === 'suspect');
  const victims  = persons.filter(p => p.fir_role === 'victim');
  const witnesses= persons.filter(p => p.fir_role === 'witness');

  container.innerHTML = `
    <div class="card">
      <div class="card-header">
        <div class="card-title">FIR #${data.fir_id} — ${data.crime_type}: ${data.sub_type}</div>
        <span class="tag tag-blue">${data.status}</span>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-bottom:20px">
        <div><div style="font-size:10px;color:var(--text-muted);margin-bottom:4px">DISTRICT / STATION</div>
          <div style="font-size:13px;font-weight:600">${data.district} · ${data.station}</div></div>
        <div><div style="font-size:10px;color:var(--text-muted);margin-bottom:4px">DATE & TIME</div>
          <div style="font-size:13px;font-weight:600">${data.date_time ? data.date_time.slice(0,16).replace('T',' ') : '—'}</div></div>
        <div><div style="font-size:10px;color:var(--text-muted);margin-bottom:4px">STATUS</div>
          <div style="font-size:13px;font-weight:600">${data.status}</div></div>
      </div>

      <div style="display:grid;grid-template-columns:2fr 1fr;gap:20px">
        <!-- Timeline -->
        <div>
          <div style="font-size:11px;font-weight:700;color:var(--text-muted);letter-spacing:0.08em;margin-bottom:12px">INVESTIGATION TIMELINE</div>
          <div class="timeline">
            ${(data.timeline || []).map((ev, i) => `
              <div class="timeline-item">
                <div class="timeline-spine">
                  <div class="timeline-dot ${ev.type}"></div>
                  ${i < data.timeline.length - 1 ? '<div class="timeline-line"></div>' : ''}
                </div>
                <div class="timeline-body">
                  <div class="timeline-time">${ev.time}</div>
                  <div class="timeline-event">${ev.event}</div>
                </div>
              </div>
            `).join('')}
          </div>
        </div>

        <!-- Persons & Vehicles -->
        <div style="display:flex;flex-direction:column;gap:14px">
          ${suspects.length ? `
            <div>
              <div style="font-size:10px;font-weight:700;color:var(--red);letter-spacing:0.08em;margin-bottom:8px">SUSPECTS</div>
              ${suspects.map(p => `
                <div style="padding:8px;background:rgba(239,68,68,0.07);border:1px solid rgba(239,68,68,0.2);border-radius:8px;margin-bottom:6px">
                  <div style="font-size:12px;font-weight:600">${p.name}</div>
                  <div style="font-size:11px;color:var(--text-muted)">Age ${p.age} · ${p.phone}</div>
                </div>
              `).join('')}
            </div>
          ` : ''}
          ${victims.length ? `
            <div>
              <div style="font-size:10px;font-weight:700;color:var(--amber);letter-spacing:0.08em;margin-bottom:8px">VICTIMS</div>
              ${victims.map(p => `
                <div style="padding:8px;background:rgba(245,158,11,0.07);border:1px solid rgba(245,158,11,0.2);border-radius:8px;margin-bottom:6px">
                  <div style="font-size:12px;font-weight:600">${p.name}</div>
                  <div style="font-size:11px;color:var(--text-muted)">Age ${p.age}</div>
                </div>
              `).join('')}
            </div>
          ` : ''}
          ${data.vehicles && data.vehicles.length ? `
            <div>
              <div style="font-size:10px;font-weight:700;color:var(--cyan);letter-spacing:0.08em;margin-bottom:8px">VEHICLES</div>
              ${data.vehicles.map(v => `
                <div style="padding:8px;background:rgba(6,182,212,0.07);border:1px solid rgba(6,182,212,0.2);border-radius:8px;margin-bottom:6px">
                  <div style="font-size:12px;font-weight:600;font-family:var(--font-mono)">${v.reg_number}</div>
                  <div style="font-size:11px;color:var(--text-muted)">${v.color} ${v.vehicle_type}</div>
                </div>
              `).join('')}
            </div>
          ` : ''}
        </div>
      </div>
    </div>
  `;
}

// ─────────────────────────────────────────────────────────────
// SEARCH TAB
// ─────────────────────────────────────────────────────────────
async function performSearch() {
  const q = document.getElementById('search-input').value.trim();
  if (q.length < 2) return;

  const container = document.getElementById('search-results-table');
  container.innerHTML = '<div class="loader-wrap"><div class="spinner"></div> Searching...</div>';

  try {
    const results = await api(`/search?q=${encodeURIComponent(q)}&limit=15`);
    if (!results.length) {
      container.innerHTML = '<div style="color:var(--text-muted);font-size:13px;padding:20px">No results found.</div>';
      return;
    }

    container.innerHTML = `
      <table class="data-table">
        <thead>
          <tr><th>FIR #</th><th>Crime Type</th><th>Sub-type</th><th>District</th><th>Date</th><th>Status</th><th>Match</th><th></th></tr>
        </thead>
        <tbody>
          ${results.map(r => `
            <tr>
              <td><span class="mono">#${r.fir_id}</span></td>
              <td>${r.crime_type}</td>
              <td><span class="tag tag-grey">${r.sub_type}</span></td>
              <td>${r.district_name}</td>
              <td>${r.date_time ? r.date_time.slice(0,10) : '—'}</td>
              <td><span class="tag ${statusTag(r.status)}">${r.status}</span></td>
              <td><span style="color:var(--green);font-weight:700">${(r.similarity_score*100).toFixed(0)}%</span></td>
              <td>
                <button class="btn btn-ghost btn-sm" onclick="loadSimilarCases(${r.fir_id})">Similar</button>
                <button class="btn btn-ghost btn-sm" onclick="openFirTimeline(${r.fir_id})">Timeline</button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;

    // Auto-show recommendations for top result
    renderInvestigationRec(results[0]);

  } catch(e) {
    container.innerHTML = `<div style="color:var(--red)">Search error: ${e.message}</div>`;
  }
}

async function loadSimilarCases(firId) {
  const card = document.getElementById('similar-cases-card');
  const list = document.getElementById('similar-cases-list');
  card.style.display = '';
  list.innerHTML = '<div class="loader-wrap"><div class="spinner"></div></div>';
  const data = await api(`/similar-cases/${firId}`);
  list.innerHTML = data.map(r => `
    <div style="padding:10px;background:var(--bg-surface);border:1px solid var(--border);border-radius:8px;cursor:pointer" onclick="openFirTimeline(${r.fir_id})">
      <div style="display:flex;justify-content:space-between">
        <span class="mono">#${r.fir_id}</span>
        <span style="color:var(--green);font-weight:700">${(r.similarity_score*100).toFixed(0)}%</span>
      </div>
      <div style="font-size:12px;font-weight:600;margin-top:3px">${r.crime_type} — ${r.sub_type}</div>
      <div style="font-size:11px;color:var(--text-muted)">${r.district_name} · ${r.date_time ? r.date_time.slice(0,10) : ''}</div>
    </div>
  `).join('');
}

function renderInvestigationRec(fir) {
  if (!fir) return;
  document.getElementById('inv-recommendations').innerHTML = `
    <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px">Based on FIR #${fir.fir_id} (${fir.crime_type})</div>
    ${[
      { icon:'🚗', text: 'Check CCTV footage and vehicle registration in the vicinity', tag: 'Priority' },
      { icon:'👤', text: 'Cross-reference suspects with repeat-offender database', tag: 'Standard' },
      { icon:'📱', text: 'Obtain call detail records (CDRs) for persons of interest', tag: 'Priority' },
      { icon:'🔗', text: 'Search for similar MO cases in neighbouring districts', tag: 'Recommended' },
      { icon:'📋', text: 'Review witness statements and compare with FIR description', tag: 'Standard' },
    ].map(r => `
      <div style="display:flex;align-items:flex-start;gap:10px;padding:8px 10px;background:rgba(59,130,246,0.05);border:1px solid var(--border);border-radius:8px">
        <span style="font-size:16px">${r.icon}</span>
        <div style="flex:1">
          <div style="font-size:12px">${r.text}</div>
        </div>
        <span class="tag ${r.tag==='Priority'?'tag-red':r.tag==='Recommended'?'tag-amber':'tag-grey'}">${r.tag}</span>
      </div>
    `).join('')}
  `;
}

function statusTag(status) {
  const map = {
    'Under Investigation': 'tag-amber',
    'Charge-Sheeted': 'tag-blue',
    'Closed-True': 'tag-green',
    'Closed-False': 'tag-grey',
    'Pending Trial': 'tag-purple',
  };
  return map[status] || 'tag-grey';
}

// ─────────────────────────────────────────────────────────────
// DATA MANAGER TAB
// ─────────────────────────────────────────────────────────────
async function loadDataStats() {
  try {
    const d = await api('/data/stats');
    document.getElementById('ds-total').textContent = (d.total_firs || 0).toLocaleString();
    document.getElementById('ds-synth').textContent = (d.synthetic_firs || 0).toLocaleString();
    document.getElementById('ds-real').textContent  = (d.real_firs || 0).toLocaleString();
  } catch(e) { console.error('Data stats error:', e); }
}

async function uploadFile(file) {
  const statusEl = document.getElementById('upload-status');
  statusEl.innerHTML = '<div class="loader-wrap" style="min-height:60px"><div class="spinner"></div> Uploading and importing...</div>';

  const form = new FormData();
  form.append('file', file);

  try {
    const token = getToken();
    const res = await fetch('/data/upload', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: form,
    });
    if (res.status === 401) { logout(); return; }
    const data = await res.json();

    if (!res.ok || !data.success) {
      statusEl.innerHTML = `
        <div class="alert-banner danger">
          <span>⚠</span>
          <span>Import failed: ${data.error || data.detail || 'Unknown error'}</span>
        </div>`;
      return;
    }

    statusEl.innerHTML = `
      <div class="alert-banner warning" style="background:rgba(16,185,129,0.1);border-color:rgba(16,185,129,0.3);color:#6ee7b7">
        <span>✓</span>
        <span>
          <strong>Import successful!</strong>
          Inserted <strong>${data.inserted}</strong> of ${data.total_rows} rows from <em>${data.filename}</em>.
          ${data.errors && data.errors.length ? `<br><small style="color:var(--amber)">${data.errors.length} row(s) skipped.</small>` : ''}
        </span>
      </div>`;

    // Refresh stats
    loadDataStats();
    // Invalidate analytics caches so next load picks up new data
    Object.keys(tabLoaded).forEach(k => { if (k !== 'datamgr') tabLoaded[k] = false; });

  } catch(e) {
    statusEl.innerHTML = `<div class="alert-banner danger"><span>⚠</span><span>Network error: ${e.message}</span></div>`;
  }
}

function handleFileSelect(input) {
  if (input.files && input.files[0]) uploadFile(input.files[0]);
}

function handleDrop(event) {
  event.preventDefault();
  document.getElementById('drop-zone').style.borderColor = '';
  const file = event.dataTransfer.files[0];
  if (file) uploadFile(file);
}

async function clearRealData() {
  if (!confirm('Remove all imported real FIRs? Synthetic data will remain.')) return;
  try {
    const token = getToken();
    const res = await fetch('/data/clear-real', { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } });
    const data = await res.json();
    document.getElementById('upload-status').innerHTML = `
      <div class="alert-banner warning">
        <span>✓</span><span>Removed <strong>${data.deleted}</strong> real FIRs. Dataset reverted to synthetic.</span>
      </div>`;
    loadDataStats();
    Object.keys(tabLoaded).forEach(k => { if (k !== 'datamgr') tabLoaded[k] = false; });
  } catch(e) {
    alert('Error: ' + e.message);
  }
}

// ─────────────────────────────────────────────────────────────
// CASE RETRIEVAL ASSISTANT WIDGET
// ─────────────────────────────────────────────────────────────

async function sendChatMessage() {
  const input = document.getElementById('chat-input');
  const text = input.value.trim();
  if (!text) return;
  
  const messages = document.getElementById('chat-messages');
  
  // User message
  messages.innerHTML += `<div style="background:var(--primary); color:#fff; padding:10px; border-radius:8px; align-self:flex-end; max-width:85%;">${text}</div>`;
  input.value = '';
  messages.scrollTop = messages.scrollHeight;
  
  // Loading indicator
  const loadingId = 'loading-' + Date.now();
  messages.innerHTML += `<div id="${loadingId}" style="background:var(--bg-elevated); padding:10px; border-radius:8px; align-self:flex-start; max-width:85%; font-style:italic;">Searching...</div>`;
  messages.scrollTop = messages.scrollHeight;
  
  try {
    const res = await api('/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ query: text })
    });
    
    document.getElementById(loadingId).remove();
    messages.innerHTML += `<div style="background:var(--bg-elevated); padding:10px; border-radius:8px; align-self:flex-start; max-width:85%;">${res.response}</div>`;
  } catch (e) {
    document.getElementById(loadingId).remove();
    messages.innerHTML += `<div style="background:rgba(239,68,68,0.1); color:#ef4444; padding:10px; border-radius:8px; align-self:flex-start; max-width:85%;">Error connecting to the Retrieval Assistant.</div>`;
  }
  
  messages.scrollTop = messages.scrollHeight;
}


// ─────────────────────────────────────────────────────────────
// INIT
// ─────────────────────────────────────────────────────────────
loadOverview();
tabLoaded['overview'] = true;
