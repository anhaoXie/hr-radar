/* 行业HR需求雷达 —— 前端逻辑。零外部依赖，图表全部手绘 SVG/CSS。 */
'use strict';

const S = {
  meta: null,
  skillNames: [],
  skillCategories: {},
  tab: 'radar',
  filters: { industry: 'all', city: '全国', source: 'all', keyword: '', days: 30 },
  analysis: null,
  jobs: [],
  jobPage: 0,
  pageSize: 30,
  mySkills: {},
  profiles: [],
  lastDiag: null,
  pollTimer: null,
  loaded: {},
};

/* ------------------------------ utils ------------------------------ */
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? '' : s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
const num = (v, d = 0) => (v == null || isNaN(v)) ? '—' : Number(v).toFixed(d);

function toast(msg, isErr) {
  const t = $('toast');
  t.textContent = msg;
  t.className = 'toast' + (isErr ? ' err' : '');
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.add('hidden'), 3200);
}

function banner(msg, kind) {
  const b = $('banner');
  if (!msg) { b.classList.add('hidden'); return; }
  b.className = 'banner' + (kind ? ' ' + kind : '');
  b.innerHTML = msg;
}

async function api(path, opts) {
  const r = await fetch(path, Object.assign({ headers: { 'Content-Type': 'application/json' } }, opts || {}));
  let j = null;
  try { j = await r.json(); } catch (e) { throw new Error('服务返回异常 (HTTP ' + r.status + ')'); }
  if (!r.ok || j.ok === false) throw new Error(j.error || ('HTTP ' + r.status));
  return j;
}
const qs = (o) => Object.keys(o).filter(k => o[k] !== '' && o[k] != null)
  .map(k => encodeURIComponent(k) + '=' + encodeURIComponent(o[k])).join('&');

const INDUSTRY_NAME = (id) => {
  if (!id || id === 'all') return '全部行业';
  const it = (S.meta.industries || []).find(x => x.id === id);
  return it ? it.name : id;
};

/* ------------------------------ charts ------------------------------ */
function barList(el, items, opt) {
  opt = opt || {};
  if (!items || !items.length) { el.innerHTML = '<div class="empty">暂无数据</div>'; return; }
  const max = Math.max.apply(null, items.map(i => Math.abs(opt.value(i)) || 0.0001));
  el.innerHTML = items.map(i => {
    const v = opt.value(i);
    const w = Math.max(1.5, Math.abs(v) / max * 100);
    const label = opt.label(i);
    const meta = opt.meta ? opt.meta(i) : '';
    return '<div class="bar-row ' + (opt.cls ? opt.cls(i) : '') + '">' +
      '<div class="bar-name" title="' + esc(label) + '">' + esc(label) + '</div>' +
      '<div class="bar-track"><div class="bar-fill" style="width:' + w.toFixed(1) + '%"></div></div>' +
      '<div class="bar-val">' + meta + '</div></div>';
  }).join('');
}

function gaugeSVG(score) {
  const R = 66, C = 84, range = 240; // 240 度表盘
  const startA = 150, endA = 150 + range;
  const a = startA + range * Math.max(0, Math.min(100, score)) / 100;
  const rad = (d) => d * Math.PI / 180;
  const pt = (ang, r) => [C + r * Math.cos(rad(ang)), C + r * Math.sin(rad(ang)) + 6];
  const arc = (a1, a2, r) => {
    const [x1, y1] = pt(a1, r), [x2, y2] = pt(a2, r);
    const large = (a2 - a1) > 180 ? 1 : 0;
    return 'M' + x1.toFixed(1) + ' ' + y1.toFixed(1) + ' A' + r + ' ' + r + ' 0 ' + large + ' 1 ' + x2.toFixed(1) + ' ' + y2.toFixed(1);
  };
  const color = score >= 75 ? '#2ecc8f' : score >= 50 ? '#4f8cff' : score >= 25 ? '#ffb020' : '#ff5c6c';
  const [tx, ty] = pt(a, R - 20);
  return '<svg width="168" height="158" viewBox="0 0 168 158">' +
    '<path d="' + arc(startA, endA, R) + '" fill="none" stroke="#202634" stroke-width="13" stroke-linecap="round"/>' +
    '<path d="' + arc(startA, Math.max(startA + 0.7, a), R) + '" fill="none" stroke="' + color + '" stroke-width="13" stroke-linecap="round"/>' +
    '<text x="' + tx.toFixed(1) + '" y="' + ty.toFixed(1) + '" fill="' + color + '" font-size="30" font-weight="800" text-anchor="middle">' + num(score, 0) + '%</text>' +
    '<text x="84" y="146" fill="#8d97ab" font-size="11" text-anchor="middle">岗位要求覆盖度</text>' +
    '</svg>';
}

function radarSVG(items) {
  items = (items || []).slice(0, 8);
  if (items.length < 3) return '<div class="empty">需要至少 3 项技能才能画雷达图</div>';
  const C = 168, R = 108;
  const n = items.length;
  const ang = (i) => (-90 + i * 360 / n) * Math.PI / 180;
  const pt = (i, v) => [C + (R * v / 5) * Math.cos(ang(i)), C + (R * v / 5) * Math.sin(ang(i))];
  const poly = (key) => items.map((it, i) => pt(i, it[key] || 0).map(v => v.toFixed(1)).join(',')).join(' ');

  let grid = '';
  for (let r = 1; r <= 5; r++) {
    const p = items.map((_, i) => pt(i, r).map(v => v.toFixed(1)).join(',')).join(' ');
    grid += '<polygon points="' + p + '" fill="none" stroke="#2a3142" stroke-width="1"' + (r === 5 ? '' : ' stroke-dasharray="3 3"') + '/>';
  }
  let axes = '', labels = '';
  items.forEach((it, i) => {
    const [x, y] = pt(i, 5);
    axes += '<line x1="' + C + '" y1="' + C + '" x2="' + x.toFixed(1) + '" y2="' + y.toFixed(1) + '" stroke="#2a3142" stroke-width="1"/>';
    const lx = C + (R + 26) * Math.cos(ang(i)), ly = C + (R + 26) * Math.sin(ang(i));
    const anchor = Math.abs(lx - C) < 8 ? 'middle' : (lx > C ? 'start' : 'end');
    labels += '<text x="' + lx.toFixed(1) + '" y="' + (ly + 4).toFixed(1) + '" fill="#8d97ab" font-size="10.5" text-anchor="' + anchor + '">' + esc(it.skill.slice(0, 10)) + '</text>';
  });
  return '<svg width="336" height="336" viewBox="0 0 336 336">' + grid + axes +
    '<polygon points="' + poly('market') + '" fill="rgba(255,176,32,.16)" stroke="#ffb020" stroke-width="2"/>' +
    '<polygon points="' + poly('me') + '" fill="rgba(79,140,255,.22)" stroke="#4f8cff" stroke-width="2"/>' +
    labels + '</svg>';
}

