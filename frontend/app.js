const fmtVal = v => v != null ? v : '—';
const avatar = (initials, color) =>
  `<div class="player-avatar" style="background:${color}">${initials}</div>`;

function valueTrend(curr, prev) {
  if (curr == null || prev == null) return { label: '—', cls: 'flat' };
  const diff = curr - prev;
  const pct = ((diff / prev) * 100).toFixed(0);
  if (diff > 0) return { label: `▲ €${diff.toFixed(0)}M (+${pct}%)`, cls: 'up' };
  if (diff < 0) return { label: `▼ €${Math.abs(diff).toFixed(0)}M (${pct}%)`, cls: 'down' };
  return { label: '→ No change', cls: 'flat' };
}

let allPlayers = [];

async function load() {
  const [players, sys, agent] = await Promise.all([
    fetch('/api/players').then(r => r.json()),
    fetch('/api/system').then(r => r.json()),
    fetch('/api/agent').then(r => r.json()),
  ]);

  allPlayers = players;

  // agent chip
  const agentInitials = agent.name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
  document.getElementById('agent-chip').innerHTML = `
    <div class="agent-avatar">${agentInitials}</div>
    <span class="agent-name">${agent.name}</span>`;

  // greeting
  const hour = new Date().getHours();
  const greet = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  document.getElementById('welcome-title').textContent = `${greet}, ${agent.name.split(' ')[0]}`;
  document.getElementById('welcome-sub').textContent =
    `Here's your ${agent.agency} portfolio update — ${players.length} players monitored.`;

  // sidebar nav
  const nav = document.getElementById('player-nav');
  players.forEach((p, i) => {
    const el = document.createElement('div');
    el.className = 'player-nav-item';
    el.dataset.index = i;
    el.innerHTML = `
      ${avatar(p.initials, p.color)}
      <div class="nav-info">
        <strong>${p.name.split(' ').slice(-1)[0]}</strong>
        <span>${p.club}</span>
      </div>
      <div class="nav-dot ${p.sentiment_overall}"></div>`;
    el.addEventListener('click', () => showPlayer(i));
    nav.appendChild(el);
  });

  // sidebar system stats
  document.getElementById('sidebar-stats').innerHTML = `
    <p>
      Last run: ${sys.last_run}<br>
      Players: ${sys.total_players}<br>
      Articles: ${sys.total_articles_processed}<br>
      Alerts: ${sys.alerts_count}<br>
      Cost: $${sys.run_cost_usd}
    </p>`;

  // KPIs
  const totalValue = players.reduce((s, p) => s + (p.market_value_eur || 0), 0);
  const avgRating  = (players.reduce((s, p) => s + (p.rating || 0), 0) / players.length).toFixed(2);
  const alertCount = players.reduce((s, p) => s + p.alerts.length, 0);
  const posCount   = players.filter(p => p.sentiment_overall === 'positive').length;

  document.getElementById('overview-kpis').innerHTML = `
    <div class="kpi-card">
      <div class="kpi-label">Portfolio Value</div>
      <div class="kpi-value">€${totalValue}<small>M</small></div>
      <div class="kpi-sub">${players.length} players</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Active Alerts</div>
      <div class="kpi-value">${alertCount}</div>
      <div class="kpi-sub">Require attention</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Positive Sentiment</div>
      <div class="kpi-value">${posCount}<small> / ${players.length}</small></div>
      <div class="kpi-sub">This week</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Avg Rating</div>
      <div class="kpi-value">${avgRating}</div>
      <div class="kpi-sub">Across portfolio</div>
    </div>`;

  // Player grid
  const grid = document.getElementById('player-grid');
  players.forEach((p, i) => {
    const trend = valueTrend(p.market_value_eur, p.market_value_prev_eur);
    const el = document.createElement('div');
    el.className = 'player-card';
    el.innerHTML = `
      <div class="card-header">
        ${avatar(p.initials, p.color)}
        <div class="card-info">
          <h3>${p.name}</h3>
          <p>${p.club} · ${p.position}</p>
        </div>
      </div>
      <div class="card-stats">
        <div class="card-stat"><div class="val">${fmtVal(p.goals)}</div><div class="lbl">Goals</div></div>
        <div class="card-stat"><div class="val">${fmtVal(p.assists)}</div><div class="lbl">Assists</div></div>
        <div class="card-stat"><div class="val">${p.rating ? p.rating.toFixed(1) : '—'}</div><div class="lbl">Rating</div></div>
      </div>
      <div class="card-footer">
        <div class="sentiment-badge ${p.sentiment_overall}">${p.sentiment_overall}</div>
        <div class="value-change ${trend.cls}">${trend.label}</div>
      </div>
      ${p.alerts.length ? `<div class="alert-indicator" style="margin-top:10px">⚠ ${p.alerts.length} alert${p.alerts.length > 1 ? 's' : ''}</div>` : ''}`;
    el.addEventListener('click', () => showPlayer(i));
    grid.appendChild(el);
  });
}

