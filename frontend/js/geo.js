/* ═══════════════════════════════════════════════════════════
   geo.js — Geospatial Intelligence Tab
   Leaflet heatmap, district choropleth, station breakdown,
   spike alerts, time/filter controls
   ═══════════════════════════════════════════════════════════ */

let leafletMap = null;
let heatLayer = null;
let districtMarkers = [];
let geoCharts = {};

// ─────────────────────────────────────────────────────────────
// MAIN LOAD
// ─────────────────────────────────────────────────────────────
async function loadGeo() {
  try {
    const [heatData, districtData, alertData] = await Promise.all([
      api('/heatmap-data'),
      api('/district-summary'),
      api('/spike-alerts'),
    ]);

    initMap(heatData, districtData);
    renderGeoAlerts(alertData);
    renderDistrictBarChart(districtData);

    // Also populate station district select
    const stationSel = document.getElementById('station-district-select');
    if (stationSel && stationSel.options.length <= 1) {
      districtData.forEach(d => {
        const opt = document.createElement('option');
        opt.value = d.district_id;
        opt.textContent = d.name;
        stationSel.appendChild(opt);
      });
    }

  } catch(e) {
    console.error('Geo load error:', e);
  }
}

// ─────────────────────────────────────────────────────────────
// LEAFLET MAP INIT
// ─────────────────────────────────────────────────────────────
function initMap(heatData, districtData) {
  if (leafletMap) {
    leafletMap.remove();
    leafletMap = null;
  }

  leafletMap = L.map('heatmap', {
    center: [15.3, 75.7],
    zoom: 7,
    zoomControl: true,
    preferCanvas: true,
  });

  // Dark tile layer
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
    maxZoom: 18,
  }).addTo(leafletMap);

  // Heatmap layer
  renderHeatLayer(heatData);

  // District circle markers
  renderDistrictCircles(districtData);
}

function renderHeatLayer(points) {
  if (heatLayer) leafletMap.removeLayer(heatLayer);
  const latLngs = points.map(p => [p.lat, p.lon, p.intensity || 1]);
  heatLayer = L.heatLayer(latLngs, {
    radius: 22,
    blur: 18,
    maxZoom: 12,
    gradient: { 0.2: '#3b82f6', 0.5: '#f59e0b', 0.8: '#ef4444', 1.0: '#ff0000' }
  }).addTo(leafletMap);
}

function renderDistrictCircles(districtData) {
  districtMarkers.forEach(m => leafletMap.removeLayer(m));
  districtMarkers = [];

  const max = Math.max(...districtData.map(d => d.total_crimes), 1);

  districtData.forEach(d => {
    const ratio = d.total_crimes / max;
    const radius = 6000 + ratio * 28000;
    const color = ratio > 0.7 ? '#ef4444' : ratio > 0.4 ? '#f59e0b' : '#3b82f6';

    const circle = L.circle([d.lat, d.lon], {
      radius,
      color,
      fillColor: color,
      fillOpacity: 0.12,
      weight: 1.5,
      opacity: 0.6,
    }).addTo(leafletMap);

    circle.bindTooltip(`
      <div style="font-family:Inter,sans-serif;min-width:140px">
        <div style="font-weight:700;margin-bottom:4px">${d.name}</div>
        <div>Total Crimes: <strong>${d.total_crimes}</strong></div>
        <div>Violent: <strong>${d.violent_crimes}</strong></div>
      </div>
    `, { sticky: true });

    circle.on('click', () => {
      document.getElementById('station-district-select').value = d.district_id;
      loadStationBreakdown();
    });

    districtMarkers.push(circle);
  });
}

// ─────────────────────────────────────────────────────────────
// APPLY FILTERS
// ─────────────────────────────────────────────────────────────
async function applyGeoFilters() {
  const district = document.getElementById('geo-district-filter').value;
  const crime = document.getElementById('geo-crime-filter').value;
  const time = document.getElementById('geo-time-filter').value;

  let url = '/heatmap-data?';
  if (district) url += 'district_id=' + district + '&';
  if (crime) url += 'crime_type=' + encodeURIComponent(crime) + '&';
  if (time) url += 'time_filter=' + time + '&';

  try {
    const data = await api(url);
    renderHeatLayer(data);
  } catch(e) {}
}

