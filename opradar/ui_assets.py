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

/* ---------- generic table ---------- */
function makeTable(cfg) {
  const state = { sort: cfg.sort, dir: cfg.dir || -1, page: 0, per: 100, rows: [] };
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

    body.innerHTML = slice.map(r => '<tr>' + cfg.columns.map(c =>
      `<td class="${c.cls || ''}${c.r ? ' r' : ''}">${c.render ? c.render(r) : esc(c.v(r) ?? '')}</td>`
    ).join('') + '</tr>').join('');

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
"""
