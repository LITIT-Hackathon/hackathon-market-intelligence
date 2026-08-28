"""CSS and JS for the static UI. Kept out of ui.py so the Python stays readable."""

# Design tokens read off litit.tech: ink #1A1C1B, white panels with large radii,
# a single yellow accent, condensed grotesque display type over Inter body text.
CSS = r"""
:root{
  --ink:#1A1C1B; --ink-2:#232624; --ink-3:#343835;
  --paper:#FFFFFF; --paper-2:#F5F5F2; --line:#E4E4DF; --line-2:#D2D2CC;
  --text:#1A1C1B; --muted:#6B6F6C; --muted-2:#8D918E;
  --accent:#FFEB00; --pos:#28D08A; --warn:#C4462F; --link:#116DFF;
  --r:24px; --r-sm:10px;
  --sans:'Inter','Helvetica Neue',Arial,sans-serif;
  --disp:'Archivo','Arial Narrow','Helvetica Neue Condensed',Arial,sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-text-size-adjust:100%}
body{background:var(--ink);color:var(--text);font:400 15px/1.5 var(--sans);
  font-feature-settings:"tnum" 1;-webkit-font-smoothing:antialiased}

.display{font-family:var(--disp);font-weight:700;font-stretch:70%;
  text-transform:uppercase;line-height:.92;letter-spacing:-.01em}
.label{font:600 11px/1 var(--sans);letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
.num{font-variant-numeric:tabular-nums}

/* ---------- shell ---------- */
header{background:var(--ink);color:#fff;padding:22px 32px 30px}
.bar{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;flex-wrap:wrap}
.brand{display:flex;align-items:baseline;gap:14px}
.brand .mark{font-family:var(--disp);font-weight:800;font-stretch:70%;font-size:30px;
  letter-spacing:.02em;text-transform:uppercase;color:#fff}
.brand .mark b{color:var(--accent)}
.brand .sub{font:500 11px/1 var(--sans);letter-spacing:.14em;text-transform:uppercase;color:var(--muted-2)}
.stamp{font:400 12px/1.6 var(--sans);color:var(--muted-2);text-align:right}
.stamp b{color:#fff;font-weight:600}

nav{display:flex;gap:2px;margin-top:26px;flex-wrap:wrap}
nav button{background:none;border:0;color:var(--muted-2);cursor:pointer;
  font:600 12px/1 var(--sans);letter-spacing:.12em;text-transform:uppercase;
  padding:12px 18px;border-radius:var(--r-sm) var(--r-sm) 0 0}
nav button:hover{color:#fff;background:var(--ink-2)}
nav button[aria-selected="true"]{color:var(--ink);background:var(--paper)}

main{background:var(--paper);border-radius:var(--r) var(--r) 0 0;padding:38px 32px 90px;min-height:70vh}
.screen{display:none}
.screen.on{display:block}
.screen>h2{font-family:var(--disp);font-weight:700;font-stretch:68%;text-transform:uppercase;
  font-size:clamp(34px,5vw,58px);line-height:.92;letter-spacing:-.015em;margin:6px 0 10px}
.lede{max-width:70ch;color:var(--muted);margin-bottom:30px}

/* ---------- kpis ---------- */
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:1px;
  background:var(--line);border:1px solid var(--line);border-radius:var(--r-sm);overflow:hidden;margin-bottom:34px}
.kpi{background:var(--paper);padding:18px 18px 16px}
.kpi .v{font-family:var(--disp);font-weight:700;font-stretch:72%;font-size:38px;line-height:1;
  letter-spacing:-.02em;margin:8px 0 4px}
.kpi .n{font:400 12px/1.4 var(--sans);color:var(--muted)}
.kpi.hl{background:var(--accent)}
.kpi.hl .label,.kpi.hl .n{color:rgba(26,28,27,.72)}

/* ---------- panels + charts ---------- */
.grid{display:grid;gap:18px;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));margin-bottom:18px}
.panel{border:1px solid var(--line);border-radius:var(--r-sm);padding:20px 20px 22px;background:var(--paper)}
.panel h3{font:600 14px/1.3 var(--sans);margin:6px 0 2px}
.panel .hint{font:400 12px/1.5 var(--sans);color:var(--muted);margin-bottom:16px}
.panel.wide{grid-column:1/-1}

.hbar{display:grid;grid-template-columns:minmax(90px,190px) 1fr auto;gap:8px 12px;align-items:center}
.hbar .k{font:400 12.5px/1.35 var(--sans);color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hbar .t{height:16px;background:var(--paper-2);border-radius:3px;overflow:hidden}
.hbar .t i{display:block;height:100%;background:var(--ink);border-radius:3px}
.hbar .t i.acc{background:var(--accent)}
.hbar .t i.mut{background:var(--line-2)}
.hbar .v{font:500 12px/1 var(--sans);color:var(--muted);text-align:right;font-variant-numeric:tabular-nums}

.hbar2{display:grid;grid-template-columns:minmax(90px,150px) 1fr auto;gap:9px 12px;align-items:center}
.hbar2 .k{font:400 12.5px/1.35 var(--sans);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hbar2 .t2{display:flex;flex-direction:column;gap:3px}
.hbar2 .t2 i{display:block;height:9px;border-radius:2px;min-width:2px}
.hbar2 .t2 i.s{background:var(--ink)}
.hbar2 .t2 i.d{background:var(--accent)}
.hbar2 .v{font:500 12px/1 var(--sans);color:var(--muted);text-align:right;font-variant-numeric:tabular-nums}
.lg{display:flex;gap:16px;margin-top:14px;font:400 11px/1 var(--sans);color:var(--muted)}
.lg span{display:inline-flex;align-items:center;gap:6px}
.lg i{width:12px;height:9px;border-radius:2px;display:inline-block}
.lg i.s{background:var(--ink)}
.lg i.d{background:var(--accent)}
.cols{display:flex;align-items:flex-end;gap:3px;height:150px;border-bottom:1px solid var(--line);padding-bottom:0}
.cols div{flex:1;background:var(--ink);border-radius:2px 2px 0 0;min-height:2px;position:relative}
.cols div.acc{background:var(--accent)}
.colx{display:flex;gap:3px;margin-top:6px}
.colx span{flex:1;font:400 9.5px/1.2 var(--sans);color:var(--muted-2);text-align:center;
  overflow:hidden;white-space:nowrap}

.note{border-left:3px solid var(--warn);background:var(--paper-2);padding:12px 14px;
  border-radius:0 var(--r-sm) var(--r-sm) 0;font:400 12.5px/1.6 var(--sans);color:var(--text);margin-top:16px}
.note b{color:var(--warn)}

/* ---------- controls ---------- */
.controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:16px}
input[type=search],select{font:400 13px var(--sans);color:var(--text);background:var(--paper);
  border:1px solid var(--line-2);border-radius:var(--r-sm);padding:9px 11px;min-width:150px}
input[type=search]{min-width:250px}
input:focus,select:focus{outline:2px solid var(--ink);outline-offset:-1px}
.chk{display:inline-flex;align-items:center;gap:7px;font:400 13px var(--sans);color:var(--text);
  border:1px solid var(--line-2);border-radius:var(--r-sm);padding:9px 12px;cursor:pointer;user-select:none}
.chk input{accent-color:var(--ink)}
.count{font:400 13px var(--sans);color:var(--muted);margin-left:auto}
.count b{color:var(--text);font-weight:600}

/* ---------- tables ---------- */
.tw{border:1px solid var(--line);border-radius:var(--r-sm);overflow:auto;max-height:66vh}
table{border-collapse:collapse;width:100%;font-size:13px}
thead th{position:sticky;top:0;z-index:1;background:var(--ink);color:#fff;text-align:left;
  font:600 11px/1 var(--sans);letter-spacing:.09em;text-transform:uppercase;
  padding:12px 12px;white-space:nowrap;cursor:pointer;border-right:1px solid var(--ink-3)}
thead th:hover{background:var(--ink-2)}
thead th.r{text-align:right}
thead th .ar{color:var(--accent);margin-left:5px}
tbody td{padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top}
tbody td.r{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
tbody tr:hover{background:var(--paper-2)}
td.nm{font-weight:500;max-width:300px}
td.ti{max-width:380px}
.tag{display:inline-block;font:600 10px/1 var(--sans);letter-spacing:.06em;text-transform:uppercase;
  padding:4px 7px;border-radius:4px;background:var(--paper-2);color:var(--muted);white-space:nowrap;border:1px solid var(--line)}
.tag.comp{background:var(--ink);color:#fff;border-color:var(--ink)}
.tag.noise{background:transparent;color:var(--muted-2);border-style:dashed}
.tag.pub{background:var(--accent);color:var(--ink);border-color:var(--accent)}
.chip{display:inline-block;font:400 11px/1 var(--sans);padding:3px 6px;border-radius:4px;
  background:var(--paper-2);color:var(--muted);margin:0 3px 3px 0;white-space:nowrap}
.age{font-weight:600}
.age.old{color:var(--warn)}
a{color:var(--link);text-decoration:none}
a:hover{text-decoration:underline}
.pager{display:flex;gap:8px;align-items:center;justify-content:center;margin-top:16px;
  font:400 13px var(--sans);color:var(--muted)}
.pager button{font:600 12px var(--sans);border:1px solid var(--line-2);background:var(--paper);
  border-radius:var(--r-sm);padding:8px 14px;cursor:pointer}
.pager button:hover:not(:disabled){background:var(--ink);color:#fff;border-color:var(--ink)}
.pager button:disabled{opacity:.35;cursor:default}

/* ---------- radar ---------- */
.sliders{display:flex;gap:22px;flex-wrap:wrap;align-items:center}
.sliders label{display:flex;align-items:center;gap:9px;font:400 12.5px var(--sans);color:var(--text)}
.sliders input[type=range]{width:120px;accent-color:var(--ink)}
.sliders b{font:600 12px var(--sans);min-width:20px;text-align:right;font-variant-numeric:tabular-nums}
.resetbtn{font:600 11px var(--sans);letter-spacing:.08em;text-transform:uppercase;
  border:1px solid var(--line-2);background:var(--paper);border-radius:var(--r-sm);
  padding:8px 12px;cursor:pointer}
.resetbtn:hover{background:var(--ink);color:#fff;border-color:var(--ink)}
.score{font-family:var(--disp);font-weight:700;font-stretch:72%;font-size:19px;letter-spacing:-.01em}
.mini{display:inline-flex;gap:2px;vertical-align:middle}
.mini i{width:7px;border-radius:1px;background:var(--line-2);align-self:flex-end}
.band{display:inline-block;font:600 10px/1 var(--sans);letter-spacing:.06em;text-transform:uppercase;
  padding:4px 7px;border-radius:4px}
.band.high{background:var(--ink);color:#fff}
.band.medium{background:var(--paper-2);color:var(--text);border:1px solid var(--line-2)}
.band.low{background:transparent;color:var(--muted-2);border:1px dashed var(--line-2)}
.svcbar{display:inline-block;width:52px;height:8px;background:var(--paper-2);border-radius:2px;
  overflow:hidden;vertical-align:middle;margin-right:6px}
.svcbar i{display:block;height:100%;background:var(--ink)}
.svcbar i.low{background:var(--warn)}
tr.evrow>td{background:var(--paper-2);padding:14px 16px 16px}
.evlist{display:grid;gap:6px}
.evlist a{font:400 12.5px var(--sans)}
.evlist .age{margin-left:8px}
.evhead{font:600 11px/1 var(--sans);letter-spacing:.1em;text-transform:uppercase;
  color:var(--muted);margin:2px 0 8px}
.uncov{font:400 12px var(--sans);color:var(--warn);margin-top:10px}
tbody tr.clickable{cursor:pointer}

/* ---------- quality ---------- */
.q{display:grid;gap:18px;grid-template-columns:repeat(auto-fit,minmax(340px,1fr))}
.q .panel.span2{grid-column:span 2}
@media(max-width:900px){.q .panel.span2{grid-column:auto}}
.kv{width:100%;font-size:13px}
.kv td{padding:7px 0;border-bottom:1px solid var(--line);line-height:1.45}
.kv td:first-child{padding-right:14px}
.kv td:last-child{text-align:right;font-variant-numeric:tabular-nums;font-weight:500;white-space:nowrap}
.lim{list-style:none}
.lim li{padding:9px 0 9px 20px;border-bottom:1px solid var(--line);position:relative;font-size:13.5px;line-height:1.6}
.lim li:before{content:"";position:absolute;left:0;top:16px;width:8px;height:2px;background:var(--warn)}
footer{background:var(--ink);color:var(--muted-2);padding:20px 32px 30px;font:400 12px/1.7 var(--sans)}
footer a{color:var(--muted-2);text-decoration:underline}
@media(max-width:640px){
  header,main,footer{padding-left:16px;padding-right:16px}
  .hbar{grid-template-columns:minmax(70px,120px) 1fr auto}
}
"""