function lineSVG(points) {
  if (!points || points.length < 1) return '<div class="empty">暂无快照数据</div>';
  const W = 760, H = 210, PL = 46, PR = 16, PT = 16, PB = 34;
  const vals = points.map(p => p.job_count || 0);
  const maxV = Math.max.apply(null, vals.concat([1]));
  const n = points.length;
  const X = (i) => n === 1 ? PL + (W - PL - PR) / 2 : PL + (W - PL - PR) * i / (n - 1);
  const Y = (v) => PT + (H - PT - PB) * (1 - v / (maxV * 1.15));
  let grid = '';
  for (let g = 0; g <= 4; g++) {
    const v = maxV * 1.15 * g / 4, y = Y(v);
    grid += '<line x1="' + PL + '" y1="' + y.toFixed(1) + '" x2="' + (W - PR) + '" y2="' + y.toFixed(1) + '" stroke="#2a3142" stroke-dasharray="3 4"/>' +
      '<text x="' + (PL - 8) + '" y="' + (y + 4).toFixed(1) + '" fill="#6b7488" font-size="10" text-anchor="end">' + Math.round(v) + '</text>';
  }
  const line = points.map((p, i) => (i ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(p.job_count || 0).toFixed(1)).join(' ');
  const area = line + ' L' + X(n - 1).toFixed(1) + ' ' + (H - PB) + ' L' + X(0).toFixed(1) + ' ' + (H - PB) + ' Z';
  let dots = '', xlab = '';
  points.forEach((p, i) => {
    dots += '<circle cx="' + X(i).toFixed(1) + '" cy="' + Y(p.job_count || 0).toFixed(1) + '" r="3.5" fill="#4f8cff"/>';
    if (n <= 12 || i % Math.ceil(n / 8) === 0 || i === n - 1) {
      xlab += '<text x="' + X(i).toFixed(1) + '" y="' + (H - 12) + '" fill="#6b7488" font-size="10" text-anchor="middle">' + esc((p.day || '').slice(5)) + '</text>';
    }
  });
  return '<svg viewBox="0 0 ' + W + ' ' + H + '" style="width:100%;height:auto">' +
    '<defs><linearGradient id="tg" x1="0" y1="0" x2="0" y2="1">' +
    '<stop offset="0%" stop-color="rgba(79,140,255,.35)"/><stop offset="100%" stop-color="rgba(79,140,255,0)"/>' +
    '</linearGradient></defs>' + grid +
    '<path d="' + area + '" fill="url(#tg)"/>' +
    '<path d="' + line + '" fill="none" stroke="#4f8cff" stroke-width="2.2" stroke-linejoin="round"/>' +
    dots + xlab + '</svg>';
}

/* ------------------------------ init ------------------------------ */
async function boot() {
  try {
    S.meta = await api('/api/meta');
  } catch (e) {
    banner('无法连接后端服务：' + e.message, 'err');
    return;
  }
  S.skillNames = (await api('/api/skills')).names || [];
  document.title = S.meta.app.name + ' · 大学生职业规划';
  $('brandSub').textContent = 'v' + S.meta.app.version + ' · 实时岗位 · 职业规划';
  $('intervalHint').textContent = S.meta.settings.request_interval;

  fillFilters();
  fillSettings();
  fillSkillDatalist();
  bindEvents();
  renderSourceList();
  loadProfiles();
  loadRiskGuide();
  loadTimeline();
  loadSurvey();
  await loadAnalysis();
  refreshDbStat();
  // 支持带页签的深链，如 http://127.0.0.1:8770/#career
  const want = (location.hash || '').slice(1);
  if (want && want !== S.tab && document.getElementById('tab-' + want)) switchTab(want);
  // ?demo=1 一键示例：自动填档案并跑出诊断结果
  if (new URLSearchParams(location.search).get('demo') === '1') await applyDemo();
}

function fillFilters() {
  const ind = $('fIndustry');
  ind.innerHTML = '<option value="all">全部行业</option>' +
    (S.meta.industries || []).map(i => '<option value="' + esc(i.id) + '">' + esc(i.name) + '</option>').join('');
  ind.value = S.filters.industry;

  const city = $('fCity'), rc = $('refreshCity');
  const cities = (S.meta.cities || []);
  city.innerHTML = '<option value="全国">全国</option>' + cities.map(c => '<option value="' + esc(c) + '">' + esc(c) + '</option>').join('');
  rc.innerHTML = city.innerHTML;
  city.value = '全国';

  $('fSource').innerHTML = '<option value="all">全部数据源</option>' +
    (S.meta.sources || []).map(s => '<option value="' + esc(s.id) + '">' + esc(s.name) + '</option>').join('');

  $('refreshIndustries').innerHTML = (S.meta.industries || []).map(i =>
    '<label><input type="checkbox" value="' + esc(i.id) + '"' + (i.id === 'internet' ? ' checked' : '') + '>' + esc(i.name) + '</label>').join('');
  $('refreshSources').innerHTML = (S.meta.sources || []).map(s =>
    '<label><input type="checkbox" value="' + esc(s.id) + '"' + (s.enabled ? ' checked' : '') + '>' + esc(s.name) + '</label>').join('');
}

function fillSkillDatalist() {
  $('skillList').innerHTML = S.skillNames.map(n => '<option value="' + esc(n) + '">').join('');
}

function fillSettings() {
  const s = S.meta.settings;
  $('sMaxKw').value = s.max_keywords_per_refresh;
  $('sDetailLimit').value = s.detail_jd_limit;
  $('sInterval').value = s.request_interval;
  $('sConc').value = s.concurrency;
  $('sCity').value = s.default_city;
  $('sAuto').value = s.auto_refresh_minutes;
  $('sFetchJd').checked = !!s.fetch_jd;
  const c = s.custom_json || {};
  $('cUrl').value = c.url_template || '';
  $('cMethod').value = c.method || 'GET';
  $('cListPath').value = c.list_path || '';
  $('cHeaders').value = c.headers && Object.keys(c.headers).length ? JSON.stringify(c.headers, null, 2) : '';
  $('cBody').value = c.body_template || '';
  $('cMap').value = JSON.stringify(c.field_map || {}, null, 2);
}

/* ------------------------------ events ------------------------------ */
function bindEvents() {
  document.querySelectorAll('.nav-item').forEach(b => b.addEventListener('click', () => switchTab(b.dataset.tab)));
  $('btnApply').addEventListener('click', () => {
    S.filters = {
      industry: $('fIndustry').value, city: $('fCity').value, source: $('fSource').value,
      keyword: $('fKeyword').value.trim(), days: $('fDays').value,
    };
    S.loaded = {};
    loadAnalysis();
    if (S.tab === 'jobs') loadJobs(0);
    if (S.tab === 'trend') loadTrend();
  });
  $('btnQuickRefresh').addEventListener('click', () => { switchTab('refresh'); $('btnStartRefresh').click(); });
  $('btnExport').addEventListener('click', () => {
    window.location = '/api/export?' + qs({ industry: S.filters.industry, city: S.filters.city, source: S.filters.source, keyword: S.filters.keyword, days: S.filters.days });
  });
  $('jobsPrev').addEventListener('click', () => loadJobs(Math.max(0, S.jobPage - 1)));
  $('jobsNext').addEventListener('click', () => loadJobs(S.jobPage + 1));

  $('btnAddSkill').addEventListener('click', addSkillFromInput);
  $('skillAdd').addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); addSkillFromInput(); } });
  $('btnDiagnose').addEventListener('click', runDiagnose);
  $('btnMatch').addEventListener('click', runMatch);
  $('btnSaveProfile').addEventListener('click', saveProfile);
  $('profileList').addEventListener('change', loadProfile);
  $('btnSurvey').addEventListener('click', runSurvey);

  $('btnStartRefresh').addEventListener('click', startRefresh);
  $('btnStopPoll').addEventListener('click', () => { stopPoll(); $('btnStopPoll').style.display = 'none'; });
  $('btnSaveSettings').addEventListener('click', saveSettings);
  $('btnReindex').addEventListener('click', reindex);
  $('btnSaveCustom').addEventListener('click', saveCustom);

  document.querySelectorAll('#sourceList input[type=checkbox]').forEach(() => {});
  window.addEventListener('hashchange', () => {
    const t = (location.hash || '').slice(1);
    if (t && t !== S.tab && document.getElementById('tab-' + t)) switchTab(t);
  });
  $('modalClose').addEventListener('click', closeModal);
  $('modal').addEventListener('click', (e) => { if (e.target.id === 'modal') closeModal(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });
}

