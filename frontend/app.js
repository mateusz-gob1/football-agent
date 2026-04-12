const fmtVal = v => v != null ? v : '—';

// ── Chart helpers ────────────────────────────────────────────────────────────

let _trendChart = null;

function destroyChart(ref) {
  if (ref) { ref.destroy(); }
  return null;
}

function renderPortfolioChart(players) {
  const sorted = [...players].sort((a, b) => (b.market_value_eur || 0) - (a.market_value_eur || 0));
  const ctx = document.getElementById('chart-portfolio').getContext('2d');
  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: sorted.map(p => p.name.split(' ').slice(-1)[0]),
      datasets: [{
        data: sorted.map(p => p.market_value_eur || 0),
        backgroundColor: sorted.map(p => p.color + 'cc'),
        borderColor: sorted.map(p => p.color),
        borderWidth: 1,
        borderRadius: 4,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: {
        callbacks: { label: ctx => ` €${ctx.raw}M` }
      }},
      scales: {
        x: { grid: { color: '#e5e5ea' }, ticks: { callback: v => `€${v}M`, font: { size: 11 } } },
        y: { grid: { display: false }, ticks: { font: { size: 11 } } }
      }
    }
  });
}

function renderSentimentChart(players) {
  const counts = { positive: 0, neutral: 0, negative: 0, mixed: 0 };
  players.forEach(p => { if (counts[p.sentiment_overall] !== undefined) counts[p.sentiment_overall]++; });
  const ctx = document.getElementById('chart-sentiment').getContext('2d');
  new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Positive', 'Neutral', 'Negative', 'Mixed'],
      datasets: [{
        data: [counts.positive, counts.neutral, counts.negative, counts.mixed],
        backgroundColor: ['#30d158cc', '#aeaeb2cc', '#ff3b30cc', '#ff9f0acc'],
        borderColor: ['#30d158', '#aeaeb2', '#ff3b30', '#ff9f0a'],
        borderWidth: 1,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '65%',
      plugins: {
        legend: { position: 'bottom', labels: { font: { size: 11 }, padding: 10, boxWidth: 10 } },
        tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${ctx.raw}` } }
      }
    }
  });
}

function renderTrendChart(canvasId, history, color) {
  _trendChart = destroyChart(_trendChart);
  if (!history || history.length < 2) return;
  const ctx = document.getElementById(canvasId).getContext('2d');
  _trendChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: history.map(h => {
        const d = new Date(h.date);
        return d.toLocaleDateString('en-GB', { month: 'short', year: '2-digit' });
      }),
      datasets: [{
        data: history.map(h => h.value_eur),
        borderColor: color,
        backgroundColor: color + '18',
        borderWidth: 2,
        pointRadius: 3,
        pointBackgroundColor: color,
        tension: 0.35,
        fill: true,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: {
        callbacks: { label: ctx => ` €${ctx.raw}M` }
      }},
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 10 }, maxTicksLimit: 8 } },
        y: { grid: { color: '#e5e5ea' }, ticks: { callback: v => `€${v}M`, font: { size: 10 } } }
      }
    }
  });
}

// ── End chart helpers ─────────────────────────────────────────────────────────

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
  const alertCount = players.reduce((s, p) => s + p.alerts.length, 0);
  const posCount   = players.filter(p => p.sentiment_overall === 'positive').length;
  const contractWarningCount = players.filter(p => p.days_until_expiry != null && p.days_until_expiry < 365).length;

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
      <div class="kpi-label">Contract Alerts</div>
      <div class="kpi-value">${contractWarningCount}</div>
      <div class="kpi-sub">Expiring &lt; 1 year</div>
    </div>`;

  // Overview charts
  renderPortfolioChart(players);
  renderSentimentChart(players);

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
        <div class="card-stat"><div class="val">${fmtVal(p.appearances)}</div><div class="lbl">Apps</div></div>
        <div class="card-stat"><div class="val">${fmtVal(p.goals)}</div><div class="lbl">Goals</div></div>
        <div class="card-stat"><div class="val">${fmtVal(p.assists)}</div><div class="lbl">Assists</div></div>
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
          <span class="badge">Age ${p.age}</span>
          <span class="badge">${p.appearances} apps · ${p.minutes ? p.minutes.toLocaleString() + "'" : ''}</span>
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
        <div class="module-title">Season Statistics <span style="font-weight:400;font-size:11px;color:var(--text-muted)">2024/25</span></div>
        <div class="stat-row"><span class="key">League</span><span class="val">${p.league}</span></div>
        <div class="stat-row"><span class="key">Appearances</span><span class="val">${fmtVal(p.appearances)}</span></div>
        <div class="stat-row"><span class="key">Goals</span><span class="val">${fmtVal(p.goals)}</span></div>
        <div class="stat-row"><span class="key">Assists</span><span class="val">${fmtVal(p.assists)}</span></div>
        <div class="stat-row"><span class="key">Minutes played</span><span class="val">${p.minutes ? p.minutes.toLocaleString() + "'" : '—'}</span></div>
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

    ${(p.value_history && p.value_history.length >= 2) ? `
    <div class="module" style="margin-bottom:16px">
      <div class="module-title">Market Value Trend</div>
      <div class="chart-wrap chart-wrap--trend"><canvas id="chart-trend"></canvas></div>
    </div>` : ''}

    <div class="module" style="margin-bottom:16px">
      <div class="module-title">Media Coverage</div>
      <div class="stat-row"><span class="key">Articles this week</span><span class="val">${p.articles_count}</span></div>
      <div class="stat-row" style="margin-bottom:10px"><span class="key">Overall sentiment</span>
        <span class="sentiment-badge ${p.sentiment_overall}">${p.sentiment_overall}</span>
      </div>
      ${buildArticleSources(p.sentiment_details || [])}
    </div>

    ${buildBriefingModule(p)}`;

  if (p.value_history && p.value_history.length >= 2) {
    renderTrendChart('chart-trend', p.value_history, p.color);
  }
}

const BROKEN_URL_PATTERNS = ['consent.yahoo.com', 'consent.google.com', 'subscribe.', 'login.'];

function isUsableUrl(url) {
  if (!url) return false;
  return !BROKEN_URL_PATTERNS.some(pattern => url.includes(pattern));
}

function buildArticleSources(articles) {
  if (!articles || articles.length === 0) return '';
  const items = articles.map(a => {
    const dot = `<span class="art-dot ${a.sentiment}"></span>`;
    const title = isUsableUrl(a.url)
      ? `<a class="art-link" href="${a.url}" target="_blank" rel="noopener noreferrer">${a.title}</a>`
      : `<span>${a.title}</span>`;
    return `<div class="article-row">${dot}${title}<span class="art-reason">${a.reason}</span></div>`;
  }).join('');
  return `<div class="article-list">${items}</div>`;
}

function renderBriefingText(text) {
  if (!text) return '';

  // Known section headers — anything else in **CAPS** is also a header
  const SECTION_HEADERS = new Set([
    'FORM & PERFORMANCE', 'MEDIA INTELLIGENCE', 'MARKET & CONTRACT',
    'RECOMMENDED ACTIONS', 'ALERTS', 'SUMMARY'
  ]);

  const SKIP_PATTERNS = [
    /^#{1,4}\s/,                                    // # markdown titles
    /^[-*_]{3,}\s*$/,                               // --- separators
    /^\*\*(PLAYER|CLUB|DATE|REPORT DATE|CLASSIFICATION|PREPARED|WEEK)[^*]*\*\*/i,
    /^\*[^*\n]{0,60}\*\s*$/,                        // *italic metadata line*
    /^\[.{0,40}\]\s*$/,                             // [Current Date] placeholders
    /^(player|club|date|classification|report date)\s*:/i,
    /^(agent use only|weekly cycle|prepared for)/i,
  ];

  const lines = text.split('\n');
  const parts = [];
  let inActionBlock = false;

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    const line = raw.trim();

    if (!line) {
      if (parts.length > 0 && parts[parts.length - 1] !== '<p class="brief-gap"></p>') {
        parts.push('<p class="brief-gap"></p>');
      }
      continue;
    }

    // Skip noise lines
    if (SKIP_PATTERNS.some(p => p.test(line))) continue;

    // Section header: **ALL CAPS TEXT** or **All Caps With &**
    const headerMatch = line.match(/^\*\*([A-Z][A-Z\s&]+)\*\*\s*$/);
    if (headerMatch || SECTION_HEADERS.has(line.replace(/\*\*/g, '').trim().toUpperCase())) {
      const label = (headerMatch ? headerMatch[1] : line.replace(/\*\*/g, '')).trim();
      inActionBlock = label === 'RECOMMENDED ACTIONS';
      parts.push(`<div class="brief-section-header">${label}</div>`);
      continue;
    }

    // Numbered action item (1. 2. 3.)
    const actionMatch = line.match(/^(\d+)\.\s+(.+)/);
    if (inActionBlock && actionMatch) {
      // Strip any **bold** inside action text
      const actionText = actionMatch[2].replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
      parts.push(`<div class="brief-action"><span class="brief-action-num">${actionMatch[1]}.</span> ${actionText}</div>`);
      continue;
    }

    // Regular paragraph — strip remaining **bold** markers as proper bold
    const para = line.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    parts.push(`<p class="brief-para">${para}</p>`);
  }

  return parts.join('');
}

function buildBriefingModule(p) {
  const ref = p.reflection || {};
  // Determine which model won
  const sonnetWon = ref.sonnet_score >= ref.flash_score;
  const winnerLabel = sonnetWon ? 'Claude Sonnet 4.6' : 'Gemini 2.5 Flash';
  const winnerScore = sonnetWon ? ref.sonnet_score : ref.flash_score;

  return `
    <div class="briefing-module">
      <div class="module-title">Weekly Intelligence Brief</div>
      <div class="briefing-pane">
        <div class="briefing-text">${renderBriefingText(p.briefing)}</div>
      </div>
      <div class="briefing-footer">
        <span>Generated ${p.last_updated} · ${winnerLabel} · score ${winnerScore}/9 · RAG-enhanced</span>
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