JS = r"""
const D = window.__OPRADAR__;
const $ = s => document.querySelector(s);
const fmt = n => n === null || n === undefined ? '' : n.toLocaleString('en-US');
const pct = n => (n * 100).toFixed(n < 0.1 ? 1 : 0) + '%';
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

/* ---------- charts ---------- */
function hbar(el, rows, opts = {}) {
  const max = Math.max(1, ...rows.map(r => r[1]));
  el.innerHTML = '<div class="hbar">' + rows.map(r => {
    const cls = r[2] || '';
    const val = opts.fmt ? opts.fmt(r[1]) : fmt(r[1]);
    return `<div class="k" title="${esc(r[0])}">${esc(r[0])}</div>`
         + `<div class="t"><i class="${cls}" style="width:${(r[1] / max * 100).toFixed(1)}%"></i></div>`
         + `<div class="v">${val}</div>`;
  }).join('') + '</div>';
}

function cols(el, rows, opts = {}) {
  const max = Math.max(1, ...rows.map(r => r[1]));
  el.innerHTML = '<div class="cols">' + rows.map(r =>
      `<div class="${r[2] || ''}" style="height:${Math.max(2, r[1] / max * 100)}%" `
    + `title="${esc(r[0])}: ${fmt(r[1])}"></div>`).join('') + '</div>'
    + '<div class="colx">' + rows.map((r, i) =>
      `<span>${(opts.every && i % opts.every) ? '' : esc(r[0])}</span>`).join('') + '</div>';
}

function hbar2(el, rows, opts = {}) {
  const max = Math.max(1e-9, ...rows.flatMap(r => [r[1], r[2]]));
  el.innerHTML = '<div class="hbar2">' + rows.map(r => {
    const a = (r[1] / max * 100).toFixed(1), b = (r[2] / max * 100).toFixed(1);
    return `<div class="k" title="${esc(r[0])}">${esc(r[0])}</div>`
         + `<div class="t2">`
         + `<i class="s" style="width:${a}%" title="supply ${(r[1]*100).toFixed(1)}%"></i>`
         + `<i class="d" style="width:${b}%" title="demand ${(r[2]*100).toFixed(1)}%"></i></div>`
         + `<div class="v">${r[3] !== undefined ? r[3].toFixed(2) : ''}</div>`;
  }).join('') + '</div>'
  + '<div class="lg"><span><i class="s"></i>supply</span><span><i class="d"></i>demand</span>'
  + '<span style="margin-left:auto">tension</span></div>';
}

/* ---------- generic table ---------- */
function makeTable(cfg) {
  const state = { sort: Math.min(cfg.sort ?? 0, cfg.columns.length - 1),
                  dir: cfg.dir || -1, page: 0, per: cfg.per || 100, rows: [] };
  const head = $(cfg.head), body = $(cfg.body), count = $(cfg.count), pager = $(cfg.pager);

  head.innerHTML = '<tr>' + cfg.columns.map((c, i) =>
    `<th data-i="${i}" class="${c.r ? 'r' : ''}">${esc(c.t)}<span class="ar"></span></th>`).join('') + '</tr>';

  head.querySelectorAll('th').forEach(th => th.onclick = () => {
    const i = +th.dataset.i;
    if (state.sort === i) state.dir *= -1; else { state.sort = i; state.dir = cfg.columns[i].asc ? 1 : -1; }
    state.page = 0; render();
  });

  function render() {
    let rows = cfg.filter();
    const col = cfg.columns[state.sort];
    const key = col.sortKey || col.v;
    rows.sort((a, b) => {
      let x = key(a), y = key(b);
      if (x === null || x === undefined) return 1;
      if (y === null || y === undefined) return -1;
      if (typeof x === 'string') return state.dir * x.localeCompare(y);
      return state.dir * (x - y);
    });
    state.rows = rows;

    head.querySelectorAll('th').forEach((th, i) =>
      th.querySelector('.ar').textContent = i === state.sort ? (state.dir < 0 ? '↓' : '↑') : '');

    const pages = Math.max(1, Math.ceil(rows.length / state.per));
    state.page = Math.min(state.page, pages - 1);
    const slice = rows.slice(state.page * state.per, (state.page + 1) * state.per);

    body.innerHTML = '';
    slice.forEach(r => {
      const tr = document.createElement('tr');
      tr.innerHTML = cfg.columns.map(c =>
        `<td class="${c.cls || ''}${c.r ? ' r' : ''}">${c.render ? c.render(r) : esc(c.v(r) ?? '')}</td>`
      ).join('');
      if (cfg.onRow) cfg.onRow(tr, r);
      body.appendChild(tr);
    });

    count.innerHTML = `<b>${fmt(rows.length)}</b> of ${fmt(cfg.total)} ${cfg.noun}`;
    pager.innerHTML = pages > 1
      ? `<button ${state.page === 0 ? 'disabled' : ''} data-d="-1">Previous</button>`
      + `<span>Page ${state.page + 1} of ${fmt(pages)}</span>`
      + `<button ${state.page >= pages - 1 ? 'disabled' : ''} data-d="1">Next</button>` : '';
    pager.querySelectorAll('button').forEach(b => b.onclick = () => {
      state.page += +b.dataset.d; render();
      document.querySelector(cfg.head).closest('.tw').scrollTop = 0;
    });
  }
  return render;
}

/* ---------- nav ---------- */
document.querySelectorAll('nav button').forEach(b => b.onclick = () => {
  document.querySelectorAll('nav button').forEach(x => x.setAttribute('aria-selected', x === b));
  document.querySelectorAll('.screen').forEach(s => s.classList.toggle('on', s.id === b.dataset.s));
  window.scrollTo(0, 0);
});

/* ---------- overview ---------- */
const C = D.charts;
hbar($('#c-groups'), C.kldb_groups.map(r => [r[0], r[1], r[2] ? 'acc' : '']));
hbar($('#c-class'), C.classes.map(r => [r[0], r[1], r[2] ? 'acc' : '']));
hbar($('#c-tech'), C.tech);
hbar($('#c-domain'), C.domains);
hbar($('#c-level'), C.levels);
cols($('#c-month'), C.months.map(r => [r[0], r[1], '']), { every: 3 });
cols($('#c-age'), C.age_buckets.map(r => [r[0], r[1], r[0].startsWith('180') || r[0].startsWith('91') ? 'acc' : '']));

const regionAbs = C.regions.map(r => [r[0], r[1]]);
const regionRel = C.regions.filter(r => r[2]).map(r => [r[0], Math.round(r[1] / r[2])])
  .sort((a, b) => b[1] - a[1]);
function drawRegions() {
  const per = $('#region-norm').checked;
  hbar($('#c-region'), (per ? regionRel : regionAbs).map(r => [r[0], r[1], '']));
  $('#region-hint').textContent = per
    ? 'Postings per million inhabitants. Bremen and Hamburg stay high, which is the crawl, not the market.'
    : 'Raw counts. These reflect crawl coverage as much as labour demand — switch to per-capita.';
}
$('#region-norm').onchange = drawRegions; drawRegions();

/* ---------- companies ---------- */
const CO = D.companies, coCols = {};
CO.cols.forEach((c, i) => coCols[c] = i);
const co = i => r => r[coCols[i]];

const renderCompanies = makeTable({
  head: '#co-head', body: '#co-body', count: '#co-count', pager: '#co-pager',
  total: CO.rows.length, noun: 'companies', sort: 3, dir: -1,
  columns: [
    { t: 'Company', v: co('company_name'), cls: 'nm' },
    { t: 'Class', v: co('company_class'), render: r => {
        const c = co('company_class')(r), comp = co('is_competitor')(r), noise = co('is_noise')(r);
        return `<span class="tag ${comp ? 'comp' : noise ? 'noise' : c === 'public_sector' ? 'pub' : ''}">`
             + esc(c.replace(/_/g, ' ')) + '</span>'
             + (co('needs_review')(r) ? ' <span class="tag" title="High volume across unrelated sectors and regions, but no agency keyword in the name — the rules cannot decide">review</span>' : ''); } },
    { t: 'Postings', v: co('postings'), r: true },
    { t: 'IT', v: co('it_postings'), r: true },
    { t: 'IT %', v: co('it_intensity'), r: true, render: r => pct(co('it_intensity')(r)) },
    { t: 'Median IT age', v: co('median_it_age_days'), r: true, render: r => {
        const v = co('median_it_age_days')(r);
        return v === null ? '<span style="color:var(--muted-2)">–</span>'
          : `<span class="age ${v > 90 ? 'old' : ''}">${fmt(v)}d</span>`; } },
    { t: 'Regions', v: co('region_count'), r: true },
    { t: 'Top technologies', v: co('top_technologies'), sortKey: r => co('top_technologies')(r).length,
      render: r => co('top_technologies')(r).slice(0, 5).map(t => `<span class="chip">${esc(t)}</span>`).join('') },
  ],
  filter: () => {
    const q = $('#co-q').value.trim().toLowerCase();
    const cls = $('#co-class').value;
    const hideComp = $('#co-hidecomp').checked;
    const hideNoise = $('#co-hidenoise').checked;
    const minIt = +$('#co-minit').value;
    return CO.rows.filter(r =>
      (!q || co('company_name')(r).toLowerCase().includes(q))
      && (!cls || co('company_class')(r) === cls)
      && (!hideComp || !co('is_competitor')(r))
      && (!hideNoise || !co('is_noise')(r))
      && co('it_postings')(r) >= minIt);
  },
});
['#co-q', '#co-class', '#co-hidecomp', '#co-hidenoise', '#co-minit']
  .forEach(s => { $(s).oninput = renderCompanies; $(s).onchange = renderCompanies; });
renderCompanies();

/* ---------- postings ---------- */
const P = D.postings, pIdx = {};
P.cols.forEach((c, i) => pIdx[c] = i);
const px = k => r => r[pIdx[k]];
const dict = (arr, i) => i === null || i === undefined ? null : arr[i];

const renderPostings = makeTable({
  head: '#po-head', body: '#po-body', count: '#po-count', pager: '#po-pager',
  total: P.rows.length, noun: 'postings', sort: 7, dir: -1,
  columns: [
    { t: 'Title', v: px('title'), cls: 'ti', render: r => {
        const id = px('id')(r);
        return `<a href="https://www.arbeitsagentur.de/jobsuche/jobdetail/${encodeURIComponent(id)}" `
             + `target="_blank" rel="noopener">${esc(px('title')(r))}</a>`; } },
    { t: 'Company', v: r => dict(D.dicts.companies, px('company')(r)), cls: 'nm' },
    { t: 'Occupational group', v: r => dict(D.dicts.groups, px('group')(r)) },
    { t: 'Level', v: r => dict(D.dicts.levels, px('level')(r)) },
    { t: 'Seniority', v: r => dict(D.dicts.seniority, px('seniority')(r)) },
    { t: 'Technologies', v: px('tech'), sortKey: r => px('tech')(r).length,
      render: r => px('tech')(r).map(i => `<span class="chip">${esc(D.dicts.tech[i])}</span>`).join('')
                || '<span style="color:var(--muted-2)">–</span>' },
    { t: 'Region', v: r => dict(D.dicts.regions, px('region')(r)) },
    { t: 'Age', v: px('age'), r: true, render: r => {
        const v = px('age')(r);
        return v === null ? '' : `<span class="age ${v > 90 ? 'old' : ''}">${fmt(v)}d</span>`; } },
  ],
  filter: () => {
    const q = $('#po-q').value.trim().toLowerCase();
    const sen = $('#po-sen').value, reg = $('#po-reg').value, tech = $('#po-tech').value;
    const minAge = +$('#po-age').value;
    const hideComp = $('#po-hidecomp').checked;
    return P.rows.filter(r =>
      (!q || px('title')(r).toLowerCase().includes(q)
          || (D.dicts.companies[px('company')(r)] || '').toLowerCase().includes(q))
      && (!sen || D.dicts.seniority[px('seniority')(r)] === sen)
      && (!reg || D.dicts.regions[px('region')(r)] === reg)
      && (!tech || px('tech')(r).some(i => D.dicts.tech[i] === tech))
      && (px('age')(r) ?? 0) >= minAge
      && (!hideComp || !px('comp')(r)));
  },
});
['#po-q', '#po-sen', '#po-reg', '#po-tech', '#po-age', '#po-hidecomp']
  .forEach(s => { $(s).oninput = renderPostings; $(s).onchange = renderPostings; });
renderPostings();

/* ---------- talent (only when the candidate parser has been run) ---------- */
if (D.talent) {
  const T = D.talent, TC = T.charts;

  hbar2($('#t-supplydemand'), TC.supply_demand);
  hbar($('#t-tensiontop'), TC.tension_top.map(r => [r[0], r[1], 'acc']), { fmt: v => v.toFixed(2) });
  hbar($('#t-tensionbot'), TC.tension_bottom.map(r => [r[0], r[1], 'mut']), { fmt: v => v.toFixed(2) });
  hbar($('#t-rolefam'), TC.role_family);
  hbar($('#t-roledemand'), TC.role_demand);
  hbar($('#t-seniority'), TC.seniority);
  hbar($('#t-experience'), TC.experience.map(r => [r[0], r[1], 'mut']));
  hbar($('#t-industry'), TC.industry);
  hbar($('#t-education'), TC.education.map(r => [r[0], r[1], 'mut']));

  /* skill market table */
  const SK = T.skills, sIdx = {};
  SK.cols.forEach((c, i) => sIdx[c] = i);
  const sx = k => r => r[sIdx[k]];
  const renderSkills = makeTable({
    head: '#sk-head', body: '#sk-body', count: '#sk-count', pager: '#sk-pager',
    total: SK.rows.length, noun: 'skills', sort: 7, dir: -1,
    columns: [
      { t: 'Skill', v: sx('skill'), cls: 'nm' },
      { t: 'Family', v: sx('skill_family'), render: r => `<span class="tag">${esc(sx('skill_family')(r))}</span>` },
      { t: 'Supply', v: sx('supply'), r: true },
      { t: 'Supply %', v: sx('supply_share'), r: true, render: r => pct(sx('supply_share')(r)) },
      { t: 'Must-have', v: sx('demand_must'), r: true },
      { t: 'Nice-to-have', v: sx('demand_nice'), r: true },
      { t: 'Demand %', v: sx('demand_share'), r: true, render: r => pct(sx('demand_share')(r)) },
      { t: 'Tension', v: sx('tension'), r: true, render: r => {
          const v = sx('tension')(r);
          return `<span class="age ${v >= 1 ? 'old' : ''}">${v.toFixed(2)}</span>`; } },
    ],
    filter: () => {
      const q = $('#sk-q').value.trim().toLowerCase(), fam = $('#sk-fam').value;
      return SK.rows.filter(r =>
        (!q || sx('skill')(r).toLowerCase().includes(q)) && (!fam || sx('skill_family')(r) === fam));
    },
  });
  ['#sk-q', '#sk-fam'].forEach(s => { $(s).oninput = renderSkills; $(s).onchange = renderSkills; });
  renderSkills();

  /* candidates table */
  const CA = T.candidates, cIdx = {};
  CA.cols.forEach((c, i) => cIdx[c] = i);
  const cx = k => r => r[cIdx[k]];
  const TECH_FAMS = new Set(['engineering', 'data']);
  const renderCands = makeTable({
    head: '#ca-head', body: '#ca-body', count: '#ca-count', pager: '#ca-pager',
    total: CA.rows.length, noun: 'candidates', sort: 8, dir: -1,
    columns: [
      { t: 'ID', v: cx('candidate_id'), cls: 'nm' },
      { t: 'Role', v: cx('role'), cls: 'nm' },
      { t: 'Family', v: cx('role_family'), render: r => {
          const f = cx('role_family')(r);
          return `<span class="tag ${TECH_FAMS.has(f) ? 'pub' : ''}">${esc(f)}</span>`; } },
      { t: 'Seniority', v: cx('seniority') },
      { t: 'Years', v: cx('years_experience'), r: true },
      { t: 'Industry', v: cx('industry') },
      { t: 'Education', v: cx('education') },
      { t: 'Skills', v: cx('skills'), sortKey: r => cx('skills')(r).length,
        render: r => cx('skills')(r).map(i => `<span class="chip">${esc(T.dicts.skills[i])}</span>`).join('') },
      { t: 'Qualified for', v: cx('qualified_for_openings'), r: true,
        render: r => fmt(cx('qualified_for_openings')(r)) },
    ],
    filter: () => {
      const q = $('#ca-q').value.trim().toLowerCase();
      const role = $('#ca-role').value, sen = $('#ca-sen').value, ind = $('#ca-ind').value;
      const techOnly = $('#ca-tech').checked;
      return CA.rows.filter(r =>
        (!role || cx('role')(r) === role)
        && (!sen || cx('seniority')(r) === sen)
        && (!ind || cx('industry')(r) === ind)
        && (!techOnly || TECH_FAMS.has(cx('role_family')(r)))
        && (!q || cx('role')(r).toLowerCase().includes(q)
               || cx('industry')(r).toLowerCase().includes(q)
               || cx('skills')(r).some(i => T.dicts.skills[i].toLowerCase().includes(q))));
    },
  });
  ['#ca-q', '#ca-role', '#ca-sen', '#ca-ind', '#ca-tech']
    .forEach(s => { $(s).oninput = renderCands; $(s).onchange = renderCands; });
  renderCands();
}

/* ---------- radar + bench (only when the scorer has run) ---------- */
if (D.radar) {
  const R = D.radar, rIdx = {};
  R.cols.forEach((c, i) => rIdx[c] = i);
  const rx = k => r => r[rIdx[k]];

  /* live weights */
  const W0 = { n1: R.meta.weights.n1, n2: R.meta.weights.n2, n3: R.meta.weights.n3, n4: R.meta.weights.n4 };
  const W = { ...W0 };
  const needOf = r => {
    const t = W.n1 + W.n2 + W.n3 + W.n4;
    if (!t) return 0;
    return (W.n1 * rx('n1')(r) + W.n2 * rx('n2')(r) + W.n3 * rx('n3')(r) + W.n4 * rx('n4')(r)) / t * 100;
  };
  const oppOf = r => needOf(r) * rx('svc')(r);
  let openKey = null;

  const mini = r => {
    const h = v => Math.max(2, Math.round(v * 18));
    return `<span class="mini" title="N1 ${(rx('n1')(r)*100).toFixed(0)} · N2 ${(rx('n2')(r)*100).toFixed(0)} · N3 ${(rx('n3')(r)*100).toFixed(0)} · N4 ${(rx('n4')(r)*100).toFixed(0)}">`
      + ['n1','n2','n3','n4'].map(k => `<i style="height:${h(r[rIdx[k]])}px"></i>`).join('') + '</span>';
  };

  const renderRadar = makeTable({
    head: '#ra-head', body: '#ra-body', count: '#ra-count', pager: '#ra-pager',
    total: R.rows.length, noun: 'companies', sort: 1, dir: -1,
    columns: [
      { t: '#', v: r => Math.round(oppOf(r)), r: true,
        render: r => `<b>${R.rows.filter(x => oppOf(x) > oppOf(r)).length + 1}</b>` },
      { t: 'Opportunity', v: oppOf, r: true,
        render: r => `<span class="score">${oppOf(r).toFixed(1)}</span>` },
      { t: 'Company', v: rx('name'), cls: 'nm', render: r =>
          esc(rx('name')(r)) + (rx('review')(r)
            ? ' <span class="tag" title="Keyword rules could not confidently classify this company — LLM-pass queue; identity confidence already discounted">review</span>' : '') },
      { t: 'Class', v: rx('class'), render: r =>
          `<span class="tag ${rx('class')(r) === 'public_sector' ? 'pub' : ''}">${esc(rx('class')(r).replace(/_/g, ' '))}</span>` },
      { t: 'Need', v: needOf, r: true, render: r => needOf(r).toFixed(1) + ' ' + mini(r) },
      { t: 'Serviceability', v: rx('svc'), r: true, render: r => {
          const v = rx('svc')(r);
          return `<span class="svcbar"><i class="${v < 0.5 ? 'low' : ''}" style="width:${(v * 100).toFixed(0)}%"></i></span>${v.toFixed(2)}`; } },
      { t: 'Confidence', v: rx('conf'), r: true,
        render: r => `<span class="band ${rx('band')(r)}">${rx('band')(r)}</span>` },
      { t: 'IT', v: rx('it_n'), r: true },
      { t: '>45d', v: rx('open45'), r: true },
      { t: '>90d', v: rx('open90'), r: true },
      { t: 'Top tech', v: rx('techs'), sortKey: r => rx('techs')(r).length,
        render: r => rx('techs')(r).slice(0, 4).map(t => `<span class="chip">${esc(t)}</span>`).join('') },
    ],
    filter: () => {
      const q = $('#ra-q').value.trim().toLowerCase();
      const cls = $('#ra-class').value, band = $('#ra-band').value;
      const noRev = $('#ra-noreview').checked;
      return R.rows.filter(r =>
        (!q || rx('name')(r).toLowerCase().includes(q))
        && (!cls || rx('class')(r) === cls)
        && (!band || rx('band')(r) === band)
        && (!noRev || !rx('review')(r)));
    },
    onRow: (tr, r) => {
      tr.classList.add('clickable');
      tr.onclick = () => {
        const key = rx('name')(r);
        openKey = openKey === key ? null : key;
        renderRadar();
        if (openKey !== key) return;
        const anchor = [...document.querySelectorAll('#ra-body tr')]
          .find(x => x.dataset.ev === key);
        if (!anchor) return;
        const ev = rx('evidence')(r), unc = rx('uncovered_families')(r);
        const row = document.createElement('tr');
        row.className = 'evrow';
        row.innerHTML = `<td colspan="11"><div class="evhead">Evidence — `
          + `${rx('covered')(r)} of ${rx('covered')(r) + rx('uncovered')(r)} demand atoms coverable, `
          + `median age ${fmt(rx('median_age')(r))}d, ${fmt(rx('senior_n')(r))} senior/lead</div>`
          + `<div class="evlist">` + ev.map(e =>
              `<div><a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.title)}</a>`
            + `<span class="age ${e.age > 90 ? 'old' : ''}">${fmt(e.age)}d</span>`
            + ` <span class="chip">${esc(e.family)}</span></div>`).join('')
          + `</div>`
          + (Object.keys(unc).length
              ? `<div class="uncov">Uncovered demand: ` + Object.entries(unc)
                  .map(([k, v]) => `${esc(k)} ×${v}`).join(', ')
                + ` — outside the bench profile</div>` : '')
          + `</td>`;
        anchor.after(row);
      };
      tr.dataset.ev = rx('name')(r);
    },
  });

  const syncW = () => {
    ['n1', 'n2', 'n3', 'n4'].forEach(k => {
      W[k] = +$('#w-' + k).value;
      $('#wv-' + k).textContent = W[k];
    });
    openKey = null;
    renderRadar();
  };
  ['n1', 'n2', 'n3', 'n4'].forEach(k => $('#w-' + k).oninput = syncW);
  $('#w-reset').onclick = () => {
    ['n1', 'n2', 'n3', 'n4'].forEach(k => $('#w-' + k).value = W0[k]);
    syncW();
  };
  ['#ra-q', '#ra-class', '#ra-band', '#ra-noreview']
    .forEach(sel => { $(sel).oninput = renderRadar; $(sel).onchange = renderRadar; });
  renderRadar();
}

if (D.bench) {
  const B = D.bench, bIdx = {};
  B.cand_cols.forEach((c, i) => bIdx[c] = i);
  const bx = k => r => r[bIdx[k]];

  hbar2($('#b-gap'), B.gap.map(g => {
    const dMax = Math.max(...B.gap.map(x => x[1]));
    const bMax = Math.max(...B.gap.map(x => x[2]));
    return [g[0], g[1] / Math.max(dMax, 1), g[2] / Math.max(bMax, 1)];
  }));
  hbar($('#b-pull'), B.supply_vs_pull.map(r => [r[0], r[2], 'acc']).sort((a, b) => b[1] - a[1]));
  hbar($('#b-supply'), B.supply_vs_pull.map(r => [r[0], r[1], '']).sort((a, b) => b[1] - a[1]));

  /* cells table */
  const renderCells = makeTable({
    head: '#ce-head', body: '#ce-body', count: '#ce-count', pager: '#ce-pager',
    total: B.cells.length, noun: 'cells', sort: 6, dir: -1,
    columns: [
      { t: 'Family', v: r => r[0], cls: 'nm' },
      { t: 'Seniority', v: r => r[1] },
      { t: 'Depth', v: r => r[2], r: true, render: r =>
          `${fmt(r[2])}` + (r[5] ? ' <span class="tag noise" title="Below the thin-cell guard: scarcity is not ranked here">thin</span>' : '') },
      { t: 'Available', v: r => r[3], r: true },
      { t: 'Readiness', v: r => r[4], r: true, render: r => (r[4] * 100).toFixed(0) + '%' },
      { t: 'Pull pct', v: r => r[7], r: true, render: r => r[7].toFixed(2) },
      { t: 'German unfilled >45d', v: r => r[6], r: true },
      { t: 'Scarcity pct', v: r => r[8], r: true, render: r => r[5] ? '<span style="color:var(--muted-2)">–</span>' : r[8].toFixed(2) },
    ],
    filter: () => B.cells,
  });
  renderCells();

  /* bench value table */
  const renderBench = makeTable({
    head: '#be-head', body: '#be-body', count: '#be-count', pager: '#be-pager',
    total: B.cand_rows.length, noun: 'consultants', sort: 8, dir: -1,
    columns: [
      { t: '#', v: bx('rank'), r: true },
      { t: 'ID', v: bx('id'), cls: 'nm', render: r =>
          esc(bx('id')(r)) + ' <span class="tag noise" title="Generated bench — no real person">synthetic</span>' },
      { t: 'Family', v: bx('family'), render: r => `<span class="tag">${esc(bx('family')(r))}</span>` },
      { t: 'Seniority', v: bx('seniority') },
      { t: 'Yrs', v: bx('years'), r: true },
      { t: 'Tags', v: bx('tags'), sortKey: r => bx('tags')(r).length,
        render: r => bx('tags')(r).map(t => `<span class="chip">${esc(t)}</span>`).join('') },
      { t: 'Availability', v: bx('availability'), render: r =>
          esc(bx('availability')(r)) + (bx('german')(r) ? ' <span class="chip">DE</span>' : '') },
      { t: 'Value', v: bx('value'), r: true, render: r => `<span class="score">${bx('value')(r).toFixed(1)}</span>` },
      { t: 'Pull', v: bx('pull'), r: true, render: r => bx('pull')(r).toFixed(2) },
      { t: 'Scarcity', v: bx('scarcity'), r: true, render: r =>
          bx('scarcity')(r).toFixed(2) + (bx('thin')(r) ? ' <span class="tag noise">thin</span>' : '') },
      { t: 'Deploy', v: bx('deploy'), r: true, render: r => bx('deploy')(r).toFixed(2) },
    ],
    filter: () => {
      const q = $('#be-q').value.trim().toLowerCase();
      const fam = $('#be-fam').value;
      const avail = $('#be-avail').checked;
      return B.cand_rows.filter(r =>
        (!fam || bx('family')(r) === fam)
        && (!avail || ['now', 'in_30d'].includes(bx('availability')(r)))
        && (!q || bx('family')(r).toLowerCase().includes(q)
               || bx('tags')(r).some(t => t.toLowerCase().includes(q))));
    },
  });
  ['#be-q', '#be-fam', '#be-avail']
    .forEach(sel => { $(sel).oninput = renderBench; $(sel).onchange = renderBench; });
  renderBench();
}

"""