function switchTab(tab) {
  S.tab = tab;
  document.querySelectorAll('.nav-item').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.id === 'tab-' + tab));
  const titles = {
    radar: '需求雷达', jobs: '岗位明细', career: '职业规划', match: '岗位匹配',
    interview: '面试准备', survey: '方向测评', trend: '趋势追踪', refresh: '实时刷新', settings: '数据源设置',
  };
  $('pageTitle').textContent = titles[tab] || tab;
  // 深链：把当前页签写进地址栏，便于收藏 / 分享 / 刷新后停留在同一页
  if (location.hash.slice(1) !== tab) history.replaceState(null, '', '#' + tab);
  if (tab === 'jobs' && !S.loaded.jobs) loadJobs(0);
  if (tab === 'trend' && !S.loaded.trend) loadTrend();
  if (tab === 'interview' && !S.loaded.interview) loadInterview();
  if (tab === 'settings') refreshDbStat();
}

/* ------------------------------ 需求雷达 ------------------------------ */
async function loadAnalysis() {
  try {
    const j = await api('/api/analysis?' + qs({
      industry: S.filters.industry, city: S.filters.city, source: S.filters.source,
      keyword: S.filters.keyword, days: S.filters.days, top_n: 26,
    }));
    S.analysis = j.data;
    renderRadar(j.data);
    S.loaded.radar = true;
  } catch (e) { banner('加载分析失败：' + e.message, 'err'); }
}

function renderRadar(a) {
  const fc = a.freshness || {};
  $('kpis').innerHTML = [
    kpi(a.job_count, '岗位样本数', 'acc'),
    kpi((a.skills || []).length ? a.skills[0].name : '—', '最热门技能'),
    kpi(salaryHeadline(a), '薪资基准', 'hl'),
    kpi(fc.new_today != null ? fc.new_today : '—', '今日新入库'),
    kpi((a.company_top || []).length, '招聘公司数'),
    kpi((a.source_mix || []).length, '覆盖数据源'),
  ].join('');

  $('skillBars').innerHTML = '';
  barList($('skillBars'), a.skills || [], {
    value: i => i.share, label: i => i.name,
    meta: i => i.share + '% · ' + i.count + '岗',
    cls: i => i.demand >= 1.15 ? 'warn' : '',
  });

  barList($('catBars'), a.skill_categories || [], {
    value: i => i.share, label: i => i.name, meta: i => i.share + '%',
  });

  renderSalary(a.salary || {});
  renderDegreeCity(a);
  $('insights').innerHTML = (a.insights || []).map(t => '<li>' + esc(t) + '</li>').join('') ||
    '<li class="muted">暂无洞察</li>';
  barList($('companyTop'), (a.company_top || []).slice(0, 10), {
    value: i => i.count, label: i => i.name, meta: i => i.count + ' 岗',
  });
  barList($('sourceMix'), a.source_mix || [], {
    value: i => i.count, label: i => i.name, meta: i => i.count + ' 岗 (' + i.share + '%)',
  });
  $('freshBox').innerHTML =
    '新鲜度：今日新增 <b>' + (fc.new_today || 0) + '</b> 条，昨日 <b>' + (fc.new_yesterday || 0) +
    '</b> 条，近 7 天 <b>' + (fc.new_7d || 0) + '</b> 条。<br>“新入库”指本次抓取首次出现在你本地库里的岗位，是需求变动最直接的信号。';

  const last = (S.meta.db.runs || [])[0];
  $('lastRefresh').textContent = last
    ? ('最近刷新：' + (last.finished_at || last.started_at || '').replace('T', ' ').slice(5, 16) + ' · ' + last.status)
    : '尚未刷新';
}

function kpi(v, k, cls) {
  return '<div class="kpi ' + (cls || '') + '"><div class="v">' + esc(v) + '</div><div class="k">' + esc(k) + '</div></div>';
}

function salaryHeadline(a) {
  const c = (a.salary || {}).CNY || {};
  if (c.day) return '¥' + num(c.day.median) + '/天';
  if (c.month) return '¥' + num(c.month.median) + '/月';
  const u = (a.salary || {}).USD;
  if (u && u.year) return '$' + num(u.year.median) + '/年';
  return '—';
}

function renderSalary(sal) {
  const keys = Object.keys(sal);
  if (!keys.length) { $('salaryBox').innerHTML = '<div class="empty">岗位未提供薪资信息</div>'; return; }
  let html = '';
  keys.forEach(cur => {
    const s = sal[cur], sym = cur === 'USD' ? '$' : '¥';
    const blocks = [];
    if (s.day) blocks.push(['日薪', s.day, sym, '/天']);
    if (s.month) blocks.push(['月薪（折算）', s.month, sym, '/月']);
    if (s.year) blocks.push(['年薪', s.year, sym, '/年']);
    if (!blocks.length) return;
    html += '<div style="margin-bottom:14px"><div class="hint" style="margin-bottom:7px">币种：' + esc(cur) + '</div>';
    blocks.forEach(([label, d, sy, unit]) => {
      html += '<div style="margin-bottom:10px">' +
        '<div style="font-size:12.5px;margin-bottom:5px"><b>' + label + '</b> 中位数 <b style="color:#4f8cff">' +
        sy + num(d.median) + '</b>' + unit + ' <span class="hint">（样本 ' + d.n + ' 条，均值 ' + sy + num(d.avg) + '）</span></div>' +
        '<div class="bar-track" style="height:10px"><div class="bar-fill" style="width:' +
        Math.max(2, Math.min(100, (d.median / (d.max || 1)) * 100)).toFixed(1) + '%"></div></div>' +
        '<div class="hint" style="margin-top:4px">P25 ' + sy + num(d.p25) + ' · 中位 ' + sy + num(d.median) +
        ' · P75 ' + sy + num(d.p75) + ' · 区间 ' + sy + num(d.min) + '–' + sy + num(d.max) + '</div></div>';
    });
    html += '</div>';
  });
  $('salaryBox').innerHTML = html || '<div class="empty">岗位未提供可解析的薪资</div>';
}

