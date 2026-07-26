/* ═══════════════════════════════════════════════════════════
   socioeconomic.js — Socio-Economic Intelligence Tab
   Correlation scatter, district ranking table, station
   performance, crime calendar, Sankey diagram
   ═══════════════════════════════════════════════════════════ */

let socioCharts = {};

async function loadSocio() {
  try {
    const [corrData, rankData, stationData, calData, sankeyData] = await Promise.all([
      api('/correlation'),
      api('/district-rank'),
      api('/station-performance'),
      api('/crime-calendar'),
      api('/sankey'),
    ]);

    renderCorrelationBadges(corrData.correlations, corrData.insights);
    renderCorrelationChart(corrData.districts);
    renderDistrictRankTable(rankData);
    renderStationPerformance(stationData);
    renderCrimeCalendar(calData);
    renderSankey(sankeyData);
  } catch(e) {
    console.error('Socio load error:', e);
  }
}

// ─────────────────────────────────────────────────────────────
// CORRELATION BADGES + INSIGHTS
// ─────────────────────────────────────────────────────────────
function renderCorrelationBadges(corr, insights) {
  const badgeContainer = document.getElementById('correlation-badges');
  const entries = [
    { label: 'Crime vs Population Density', val: corr.crime_vs_population_density, key: 'density' },
    { label: 'Crime vs Literacy Rate',      val: corr.crime_vs_literacy,            key: 'literacy' },
    { label: 'Crime vs Urban %',            val: corr.crime_vs_urban_pct,           key: 'urban' },
  ];

  badgeContainer.innerHTML = entries.map(e => {
    const v = e.val;
    const color = v > 0.3 ? '#ef4444' : v < -0.3 ? '#10b981' : '#f59e0b';
    const dir = v > 0 ? 'Increase' : 'Decrease';
    return '<div class="corr-badge" style="background:' + color + '22;border:1px solid ' + color + '44;color:' + color + '">' +
      dir + ' r = ' + v.toFixed(3) +
      '<span style="font-size:10px;font-weight:400;color:var(--text-secondary);font-family:Inter,sans-serif;margin-left:6px">' + e.label + '</span>' +
    '</div>';
  }).join('');

  const insightContainer = document.getElementById('correlation-insights');
  insightContainer.innerHTML = insights.map(ins =>
    '<div style="display:flex;gap:8px;padding:8px 12px;background:rgba(59,130,246,0.06);border-left:3px solid #3b82f6;border-radius:0 8px 8px 0;font-size:12px;color:var(--text-secondary)">' +
    '💡 ' + ins + '</div>'
  ).join('');
}

// ─────────────────────────────────────────────────────────────
// CORRELATION SCATTER CHART
// ─────────────────────────────────────────────────────────────
function renderCorrelationChart(districts) {
  const ctx = document.getElementById('correlationChart');
  if (socioCharts.corr) socioCharts.corr.destroy();

  socioCharts.corr = new Chart(ctx, {
    type: 'scatter',
    data: {
      datasets: [
        {
          label: 'Crime Rate vs Literacy',
          data: districts.map(d => ({ x: d.literacy_rate, y: d.crime_rate, name: d.name })),
          backgroundColor: 'rgba(59,130,246,0.65)',
          pointRadius: 6,
          pointHoverRadius: 9,
        },
        {
          label: 'Crime Rate vs Urban %',
          data: districts.map(d => ({ x: d.urban_pct, y: d.crime_rate, name: d.name })),
          backgroundColor: 'rgba(245,158,11,0.65)',
          pointRadius: 6,
          pointHoverRadius: 9,
        }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'top' },
        tooltip: {
          callbacks: {
            label: ctx => {
              const d = ctx.raw;
              return (d.name || '') + ' — x: ' + d.x + ', crime rate: ' + d.y;
            }
          }
        }
      },
      scales: {
        x: { grid: { color: 'rgba(56,120,255,0.07)' }, title: { display: true, text: 'Socio-Economic Indicator', color: '#8ba3cc' } },
        y: { grid: { color: 'rgba(56,120,255,0.07)' }, beginAtZero: true,
             title: { display: true, text: 'Crime Rate (per 1000 pop density)', color: '#8ba3cc' } }
      },
      animation: { duration: 700 }
    }
  });
}