function showPlayer(index) {
  document.querySelectorAll('.player-nav-item').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.player-nav-item')[index].classList.add('active');

  document.getElementById('view-overview').classList.add('hidden');
  const detail = document.getElementById('view-player');
  detail.classList.remove('hidden');

  const p = allPlayers[index];
  const trend = valueTrend(p.market_value_eur, p.market_value_prev_eur);
  const contractWarning = p.days_until_expiry < 500;

  detail.innerHTML = `
    <button class="detail-back" onclick="showOverview()">← Back to portfolio</button>

    <div class="detail-hero">
      <div class="detail-avatar" style="background:${p.color}">${p.initials}</div>
      <div class="detail-info">
        <h1>${p.name}</h1>
        <p>${p.club} · ${p.league} · ${p.nationality}</p>
        <div class="detail-badges">
          <span class="badge">${p.position}</span>
          <span class="badge">${p.appearances} apps</span>
          <span class="sentiment-badge ${p.sentiment_overall}">${p.sentiment_overall} sentiment</span>
        </div>
      </div>
      <div class="detail-right">
        <div class="detail-value">€${fmtVal(p.market_value_eur)}<small>M</small></div>
        <div class="value-change ${trend.cls}" style="margin-top:4px;font-size:12px">${trend.label}</div>
        <div class="detail-contract ${contractWarning ? 'warning' : ''}" style="margin-top:8px">
          Contract until ${p.contract_expires}
          ${contractWarning ? `<br>⚠ ${p.days_until_expiry} days remaining` : ''}
        </div>
      </div>
    </div>

    <div class="detail-grid">
      <div class="module">
        <div class="module-title">Season Statistics</div>
        <div class="stat-row"><span class="key">League</span><span class="val">${p.league}</span></div>
        <div class="stat-row"><span class="key">Appearances</span><span class="val">${fmtVal(p.appearances)}</span></div>
        <div class="stat-row"><span class="key">Goals</span><span class="val">${fmtVal(p.goals)}</span></div>
        <div class="stat-row"><span class="key">Assists</span><span class="val">${fmtVal(p.assists)}</span></div>
        <div class="stat-row"><span class="key">Avg Rating</span><span class="val">${p.rating ? p.rating.toFixed(2) : '—'}</span></div>
      </div>
      <div class="module">
        <div class="module-title">Alerts</div>
        <div class="alert-list">
          ${p.alerts.length
            ? p.alerts.map(a => `<div class="alert-row">⚠ ${a}</div>`).join('')
            : '<div class="no-alert">No alerts this week</div>'
          }
        </div>
      </div>
    </div>

    <div class="module" style="margin-bottom:16px">
      <div class="module-title">Media Coverage</div>
      <div class="stat-row"><span class="key">Articles this week</span><span class="val">${p.articles_count}</span></div>
      <div class="stat-row"><span class="key">Overall sentiment</span>
        <span class="sentiment-badge ${p.sentiment_overall}">${p.sentiment_overall}</span>
      </div>
    </div>

    <div class="briefing-module">
      <div class="module-title">Weekly Briefing</div>
      <div class="briefing-text">${p.briefing}</div>
      <div class="briefing-footer">
        <span>Generated ${p.last_updated} · gemini-2.5-flash · RAG-enhanced</span>
        <button class="btn-regen" onclick="openModal()">Regenerate</button>
      </div>
    </div>`;
}

function showOverview() {
  document.querySelectorAll('.player-nav-item').forEach(el => el.classList.remove('active'));
  document.getElementById('view-overview').classList.remove('hidden');
  document.getElementById('view-player').classList.add('hidden');
}

function openModal()  { document.getElementById('overlay').classList.remove('hidden'); }
function closeModal() { document.getElementById('overlay').classList.add('hidden'); }

load();