function renderDegreeCity(a) {
  let h = '<div class="hint" style="margin-bottom:6px">学历要求</div>';
  h += (a.degree || []).map(d =>
    '<div class="bar-row"><div class="bar-name">' + esc(d.name) + '</div><div class="bar-track"><div class="bar-fill" style="width:' +
    Math.max(2, d.share) + '%"></div></div><div class="bar-val">' + d.share + '%</div></div>').join('') || '<div class="empty">无数据</div>';
  h += '<div class="hint" style="margin:14px 0 6px">城市分布 Top</div>';
  h += (a.city_top || []).slice(0, 8).map(d =>
    '<div class="bar-row"><div class="bar-name">' + esc(d.name) + '</div><div class="bar-track"><div class="bar-fill" style="width:' +
    Math.max(2, d.share) + '%"></div></div><div class="bar-val">' + d.count + ' 岗</div></div>').join('') || '<div class="empty">无数据</div>';
  $('degreeCity').innerHTML = h;
}

/* ------------------------------ 岗位明细 ------------------------------ */
async function loadJobs(page) {
  S.jobPage = page;
  try {
    const j = await api('/api/jobs?' + qs({
      industry: S.filters.industry, city: S.filters.city, source: S.filters.source,
      keyword: S.filters.keyword, days: S.filters.days, limit: 600,
      offset: page * S.pageSize, page_size: S.pageSize,
    }));
    S.jobs = j.jobs || [];
    S.loaded.jobs = true;
    $('jobsCount').textContent = '匹配 ' + j.total + ' 条，当前第 ' + (page + 1) + ' 页';
    $('jobsPage').textContent = '第 ' + (page + 1) + ' 页';
    const tb = document.querySelector('#jobsTable tbody');
    if (!S.jobs.length) {
      tb.innerHTML = '<tr><td colspan="8" class="empty">没有岗位。先到「实时刷新」抓取数据，或放宽筛选条件。</td></tr>';
      return;
    }
    tb.innerHTML = S.jobs.map((j2, i) => '<tr>' +
      '<td><span class="t-title" data-i="' + i + '">' + esc(j2.title) + '</span>' +
      (j2.job_type ? '<div class="hint">' + esc(j2.job_type) + (j2.industry_name ? ' · ' + esc(j2.industry_name) : '') + '</div>' : '') + '</td>' +
      '<td>' + esc(j2.company || '—') + '</td>' +
      '<td>' + esc(j2.city || '—') + '</td>' +
      '<td>' + esc(j2.degree || '—') + '</td>' +
      '<td>' + esc(j2.salary_raw || '—') + '</td>' +
      '<td>' + (j2.skills || []).slice(0, 6).map(s => '<span class="chip">' + esc(s) + '</span>').join('') + '</td>' +
      '<td>' + esc(sourceName(j2.source)) + '</td>' +
      '<td class="hint">' + esc((j2.last_seen || '').replace('T', ' ').slice(5, 16)) + '</td>' +
      '</tr>').join('');
    tb.querySelectorAll('.t-title').forEach(el => el.addEventListener('click', () => openJob(S.jobs[+el.dataset.i])));
  } catch (e) { banner('加载岗位失败：' + e.message, 'err'); }
}

function sourceName(id) {
  const s = (S.meta.sources || []).find(x => x.id === id);
  return s ? s.name : id;
}

async function openJob(j) {
  openModal('<div class="empty">加载中…</div>');
  try {
    const r = await api('/api/job?' + qs({ source: j.source, uid: j.uid }));
    const job = r.job;
    const risks = (job.risk || []).map(k =>
      '<div class="risk ' + esc(k.level) + '"><b>[' + esc(k.level) + '风险]</b> ' + esc(k.desc) +
      '<div class="hint" style="color:inherit;opacity:.85">' + esc(k.advice) + '</div></div>').join('');
    openModal(
      '<h3>' + esc(job.title) + '</h3>' +
      '<div class="jmeta">' +
      '<span>公司 <b>' + esc(job.company || '—') + '</b></span>' +
      '<span>城市 <b>' + esc(job.city || '—') + '</b></span>' +
      '<span>学历 <b>' + esc(job.degree || '—') + '</b></span>' +
      '<span>薪资 <b>' + esc(job.salary_raw || '—') + '</b></span>' +
      '<span>来源 <b>' + esc(sourceName(job.source)) + '</b></span>' +
      '<span>类型 <b>' + esc(job.job_type || '—') + '</b></span>' +
      '</div>' +
      '<div class="seclabel">岗位要求技能（本工具从 JD 自动抽取）</div>' +
      ((job.skills || []).length ? (job.skills || []).map(s => '<span class="chip">' + esc(s) + '</span>').join('') : '<span class="hint">未能从该岗位抽取到明确技能</span>') +
      '<div class="seclabel">风险提示</div>' + risks +
      '<div class="seclabel">岗位描述原文</div>' +
      '<div class="jd">' + (job.jd ? esc(job.jd) : '<span class="hint">该岗位没有抓到详情正文（可在「数据源设置」里开启 JD 补全后重新刷新）</span>') + '</div>' +
      (job.url ? '<div style="margin-top:14px"><a class="btn small" href="' + esc(job.url) + '" target="_blank" rel="noopener">打开原始岗位页 ↗</a></div>' : '')
    );
  } catch (e) { openModal('<div class="banner err">加载失败：' + esc(e.message) + '</div>'); }
}

function openModal(html) { $('modalBody').innerHTML = html; $('modal').classList.remove('hidden'); }
function closeModal() { $('modal').classList.add('hidden'); }

/* ------------------------------ 职业规划 ------------------------------ */
function addSkillFromInput() {
  const v = $('skillAdd').value.trim();
  if (!v) return;
  S.mySkills[v] = S.mySkills[v] || 3;
  $('skillAdd').value = '';
  renderMySkills();
}