// ─────────────────────────────────────────────────────────────
// DISTRICT RANKING TABLE
// ─────────────────────────────────────────────────────────────
function renderDistrictRankTable(data) {
  const tbody = document.getElementById('district-rank-tbody');
  const rankColors = ['gold', 'silver', 'bronze'];

  tbody.innerHTML = data.map((d, i) => {
    const rankClass = i < 3 ? rankColors[i] : '';
    const color = riskColor(d.composite_score);
    return '<tr>' +
      '<td><span class="rank-number ' + rankClass + '">' + d.rank + '</span></td>' +
      '<td style="font-weight:600">' + d.name + '</td>' +
      '<td><span style="font-size:15px;font-weight:800;color:' + color + '">' + d.composite_score + '</span></td>' +
      '<td>' + d.total_crimes + '</td>' +
      '<td><span style="color:#ef4444">' + d.violent_crimes + '</span></td>' +
      '<td>' +
        '<div class="gauge-bar-wrap" style="width:80px;display:inline-block;vertical-align:middle;margin-right:6px">' +
          '<div class="gauge-bar" style="width:' + Math.min(100, d.avg_pending_pct) + '%;background:' + (d.avg_pending_pct > 40 ? '#ef4444' : '#f59e0b') + '"></div>' +
        '</div>' +
        d.avg_pending_pct + '%' +
      '</td>' +
      '<td>' + d.avg_investigation_days + 'd</td>' +
      '<td><span style="color:#8b5cf6">' + d.repeat_offenders + '</span></td>' +
    '</tr>';
  }).join('');
}

// ─────────────────────────────────────────────────────────────
// STATION PERFORMANCE
// ─────────────────────────────────────────────────────────────
function renderStationPerformance(data) {
  const tbody = document.getElementById('station-perf-tbody');
  const top = data.slice(0, 25);
  tbody.innerHTML = top.map(s =>
    '<tr>' +
      '<td style="font-size:11px;font-weight:500">' + s.name + '</td>' +
      '<td><span class="mono" style="color:#3b82f6">' + (s.actual_firs || s.fir_count) + '</span></td>' +
      '<td>' +
        '<div class="gauge-bar-wrap" style="width:60px;display:inline-block;vertical-align:middle;margin-right:4px">' +
          '<div class="gauge-bar" style="width:' + Math.min(100, s.pending_pct) + '%;background:' + (s.pending_pct > 40 ? '#ef4444' : '#10b981') + '"></div>' +
        '</div>' + s.pending_pct + '%' +
      '</td>' +
      '<td style="color:' + (s.avg_investigation_days > 60 ? '#ef4444' : s.avg_investigation_days > 30 ? '#f59e0b' : '#10b981') + '">' + s.avg_investigation_days + 'd</td>' +
    '</tr>'
  ).join('');
}

// ─────────────────────────────────────────────────────────────
// CRIME CALENDAR (monthly totals)
// ─────────────────────────────────────────────────────────────
function renderCrimeCalendar(data) {
  const ctx = document.getElementById('calendarChart');
  if (socioCharts.calendar) socioCharts.calendar.destroy();

  const last24 = data.slice(-24);
  const maxVal = Math.max(...last24.map(d => d.total), 1);

  socioCharts.calendar = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: last24.map(d => d.month),
      datasets: [{
        label: 'Monthly Crime Count',
        data: last24.map(d => d.total),
        backgroundColor: last24.map(d => {
          const ratio = d.total / maxVal;
          if (ratio > 0.8) return 'rgba(239,68,68,0.75)';
          if (ratio > 0.5) return 'rgba(245,158,11,0.7)';
          return 'rgba(59,130,246,0.6)';
        }),
        borderRadius: 3,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { maxRotation: 45, font: { size: 9 }, maxTicksLimit: 16 } },
        y: { grid: { color: 'rgba(56,120,255,0.07)' }, beginAtZero: true }
      },
      animation: { duration: 700 }
    }
  });
}

