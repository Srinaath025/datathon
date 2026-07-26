/* ═══════════════════════════════════════════════════════════
   network.js — Criminal Network Tab
   D3.js force-directed graph, repeat-offender scorecards
   ═══════════════════════════════════════════════════════════ */

let networkSim = null;
let networkData = null;

async function loadNetwork() {
  try {
    const offenders = await api('/offenders?min_firs=2&limit=40');
    renderOffenderList(offenders);
    document.getElementById('offender-count-tag').textContent = offenders.length + ' found';
  } catch(e) {
    console.error('Network load error:', e);
  }
}

function renderOffenderList(offenders) {
  const container = document.getElementById('offender-list');
  container.innerHTML = offenders.map(o => {
    const initials = o.name.split(' ').map(n => n[0]).join('').slice(0,2).toUpperCase();
    const rc = riskColor(o.risk_score);
    return '<div class="offender-card" onclick="selectOffender(' + o.person_id + ')">' +
      '<div class="offender-avatar">' + initials + '</div>' +
      '<div class="offender-info">' +
        '<div class="offender-name">' + o.name + '</div>' +
        '<div class="offender-meta">' + o.prior_fir_count + ' prior FIRs · ' + o.districts_active_count + ' districts · ' + o.gender + '</div>' +
        '<div style="display:flex;gap:5px;margin-top:5px;flex-wrap:wrap">' +
          o.mo_tags.slice(0, 3).map(t => '<span class="tag tag-grey">' + t + '</span>').join('') +
        '</div>' +
      '</div>' +
      '<div class="offender-risk">' +
        '<div class="offender-risk-score" style="color:' + rc + '">' + o.risk_score.toFixed(0) + '</div>' +
        '<div class="offender-risk-label" style="color:' + rc + '">' + o.risk_level + '</div>' +
      '</div>' +
    '</div>';
  }).join('');
}

async function selectOffender(personId) {
  document.querySelectorAll('.offender-card').forEach(c => c.style.borderColor = '');
  const clickedCard = event.currentTarget;
  if (clickedCard) clickedCard.style.borderColor = 'var(--blue-primary)';

  document.getElementById('network-loader').style.display = 'flex';
  document.getElementById('network-svg').innerHTML = '';

  try {
    const [graphData, profile] = await Promise.all([
      api('/network/person/' + personId),
      api('/offenders/' + personId),
    ]);
    networkData = graphData;
    document.getElementById('network-loader').style.display = 'none';
    renderNetworkGraph(graphData);
    renderOffenderCard(profile);
  } catch(e) {
    document.getElementById('network-loader').innerHTML =
      '<span style="color:var(--red)">Error: ' + e.message + '</span>';
  }
}