function renderMySkills() {
  const keys = Object.keys(S.mySkills);
  $('mySkills').innerHTML = keys.length ? keys.map(k =>
    '<span class="skill-chip"><b>' + esc(k) + '</b>' +
    '<input type="range" min="1" max="5" step="1" value="' + S.mySkills[k] + '" data-k="' + esc(k) + '">' +
    '<span class="lv">' + S.mySkills[k] + '</span>' +
    '<span class="x" data-del="' + esc(k) + '">×</span></span>').join('')
    : '<span class="hint">还没有添加技能。可以先从下面的「热门技能」快速点选。</span>';
  $('mySkills').querySelectorAll('input[type=range]').forEach(r => {
    r.addEventListener('input', () => {
      S.mySkills[r.dataset.k] = +r.value;
      r.parentNode.querySelector('.lv').textContent = r.value;
    });
  });
  $('mySkills').querySelectorAll('.x').forEach(x => x.addEventListener('click', () => {
    delete S.mySkills[x.dataset.del]; renderMySkills();
  }));
}

function renderQuickPick() {
  const a = S.analysis;
  const top = (a && a.skills ? a.skills.slice(0, 16) : []).map(s => s.name);
  $('quickPick').innerHTML = '<span class="hint" style="align-self:center;margin-right:4px">热门技能快速添加：</span>' +
    top.map(n => '<span class="qp" data-s="' + esc(n) + '">+ ' + esc(n) + '</span>').join('');
  $('quickPick').querySelectorAll('.qp').forEach(el => el.addEventListener('click', () => {
    S.mySkills[el.dataset.s] = S.mySkills[el.dataset.s] || 3; renderMySkills();
  }));
}

function collectProfile() {
  return {
    major: $('pMajor').value.trim(),
    degree: $('pDegree').value,
    grade: $('pGrade').value,
    city_pref: $('pCity').value.trim(),
    target_job: $('pJob').value.trim(),
    skills: S.mySkills,
  };
}

async function runDiagnose() {
  const p = collectProfile();
  if (!Object.keys(p.skills).length) { toast('请先添加至少 1 个你会（或正在学）的技能', true); return; }
  $('diagnoseBody').innerHTML = '<div class="empty">诊断中…</div>';
  try {
    const j = await api('/api/diagnose', {
      method: 'POST',
      body: JSON.stringify({ profile: p, industry: S.filters.industry, city: S.filters.city, days: S.filters.days }),
    });
    S.lastDiag = j.data;
    renderDiagnose(j.data);
  } catch (e) { $('diagnoseBody').innerHTML = '<div class="banner err">诊断失败：' + esc(e.message) + '</div>'; }
}

function renderDiagnose(d) {
  const note = d.data_source === 'prior'
    ? '<div class="banner" style="margin-bottom:12px">' + esc(d.data_note) + '</div>' : '';
  $('diagnoseBody').innerHTML = note +
    '<div class="gauge">' + gaugeSVG(d.match_score) +
    '<div class="gauge-text"><div class="big">' + esc(d.summary) + '</div>' +
    '<div class="mini-note">行业：<b>' + esc(d.industry_name) + '</b> · 城市：' + esc(d.city) +
    ' · 市场要求技能 ' + d.market_skill_count + ' 项 · 你已填 ' + d.profile.skill_count + ' 项</div></div></div>' +
    '<div class="seclabel">能力对照雷达图</div>' +
    '<div class="radar-wrap">' + radarSVG(d.radar) + '</div>' +
    '<div class="legend"><span><i class="dot" style="background:#ffb020"></i>市场要求强度</span>' +
    '<span><i class="dot" style="background:#4f8cff"></i>我的水平（自评）</span></div>' +
    umbrellaNote(d.umbrella_credited) +
    '<div class="seclabel">优先补齐清单（按性价比排序）</div>' +
    '<div class="gap-list">' + ((d.gaps || []).length ? d.gaps.map((g, i) =>
      '<div class="gap-item ' + (i < 3 ? 'p1' : i < 6 ? 'p2' : 'p3') + '">' +
      '<div class="rank">' + (i + 1) + '</div><div><b>' + esc(g.skill) + '</b>' +
      '<span class="chip" style="margin-left:6px">' + esc(g.category) + '</span>' +
      '<div class="gap-meta">市场要求 ' + g.market_level + '/5（' + g.market_share + '% 的岗位提到） · 我的水平 ' + g.my_level + '/5 · 缺口 ' + g.gap + '</div></div>' +
      '<div class="hint">' + (g.in_market_top ? '高频' : '') + '</div></div>').join('')
      : '<div class="empty">没有明显缺口，你的技能组合已经覆盖主要要求 🎉</div>') + '</div>' +
    ((d.strengths || []).length ? '<div class="seclabel">你的优势</div>' +
      d.strengths.map(s => '<span class="chip hit">' + esc(s.skill) + ' ' + s.my_level + '/5</span>').join('') : '') +
    ((d.extra_skills || []).length ? '<div class="seclabel">你会的、但市场要求里没有的技能</div>' +
      d.extra_skills.map(s => '<span class="chip">' + esc(s) + '</span>').join('') +
      '<div class="mini-note">这些不一定是无效技能——跨领域组合往往就是差异化优势；但如果它们和你的目标岗位完全无关，要警惕精力分散。</div>' : '');

  renderPath(d.learning_path);
  renderHardChecks(d.hard_checks);
  renderMajorFit(d.major_fit);
  renderTimeline(d.timeline);
  renderQuickPick();
}

function umbrellaNote(credited) {
  const keys = Object.keys(credited || {});
  if (!keys.length) return '';
  return '<div class="mini-note">已按能力归并：' +
    keys.map(k => '你填的「' + esc((credited[k] || []).join('、')) + '」已计入「' + esc(k) + '」').join('；') +
    '。上位技能不再重复计为缺口，但仍按你填的熟练度打分。</div>';
}

function renderPath(lp) {
  if (!lp || !lp.phases) { $('pathCard').style.display = 'none'; return; }
  $('pathCard').style.display = '';
  $('pathBody').innerHTML = lp.phases.map(ph => {
    if (!ph.tasks.length) return '';
    return '<div class="phase"><h4>' + esc(ph.title) + '</h4><div class="pdesc">' + esc(ph.desc) + '</div>' +
      ph.tasks.map(t => '<div class="task"><div class="tname">' + esc(t.skill) +
        '<span class="chip">' + esc(t.category) + '</span></div>' +
        '<div class="gap-meta">' + esc(t.why) + '</div>' +
        '<ul>' + t.learn.map(l => '<li>' + esc(l) + '</li>').join('') + '</ul>' +
        '<div class="proj">可以做的小项目：' + esc(t.project) + '</div>' +
        '<div class="prove">要拿出的证明：' + esc(t.prove) + '</div></div>').join('') + '</div>';
  }).join('') + '<div class="mini-note">' + esc(lp.advice) + '</div>';
}

function renderHardChecks(checks) {
  $('hardChecks').innerHTML = (checks || []).map(c =>
    '<div class="check-row"><div class="check-mark ' + (c.pass ? 'ok' : 'no') + '">' + (c.pass ? '✓' : '!') + '</div>' +
    '<div><b>' + esc(c.name) + '</b><div class="hint" style="margin-top:2px">' + esc(c.detail) + '</div>' +
    (c.fix ? '<div class="fix">→ ' + esc(c.fix) + '</div>' : '') + '</div></div>').join('') || '<div class="empty">暂无</div>';
}