// ─────────────────────────────────────────────────────────────
// GEO ALERTS
// ─────────────────────────────────────────────────────────────
function renderGeoAlerts(alerts) {
  const container = document.getElementById('geo-alerts');
  if (!alerts.length) { container.innerHTML = ''; return; }
  container.innerHTML = alerts.slice(0, 2).map(a =>
    '<div class="alert-banner ' + (a.spike_factor > 2 ? 'danger' : 'warning') + '" style="margin-bottom:8px">' +
    ' <strong>Spike Alert:</strong> District #' + a.district_id +
    ' — ' + a.spike_factor + '× above baseline (' + a.recent_count +
    ' recent vs avg ' + a.baseline_avg + ')' +
    '</div>'
  ).join('');
}

// ─────────────────────────────────────────────────────────────
// DISTRICT BAR CHART
// ─────────────────────────────────────────────────────────────
function renderDistrictBarChart(data) {
  const sorted = [...data].sort((a, b) => b.total_crimes - a.total_crimes).slice(0, 15);
  const ctx = document.getElementById('districtBarChart');
  if (geoCharts.district) geoCharts.district.destroy();

  geoCharts.district = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: sorted.map(d => d.name.split(' ')[0]),
      datasets: [
        {
          label: 'Total Crimes',
          data: sorted.map(d => d.total_crimes),
          backgroundColor: 'rgba(59,130,246,0.6)',
          borderRadius: 3,
        },
        {
          label: 'Violent Crimes',
          data: sorted.map(d => d.violent_crimes),
          backgroundColor: 'rgba(239,68,68,0.65)',
          borderRadius: 3,
        }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'top' } },
      scales: {
        x: { grid: { display: false }, ticks: { maxRotation: 35, font: { size: 9 } } },
        y: { grid: { color: 'rgba(56,120,255,0.07)' }, beginAtZero: true }
      },
      animation: { duration: 700 }
    }
  });
}

// ─────────────────────────────────────────────────────────────
// STATION BREAKDOWN
// ─────────────────────────────────────────────────────────────
async function loadStationBreakdown() {
  const districtId = document.getElementById('station-district-select').value;
  if (!districtId) return;

  const container = document.getElementById('station-breakdown-content');
  container.innerHTML = '<div class="loader-wrap"><div class="spinner"></div></div>';

  try {
    const data = await api('/station-breakdown/' + districtId);
    if (!data.length) {
      container.innerHTML = '<div style="color:var(--text-muted);font-size:12px;padding:12px">No station data.</div>';
      return;
    }

    const max = Math.max(...data.map(s => s.fir_count || 0), 1);
    container.innerHTML = data.map(s =>
      '<div style="padding:10px;background:var(--bg-surface);border:1px solid var(--border);border-radius:8px;margin-bottom:6px">' +
        '<div style="display:flex;justify-content:space-between;margin-bottom:6px;align-items:center">' +
          '<div style="font-size:12px;font-weight:600">' + s.name + '</div>' +
          '<span class="tag tag-blue">' + (s.fir_count || 0) + ' FIRs</span>' +
        '</div>' +
        '<div class="gauge-bar-wrap" style="margin-bottom:6px">' +
          '<div class="gauge-bar" style="width:' + (((s.fir_count||0)/max)*100) + '%;background:#3b82f6"></div>' +
        '</div>' +
        '<div style="display:flex;gap:16px;font-size:11px;color:var(--text-muted);margin-bottom:5px">' +
          '<span>Pend: ' + s.pending_pct + '%</span>' +
          '<span>Avg: ' + s.avg_investigation_days + 'd</span>' +
        '</div>' +
      '</div>'
    ).join('');

    // Pan map to district
    if (data[0] && leafletMap) leafletMap.setView([data[0].lat || 15.3, data[0].lon || 75.7], 10);

  } catch(e) {
    container.innerHTML = '<div style="color:var(--red);font-size:12px;padding:12px">Error loading stations.</div>';
  }
}