// ─────────────────────────────────────────────────────────────
// SANKEY (Plotly-free, using D3 path rendering)
// ─────────────────────────────────────────────────────────────
function renderSankey(data) {
  const container = document.getElementById('sankey-container');

  if (!data.nodes || !data.links || data.nodes.length === 0) {
    container.innerHTML = '<div style="color:var(--text-muted);text-align:center;padding:60px;font-size:13px">Sankey data unavailable</div>';
    return;
  }

  const W = container.clientWidth || 800;
  const H = 320;
  const PAD = 20;
  const NODE_W = 18;
  const NODE_GAP = 10;

  // Group nodes by category
  const categories = ['crime_type', 'district', 'status'];
  const catNodes = {};
  categories.forEach(cat => {
    catNodes[cat] = data.nodes.filter(n => n.category === cat);
  });

  // Layout
  const colX = [PAD, W / 2 - NODE_W / 2, W - PAD - NODE_W];

  function layoutColumn(nodes, x) {
    const totalH = H - PAD * 2;
    const step = totalH / (nodes.length || 1);
    nodes.forEach((n, i) => {
      n._x = x;
      n._y = PAD + i * step;
      n._h = Math.max(8, step - NODE_GAP);
    });
  }

  layoutColumn(catNodes.crime_type || [], colX[0]);
  layoutColumn(catNodes.district || [], colX[1]);
  layoutColumn(catNodes.status || [], colX[2]);

  const nodeById = {};
  data.nodes.forEach(n => { nodeById[n.id] = n; });

  const svg = d3.create('svg').attr('width', W).attr('height', H);

  // Links
  const maxLinkVal = Math.max(...data.links.map(l => l.value), 1);
  data.links.forEach(l => {
    const src = nodeById[l.source];
    const tgt = nodeById[l.target];
    if (!src || !tgt || src._x === undefined || tgt._x === undefined) return;

    const sx = src._x + NODE_W;
    const sy = src._y + (src._h || 20) / 2;
    const tx = tgt._x;
    const ty = tgt._y + (tgt._h || 20) / 2;
    const strokeW = Math.max(1, (l.value / maxLinkVal) * 20);

    svg.append('path')
      .attr('d', 'M' + sx + ',' + sy + ' C' + (sx+80) + ',' + sy + ' ' + (tx-80) + ',' + ty + ' ' + tx + ',' + ty)
      .attr('fill', 'none')
      .attr('stroke', 'rgba(59,130,246,0.25)')
      .attr('stroke-width', strokeW);
  });

  // Nodes
  data.nodes.forEach(n => {
    if (n._x === undefined) return;
    const color = n.category === 'crime_type' ? '#3b82f6' : n.category === 'district' ? '#8b5cf6' : '#10b981';
    svg.append('rect')
      .attr('x', n._x).attr('y', n._y)
      .attr('width', NODE_W).attr('height', n._h || 20)
      .attr('fill', color).attr('rx', 3);

    svg.append('text')
      .attr('x', n.category === 'status' ? n._x - 4 : n._x + NODE_W + 4)
      .attr('y', n._y + (n._h || 20) / 2)
      .attr('dominant-baseline', 'middle')
      .attr('text-anchor', n.category === 'status' ? 'end' : 'start')
      .attr('fill', '#8ba3cc')
      .attr('font-size', 10)
      .attr('font-family', 'Inter, sans-serif')
      .text(n.label && n.label.length > 14 ? n.label.slice(0,12) + '…' : (n.label || ''));
  });

  // Column headers
  [['Crime Type', colX[0]], ['District', colX[1]], ['Status', colX[2]]].forEach(([label, x]) => {
    svg.append('text')
      .attr('x', x + NODE_W / 2).attr('y', 10)
      .attr('text-anchor', 'middle')
      .attr('fill', '#4a6490').attr('font-size', 9)
      .attr('font-family', 'Inter, sans-serif')
      .attr('font-weight', '700')
      .attr('letter-spacing', '0.06em')
      .text(label.toUpperCase());
  });

  container.innerHTML = '';
  container.appendChild(svg.node());
}