function renderMajorFit(mf) {
  if (!mf) { $('majorFit').innerHTML = '<div class="empty">暂无</div>'; return; }
  const cls = mf.fit_level === '高' ? 'hit' : mf.fit_level === '低' ? 'miss' : '';
  $('majorFit').innerHTML = '<div style="font-size:13px"><span class="chip ' + cls + '">对口度：' + esc(mf.fit_level) + '</span></div>' +
    '<div style="font-size:12.5px;margin-top:9px;line-height:1.7">' + esc(mf.message) + '</div>' +
    (mf.advice ? '<div class="mini-note">' + esc(mf.advice) + '</div>' : '') +
    ((mf.suggested || []).length ? '<div class="seclabel">该行业常见对口专业</div>' +
      mf.suggested.map(s => '<span class="chip">' + esc(s) + '</span>').join('') : '');
}

function renderTimeline(tl) {
  if (!tl) return;
  $('timelineGrade').textContent = '当前：' + tl.grade;
  $('timeline').innerHTML = tl.stages.map(s =>
    '<div class="tl-item"><h4>' + esc(s.title) + '</h4><ul>' +
    s.actions.map(a => '<li>' + esc(a) + '</li>').join('') + '</ul></div>').join('');
}

async function loadTimeline() {
  try { const j = await api('/api/timeline?grade=' + encodeURIComponent($('pGrade').value)); renderTimeline(j.data); } catch (e) {}
}

async function loadRiskGuide() {
  try {
    const j = await api('/api/risk-guide');
    const d = j.data;
    $('riskGuide').innerHTML = '<b style="color:#ffb020">' + esc(d.title) + '</b><ul style="margin:7px 0 0;padding-left:17px">' +
      d.items.map(i => '<li>' + esc(i) + '</li>').join('') + '</ul>' +
      '<div style="margin-top:7px">依据：' + esc(d.source) + '</div>';
  } catch (e) {}
}

/* ------------------------------ 档案 ------------------------------ */
async function loadProfiles() {
  try {
    const j = await api('/api/profiles');
    S.profiles = j.profiles || [];
    $('profileList').innerHTML = '<option value="">载入已存档案…</option>' +
      S.profiles.map(p => '<option value="' + p.id + '">' + esc(p.name) + '</option>').join('');
  } catch (e) {}
}

async function saveProfile() {
  const name = prompt('给这份档案起个名字：', ($('pMajor').value || '我的') + ' - ' + ($('pJob').value || '档案'));
  if (!name) return;
  try {
    await api('/api/profiles', { method: 'POST', body: JSON.stringify({ name: name, data: collectProfile() }) });
    toast('档案已保存');
    loadProfiles();
  } catch (e) { toast('保存失败：' + e.message, true); }
}

function loadProfile() {
  const id = +$('profileList').value;
  if (!id) return;
  const p = S.profiles.find(x => x.id === id);
  if (!p) return;
  const d = p.data || {};
  $('pMajor').value = d.major || ''; $('pDegree').value = d.degree || '本科';
  $('pGrade').value = d.grade || '大三'; $('pCity').value = d.city_pref || '';
  $('pJob').value = d.target_job || '';
  S.mySkills = d.skills || {};
  renderMySkills(); loadTimeline();
  toast('已载入档案：' + p.name);
}

/* ------------------------------ 岗位匹配 ------------------------------ */
async function runMatch() {
  const p = collectProfile();
  if (!Object.keys(p.skills || {}).length) { toast('请先添加技能', true); return; }
  $('matchList').innerHTML = '<div class="empty">匹配中…</div>';
  try {
    const j = await api('/api/match', { method: 'POST', body: JSON.stringify({ profile: p, industry: S.filters.industry, city: S.filters.city }) });
    const d = j.data;
    if (!d.ok) { $('matchList').innerHTML = '<div class="empty">' + esc(d.message) + '</div>'; return; }
    $('matchAdvice').textContent = d.advice + '（已扫描 ' + d.scanned + ' 条岗位）';
    $('matchList').innerHTML = d.jobs.map(x => {
      const color = x.score >= 70 ? '#2ecc8f' : x.score >= 45 ? '#4f8cff' : '#ffb020';
      return '<div class="match-item"><div class="match-top"><div>' +
        '<div class="match-title">' + esc(x.title) + '</div>' +
        '<div class="match-sub">' + esc(x.company || '—') + ' · ' + esc(x.city) + ' · ' + esc(x.degree) +
        ' · ' + esc(x.salary_raw || '薪资未标') + ' · ' + esc(sourceName(x.source)) +
        ' · JD 识别出 ' + (x.evidence || 0) + ' 项技能</div></div>' +
        '<div class="match-score" style="color:' + color + '">' + x.score + '<small>匹配度</small></div></div>' +
        '<div style="margin-top:8px">' + (x.hit || []).map(s => '<span class="chip hit">✓ ' + esc(s) + '</span>').join('') +
        (x.miss || []).slice(0, 6).map(s => '<span class="chip miss">缺 ' + esc(s) + '</span>').join('') + '</div>' +
        '<div class="match-reason">' + esc(x.reason) + '</div>' +
        (x.url ? '<div style="margin-top:9px"><a class="btn small" href="' + esc(x.url) + '" target="_blank" rel="noopener">查看原始岗位 ↗</a></div>' : '') +
        '</div>';
    }).join('') || '<div class="empty">没有可匹配的岗位</div>';
  } catch (e) { $('matchList').innerHTML = '<div class="banner err">匹配失败：' + esc(e.message) + '</div>'; }
}

/* ------------------------------ 面试 ------------------------------ */
async function loadInterview() {
  try {
    const j = await api('/api/interview?' + qs({ industry: S.filters.industry, city: S.filters.city, target_job: $('pJob').value }));
    const d = j.data;
    S.loaded.interview = true;
    $('interviewTech').innerHTML = d.technical.map(q => qaItem(q)).join('');
    $('interviewBehavior').innerHTML = d.behavioral.map(q => qaItem(q)).join('');
    $('interviewChecklist').innerHTML = d.checklist.map((c, i) =>
      '<div class="check-item"><span class="n">' + (i + 1) + '</span><span>' + esc(c) + '</span></div>').join('');
    $('interviewNote').innerHTML = esc(d.note) + '<br>' + esc(d.evidence);
  } catch (e) { $('interviewTech').innerHTML = '<div class="banner err">加载失败：' + esc(e.message) + '</div>'; }
}
function qaItem(q) {
  return '<div class="qa-item"><div class="qa-q">' + esc(q.q) + '</div>' +
    '<div class="qa-why">为什么问：' + esc(q.why) + '</div>' +
    '<div class="qa-how">怎么答：' + esc(q.how) + '</div></div>';
}