function renderNetworkGraph(data) {
  const container = document.getElementById('network-svg-container');
  const W = container.clientWidth;
  const H = container.clientHeight;
  const svg = d3.select('#network-svg').attr('width', W).attr('height', H);
  svg.selectAll('*').remove();

  if (!data.nodes.length) {
    svg.append('text').attr('x', W/2).attr('y', H/2)
      .attr('text-anchor', 'middle').attr('fill', '#4a6490')
      .text('No network data available');
    return;
  }

  const nodeColor = { suspect: '#3b82f6', victim: '#ef4444', witness: '#8b5cf6' };
  const typeColor = { vehicle: '#f59e0b', phone: '#10b981', person: '#3b82f6' };

  function getColor(n) {
    if (n.entity_type === 'person') return nodeColor[n.sub_type] || '#8b5cf6';
    return typeColor[n.entity_type] || '#8ba3cc';
  }

  const defs = svg.append('defs');
  const filter = defs.append('filter').attr('id', 'node-glow');
  filter.append('feGaussianBlur').attr('stdDeviation', '3').attr('result', 'coloredBlur');
  const merge = filter.append('feMerge');
  merge.append('feMergeNode').attr('in', 'coloredBlur');
  merge.append('feMergeNode').attr('in', 'SourceGraphic');

  const g = svg.append('g');
  svg.call(d3.zoom().scaleExtent([0.2, 4]).on('zoom', e => g.attr('transform', e.transform)));

  if (networkSim) networkSim.stop();
  networkSim = d3.forceSimulation(data.nodes)
    .force('link', d3.forceLink(data.links).id(d => d.id).distance(200).strength(0.3))
    .force('charge', d3.forceManyBody().strength(-600))
    .force('center', d3.forceCenter(W / 2, H / 2))
    .force('collision', d3.forceCollide(50));

  const link = g.append('g').selectAll('line')
    .data(data.links).join('line')
    .attr('stroke', 'rgba(59,130,246,0.35)')
    .attr('stroke-width', 1.5)
    .attr('stroke-dasharray', d => d.label === 'uses_phone' ? '4,3' : null);

  const linkLabel = g.append('g').selectAll('text')
    .data(data.links).join('text')
    .attr('fill', '#4a6490').attr('font-size', 8)
    .attr('text-anchor', 'middle').attr('font-family', 'Inter, sans-serif')
    .text(d => (d.label || '').replace(/_/g, ' '));

  const node = g.append('g').selectAll('g')
    .data(data.nodes).join('g').attr('cursor', 'pointer')
    .call(d3.drag()
      .on('start', (e, d) => { if (!e.active) networkSim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on('drag',  (e, d) => { d.fx = e.x; d.fy = e.y; })
      .on('end',   (e, d) => { if (!e.active) networkSim.alphaTarget(0); d.fx = null; d.fy = null; })
    );

  node.append('circle')
    .attr('r', d => d.entity_type === 'person' && d.sub_type === 'suspect' ? 18 : 13)
    .attr('fill', d => getColor(d) + '33')
    .attr('stroke', d => getColor(d))
    .attr('stroke-width', 2)
    .attr('filter', 'url(#node-glow)');

  const iconMap = { person: '👤', vehicle: '🚗', phone: '📱' };
  node.append('text').attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
    .attr('font-size', 12).text(d => iconMap[d.entity_type] || '●');

  node.append('text').attr('dy', 28).attr('text-anchor', 'middle')
    .attr('fill', '#8ba3cc').attr('font-size', 9).attr('font-family', 'Inter, sans-serif')
    .text(d => d.label ? (d.label.length > 14 ? d.label.slice(0,12) + '…' : d.label) : '');

  node.filter(d => d.risk && d.risk >= 60).append('circle')
    .attr('r', 22).attr('fill', 'none')
    .attr('stroke', '#ef4444').attr('stroke-width', 1)
    .attr('stroke-dasharray', '3,3').attr('opacity', 0.6);

  const tooltip = document.getElementById('global-tooltip');
  node.on('mouseover', (e, d) => {
    tooltip.style.display = 'block';
    tooltip.style.left = (e.clientX + 12) + 'px';
    tooltip.style.top = (e.clientY - 10) + 'px';
    tooltip.innerHTML = '<strong>' + (d.label || d.id) + '</strong><br>' +
      '<span style="color:#8ba3cc">' + d.entity_type + (d.sub_type ? ' · ' + d.sub_type : '') + '</span>' +
      (d.risk ? '<br><span style="color:' + riskColor(d.risk) + '">Risk: ' + d.risk + '</span>' : '');
  }).on('mousemove', e => {
    tooltip.style.left = (e.clientX + 12) + 'px';
    tooltip.style.top = (e.clientY - 10) + 'px';
  }).on('mouseout', () => { tooltip.style.display = 'none'; });

  networkSim.on('tick', () => {
    link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
    linkLabel.attr('x', d => (d.source.x + d.target.x) / 2)
             .attr('y', d => (d.source.y + d.target.y) / 2);
    node.attr('transform', d => 'translate(' + d.x + ',' + d.y + ')');
  });
}

function renderOffenderCard(profile) {
  if (!profile) return;
  const card = document.getElementById('selected-offender-card');
  card.style.display = '';
  const rc = riskColor(profile.risk_score);
  const mo = (profile.mo_pattern || []).map(t => '<span class="tag tag-grey">' + t + '</span>').join(' ');
  const firs = (profile.fir_history || []).slice(0, 4);

  card.innerHTML = '<div style="background:var(--bg-surface);border:1px solid var(--border);border-radius:12px;padding:14px">' +
    '<div style="display:flex;align-items:center;gap:14px;margin-bottom:12px">' +
      '<div class="offender-avatar" style="width:48px;height:48px;font-size:18px">' +
        profile.name.split(' ').map(n => n[0]).join('').slice(0,2).toUpperCase() +
      '</div>' +
      '<div style="flex:1"><div style="font-size:14px;font-weight:700">' + profile.name + '</div>' +
        '<div style="font-size:11px;color:var(--text-muted)">Age ' + profile.age + ' · ' + profile.gender + '</div></div>' +
      '<div style="text-align:right"><div style="font-size:26px;font-weight:800;color:' + rc + '">' + profile.risk_score.toFixed(0) + '</div>' +
        '<div style="font-size:9px;text-transform:uppercase;color:' + rc + '">Risk Score</div></div>' +
    '</div>' +
    '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:10px">' +
      '<div style="text-align:center;padding:7px;background:rgba(239,68,68,0.08);border-radius:8px;border:1px solid rgba(239,68,68,0.2)">' +
        '<div style="font-size:18px;font-weight:800;color:#ef4444">' + profile.prior_fir_count + '</div>' +
        '<div style="font-size:9px;color:var(--text-muted)">Prior FIRs</div></div>' +
      '<div style="text-align:center;padding:7px;background:rgba(245,158,11,0.08);border-radius:8px;border:1px solid rgba(245,158,11,0.2)">' +
        '<div style="font-size:18px;font-weight:800;color:#f59e0b">' + (profile.districts_active || []).length + '</div>' +
        '<div style="font-size:9px;color:var(--text-muted)">Districts</div></div>' +
      '<div style="text-align:center;padding:7px;background:rgba(59,130,246,0.08);border-radius:8px;border:1px solid rgba(59,130,246,0.2)">' +
        '<div style="font-size:18px;font-weight:800;color:#3b82f6">' + firs.length + '</div>' +
        '<div style="font-size:9px;color:var(--text-muted)">Active Cases</div></div>' +
    '</div>' +
    '<div style="font-size:10px;color:var(--text-muted);margin-bottom:5px;font-weight:700;letter-spacing:0.08em">MO PATTERN</div>' +
    '<div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:10px">' + mo + '</div>' +
    (firs.length ? '<div style="font-size:10px;color:var(--text-muted);margin-bottom:5px;font-weight:700;letter-spacing:0.08em">CASE HISTORY</div>' +
      firs.map(f => '<div style="display:flex;justify-content:space-between;padding:5px 8px;background:rgba(255,255,255,0.03);border-radius:6px;margin-bottom:3px;font-size:10px">' +
        '<span class="mono">#' + f.fir_id + '</span><span>' + f.crime_type + '</span>' +
        '<span style="color:var(--text-muted)">' + (f.date_time ? f.date_time.slice(0,10) : '') + '</span></div>'
      ).join('') : '') +
  '</div>';
}