/* ------------------------------ 方向测评 ------------------------------ */
const DIMS = [
  ['data', '和数据、逻辑打交道', '喜欢从数字里找规律、做推理'],
  ['people', '和人打交道', '喜欢沟通、说服、协调'],
  ['build', '动手做出实物/系统', '喜欢把东西真正造出来、跑起来'],
  ['create', '创意与表达', '喜欢写作、设计、内容创作'],
  ['order', '规则与流程', '喜欢清晰规范、稳定可预期的环境'],
  ['research', '钻研与研究', '喜欢深挖原理、长期研究一个问题'],
];

function loadSurvey() {
  $('surveyForm').innerHTML = DIMS.map(d =>
    '<div class="sv-row"><div><b>' + esc(d[1]) + '</b><span class="sv-sub">' + esc(d[2]) + '</span></div>' +
    '<input type="range" min="0" max="5" step="1" value="3" data-dim="' + d[0] + '">' +
    '<div class="sv-val" id="sv-' + d[0] + '">3</div></div>').join('');
  $('surveyForm').querySelectorAll('input[type=range]').forEach(r => {
    r.addEventListener('input', () => { $('sv-' + r.dataset.dim).textContent = r.value; });
  });
}

async function runSurvey() {
  const scores = {};
  $('surveyForm').querySelectorAll('input[type=range]').forEach(r => { scores[r.dataset.dim] = +r.value; });
  try {
    const j = await api('/api/survey', { method: 'POST', body: JSON.stringify({ scores: scores }) });
    const d = j.data;
    if (!d.ok) { toast(d.message, true); return; }
    $('surveyResultCard').style.display = '';
    $('surveyResult').innerHTML = d.ranked.map((r, i) =>
      '<div class="sv-item"><div class="sv-rank">' + (i + 1) + '</div>' +
      '<div><b>' + esc(r.industry_name) + '</b>' +
      '<div class="why">' + esc(r.why) + '</div>' +
      '<div class="maj">常见对口专业：' + esc((r.majors || []).join('、') || '—') + '</div></div>' +
      '<div class="sv-score">' + r.score + '</div></div>').join('') +
      '<div class="mini-note">测评只是起点，不是判决。想验证某个方向，成本最低的办法是：按「职业规划」页给出的学习路径做一个小项目，再点「岗位匹配」看看真实岗位。' +
      '调查显示 67.06% 的受访者认为「求职目标不明确」是就业主要困难，越早试错成本越低。</div>';
  } catch (e) { toast('测评失败：' + e.message, true); }
}

/* ------------------------------ 趋势 ------------------------------ */
async function loadTrend() {
  try {
    const j = await api('/api/trend?' + qs({ industry: S.filters.industry, city: S.filters.city }));
    const d = j.data;
    S.loaded.trend = true;
    $('trendChart').innerHTML = lineSVG(d.points);
    $('trendNote').innerHTML = esc(d.note || '') +
      ((d.points || []).length < 2 && !d.note
        ? '<br>目前只有 1 个快照点，还看不出变化。再刷新一次（或过几天再刷新）就会出现完整的趋势对比。' : '') +
      (d.compare ? '<br>对比：' + esc((d.compare.from || '').slice(0, 16)) + ' → ' + esc((d.compare.to || '').slice(0, 16)) +
        '，岗位量 ' + d.compare.from_count + ' → ' + d.compare.to_count +
        '（' + ((d.job_count_delta || 0) >= 0 ? '+' : '') + (d.job_count_delta || 0) + '）' : '') +
      '<br>说明：快照是每次刷新时该行业的岗位构成（按城市对齐），用于观察技能需求的结构性变化，而不是全网岗位总量的变化。';
    const up = (d.skill_delta || []).filter(x => x.share_delta > 0).slice(0, 10);
    const down = (d.skill_delta || []).filter(x => x.share_delta < 0).slice(-10).reverse();
    barList($('trendUp'), up, { value: x => x.share_delta, label: x => x.name, meta: x => '+' + x.share_delta + 'pp', cls: () => 'up' });
    barList($('trendDown'), down, { value: x => Math.abs(x.share_delta), label: x => x.name, meta: x => x.share_delta + 'pp', cls: () => 'down' });
    loadHistory();
  } catch (e) { $('trendChart').innerHTML = '<div class="banner err">加载失败：' + esc(e.message) + '</div>'; }
}

async function loadHistory() {
  try {
    const j = await api('/api/history?limit=15');
    $('runHistory').innerHTML = (j.runs || []).map(r =>
      '<div class="run-item"><span class="st ' + esc(r.status) + '">' + esc(r.status) + '</span>' +
      '<div><b>#' + r.id + '</b> ' + esc((r.industries || []).join('、') || '全部') +
      ' · ' + esc(r.city || '全国') + '<div class="hint">关键词：' + esc((r.keywords || []).join('、') || '默认') + '</div></div>' +
      '<div class="hint" style="text-align:right">新增 ' + r.inserted + ' / 更新 ' + r.updated +
      '<br>' + esc((r.finished_at || r.started_at || '').replace('T', ' ').slice(5, 16)) + '</div></div>').join('') ||
      '<div class="empty">还没有刷新记录</div>';
  } catch (e) {}
}

/* ------------------------------ 刷新 ------------------------------ */
async function startRefresh() {
  const inds = Array.from($('refreshIndustries').querySelectorAll('input:checked')).map(i => i.value);
  const srcs = Array.from($('refreshSources').querySelectorAll('input:checked')).map(i => i.value);
  const kws = $('refreshKeywords').value.split(/[,，]/).map(s => s.trim()).filter(Boolean);
  if (!inds.length && !kws.length) { toast('至少选一个行业，或填一个关键词', true); return; }
  if (!srcs.length) { toast('至少选一个数据源', true); return; }
  try {
    $('btnStartRefresh').disabled = true;
    const j = await api('/api/refresh', {
      method: 'POST',
      body: JSON.stringify({ industries: inds, keywords: kws, city: $('refreshCity').value, sources: srcs }),
    });
    toast('刷新已启动');
    $('refreshProgress').classList.remove('hidden');
    $('btnStopPoll').style.display = '';
    renderProgress(j.progress);
    startPoll();
  } catch (e) {
    $('btnStartRefresh').disabled = false;
    toast('启动失败：' + e.message, true);
  }
}

function startPoll() {
  stopPoll();
  S.pollTimer = setInterval(pollOnce, 1500);
}
function stopPoll() { if (S.pollTimer) { clearInterval(S.pollTimer); S.pollTimer = null; } }

async function pollOnce() {
  try {
    const j = await api('/api/refresh/status');
    if (!j.progress) return;
    renderProgress(j.progress);
    if (j.progress.finished) {
      stopPoll();
      $('btnStartRefresh').disabled = false;
      $('btnStopPoll').style.display = 'none';
      toast('刷新完成：新增 ' + j.progress.inserted + ' 条，更新 ' + j.progress.updated + ' 条');
      S.loaded = {};
      S.meta.db.runs = (await api('/api/history?limit=5')).runs;
      await loadAnalysis();
      refreshDbStat();
      if (S.tab === 'trend') loadTrend();
    }
  } catch (e) { stopPoll(); $('btnStartRefresh').disabled = false; }
}

function renderProgress(p) {
  if (!p) return;
  $('refreshProgress').classList.remove('hidden');
  $('refreshKpis').innerHTML = [
    kpi(p.status, '状态'), kpi(p.fetched, '抓到岗位'), kpi(p.inserted, '新增'),
    kpi(p.updated, '更新'), kpi(p.detail_done, '补全JD'), kpi(p.elapsed + 's', '已用时'),
  ].join('');
  $('refreshLog').textContent = (p.logs || []).join('\n') +
    ((p.errors || []).length ? '\n\n错误：\n' + p.errors.join('\n') : '');
  $('refreshLog').scrollTop = $('refreshLog').scrollHeight;
}

async function refreshDbStat() {
  try {
    const j = await api('/api/analysis?' + qs({ industry: 'all', days: '' }));
    const mix = j.data.source_mix || [];
    $('sourceStat').innerHTML = '';
    barList($('sourceStat'), mix, { value: i => i.count, label: i => sourceName(i.name), meta: i => i.count + ' 岗' });
    const total = S.meta.db.jobs;
    $('dbStat').textContent = '岗位库：' + total + ' 条 · ' + mix.length + ' 个源';
  } catch (e) {}
}

/* ------------------------------ 设置 ------------------------------ */
function renderSourceList() {
  $('sourceList').innerHTML = (S.meta.sources || []).map(s =>
    '<div class="src-item"><label class="switch"><input type="checkbox" data-sid="' + esc(s.id) + '"' + (s.enabled ? ' checked' : '') + '><span class="slider"></span></label>' +
    '<div class="src-main"><div class="src-name">' + esc(s.name) +
    '<span class="tag ' + esc(s.region) + '">' + (s.region === 'cn' ? '中国市场' : '国际市场') + '</span>' +
    '<span class="tag">' + esc(s.kind) + '</span>' +
    (s.region === 'cn' && s.id === 'custom_json' ? '<span class="tag ' + (s.ready ? 'ready' : 'notready') + '">' + (s.ready ? '已配置' : '待配置') + '</span>' : '') +
    '</div><div class="src-note">' + esc(s.note) + '</div></div></div>').join('');
  $('sourceList').querySelectorAll('input[data-sid]').forEach(cb => cb.addEventListener('change', async () => {
    const patch = { sources: {} };
    patch.sources[cb.dataset.sid] = cb.checked;
    try {
      await api('/api/settings', { method: 'POST', body: JSON.stringify(patch) });
      const s = S.meta.sources.find(x => x.id === cb.dataset.sid);
      if (s) s.enabled = cb.checked;
      const rc = $('refreshSources').querySelector('input[value="' + cb.dataset.sid + '"]');
      if (rc) rc.checked = cb.checked;
      toast('已' + (cb.checked ? '启用' : '关闭') + '：' + (s ? s.name : cb.dataset.sid));
    } catch (e) { toast('保存失败：' + e.message, true); }
  }));
}

async function saveSettings() {
  const patch = {
    max_keywords_per_refresh: +$('sMaxKw').value,
    detail_jd_limit: +$('sDetailLimit').value,
    request_interval: +$('sInterval').value,
    concurrency: +$('sConc').value,
    default_city: $('sCity').value,
    auto_refresh_minutes: +$('sAuto').value,
    fetch_detail_jd: $('sFetchJd').checked,
  };
  try {
    const j = await api('/api/settings', { method: 'POST', body: JSON.stringify({ settings: patch }) });
    S.meta.settings = j.settings;
    $('intervalHint').textContent = j.settings.request_interval;
    $('settingsMsg').textContent = '已保存 ' + new Date().toLocaleTimeString();
    toast('设置已保存');
  } catch (e) { toast('保存失败：' + e.message, true); }
}

async function reindex() {
  const btn = $('btnReindex');
  btn.disabled = true;
  $('settingsMsg').textContent = '正在重算…';
  try {
    const j = await api('/api/reindex', { method: 'POST', body: JSON.stringify({}) });
    const d = j.data;
    $('settingsMsg').textContent = d.ok
      ? `已重算 ${d.updated} 条，其中 ${d.changed} 条标签发生变化（${d.with_jd} 条用 JD 正文抽取）`
      : (d.message || '未执行');
    toast('技能标签已用最新词典重算');
    S.loaded = {};
    await loadAnalysis();
  } catch (e) {
    $('settingsMsg').textContent = '重算失败：' + e.message;
  } finally {
    btn.disabled = false;
  }
}

async function saveCustom() {
  let headers = {}, fmap = {};
  try { headers = $('cHeaders').value.trim() ? JSON.parse($('cHeaders').value) : {}; }
  catch (e) { toast('请求头不是合法 JSON', true); return; }
  try { fmap = $('cMap').value.trim() ? JSON.parse($('cMap').value) : {}; }
  catch (e) { toast('字段映射不是合法 JSON', true); return; }
  const patch = {
    custom_json: {
      url_template: $('cUrl').value.trim(), method: $('cMethod').value,
      list_path: $('cListPath').value.trim(), headers: headers,
      body_template: $('cBody').value.trim(), field_map: fmap,
    },
  };
  try {
    const j = await api('/api/settings', { method: 'POST', body: JSON.stringify({ settings: patch }) });
    S.meta.settings = j.settings;
    $('customMsg').textContent = '已保存';
    toast('自定义接口已保存');
  } catch (e) { toast('保存失败：' + e.message, true); }
}

/* ------------------------------ 示例模式 ------------------------------ */
// 用 ?demo=1 打开时，自动选定「人工智能」行业、填入一份示例档案并跑一次诊断 +
// 岗位匹配，让第一次打开的人 3 秒内看清这个工具到底能给出什么结论。
// 只操作前端状态，不写入数据库、不影响任何真实数据。
async function applyDemo() {
  try {
    $('fIndustry').value = 'ai';
    S.filters.industry = 'ai';
    S.loaded = {};
    await loadAnalysis();

    $('pMajor').value = '计算机科学与技术';
    $('pDegree').value = '本科';
    $('pGrade').value = '大三';
    $('pCity').value = '北京';
    $('pJob').value = '大模型算法实习生';
    S.mySkills = { 'Python': 4, 'PyTorch': 3, '大模型': 3, 'SQL': 3, 'Linux': 2 };
    renderMySkills();

    switchTab('career');
    await runDiagnose();
    await runMatch();
    switchTab('career');
  } catch (e) {
    // 示例模式只是锦上添花，失败时静默回落到正常界面
  }
}

/* ------------------------------ go ------------------------------ */
window.addEventListener('DOMContentLoaded', boot);
window.addEventListener('error', (e) => { try { toast('前端异常：' + e.message, true); } catch (_) {} });
