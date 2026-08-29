"""CSS and JS for the static UI. Kept out of ui.py so the Python stays readable."""

# Design tokens read off litit.tech: ink #1A1C1B, white panels with large radii,
# a single yellow accent, condensed grotesque display type over Inter body text.
CSS = r"""
:root{
  --ink:#1A1C1B; --ink-2:#232624; --ink-3:#343835;
  --paper:#FFFFFF; --paper-2:#F5F5F2; --line:#E4E4DF; --line-2:#D2D2CC;
  --text:#1A1C1B; --muted:#6B6F6C; --muted-2:#8D918E;
  /* Two accents, each with a job, so colour carries meaning instead of
     decorating: yellow is the market's demand, iris is our side of the trade
     -- bench coverage, deal size, anything we bring. Yellow is illegible on
     white, so it owns the dark data surfaces and iris owns the light ones. */
  --accent:#FFEB00; --iris:#5B47F5; --iris-lit:#9384FF; --iris-soft:#EFECFF;
  --pos:#28D08A; --warn:#C4462F; --link:#5B47F5;
  --r:24px; --r-sm:10px; --r-ctl:9px; --pill:999px;
  /* one spacing scale -- every gap on the page is one of these six values.
     Before this, blocks were spaced with ad-hoc negative margins. */
  --s1:6px; --s2:10px; --s3:16px; --s4:24px; --s5:34px; --s6:48px;
  --ring:0 0 0 3px rgba(26,28,27,.13);
  --lift:0 1px 2px rgba(26,28,27,.06);
  --pop:0 14px 38px rgba(26,28,27,.16);
  --ease:.16s cubic-bezier(.4,0,.2,1);
  --sans:'Inter','Helvetica Neue',Arial,sans-serif;
  --disp:'Archivo','Arial Narrow','Helvetica Neue Condensed',Arial,sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-text-size-adjust:100%}
body{background:var(--ink);color:var(--text);font:400 15px/1.5 var(--sans);
  font-feature-settings:"tnum" 1;-webkit-font-smoothing:antialiased}

/* ---------- scrollbars ----------
   The platform default is a 17px grey trough that dates the whole page.
   Overlay-thin, rounded, and tinted to whatever surface it sits on. */
/* scrollbar-width does not inherit, so every scroll container needs it or it
   falls back to the 17px platform trough */
*{scrollbar-width:thin;scrollbar-color:var(--line-2) transparent}
html{scrollbar-color:#3D423F var(--ink)}
/* fallback for engines without the standard properties */
::-webkit-scrollbar{width:10px;height:10px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--line-2);border:3px solid transparent;
  background-clip:padding-box;border-radius:var(--pill)}
::-webkit-scrollbar-thumb:hover{background:var(--muted-2);background-clip:padding-box}
::-webkit-scrollbar-corner{background:transparent}
html::-webkit-scrollbar-thumb{background:#3D423F;background-clip:padding-box}

.display{font-family:var(--disp);font-weight:700;font-stretch:70%;
  text-transform:uppercase;line-height:.92;letter-spacing:-.01em}
.label{font:600 11px/1 var(--sans);letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
.num{font-variant-numeric:tabular-nums}

/* ---------- shell ---------- */
header{background:var(--ink);color:#fff;padding:22px 32px 0}
.bar{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;flex-wrap:wrap}
.brand{display:flex;align-items:baseline;gap:14px}
.brand{align-items:center}
.brand .mark{font-family:var(--disp);font-weight:800;font-stretch:75%;font-size:34px;
  letter-spacing:.01em;text-transform:uppercase;color:#fff;line-height:.86}
.brand .byline{font:600 9.5px/1.25 var(--sans);letter-spacing:.13em;text-transform:uppercase;
  color:var(--muted-2);align-self:center}
.brand .byline b{display:block;color:#fff;font-weight:700}
.brand .mark b{color:var(--accent)}
.brand .sub{font:500 11px/1 var(--sans);letter-spacing:.14em;text-transform:uppercase;color:var(--muted-2)}
.stamp{display:flex;gap:7px;flex-wrap:wrap;justify-content:flex-end}
.mchip{font:500 11px/1 var(--sans);color:var(--muted-2);background:var(--ink-2);
  border:1px solid #2E3230;border-radius:var(--pill);padding:7px 12px;white-space:nowrap}
.mchip b{color:#fff;font-weight:600;font-variant-numeric:tabular-nums}

/* Folder tabs. The active tab is the same white surface as the panel and sits
   flush on its top edge -- header padding-bottom is 0 so there is no gap to
   fall through -- with an outward curve at each bottom corner, so tab and
   panel read as one continuous sheet instead of a pill floating above one. */
/* the gap equals the flare radius below, so a neighbour's hover background can
   never reach into the active tab's curve and clip it */
nav{display:flex;gap:12px;margin-top:var(--s4);align-items:flex-end}
nav button{position:relative;z-index:1;background:none;border:0;color:var(--muted-2);cursor:pointer;
  /* whole-pixel line-height: a fractional tab height puts the seam between
     tab and panel on a half pixel, which antialiases into a visible hairline */
  font:600 11.5px/14px var(--sans);letter-spacing:.1em;text-transform:uppercase;
  padding:13px 20px;border-radius:var(--r-sm) var(--r-sm) 0 0;
  transition:color var(--ease),background var(--ease)}
nav button:hover{color:#fff;background:var(--ink-2)}
nav button[aria-selected="true"]{color:var(--ink);background:var(--paper);
  padding-top:15px;z-index:2}
/* the two quarter-circle flares that tie the tab into the panel below */
nav button[aria-selected="true"]::before,
nav button[aria-selected="true"]::after{content:"";position:absolute;bottom:0;
  width:12px;height:12px;pointer-events:none}
nav button[aria-selected="true"]::before{left:-12px;
  background:radial-gradient(circle at top left,transparent 11.5px,var(--paper) 12px)}
nav button[aria-selected="true"]::after{right:-12px;
  background:radial-gradient(circle at top right,transparent 11.5px,var(--paper) 12px)}
nav button:focus-visible{outline:2px solid var(--accent);outline-offset:-3px}

main{background:var(--paper);border-radius:var(--r) var(--r) 0 0;
  padding:var(--s5) 32px 90px;min-height:70vh}
.screen{display:none}
.screen.on{display:block}
.screen>h2{font-family:var(--disp);font-weight:800;font-stretch:75%;text-transform:uppercase;
  font-size:clamp(34px,5vw,58px);line-height:.88;letter-spacing:-.02em;margin:6px 0 14px;
  text-wrap:balance}

/* ---------- marker highlights ----------
   litit.tech's signature device: a solid colour block set behind a phrase,
   with the text knocked through in the contrasting ink. Here it is not
   decoration -- the colour carries the same meaning it carries everywhere
   else on the page, so a highlight always marks the SUBJECT of the heading:
   yellow for the market's demand, iris for our side of the trade, green for
   something confirmed. box-decoration-break keeps the block intact when a
   phrase wraps across lines, which is what makes it read as marker pen
   rather than as a button. */
/* ---------- hover glossary ----------
   Half these column names are terms of art -- "tension", "nice-to-have",
   "coverage gap" -- and a reader who has to guess what a number means will
   either ignore it or, worse, quote it wrongly. Any element carrying
   data-help explains itself on hover and on keyboard focus.

   The tooltip is positioned BELOW its anchor on purpose: table headers sit at
   the top of a scroll container whose overflow clips anything above them, so
   an upward tooltip would be invisible exactly where it is needed most. */
[data-help]{position:relative}
th[data-help]>.t,.kpi[data-help]>.label{border-bottom:1px dotted var(--muted-2);cursor:help}
[data-help]::after{content:attr(data-help);position:absolute;z-index:40;
  top:calc(100% + 7px);left:0;width:max-content;max-width:290px;
  background:var(--ink);color:#fff;border-radius:var(--r-sm);
  padding:9px 12px;font:400 12px/1.45 var(--sans);letter-spacing:0;
  text-transform:none;text-align:left;white-space:normal;
  box-shadow:var(--pop);opacity:0;visibility:hidden;transform:translateY(-3px);
  transition:opacity var(--ease),transform var(--ease),visibility var(--ease);
  pointer-events:none}
[data-help]:hover::after,[data-help]:focus-visible::after{opacity:1;visibility:visible;transform:none}
/* a tooltip on the last columns would run off the right edge */
th[data-help].r::after{left:auto;right:0}

.mk{display:inline;padding:.04em .26em;border-radius:.14em;
  background:var(--accent);color:var(--ink);
  -webkit-box-decoration-break:clone;box-decoration-break:clone}
.mk-i{background:var(--iris);color:#fff}
.mk-g{background:var(--pos);color:var(--ink)}
.lede{max-width:70ch;color:var(--muted);margin-bottom:var(--s5)}

/* ---------- kpis ---------- */
/* Headline numbers sit on a dark slab, not white cards on a white page:
   it anchors the screen and matches the other data surfaces (the timeline). */
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:1px;
  background:var(--ink-3);border-radius:var(--r-ctl);overflow:hidden;margin-bottom:var(--s5)}
/* a collapsed "more numbers" block belongs to the row above it */
.kpis:has(+ details.more){margin-bottom:var(--s2)}
.kpi{background:var(--ink);padding:17px 18px 19px}
.kpi .label{color:var(--muted-2)}
.kpi .v{font-family:var(--disp);font-weight:700;font-stretch:72%;font-size:42px;line-height:1;
  letter-spacing:-.025em;margin:11px 0 5px;color:#fff}
.kpi .n{font:400 12px/1.45 var(--sans);color:var(--muted-2)}
.kpi.hl{background:var(--accent)}
.kpi.hl .v{color:var(--ink)}
.kpi.hl .label,.kpi.hl .n{color:rgba(26,28,27,.7)}

/* ---------- progressive disclosure ----------
   Three tiers: the three numbers that answer the page's question stay visible;
   everything else is one click away. NN/g/Few: a header full of competing
   figures gets skipped entirely, so fewer numbers are read more. */
details.more{margin:0 0 var(--s5)}
details.more summary{cursor:pointer;font:500 12.5px var(--sans);color:var(--muted);
  padding:8px 0;list-style:none;display:inline-flex;align-items:center;gap:7px}
details.more summary::-webkit-details-marker{display:none}
details.more summary::before{content:"+";font-weight:600;font-size:14px;line-height:1;
  width:19px;height:19px;border:1px solid var(--line);border-radius:50%;background:var(--paper-2);
  display:inline-flex;align-items:center;justify-content:center;
  transition:background var(--ease),border-color var(--ease),color var(--ease)}
details.more summary:hover::before{background:var(--ink);border-color:var(--ink);color:var(--paper)}
details.more[open] summary::before{content:"–"}
details.more summary:hover{color:var(--ink)}
details.more .kpis{margin-top:10px}

/* ---------- panels + charts ---------- */
.grid{display:grid;gap:var(--s3);grid-template-columns:repeat(auto-fit,minmax(340px,1fr));
  margin-bottom:var(--s3)}
.panel{border:1px solid var(--line);border-radius:var(--r-sm);padding:20px 20px 22px;background:var(--paper)}
.panel h3{font:600 14px/1.3 var(--sans);margin:6px 0 2px}
.panel .hint{font:400 12px/1.5 var(--sans);color:var(--muted);margin-bottom:16px}
.hint.spaced{margin-bottom:var(--s4)}
h3.tight{margin-bottom:var(--s1)}
.chk.spaced{margin-bottom:var(--s3)}
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
.hbar2 .t2 i.s{background:var(--iris)}
.hbar2 .t2 i.d{background:var(--ink)}
.hbar2 .v{font:500 12px/1 var(--sans);color:var(--muted);text-align:right;font-variant-numeric:tabular-nums}
.lg{display:flex;gap:16px;margin-top:14px;font:400 11px/1 var(--sans);color:var(--muted)}
.lg span{display:inline-flex;align-items:center;gap:6px}
.lg i{width:12px;height:9px;border-radius:2px;display:inline-block}
.lg i.s{background:var(--iris)}
.lg i.d{background:var(--ink)}
/* two charts stacked in one panel */
.stack{height:var(--s4)}
.cols{display:flex;align-items:flex-end;gap:3px;height:150px;border-bottom:1px solid var(--line);padding-bottom:0}
.cols div{flex:1;background:var(--ink);border-radius:2px 2px 0 0;min-height:2px;position:relative}
.cols div.acc{background:var(--accent)}
.colx{display:flex;gap:3px;margin-top:6px}
.colx span{flex:1;font:400 9.5px/1.2 var(--sans);color:var(--muted-2);text-align:center;
  overflow:hidden;white-space:nowrap}

.note{border-left:3px solid var(--warn);background:var(--paper-2);padding:13px 16px;
  border-radius:var(--r-ctl);font:400 12.5px/1.6 var(--sans);color:var(--text);margin:0 0 var(--s5)}
/* a note that trails a block rather than introducing one */
.note.after{margin:var(--s4) 0 0}
.panel .note{margin:var(--s3) 0 0}
.note b{color:var(--warn)}

/* ---------- controls ----------
   Every control in a row is the same height and shares one border, hover and
   focus treatment; the native select chevron and checkbox are replaced. */
.controls{display:flex;gap:var(--s2);flex-wrap:wrap;align-items:center;margin-bottom:var(--s3)}
/* the filter bar stays reachable while the ranking scrolls */
.controls.stick{position:sticky;top:0;z-index:4;background:var(--paper);
  margin:0 -32px var(--s3);padding:14px 32px;border-bottom:1px solid var(--line)}
input[type=search],select,.chk{height:40px;font:400 13px var(--sans);color:var(--text);
  background:var(--paper);border:1px solid var(--line);border-radius:var(--r-ctl);
  transition:border-color var(--ease),box-shadow var(--ease),background var(--ease)}
input[type=search],select{padding:0 12px;min-width:158px}
input[type=search]:hover,select:hover,.chk:hover{border-color:var(--line-2)}
input[type=search]:focus-visible,select:focus-visible{outline:none;
  border-color:var(--ink);box-shadow:var(--ring)}

input[type=search]{min-width:266px;padding-left:34px;
  background-image:url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' fill='none'%3E%3Ccircle cx='6' cy='6' r='4.6' stroke='%238D918E' stroke-width='1.5'/%3E%3Cpath d='M9.6 9.6 13 13' stroke='%238D918E' stroke-width='1.5' stroke-linecap='round'/%3E%3C/svg%3E");
  background-repeat:no-repeat;background-position:12px center}
input[type=search]::-webkit-search-cancel-button{-webkit-appearance:none;width:14px;height:14px;
  cursor:pointer;background:url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' fill='none'%3E%3Cpath d='M3.5 3.5 10.5 10.5M10.5 3.5 3.5 10.5' stroke='%236B6F6C' stroke-width='1.6' stroke-linecap='round'/%3E%3C/svg%3E") center/contain no-repeat}

select{-webkit-appearance:none;appearance:none;cursor:pointer;padding-right:34px;
  background-image:url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' fill='none'%3E%3Cpath d='M1 1.8 6 6.4 11 1.8' stroke='%236B6F6C' stroke-width='1.7' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
  background-repeat:no-repeat;background-position:right 12px center}

.chk{display:inline-flex;align-items:center;gap:9px;padding:0 14px;cursor:pointer;user-select:none}
.chk:has(input:checked){border-color:var(--ink);background:var(--paper-2)}
.chk input{-webkit-appearance:none;appearance:none;position:relative;flex:none;
  width:17px;height:17px;border:1.5px solid var(--line-2);border-radius:5px;
  background:var(--paper);cursor:pointer;transition:background var(--ease),border-color var(--ease)}
.chk input:checked{background:var(--ink);border-color:var(--ink)}
.chk input:checked::after{content:"";position:absolute;left:5px;top:1.5px;width:4px;height:8.5px;
  border:solid var(--accent);border-width:0 2px 2px 0;transform:rotate(43deg)}
.chk input:focus-visible{outline:none;box-shadow:var(--ring)}

.count{font:400 13px var(--sans);color:var(--muted);margin-left:auto}
.count b{color:var(--text);font-weight:600}

/* ---------- tables ---------- */
.tw{border:1px solid var(--line);border-radius:var(--r-ctl);overflow:auto;max-height:66vh;
  background:var(--paper)}
table{border-collapse:collapse;width:100%;font-size:13px}
/* no vertical rules between columns -- alignment does that job, gridlines
   just add noise */
thead th{position:sticky;top:0;z-index:1;background:var(--ink);color:#fff;text-align:left;
  font:600 11px/1 var(--sans);letter-spacing:.09em;text-transform:uppercase;
  padding:14px;white-space:nowrap;cursor:pointer;transition:background var(--ease)}
thead th:first-child{padding-left:18px}
thead th:last-child{padding-right:18px}
thead th:hover{background:var(--ink-2)}
thead th.r{text-align:right}
thead th .ar{color:var(--accent);margin-left:5px}
tbody td{padding:12px 14px;border-bottom:1px solid var(--line);vertical-align:top}
tbody td:first-child{padding-left:18px}
tbody td:last-child{padding-right:18px}
tbody td.r{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
tbody tr{transition:background var(--ease)}
tbody tr:hover{background:var(--paper-2)}
tbody tr:last-child td{border-bottom:0}
td.nm{font-weight:500;max-width:300px}
td.ti{max-width:380px}
.tag{display:inline-block;font:600 10px/1 var(--sans);letter-spacing:.06em;text-transform:uppercase;
  padding:5px 9px;border-radius:var(--pill);background:var(--paper-2);color:var(--muted);
  white-space:nowrap;border:1px solid var(--line)}
.tag.comp{background:var(--ink);color:#fff;border-color:var(--ink)}
.tag.noise{background:transparent;color:var(--muted-2);border-style:dashed}
.tag.pub{background:var(--accent);color:var(--ink);border-color:var(--accent)}
.chip{display:inline-block;font:400 11px/1 var(--sans);padding:5px 9px;border-radius:var(--pill);
  background:var(--paper-2);color:var(--muted);margin:0 4px 4px 0;white-space:nowrap}
.age{font-weight:600}
.age.old{color:var(--warn)}
a{color:var(--link);text-decoration:none}
a:hover{text-decoration:underline}
::selection{background:var(--accent);color:var(--ink)}
code{font:500 12px/1 ui-monospace,'SF Mono',Menlo,Consolas,monospace;background:var(--paper-2);
  border:1px solid var(--line);border-radius:5px;padding:3px 6px;color:var(--ink)}
.pager{display:flex;gap:8px;align-items:center;justify-content:center;margin-top:var(--s3);
  font:400 13px var(--sans);color:var(--muted)}
.pager:empty{display:none}
.pager button{font:600 12px var(--sans);border:1px solid var(--line);background:var(--paper);
  border-radius:var(--r-ctl);padding:9px 15px;cursor:pointer;
  transition:background var(--ease),color var(--ease),border-color var(--ease)}
.pager button:hover:not(:disabled){background:var(--ink);color:#fff;border-color:var(--ink)}
.pager button:focus-visible{outline:none;box-shadow:var(--ring)}
.pager button:disabled{opacity:.35;cursor:default}

/* ---------- radar ---------- */
.sliders{display:flex;gap:var(--s4);flex-wrap:wrap;align-items:center}
.sliders label{display:flex;align-items:center;gap:var(--s2);font:400 12.5px var(--sans);color:var(--text)}
input[type=range]{-webkit-appearance:none;appearance:none;width:124px;height:4px;
  background:var(--line);border-radius:var(--pill);cursor:pointer}
input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:16px;height:16px;
  border-radius:50%;background:var(--ink);border:3px solid var(--paper);
  box-shadow:0 0 0 1px var(--line-2),var(--lift);transition:box-shadow var(--ease)}
input[type=range]:hover::-webkit-slider-thumb{box-shadow:0 0 0 1px var(--ink),var(--lift)}
input[type=range]:focus-visible{outline:none}
input[type=range]:focus-visible::-webkit-slider-thumb{box-shadow:0 0 0 1px var(--ink),var(--ring)}
input[type=range]::-moz-range-thumb{width:14px;height:14px;border-radius:50%;
  background:var(--ink);border:3px solid var(--paper)}
.sliders b{font:600 12px var(--sans);min-width:20px;text-align:right;font-variant-numeric:tabular-nums}
.resetbtn{font:600 11px var(--sans);letter-spacing:.08em;text-transform:uppercase;
  border:1px solid var(--line);background:var(--paper);border-radius:var(--r-ctl);
  padding:9px 14px;cursor:pointer;
  transition:background var(--ease),color var(--ease),border-color var(--ease)}
.resetbtn:hover{background:var(--ink);color:#fff;border-color:var(--ink)}
.resetbtn:focus-visible{outline:none;box-shadow:var(--ring)}
/* ---------- the ranking row ----------
   Collapsed, a row answers three questions and no more: who, how much demand
   against how much of it we can serve, and what that scores. Every other
   number lives in the panel underneath. */
.rk{font:600 12px/1 var(--sans);color:var(--muted-2);font-variant-numeric:tabular-nums}
.cname{font-weight:600;font-size:14.5px;letter-spacing:-.005em}
.opp-label{display:block;margin-top:5px;font:600 13px/1.35 var(--sans);color:var(--text)}
.opp-label::before{content:"";display:inline-block;width:6px;height:6px;border-radius:2px;
  background:var(--accent);margin-right:7px;vertical-align:middle}
.opp-approach{display:block;margin-top:6px;padding:10px 13px;border-radius:var(--r-sm);
  background:var(--iris-soft);color:var(--text);font:400 13px/1.5 var(--sans);max-width:74ch}
.opp-approach b{font-weight:600}
.csub{display:block;margin-top:4px;font:400 12.5px/1.45 var(--sans);color:var(--muted);max-width:52ch}
.na{color:var(--muted);font-style:italic}
.cchips{display:block;margin-top:7px}

.sig{display:grid;gap:7px;min-width:172px;max-width:290px}
.sigrow{display:grid;grid-template-columns:64px 1fr 26px;gap:9px;align-items:center}
.sigrow .k{font:600 9.5px/1 var(--sans);letter-spacing:.07em;text-transform:uppercase;
  color:var(--muted-2)}
.sigrow .t{height:6px;border-radius:var(--pill);background:var(--paper-2)}
.sigrow .t i{display:block;height:100%;border-radius:var(--pill);background:var(--ink)}
.sigrow.sup .t i{background:var(--iris)}
.sigrow .n{font:600 11px/1 var(--sans);color:var(--muted);text-align:right;
  font-variant-numeric:tabular-nums}

.scorecell{display:inline-flex;align-items:center;justify-content:flex-end;gap:11px}
.scoren{font-family:var(--disp);font-weight:700;font-stretch:72%;font-size:27px;line-height:1;
  letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.scoremeter{width:4px;height:32px;border-radius:2px;background:var(--paper-2);position:relative}
.scoremeter i{position:absolute;left:0;right:0;bottom:0;border-radius:2px;background:var(--ink)}
.exp{width:23px;height:23px;flex:none;border-radius:50%;border:1px solid var(--line);
  display:inline-flex;align-items:center;justify-content:center;
  transition:transform var(--ease),background var(--ease),border-color var(--ease)}
.exp::before{content:"";width:6px;height:6px;margin-top:-3px;
  border-right:1.7px solid var(--muted);border-bottom:1.7px solid var(--muted);
  transform:rotate(45deg)}
tr:hover .exp{border-color:var(--line-2)}
tr.open .exp{background:var(--ink);border-color:var(--ink);transform:rotate(180deg)}
tr.open .exp::before{border-color:var(--accent)}
/* the open row is marked on the rail, not by shouting */
#ra-body tr:hover td:first-child{box-shadow:inset 3px 0 0 var(--line-2)}
#ra-body tr.open td:first-child{box-shadow:inset 3px 0 0 var(--accent)}
#ra-body tr.open{background:var(--paper-2)}
.tag.warn{background:#fff4d6;border-color:#e8c766;color:#6b5200}
td .z{color:var(--muted-2)}
.evwhy{margin-bottom:14px}
.evwhy ul{margin:6px 0 0;padding-left:18px;display:grid;gap:5px}
.evwhy li{font:400 13px/1.5 var(--sans);color:var(--ink)}
details.adv{margin:var(--s4) 0 0;border:1px solid var(--line);border-radius:var(--r-ctl);
  padding:14px 16px;background:var(--paper);transition:border-color var(--ease)}
details.adv:hover{border-color:var(--line-2)}
details.adv summary{cursor:pointer;font:600 13px var(--sans);color:var(--muted);
  list-style:none;display:flex;align-items:center;gap:8px}
details.adv summary::-webkit-details-marker{display:none}
details.adv summary::before{content:"";width:6px;height:6px;flex:none;border-right:1.6px solid currentColor;
  border-bottom:1.6px solid currentColor;transform:rotate(-45deg);margin-left:2px;
  transition:transform var(--ease)}
details.adv[open] summary::before{transform:rotate(45deg)}
details.adv[open] summary{margin-bottom:var(--s3);color:var(--ink)}
.svctxt{display:block;font:400 11.5px var(--sans);color:var(--muted);margin-top:3px;white-space:nowrap}
.band{display:inline-block;font:600 10px/1 var(--sans);letter-spacing:.06em;text-transform:uppercase;
  padding:5px 9px;border-radius:var(--pill)}
.band.high{background:var(--ink);color:#fff}
.band.medium{background:var(--paper-2);color:var(--text);border:1px solid var(--line-2)}
.band.low{background:transparent;color:var(--muted-2);border:1px dashed var(--line-2)}
.svcbar{display:inline-block;width:52px;height:8px;background:var(--paper-2);border-radius:2px;
  overflow:hidden;vertical-align:middle;margin-right:6px}
.svcbar i{display:block;height:100%;background:var(--iris)}
.svcbar i.low{background:var(--warn)}
/* ---------- the detail panel: tier two ---------- */
tr.evrow>td{background:var(--paper-2);padding:0}
.ex{padding:20px 18px 22px 20px;box-shadow:inset 3px 0 0 var(--accent)}
.extiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(128px,1fr));gap:1px;
  background:var(--line);border:1px solid var(--line);border-radius:var(--r-ctl);
  overflow:hidden;margin-bottom:var(--s4)}
.tile{background:var(--paper);padding:11px 14px 13px}
.tile .k{font:600 9.5px/1.3 var(--sans);letter-spacing:.08em;text-transform:uppercase;
  color:var(--muted-2)}
.tile .v{font:600 20px/1 var(--sans);margin-top:8px;font-variant-numeric:tabular-nums;
  letter-spacing:-.015em}
.tile .v .sfx{font-weight:400;font-size:12.5px;color:var(--muted);margin-left:4px;letter-spacing:0}
.evhead .sfx{font-weight:400;font-size:11px;letter-spacing:0;text-transform:none;
  color:var(--muted-2);margin-left:9px}
.tile.acc .v{color:var(--iris)}
.tile.zero .v{color:var(--muted-2)}
.excols{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:var(--s4) var(--s5);
  margin-bottom:var(--s4)}
@media(max-width:920px){.excols{grid-template-columns:1fr}}
.evhead{font:600 10px/1 var(--sans);letter-spacing:.12em;text-transform:uppercase;
  color:var(--muted-2);margin:0 0 11px}
.why{list-style:none;display:grid;gap:8px}
.why li{position:relative;padding-left:16px;font:400 13px/1.5 var(--sans);color:var(--ink)}
.why li::before{content:"";position:absolute;left:0;top:8px;width:6px;height:6px;
  border-radius:50%;background:var(--accent);box-shadow:0 0 0 1px var(--line-2)}
.why li.sup::before{background:var(--iris);box-shadow:none}
.mix{display:grid;gap:9px;max-width:440px}
.mix+.evhead{margin-top:var(--s4)}
.mixrow{display:grid;grid-template-columns:minmax(0,1fr) 92px 30px;gap:12px;align-items:center}
.mixrow .k{font:400 12.5px/1.35 var(--sans);color:var(--ink)}
.mixrow .t{height:7px;border-radius:var(--pill);background:var(--line)}
.mixrow .t i{display:block;height:100%;border-radius:var(--pill);background:var(--ink)}
.mixrow.sup .t i{background:var(--iris)}
.mixrow .n{font:600 11.5px/1 var(--sans);text-align:right;color:var(--muted);
  font-variant-numeric:tabular-nums}
.uncov{font:400 12px/1.6 var(--sans);color:var(--muted);margin-top:var(--s3)}
.uncov b{color:var(--warn);font-weight:600}
.uncov .chip{background:#FBEAE6;color:#8C3121}
/* ---------- open-roles timeline (evidence panel) ---------- */
.tlc{position:relative;background:var(--ink);border-radius:var(--r-sm);padding:10px 12px 10px;margin-top:4px}
.tlc svg{display:block;width:100%;height:auto}
.tlc a{cursor:pointer}
.tlc a:hover text{fill:var(--accent)}
.tlhit{cursor:crosshair}
/* Leader lines need more contrast on a dark ground than on a light one --
   at #383C39 they read as gridlines rather than as connectors. */
.tll{stroke:#585D59;stroke-width:1;transition:stroke .14s,stroke-width .14s}
.tlb .cbg{fill:#212422;stroke:#2E3230;transition:fill .14s,stroke .14s}
.tlm .halo{transition:r .14s,opacity .14s}
/* the label, its leader and its dot light up together, so which ad caused
   which step is never in doubt */
.tll.on{stroke:var(--accent);stroke-width:1.5}
.tlb.on .cbg{fill:#31331F;stroke:#5C5B22}
.tlm.on .halo{r:13px;opacity:.26}
.tlmeta{font:400 11.5px/1.5 var(--sans);color:var(--muted-2);margin:9px 2px 0}
.tlmeta b{color:var(--paper);font-weight:600}
/* the hover read-out: which roles were open at the point under the cursor */
.tltip{position:absolute;z-index:6;left:0;top:0;pointer-events:none;opacity:0;
  transition:opacity .1s;width:268px;background:var(--paper);border:1px solid var(--line);
  border-radius:var(--r-sm);box-shadow:0 12px 34px rgba(0,0,0,.4);padding:9px 11px 10px}
.tltip.on{opacity:1}
.tltip.pin{pointer-events:auto}
.tth{font:600 12.5px var(--sans);color:var(--ink);padding-bottom:6px;
  display:flex;justify-content:space-between;align-items:baseline;gap:10px}
.tth span{font:400 10px var(--sans);color:var(--muted);white-space:nowrap}
.ttr{display:grid;grid-template-columns:9px 1fr;gap:0 9px;padding:5px 0;
  border-top:1px solid var(--line);text-decoration:none}
.ttr i{width:8px;height:8px;border-radius:50%;background:var(--accent);
  border:1px solid var(--ink);margin-top:3px}
.ttr.dead i{background:var(--paper);border-color:var(--line-2)}
.ttr.unk i{background:var(--line)}
.ttt{font:500 11.5px/1.3 var(--sans);color:var(--ink)}
.ttm{grid-column:2;font:400 10px var(--sans);color:var(--muted);margin-top:1px}
.ttr.dead .ttt{color:var(--muted)}
.tltip.pin .ttr:hover .ttt{color:var(--link);text-decoration:underline}
.ttmore{font:400 10.5px var(--sans);color:var(--muted);padding-top:7px;border-top:1px solid var(--line)}
.tlpin{display:none;font:600 9.5px var(--sans);letter-spacing:.09em;text-transform:uppercase;
  color:var(--muted-2);margin-top:8px}
.tltip.pin .tlpin{display:block}
tbody tr.clickable{cursor:pointer}

/* ---------- quality ---------- */
.q{display:grid;gap:var(--s3);grid-template-columns:repeat(auto-fit,minmax(340px,1fr))}
.q .panel.span2{grid-column:span 2}
@media(max-width:900px){.q .panel.span2{grid-column:auto}}
.kv{width:100%;font-size:13px}
.kv td{padding:7px 0;border-bottom:1px solid var(--line);line-height:1.45}
.kv td:first-child{padding-right:14px}
.kv td:last-child{text-align:right;font-variant-numeric:tabular-nums;font-weight:500;white-space:nowrap}
.lim{list-style:none}
.lim li{padding:9px 0 9px 20px;border-bottom:1px solid var(--line);position:relative;font-size:13.5px;line-height:1.6}
.lim li:before{content:"";position:absolute;left:0;top:16px;width:8px;height:2px;background:var(--warn)}
footer{background:var(--ink);color:var(--muted-2);padding:var(--s4) 32px var(--s5);
  font:400 12px/1.7 var(--sans)}
footer a{color:var(--muted-2);text-decoration:underline}
@media(max-width:640px){
  header,main,footer{padding-left:16px;padding-right:16px}
  .controls.stick{margin-left:-16px;margin-right:-16px;padding-left:16px;padding-right:16px}
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
  /* rows are [label, ours, market, tension?]: the first bar is always our
     side of the trade, the second always the market's. */
  const [lo, lm] = opts.legend || ['supply', 'demand'];
  const max = Math.max(1e-9, ...rows.flatMap(r => [r[1], r[2]]));
  /* Right-hand value column: either an explicit per-row number (r[3], used by
     the skill-tension chart) or a function of the two bars, which is how the
     gap charts show the thing the reader is actually looking for -- how far
     the market's share runs ahead of ours. */
  const valueOf = opts.value || (r => (r[3] !== undefined ? r[3].toFixed(2) : ''));
  const showValue = opts.value ? true : rows.some(r => r[3] !== undefined);
  const tension = showValue;
  el.innerHTML = '<div class="hbar2">' + rows.map(r => {
    const a = (r[1] / max * 100).toFixed(1), b = (r[2] / max * 100).toFixed(1);
    return `<div class="k" title="${esc(r[0])}">${esc(r[0])}</div>`
         + `<div class="t2">`
         + `<i class="s" style="width:${a}%" title="${esc(lo)} ${(r[1]*100).toFixed(1)}%"></i>`
         + `<i class="d" style="width:${b}%" title="${esc(lm)} ${(r[2]*100).toFixed(1)}%"></i></div>`
         + `<div class="v">${showValue ? esc(String(valueOf(r) ?? '')) : ''}</div>`;
  }).join('') + '</div>'
  + `<div class="lg"><span><i class="s"></i>${esc(lo)}</span><span><i class="d"></i>${esc(lm)}</span>`
  + (showValue ? `<span style="margin-left:auto">${esc(opts.vlabel || 'tension')}</span>` : '')
  + '</div>';
}

/* ---------- generic table ---------- */
function makeTable(cfg) {
  const state = { sort: Math.min(cfg.sort ?? 0, cfg.columns.length - 1),
                  dir: cfg.dir || -1, page: 0, per: cfg.per || 100, rows: [] };
  const head = $(cfg.head), body = $(cfg.body), count = $(cfg.count), pager = $(cfg.pager);

  head.innerHTML = '<tr>' + cfg.columns.map((c, i) => {
    const help = c.help || HELP[c.t];
    return `<th data-i="${i}" class="${c.r ? 'r' : ''}"`
      + (help ? ` data-help="${esc(help)}"` : '')
      + `><span class="t">${esc(c.t)}</span><span class="ar"></span></th>`;
  }).join('') + '</tr>';

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
    slice.forEach((r, i) => {
      /* position within what the reader is actually looking at, not the whole set --
         a filtered list that starts at "3" reads like a bug */
      const pos = state.page * state.per + i + 1;
      const tr = document.createElement('tr');
      tr.innerHTML = cfg.columns.map(c =>
        `<td class="${c.cls || ''}${c.r ? ' r' : ''}">${c.render ? c.render(r, pos) : esc(c.v(r) ?? '')}</td>`
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


/* ---------- glossary ----------
   One definition per term, keyed by the label as it appears on screen, so a
   column and a headline card that say the same word cannot drift into saying
   two different things. Written for a salesperson, not for us: each one says
   what the number IS, and where useful what it is NOT. */
const HELP = {
  /* --- the skill market, the worst offenders --- */
  'Tension': 'Demand share divided by supply share for this skill. Above 1.00 means more openings ask for it than candidates hold it; below 1.00 means we have more of it than the market wants. On this synthetic dataset the whole range is 0.85-1.18, which is too narrow to act on.',
  'Must-have': 'Openings that list this skill as a hard requirement. A candidate without it does not qualify at all.',
  'Nice-to-have': 'Openings that list this skill as desirable but optional. It helps a candidate stand out; its absence does not disqualify them.',
  'Weighted demand': 'Must-have mentions plus nice-to-have mentions at reduced weight, so a hard requirement counts for more than a preference.',
  'Supply': 'Candidates in the dataset who hold this skill.',
  'Supply %': 'Share of all candidates holding this skill.',
  'Demand %': 'Share of all openings asking for this skill.',
  'Qualified for': 'How many of the openings this person meets the must-have threshold for. Recomputed here, not taken from the dataset labels.',

  /* --- company ranking --- */
  'Score /100': 'A percentile within this list, not an absolute grade: 87 means ahead of 87% of the companies here. There is no outcome data to calibrate an absolute score against, so we do not claim one.',
  'Demand · we staff': 'Two separate meters. Demand is how badly this company needs people; We staff is how much of that demand our bench could actually cover. A high score needs both.',
  'IT': 'IT vacancies from this company in the June snapshot, after removing apprenticeships and training roles.',
  'IT %': 'Share of this company’s total job ads that are IT roles. High share plus low volume usually means a software firm, not a buyer.',
  'Median IT age': 'The middle vacancy age: half their IT ads are older than this. Long ages mean roles they are struggling to fill.',
  'Vacancies': 'Open roles counted for this row.',
  'Class': 'What kind of organisation this is, and therefore whether it can appear as a lead: end client and captive IT are prospects, agencies and IT vendors are not.',
  'Top technologies': 'Technologies named in this company’s job titles. Titles only — the source carries no job descriptions, so roughly half of ads name no technology at all.',
  'Regions': 'How many German regions this employer advertises in. A small company hiring across many regions is usually placing people, not hiring them.',

  /* --- bench --- */
  'German demand for this': 'How much unfilled German demand exists for this person’s role and skills, measured from real job ads — never from the synthetic openings.',
  'How rare on our bench': 'How few colleagues could cover the same work. Rare is valuable; common means they are replaceable, however strong the CV.',
  'Public code': 'Public repository activity, shown only for roles that actually publish code. Support and analyst profiles read “not a signal here” because an empty profile says nothing about them either way. Simulated.',
  'Day rate': 'What we would charge a German client per day, and the same figure annualised over 215 billable days — the number a client compares against a salary. Simulated, and deliberately not part of any score.',
  'Available': 'When this person could start. Someone who cannot start does not unlock work this quarter, whatever their skills.',
  'Coverage gap': 'How badly our bench covers this pocket of demand. 1.00 means nobody on the bench can serve it at all.',
  'Bench depth': 'Consultants who could cover this cell. Below five the scarcity estimate is unstable, so we flag it rather than promise it.',
  'Companies': 'Distinct companies whose open roles fall into this cell.',
  'Score': 'What the bench would lose if this person were not on it, times how deployable they are. Not a measure of how good they are in the abstract.',

  /* --- postings --- */
  'Age': 'Days between the ad being published and the snapshot date. Older means longer unfilled — which is the opening, not a defect.',
  'Level': 'Skill level from the German KldB occupational code, not from the job title.',
  'Occupational group': 'The official KldB occupational group the source assigned. It is wrong at row level often enough that we never use it as ground truth.',
};

/* Headline cards carry the same terms as the columns, so they read from the
   same glossary rather than growing a second set of wordings. Matching on the
   visible label keeps this working when a card is added or removed. */
const KPI_HELP = {
  'Companies hiring IT': 'Employers with three or more open IT roles. Below three we cannot tell a hiring pattern from coincidence, so they are not ranked.',
  'Roles open past 3 months': 'Share of IT vacancies still advertised more than 90 days after posting. This is the opening: roles German employers are failing to fill locally.',
  'Hiring done by agencies': 'Share of IT ads placed by recruiters and IT firms rather than the employer who actually needs the person. These are filtered out of the lead list.',
  'Not just counting job ads': 'Rank correlation between our score and simply counting job ads. 0 = completely different, 1 = identical. Lower is better — anyone can count ads.',
  'Recruiters in the list': 'Staffing agencies, IT vendors and our own group appearing in the ranked leads. Should be zero.',
  'Ranking stability': 'Of the top 20, how many stay in the top 20 when every weighting is nudged up or down by a fifth. A list that reshuffles under small changes is being decided by the weights, not the evidence.',
  'Not just the longest CV': 'Rank correlation between a consultant’s value and their number of skills. Near zero is the point: “most skills wins” is as wrong for people as “most vacancies wins” is for companies.',
  'Skill groups': 'Role family × seniority combinations on the bench.',
  'Typical time open': 'The middle vacancy age across the set — half are older, half younger.',
  'Match too loose': 'Mean candidates qualifying per opening in the shipped dataset. With 73 skills and 3-5 must-haves, almost everyone matches almost everything, which is why we do not report retrieval accuracy against it.',
  'Different skills': 'Size of the skill vocabulary in the candidate dataset.',
  'In tech roles': 'Candidates in engineering or data roles. The rest are sales, finance and marketing profiles, irrelevant to an IT consultancy.',
};
document.querySelectorAll('.kpi').forEach(k => {
  const label = k.querySelector('.label');
  const help = label && KPI_HELP[label.textContent.trim()];
  if (help) k.setAttribute('data-help', help);
});

/* ---------- nav ---------- */
document.querySelectorAll('nav button').forEach(b => b.onclick = () => {
  document.querySelectorAll('nav button').forEach(x => x.setAttribute('aria-selected', x === b));
  /* Sections are grouped: one nav tab can reveal several stacked sections. */
  document.querySelectorAll('.screen').forEach(s =>
    s.classList.toggle('on', (s.dataset.g || s.id) === b.dataset.s));
  window.scrollTo(0, 0);
  window.scrollTo(0, 0);
});

/* ---------- overview ---------- */
const C = D.charts;
hbar($('#c-groups'), C.kldb_groups.map(r => [r[0], r[1], r[2] ? 'acc' : '']));
hbar($('#c-class'), C.classes.map(r => [r[0], r[1], r[2] ? 'acc' : '']));
hbar($('#c-tech'), C.tech);
hbar($('#c-domain'), C.domains);
hbar($('#c-level'), C.levels);
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

  hbar2($('#t-supplydemand'), TC.supply_demand,
        {legend: ['candidates who have it', 'openings asking for it']});
  hbar($('#t-tensiontop'), TC.tension_top.map(r => [r[0], r[1], 'acc']), { fmt: v => v.toFixed(2) });

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

  /* Live weights over the scorer's own arithmetic: five effective signals
     (already shrunk toward the pool prior by their evidence weights),
     combined as a weighted GEOMETRIC mean, then read as a percentile inside
     the pool. Reproducing it here rather than approximating it means the
     sliders move the real ranking, not a second looser model. */
  const SIG = ['unmet', 'expansion', 'programme', 'seniority', 'svcsig', 'dealsig'];
  const OURS = ['svcsig', 'dealsig'];        /* our side of the trade */
  const WKEY = { svcsig: 'serviceability', dealsig: 'dealsize' };
  const FLOOR = R.meta.floor || 0.05;
  const W0 = {};
  SIG.forEach(k => W0[k] = Math.round((R.meta.weights[WKEY[k] || k] || 0) * 100));
  const W = { ...W0 };

  const gmean = (r, keys) => {
    let tw = 0, acc = 0;
    keys.forEach(k => {
      const w = W[k];
      if (!w) return;
      tw += w;
      acc += w * Math.log(Math.max(FLOOR, rx(k)(r)));
    });
    return tw ? Math.exp(acc / tw) : 0;
  };
  const pressureOf = r => gmean(r, SIG);
  /* the market's four signals on their own -- the half of the score that has
     nothing to do with us */
  const marketOf = r => gmean(r, SIG.filter(k => OURS.indexOf(k) < 0));
  const reachRaw = r => gmean(r, OURS);

  /* Everything on a row is a percentile of this pool, including the two
     meters. Raw geometric means are tiny and incomparable -- "Demand 15"
     beside "Score 91" reads as a bug, when both describe the same company. */
  let PCT = new Map(), PDEM = new Map(), PREACH = new Map();
  const rank01 = fn => {
    const xs = R.rows.map(r => [r, fn(r)]).sort((a, b) => a[1] - b[1]);
    const m = new Map();
    xs.forEach(([r], i) => m.set(r, xs.length > 1 ? Math.round(1000 * i / (xs.length - 1)) / 10 : 100));
    return m;
  };
  const repct = () => {
    PCT = rank01(pressureOf);
    PDEM = rank01(marketOf);
    PREACH = rank01(reachRaw);
  };
  repct();
  const oppOf = r => PCT.get(r) ?? 0;
  const demandOf = r => PDEM.get(r) ?? 0;
  const reachOf = r => PREACH.get(r) ?? 0;
  let openKey = null;

  /* Score = Demand x what we can serve of it, so a collapsed row carries
     exactly those two meters and its own arithmetic is visible. The four
     components behind Demand, and everything else, live in the panel. */
  const meter = (cls, label, pct) => {
    const w = Math.max(1.5, Math.min(100, pct));
    return `<span class="sigrow ${cls}"><span class="k">${label}</span>`
      + `<span class="t"><i style="width:${w.toFixed(1)}%"></i></span>`
      + `<span class="n">${Math.round(pct)}</span></span>`;
  };
  const NEEDMIX = [
    ['unmet', 'Roles they cannot fill'],
    ['expansion', 'Hiring above their own baseline'],
    ['programme', 'One programme, not scattered backfill'],
    ['seniority', 'Senior roles they cannot fill'],
  ];

  /* One plain-English line describing what is happening at this company.
     Non-technical readers get the story here; the numbers are the columns. */
  const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
  const plain = r => {
    const it = rx('it_n')(r), dead = rx('dead_n')(r) || 0, up = it - dead;
    const o45 = rx('open45')(r);
    const sen = rx('senior_n')(r), techs = rx('techs')(r);
    const stock = rx('now_stock')(r), aged = rx('now_aged')(r);
    const bits = [];
    /* Where the live board answered, lead with what is open TODAY: the
       snapshot is a June crawl and its counts are three months stale. */
    if (rx('verified')(r) && stock !== null && stock !== undefined) {
      bits.push(`${plural(stock, 'IT role', 'IT roles')} open on the board today`);
      if (aged) bits.push(`${aged} of them for over a month`);
    } else {
      bits.push(`${plural(up, 'IT role', 'IT roles')} still up`);
      if (dead) bits.push(`${dead} already taken down`);
      if (o45) bits.push(`${o45} open over 6 weeks`);
    }
    if (sen) bits.push(`${plural(sen, 'is senior', 'are senior')}`);
    let s = bits.join(', ') + '.';
    if (techs.length) {
      s += ` Mostly ${techs.slice(0, 2).join(' and ')}.`;
    }
    const v = rx('svc')(r);
    if (v < 0.5) s += ` We could only staff ${staffLabel(v)}.`;
    return s;
  };

  /* Serviceability in words. The number is a ratio nobody reads correctly;
     the label is what a salesperson actually needs. */
  const staffLabel = v =>
    v >= 0.8 ? 'nearly all of it'
  : v >= 0.6 ? 'most of it'
  : v >= 0.35 ? 'about half'
  : v > 0 ? 'only part of it'
  : 'none of it';

  /* Plain reasons, driven by the same percentiles that drive the score. */
  const reasons = r => {
    const dem = [], sup = [], techs = rx('techs')(r);
    const out = dem;
    const o45 = rx('open45')(r), sen = rx('senior_n')(r);
    if (rx('unmet')(r) >= 0.6)
      out.push(`A high share of their IT ads is still sitting unfilled — demand they cannot close on their own.`);
    else if (o45)
      out.push(`${plural(o45, 'role has', 'roles have')} been open more than 6 weeks.`);
    if (rx('expansion')(r) >= 0.6)
      out.push(`They are hiring well above their own recent baseline — this is growth, not backfill.`);
    if (rx('programme')(r) >= 0.6 && techs.length)
      out.push(`Hiring is concentrated in ${techs[0]} far past what a company this size would do by chance — that is one programme, not routine churn.`);
    if (rx('seniority')(r) >= 0.6 && sen)
      out.push(`Heavy on senior and lead roles (${sen}) — the hardest and slowest to hire.`);
    if (!out.length)
      out.push(`Steady IT hiring, but nothing unusual about the pattern.`);
    /* Staffing bullet: counts only roles still up (delisted ads are not
       demand anyone can staff), and explains depth instead of contradicting
       the "Can we staff it" column. */
    const cov = rx('covered')(r), tot = cov + rx('uncovered')(r), v = rx('svc')(r);
    if (!tot)
      sup.push(`Every ad they were running has since been taken down — nothing left to staff today.`);
    else if (cov === tot && v >= 0.8)
      sup.push(`Our bench covers all ${plural(tot, 'role still up', 'roles still up')}, with depth behind them.`);
    else if (cov === tot)
      sup.push(`Someone on our bench fits each of the ${tot} roles still up, but depth is thin in places.`);
    else
      sup.push(`Our bench could cover ${cov} of the ${tot} roles still up.`);
    /* Deal size: more people on one contract is a different kind of deal. */
    const placeable = rx('placeable')(r);
    if (rx('deal')(r) >= 0.95)
      sup.push(`Team-sized: enough staffable roles here to place about ${Math.round(placeable)} people at once, not one.`);
    else if (tot && placeable < 1.2)
      sup.push(`Thin deal \u2014 about one placeable role, which is a body-shop order rather than a project.`);
    /* the marker colour tells you whose side of the trade a line is about */
    return dem.map(t => ({t: t, sup: false})).concat(sup.map(t => ({t: t, sup: true})));
  };

  /* ---- the detail tier: every number the collapsed row left out ---- */
  const tile = (k, v, cls) =>
    `<div class="tile ${cls || ''}"><p class="k">${k}</p><p class="v">${v}</p></div>`;

  const detailPanel = r => {
    const dead = rx('dead_n')(r) || 0, live = rx('it_n')(r) - dead;
    const o45 = rx('open45')(r), sen = rx('senior_n')(r);
    const cov = rx('covered')(r), tot = cov + rx('uncovered')(r);
    const unc = rx('uncovered_families')(r);

    const verified = rx('verified')(r);
    const stock = rx('now_stock')(r), aged = rx('now_aged')(r);
    /* Two different observations, labelled as such. The board is today and it
       is what the score rests on; the crawl is June and it is the only thing
       we hold clickable URLs for. Showing one without the other is what makes
       "99/100" beside eight dead links look like a bug. */
    const tiles = (verified && stock !== null && stock !== undefined
        ? tile('Open on the board today', stock, stock ? 'acc' : 'zero')
          + tile('Open there over a month', aged || 0, aged ? 'acc' : 'zero')
        : '')
      + tile('From our crawl, still up', live, live ? '' : 'zero')
      + tile('From our crawl, taken down', dead, dead ? '' : 'zero')
      + tile('Open 6+ weeks at crawl', o45, o45 ? '' : 'zero')
      + tile('Senior or lead', sen, sen ? '' : 'zero')
      + tile('Typical age', rx('median_age')(r) + '<span class="sfx">days</span>')
      + tile('Roles we could fill', cov + '<span class="sfx">of ' + tot + '</span>', 'acc')
      + tile('People we could place', rx('placeable')(r).toFixed(1), 'acc');

    const row = (cls, label, frac) =>
      `<div class="mixrow ${cls}"><span class="k">${label}</span>`
      + `<span class="t"><i style="width:${Math.max(1.5, frac * 100).toFixed(1)}%"></i></span>`
      + `<span class="n">${Math.round(frac * 100)}</span></div>`;

    const mix = NEEDMIX.map(([k, label]) => row('', label, rx(k)(r))).join('');
    const ours = row('sup', 'Depth of bench behind those roles', rx('svc')(r))
      + row('sup', 'Deal size \u2014 people we could place at once', rx('deal')(r));

    const uncov = Object.keys(unc).length
      ? `<p class="uncov"><b>We cannot staff:</b> `
        + Object.entries(unc).map(([k, v]) => `<span class="chip">${esc(k)} ×${v}</span>`).join('')
        + ` not skills our bench carries today.</p>` : '';

    return `<div class="ex">`
      /* Open the drawer with the pitch, not the arithmetic: the salesperson
         needs the sentence they will say before the numbers behind it. */
      + `<p class="evhead">The opportunity</p>`
      + `<p class="opp-approach"><b>${esc(rx('opp_label')(r))}.</b> `
      + `${esc(rx('opp_approach')(r))}</p>`
      + `<div class="extiles">${tiles}</div>`
      + `<div class="excols"><div><p class="evhead">Why this company</p><ul class="why">`
      + reasons(r).map(b => `<li${b.sup ? ' class="sup"' : ''}>${esc(b.t)}</li>`).join('')
      + `</ul></div><div>`
      + `<p class="evhead">What the market is doing <span class="sfx">percentile vs the rest of this list</span></p>`
      + `<div class="mix">${mix}</div>`
      + `<p class="evhead">What we bring</p><div class="mix">${ours}</div>${uncov}`
      + `</div></div>`
      + `<p class="evhead">Open roles over time`
      + `<span class="sfx">from the June crawl &mdash; hover the line to see which</span></p>`
      + timeline(rx('timeline')(r)) + `</div>`;
  };

  /* ------------------------------------------------------ open-roles timeline
     The snapshot is a STOCK of ads that were open on the crawl date, so every
     ad counts as open from the day it went up until the day we verified it
     gone: this curve is real concurrent demand, not a per-day posting
     histogram (length bias makes those meaningless). Between the snapshot and
     the re-check we know nothing, so that stretch is drawn as an explicit
     dashed gap instead of a guessed fill date. Hovering anywhere reads out the
     roles that were open at that moment. */
  const TL = {seq: 0, store: {}};
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  /* SVG has no word wrap, and clipping titles mid-word was the whole problem
     with the first version: wrap to two lines, ellipsis only as a last resort */
  const tlWrap = (t, per, maxLines) => {
    const words = String(t).split(/\s+/), lines = [];
    let cur = '', cut = false;
    for (const w of words) {
      const next = cur ? cur + ' ' + w : w;
      if (next.length <= per) { cur = next; continue; }
      if (cur && lines.length + 1 >= maxLines) { cut = true; break; }
      if (cur) lines.push(cur);
      cur = w.length > per ? w.slice(0, per - 1) + '\u2026' : w;
    }
    if (cur) lines.push(cur);
    if (cut) {
      const i = lines.length - 1;
      lines[i] = lines[i].slice(0, per - 1).replace(/[\s,;/-]+$/, '') + '\u2026';
    }
    return lines.slice(0, maxLines);
  };

  const timeline = tl => {
    if (!tl || !tl.length) return '';
    const id = 'tl' + (++TL.seq);
    const ads = tl.slice().sort((a, b) => b.age - a.age);          /* oldest first */

    /* +1 the day an ad went up, -1 the day we verified it gone */
    const evm = new Map();
    const slot = d => { if (!evm.has(d)) evm.set(d, {up: [], down: []}); return evm.get(d); };
    ads.forEach(a => {
      slot(a.age).up.push(a);
      if (a.gone !== null && a.gone !== undefined && a.gone < a.age) slot(a.gone).down.push(a);
    });
    const days = [...evm.keys()].sort((a, b) => b - a);            /* left -> right */

    const maxAge = ads[0].age;
    const lastD = days[days.length - 1];
    /* a tail past the last take-down, otherwise the drop lands exactly on the
       right edge and the state it drops TO is a zero-width period */
    const tail = lastD < 0 ? Math.max(3, Math.round(-lastD * 0.14)) : 0;
    const hi = lastD < 0 ? lastD - tail : 0;                       /* right edge, days ago */
    const lo = Math.max(maxAge + 3, 10);                           /* left edge */

    const W = 1000, L = 46, R = 20, B = 40, PH = 152;
    const pw = W - L - R;
    const gapShare = hi < 0 ? 0.19 : 0;    /* the unobserved stretch, compressed */
    const wA = pw * (1 - gapShare), wB = pw - wA;
    const X = a => a >= 0 ? L + (lo - a) / lo * wA : L + wA + (-a) / (-hi) * wB;
    const xSnap = L + wA;

    const withDate = ads.find(a => a.posted);
    const snapMs = withDate ? Date.parse(withDate.posted) + withDate.age * 864e5 : null;
    const dstr = (a, yr) => {
      if (snapMs === null) return a >= 0 ? a + 'd ago' : (-a) + 'd later';
      const d = new Date(snapMs - a * 864e5);
      return d.getDate() + ' ' + MON[d.getMonth()] + (yr ? ' ' + d.getFullYear() : '');
    };

    /* periods: a run of days over which the set of open roles does not change */
    const periods = [], after = new Map();
    let open = [], cursor = lo;
    days.forEach(d => {
      periods.push({a0: cursor, a1: d, open: open.slice()});
      const ev = evm.get(d);
      open = open.filter(x => ev.down.indexOf(x) < 0).concat(ev.up);
      after.set(d, open.length);
      cursor = d;
    });
    periods.push({a0: cursor, a1: hi, open: open.slice(), tail: tail > 0});
    periods.forEach(q => { q.n = q.open.length; q.x0 = X(q.a0); q.x1 = X(q.a1); });
    const yMax = Math.max(2, periods.reduce((m, q) => Math.max(m, q.n), 0) + 1);

    /* one label per posting day, packed into lanes so two can never collide */
    const LN = 13.5, LMAX = 3, CH = 6.15;
    const labels = [];
    days.forEach(d => {
      const ev = evm.get(d);
      if (!ev.up.length) return;
      const lines = tlWrap(ev.up[0].title, 30, 2);
      if (ev.up.length > 1) {                     /* the counter never wraps alone */
        const suf = '  +' + (ev.up.length - 1);
        const i = lines.length - 1;
        if (lines[i].length + suf.length > 30) lines[i] = lines[i].slice(0, 27 - suf.length) + '\u2026';
        lines[i] += suf;
      }
      labels.push({d, x: X(d), ups: ev.up, lines,
                   w: Math.max(...lines.map(x => x.length)) * CH + 20,
                   dead: ev.up.every(a => a.live === false)});
    });
    const laneEnd = [];
    let lanes = 1;
    labels.forEach(lb => {
      lb.lx = Math.min(Math.max(lb.x, L + lb.w / 2), W - R - lb.w / 2);
      let k = 0;
      while (k < LMAX && laneEnd[k] !== undefined && laneEnd[k] > lb.lx - lb.w / 2) k++;
      if (k >= LMAX) { lb.hide = true; return; }   /* too dense to label: it is in the hover */
      lb.lane = k;
      laneEnd[k] = lb.lx + lb.w / 2 + 10;
      lanes = Math.max(lanes, k + 1);
    });

    const LANEH = 2 * LN + 11;
    const T = 12 + lanes * LANEH + 24;
    const H = Math.round(T + PH + B);
    const Y = c => T + (1 - c / yMax) * PH;
    const laneTop = k => 12 + (lanes - 1 - k) * LANEH;
    periods.forEach(q => q.y = Y(q.n));
    const f = v => v.toFixed(1);

    /* ---- grid + axes ---- */
    let g = '';
    const yStep = Math.max(1, Math.ceil(yMax / 4));
    for (let c = 0; c <= yMax; c += yStep) {
      g += `<line x1="${L}" y1="${f(Y(c))}" x2="${W - R}" y2="${f(Y(c))}" stroke="#2B2E2C"/>`
         + `<text x="${L - 10}" y="${f(Y(c) + 4)}" text-anchor="end" font-size="11.5" `
         + `fill="#8D918E">${c}</text>`;
    }
    g += `<text transform="translate(15,${f(T + PH / 2)}) rotate(-90)" text-anchor="middle" `
       + `font-size="9.5" letter-spacing="1.3" fill="#6B6F6C">OPEN ROLES</text>`;
    const NT = 5;
    for (let i = 0; i < NT; i++) {
      const a = lo - lo * i / NT, x = X(a);
      g += `<line x1="${f(x)}" y1="${f(T)}" x2="${f(x)}" y2="${f(T + PH)}" stroke="#232624"/>`
         + `<text x="${f(x)}" y="${f(T + PH + 17)}" text-anchor="middle" font-size="11" `
         + `fill="#8D918E">${dstr(a)}</text>`;
    }

    /* ---- the snapshot divider and the stretch we have no data for ---- */
    let gapEl = '';
    if (wB > 0) {
      gapEl = `<rect x="${f(xSnap)}" y="${f(T)}" width="${f(wB)}" height="${PH}" fill="#FFFFFF" opacity=".035"/>`
        + `<text x="${f((xSnap + X(lastD)) / 2)}" y="${f(T + PH + 17)}" text-anchor="middle" `
        + `font-size="10.5" fill="#6B6F6C">not observed</text>`
        + `<text x="${W - R}" y="${f(T - 12)}" text-anchor="end" font-size="9.5" letter-spacing="1.1" `
        + `fill="#8D918E">RE-CHECKED ${dstr(lastD).toUpperCase()}</text>`;
    }
    const snapEl = `<line x1="${f(xSnap)}" y1="${f(T - 6)}" x2="${f(xSnap)}" y2="${f(T + PH + 3)}" `
      + `stroke="#565A57" stroke-dasharray="2 4"/>`
      + `<text x="${f(xSnap - 6)}" y="${f(T - 12)}" text-anchor="end" font-size="9.5" letter-spacing="1.1" `
      + `fill="#8D918E">SNAPSHOT ${dstr(0).toUpperCase()}</text>`;

    /* ---- the step line: solid where observed, dashed across the gap ---- */
    const pts = [];
    let cc = 0;
    pts.push([L, Y(0)]);
    days.forEach(d => {
      const x = X(d);
      pts.push([x, Y(cc)]);
      cc = after.get(d);
      pts.push([x, Y(cc)]);
    });
    pts.push([X(hi), Y(cc)]);

    const solid = [], dash = [];
    pts.forEach(q => {
      if (q[0] <= xSnap + 0.01) solid.push(q);
      else {
        if (!dash.length) dash.push([xSnap, solid[solid.length - 1][1]]);
        dash.push(q);
      }
    });
    if (dash.length && solid[solid.length - 1][0] < xSnap - 0.01)
      solid.push([xSnap, solid[solid.length - 1][1]]);

    const pstr = arr => arr.map((q, i) => (i ? 'L' : 'M') + f(q[0]) + ' ' + f(q[1])).join(' ');
    const defs = `<defs><linearGradient id="${id}g" x1="0" y1="0" x2="0" y2="1">`
      + `<stop offset="0" stop-color="#FFEB00" stop-opacity=".2"/>`
      + `<stop offset="1" stop-color="#FFEB00" stop-opacity="0"/></linearGradient></defs>`;
    const area = `<path d="${pstr(solid)} L${f(solid[solid.length - 1][0])} ${f(T + PH)} `
      + `L${L} ${f(T + PH)} Z" fill="url(#${id}g)"/>`;
    const lineA = `<path d="${pstr(solid)}" fill="none" stroke="#FFEB00" stroke-width="2.6" `
      + `stroke-linejoin="round" stroke-linecap="round"/>`;
    const lineB = dash.length
      ? `<path d="${pstr(dash)}" fill="none" stroke="#FFEB00" stroke-width="2" stroke-dasharray="5 5" `
        + `opacity=".5" stroke-linejoin="round"/>` : '';

    /* ---- markers: a dot per step up, a ring per verified take-down ---- */
    /* a bare 4.5px dot disappears against the line it sits on: each marker is
       a solid core inside a translucent halo that grows when its step is
       hovered, so the point of change is unmistakable */
    let marks = '';
    labels.forEach(lb => {
      const cy = Y(after.get(lb.d));
      marks += `<g class="tlm" data-day="${lb.d}">`
        + `<circle class="halo" cx="${f(lb.x)}" cy="${f(cy)}" r="9.5" `
        + `fill="${lb.dead ? '#8D918E' : '#FFEB00'}" opacity="${lb.dead ? '.1' : '.16'}"/>`
        + `<circle cx="${f(lb.x)}" cy="${f(cy)}" r="5.5" fill="${lb.dead ? '#1A1C1B' : '#FFEB00'}" `
        + `stroke="${lb.dead ? '#8D918E' : '#1A1C1B'}" stroke-width="2.5"/></g>`;
    });
    days.filter(d => evm.get(d).down.length).forEach(d => {
      const n = evm.get(d).down.length, x = X(d), y = Y(after.get(d));
      marks += `<g class="tlm" data-day="${d}">`
        + `<circle class="halo" cx="${f(x)}" cy="${f(y)}" r="9.5" fill="#8D918E" opacity=".1"/>`
        + `<circle cx="${f(x)}" cy="${f(y)}" r="5.5" fill="#1A1C1B" stroke="#A8ADA9" stroke-width="2.5"/>`
        + `<text x="${f(x - 12)}" y="${f(y + 4)}" text-anchor="end" font-size="11.5" font-weight="600" `
        + `fill="#A8ADA9">\u2212${n} taken down</text></g>`;
    });

    /* ---- labels: leaders first, then chips, so nothing draws over a title ---- */
    const vis = labels.filter(lb => !lb.hide);
    let lab = vis.map(lb => {
      const top = laneTop(lb.lane), h = lb.lines.length * LN + 9;
      return `<line class="tll" data-day="${lb.d}" x1="${f(lb.lx)}" y1="${f(top + h)}" `
        + `x2="${f(lb.x)}" y2="${f(Y(after.get(lb.d)) - 10)}"/>`;
    }).join('');
    lab += vis.map(lb => {
      const top = laneTop(lb.lane), h = lb.lines.length * LN + 9, x0 = lb.lx - lb.w / 2;
      const text = lb.lines.map((t, j) =>
        `<text x="${f(x0 + 11)}" y="${f(top + 6 + LN * (j + 1) - 3)}" font-size="12" `
        + `font-weight="${j ? 400 : 600}" fill="${lb.dead ? '#9AA09C' : '#F2F2EE'}">${esc(t)}</text>`).join('');
      return `<g class="tlb" data-day="${lb.d}">`
        + `<a href="${esc(lb.ups[0].url)}" target="_blank" rel="noopener">`
        + `<title>${esc(lb.ups.map(a => a.title).join('\n'))}</title>`
        + `<rect class="cbg" x="${f(x0)}" y="${f(top)}" width="${f(lb.w)}" height="${f(h)}" rx="5"/>`
        + `<rect x="${f(x0)}" y="${f(top)}" width="2.5" height="${f(h)}" rx="1.2" `
        + `fill="${lb.dead ? '#8D918E' : '#FFEB00'}"/>${text}</a></g>`;
    }).join('');

    /* ---- hover layer ---- */
    /* a full crosshair: the vertical line finds the date, the horizontal one
       runs back to the axis and carries the count, so the number can be read
       off the chart without going to the tooltip at all */
    const hov = `<g class="tlhi" style="display:none">`
      + `<rect class="tlband" x="0" y="${f(T)}" width="0" height="${PH}" fill="#FFEB00" opacity=".07"/>`
      + `<line class="tlcur" x1="0" x2="0" y1="${f(T - 6)}" y2="${f(T + PH)}" stroke="#FFEB00" opacity=".5"/>`
      + `<line class="tlcurh" x1="${f(L)}" x2="0" y1="0" y2="0" stroke="#FFEB00" opacity=".3" `
      + `stroke-dasharray="3 4"/>`
      + `<circle class="tlcd" cx="0" cy="0" r="6" fill="#FFEB00" stroke="#1A1C1B" stroke-width="2.5"/>`
      + `<g class="tlvp"><rect rx="4" x="0" y="0" width="0" height="18" fill="#FFEB00"/>`
      + `<text x="0" y="0" text-anchor="middle" font-size="11.5" font-weight="700" fill="#1A1C1B"></text>`
      + `</g></g>`
      + `<rect class="tlhit" x="${L}" y="${f(T - 6)}" width="${f(pw)}" height="${f(PH + 6)}" fill="transparent"/>`;

    const svg = `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" `
      + `font-family="Inter,Arial,sans-serif">${defs}${g}${gapEl}${snapEl}${area}${lineA}${lineB}`
      + `${marks}${lab}${hov}</svg>`;

    TL.store[id] = {
      W: W,
      axisX: L,
      periods: periods.map(q => ({
        x0: q.x0, x1: q.x1, y: q.y, n: q.n,
        day: q.a0 >= lo ? null : q.a0,     /* the posting day that opened it */
        label: q.tail ? 'as of ' + dstr(q.a0)
             : (q.a0 >= lo ? 'before ' + dstr(q.a1) : dstr(q.a0) + ' \u2013 ' + dstr(q.a1)),
        open: q.open.map(a => ({title: a.title, url: a.url, live: a.live, family: a.family,
                                when: dstr(a.age, true)})),
      })),
    };

    const liveN = ads.filter(a => a.live === true).length;
    const deadN = ads.filter(a => a.live === false).length;
    const unkN = ads.length - liveN - deadN;
    const meta = `<div class="tlmeta">Every step up is one ad going live; the height is how many `
      + `roles were open at the same time. <b>${ads.length}</b> ads over ${maxAge} days`
      + (deadN ? ` &middot; <b>${deadN}</b> taken down by the re-check` : '')
      + (liveN ? ` &middot; <b>${liveN}</b> still live` : '')
      + (unkN ? ` &middot; ${unkN} not re-checked` : '')
      + ` &middot; hover the line for the roles open on any date, click to pin.`
      + (labels.length > vis.length
          ? ` <b>${labels.length - vis.length}</b> more posting days than fit as labels &mdash; `
            + `they are all on the line.` : '')
      + `</div>`;

    return `<div class="tlc" id="${id}">${svg}`
      + `<div class="tltip"><div class="ttbody"></div>`
      + `<div class="tlpin">pinned &mdash; click the chart to release</div></div>${meta}</div>`;
  };

  /* Listeners have to be attached after the panel HTML lands in the DOM. */
  const wireTimeline = root => {
    root.querySelectorAll('.tlc').forEach(box => {
      const st = TL.store[box.id];
      if (!st || !st.periods.length) return;
      const svg = box.querySelector('svg');
      const tip = box.querySelector('.tltip'), body = tip.querySelector('.ttbody');
      const hl = svg.querySelector('.tlhi'), band = svg.querySelector('.tlband');
      const cur = svg.querySelector('.tlcur'), cd = svg.querySelector('.tlcd');
      const curh = svg.querySelector('.tlcurh');
      const vp = svg.querySelector('.tlvp'), vpr = vp.querySelector('rect'), vpt = vp.querySelector('text');
      let pinned = false, shown = null, litDay = null;

      /* light the label / leader / dot belonging to the hovered step */
      const light = day => {
        if (day === litDay) return;
        svg.querySelectorAll('.on').forEach(el => el.classList.remove('on'));
        if (day !== null && day !== undefined)
          svg.querySelectorAll('[data-day="' + day + '"]').forEach(el => el.classList.add('on'));
        litDay = day;
      };

      const rowOf = a => `<a class="ttr${a.live === false ? ' dead' : (a.live === true ? '' : ' unk')}" `
        + `href="${esc(a.url)}" target="_blank" rel="noopener"><i></i>`
        + `<span class="ttt">${esc(a.title)}</span><span class="ttm">${esc(a.family)}`
        + ` &middot; posted ${esc(a.when)}${a.live === false ? ' &middot; since taken down' : ''}`
        + `</span></a>`;

      const hide = () => {
        hl.style.display = 'none'; tip.classList.remove('on'); shown = null; light(null);
      };

      const paint = (q, cx, cy, vx) => {
        band.setAttribute('x', q.x0);
        band.setAttribute('width', Math.max(0, q.x1 - q.x0));
        cur.setAttribute('x1', vx); cur.setAttribute('x2', vx);
        cd.setAttribute('cx', vx); cd.setAttribute('cy', q.y);
        curh.setAttribute('x2', vx);
        curh.setAttribute('y1', q.y); curh.setAttribute('y2', q.y);
        const vw = 17 + String(q.n).length * 7;
        vpr.setAttribute('x', st.axisX - 7 - vw); vpr.setAttribute('y', q.y - 9);
        vpr.setAttribute('width', vw);
        vpt.setAttribute('x', st.axisX - 7 - vw / 2); vpt.setAttribute('y', q.y + 4);
        vpt.textContent = q.n;
        hl.style.display = '';
        light(q.day);
        if (shown !== q) {
          body.innerHTML = `<div class="tth"><b>${q.n}</b> ${q.n === 1 ? 'role open' : 'roles open'}`
            + `<span>${esc(q.label)}</span></div>`
            + (q.open.length
                ? q.open.slice(0, 5).map(rowOf).join('')
                  + (q.open.length > 5
                      ? `<div class="ttmore">+${q.open.length - 5} more open at the time</div>` : '')
                : `<div class="ttmore">Nothing open yet.</div>`);
          shown = q;
        }
        tip.classList.add('on');
        /* Flip to the other side of the cursor rather than clamping: clamping
           parks the panel on top of the half of the chart being pointed at. */
        const tw = tip.offsetWidth, th = tip.offsetHeight;
        const bw = box.clientWidth, bh = box.clientHeight, PAD = 8, OFF = 18;
        const left = cx + OFF + tw <= bw - PAD ? cx + OFF
                   : (cx - OFF - tw >= PAD ? cx - OFF - tw : Math.max(PAD, bw - tw - PAD));
        tip.style.left = left + 'px';
        tip.style.top = Math.max(PAD, Math.min(cy - th / 2, bh - th - PAD)) + 'px';
      };

      svg.addEventListener('mousemove', e => {
        if (pinned) return;
        const r = svg.getBoundingClientRect(), b = box.getBoundingClientRect();
        const vx = (e.clientX - r.left) / r.width * st.W;
        let q = null;
        st.periods.forEach(z => { if (vx >= z.x0 - 0.5) q = z; });
        if (!q) { hide(); return; }
        paint(q, e.clientX - b.left, e.clientY - b.top, vx);
      });
      svg.addEventListener('mouseleave', () => { if (!pinned) hide(); });
      svg.addEventListener('click', e => {
        if (e.target.closest && e.target.closest('a')) return;
        pinned = !pinned;
        tip.classList.toggle('pin', pinned);
        if (!pinned) hide();
      });
    });
  };

  const renderRadar = makeTable({
    head: '#ra-head', body: '#ra-body', count: '#ra-count', pager: '#ra-pager',
    total: R.rows.length, noun: 'companies', sort: 3, dir: -1,   /* 3 = Score */
    columns: [
      { t: '#', v: r => Math.round(oppOf(r)), r: true,
        render: (r, pos) => `<span class="rk">${pos}</span>` },
      { t: 'Company', v: rx('name'), cls: 'nm', render: r =>
          `<span class="cname">${esc(rx('name')(r))}</span>`
          + (rx('review')(r)
            ? ' <span class="tag warn" title="We could not confirm from the data whether this is a customer or an IT supplier. Check before calling.">unconfirmed</span>' : '')
          + (rx('band')(r) === 'low'
            ? ' <span class="tag" title="Based on only a few job ads">thin evidence</span>' : '')
          + (rx('verified')(r)
            ? ' <span class="tag pub" title="Re-observed on the Bundesagentur board today: open roles, posting flow and agency flags all come from the source rather than from our inference">live-checked</span>' : '')
          /* The brief's missing line: not how big the opportunity is, but
             WHAT it is. Shown above the evidence sentence because it is the
             thing a salesperson reads first and repeats on the call. */
          + `<span class="opp-label">${esc(rx('opp_label')(r))}</span>`
          + `<span class="csub">${esc(plain(r))}</span>`
          + `<span class="cchips">`
          + rx('techs')(r).slice(0, 3).map(t => `<span class="chip">${esc(t)}</span>`).join('')
          + `</span>` },
      { t: 'Demand \u00b7 we staff', v: demandOf, cls: 'sg', render: r =>
          `<span class="sig">${meter('', 'Demand', demandOf(r))}`
          + `${meter('sup', 'We staff', reachOf(r))}</span>` },
      { t: 'Score /100', v: oppOf, r: true, render: r => {
          const v = oppOf(r);
          return `<span class="scorecell"><span class="scoren">${Math.round(v)}</span>`
            + `<span class="scoremeter"><i style="height:${Math.max(4, Math.min(100, v)).toFixed(0)}%"></i></span>`
            + `<span class="exp"></span></span>`; } },
    ],
    filter: () => {
      const q = $('#ra-q').value.trim().toLowerCase();
      const cls = $('#ra-class').value, band = $('#ra-band').value;
      const noRev = $('#ra-noreview').checked;
      const out = R.rows.filter(r =>
        (!q || rx('name')(r).toLowerCase().includes(q))
        && (!cls || rx('segment')(r) === cls)
        && (!band || rx('band')(r) === band)
        && (!noRev || !rx('review')(r)));
      /* headline numbers describe what is on screen -- a header saying 306
         above a list of 109 reads as a bug to anyone who is not us */
      const sum = k => out.reduce((a, r) => a + rx(k)(r), 0);
      /* Headline cards are optional: a removed card must not take the whole
         script down with it. Before this guard, deleting one KPI threw on the
         first filter pass and every table on every tab rendered empty. */
      const setKpi = (sel, v) => { const el = $(sel); if (el) el.textContent = fmt(v); };
      setKpi('#k-ranked', out.length);
      setKpi('#k-roles', sum('it_n'));
      setKpi('#k-stuck', sum('open45'));
      return out;
    },
    onRow: (tr, r) => {
      tr.classList.add('clickable');
      if (rx('name')(r) === openKey) tr.classList.add('open');
      tr.onclick = () => {
        const key = rx('name')(r);
        openKey = openKey === key ? null : key;
        renderRadar();
        if (openKey !== key) return;
        const anchor = [...document.querySelectorAll('#ra-body tr')]
          .find(x => x.dataset.ev === key);
        if (!anchor) return;
        const row = document.createElement('tr');
        row.className = 'evrow';
        row.innerHTML = `<td colspan="4">${detailPanel(r)}</td>`;
        anchor.after(row);
        wireTimeline(row);
      };
      tr.dataset.ev = rx('name')(r);
    },
  });

  const syncW = () => {
    SIG.forEach(k => {
      W[k] = +$('#w-' + k).value;
      $('#wv-' + k).textContent = W[k];
    });
    repct();
    openKey = null;
    renderRadar();
  };
  SIG.forEach(k => {
    const el = $('#w-' + k);
    el.value = W0[k];
    $('#wv-' + k).textContent = W0[k];
    el.oninput = syncW;
  });
  $('#w-reset').onclick = () => {
    SIG.forEach(k => $('#w-' + k).value = W0[k]);
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

  /* Both series are normalised to their own SUM, not their own maximum.
     Dividing each by its max only says "this is the biggest bar in its row" --
     the two bars then sit side by side implying a comparison that neither
     number supports, because postings and consultants are different units.
     Shares are comparable: "erp is 7% of the demand we rank and 1% of the
     people we have" is a true sentence, and it is the sentence this chart
     exists to make.
     `unspecified` is dropped: it is 41% of demand and 0% of the bench, so on
     the old scaling it drew a full-width gap bar for a technology that does
     not exist. It is the half of ads that name no technology at all -- a
     coverage limit, reported as a number below, not a capability gap. */
  const gapRows = B.gap.filter(g => g[0] !== 'unspecified');
  const dSum = gapRows.reduce((a, g) => a + g[1], 0) || 1;
  const bSum = gapRows.reduce((a, g) => a + g[2], 0) || 1;
  hbar2($('#b-gap'),
    gapRows.map(g => [g[0], g[2] / bSum, g[1] / dSum])
           .sort((a, b) => b[2] - a[2]),
    {legend: ['share of our bench', 'share of ranked demand'],
     vlabel: 'gap',
     value: r => ((r[2] - r[1]) * 100).toFixed(0) + ' pts'});

  /* One paired chart, not two one-sided ones: demand and supply per role
     family are the same comparison, and showing them as separate charts made
     the reader hold two orderings in their head to spot a gap. */
  const famSum = B.supply_vs_pull.reduce((a, r) => [a[0] + r[1], a[1] + r[2]], [0, 0]);
  hbar2($('#b-famgap'),
    B.supply_vs_pull.map(r => [r[0], r[1] / (famSum[0] || 1), r[2] / (famSum[1] || 1)])
                    .sort((a, b) => b[2] - a[2]),
    {legend: ['share of our bench', 'share of ranked demand'],
     vlabel: 'gap',
     value: r => ((r[2] - r[1]) * 100).toFixed(0) + ' pts'});

  /* cells table */
  const renderCells = makeTable({
    head: '#ce-head', body: '#ce-body', count: '#ce-count', pager: '#ce-pager',
    total: B.cells.length, noun: 'cells', sort: 3, dir: -1,
    columns: [
      { t: 'Family', v: r => r[0], cls: 'nm' },
      { t: 'Seniority', v: r => r[1] },
      { t: 'Technology', v: r => r[2], render: r => `<span class="chip">${esc(r[2])}</span>` },
      { t: 'Weighted demand', v: r => r[3], r: true, render: r => r[3].toFixed(1) },
      { t: 'Coverage gap', v: r => r[4], r: true, render: r =>
          `<span class="svcbar"><i class="${r[4] > 0.5 ? 'low' : ''}" style="width:${(r[4]*100).toFixed(0)}%"></i></span>`
          + `<span class="svctxt">${(r[4] * 100).toFixed(0)}%</span>` },
      { t: 'Bench depth', v: r => r[5], r: true, render: r =>
          `${fmt(r[5])}` + (r[5] < 3 ? ' <span class="tag noise" title="Fewer than three consultants can serve this cell">thin</span>' : '') },
      { t: 'Vacancies', v: r => r[6], r: true },
      { t: 'Companies', v: r => r[7], r: true },
    ],
    filter: () => B.cells,
  });
  renderCells();

  /* Say out loud what the ranking is based on. The three factors are the
     score; showing them as bare 0-1 decimals told the reader nothing. */
  const bandWord = v =>
    v >= 0.75 ? '<b>high</b>' : v >= 0.45 ? 'medium' : '<span class="z">low</span>';
  const availWord = a => ({
    now: 'now', in_30d: 'in 30 days', in_90d: 'in 90 days', unavailable: 'not available'
  }[a] || a);
  const benchPlain = r => {
    const sen = bx('seniority')(r), fam = bx('family')(r), yrs = bx('years')(r);
    const tags = bx('tags')(r), pull = bx('pull')(r), scar = bx('scarcity')(r);
    let s = `${sen} ${fam}, ${yrs} yrs`;
    if (tags.length) s += ` — ${tags.slice(0, 2).join(' and ')}`;
    s += '.';
    s += pull >= 0.75 ? ' German companies badly need this skill'
       : pull >= 0.45 ? ' There is steady German demand for this'
       : ' German demand for this is thin';
    s += scar >= 0.75 ? ', and we have very few people like this.'
       : scar >= 0.45 ? ', and we are not deep in it.'
       : ', and we already have plenty of them.';
    return s;
  };

  /* bench value table */
  const renderBench = makeTable({
    head: '#be-head', body: '#be-body', count: '#be-count', pager: '#be-pager',
    total: B.cand_rows.length, noun: 'consultants', sort: 8, dir: -1,   /* 8 = Score */
    columns: [
      { t: '#', v: bx('rank'), r: true, render: (r, pos) => `<b>${pos}</b>` },
      { t: 'Consultant', v: bx('id'), cls: 'nm', render: r =>
          `<span class="cname">${esc(bx('id')(r))}</span>`
          + ' <span class="tag noise" title="Generated bench — no real person">synthetic</span>'
          + (bx('german')(r) ? ' <span class="tag">speaks German</span>' : '')
          + `<span class="csub">${esc(benchPlain(r))}</span>` },
      { t: 'Skills', v: bx('tags'), sortKey: r => bx('tags')(r).length,
        render: r => bx('tags')(r).map(t => `<span class="chip">${esc(t)}</span>`).join('') },
      { t: 'Available', v: bx('availability'), render: r => esc(availWord(bx('availability')(r))) },
      { t: 'German demand for this', v: bx('pull'), r: true,
        render: r => bandWord(bx('pull')(r)) },
      { t: 'How rare on our bench', v: bx('scarcity'), r: true, render: r =>
          bandWord(bx('scarcity')(r)) + (bx('thin')(r) ? ' <span class="tag noise">thin</span>' : '') },
      /* Public code. Only shown where it means something: analyst and support
         consultants are not worse engineers for having no repositories, so the
         column says so rather than printing a zero that reads as a verdict. */
      { t: 'Public code', v: r => bx('gh_score')(r) ?? -1, r: true,
        sortKey: r => bx('gh_score')(r) ?? -1,
        render: r => {
          if (!bx('gh_relevant')(r))
            return '<span class="na" title="A public profile is not evidence '
                 + 'either way for this kind of role">not a signal here</span>';
          const s = bx('gh_score')(r);
          if (s === null || s === undefined)
            return '<span class="na" title="No public profile found">none</span>';
          return `${bandWord(s / 100)}<span class="csub">`
               + `${bx('gh_contrib')(r).toLocaleString()} contributions · `
               + `${bx('gh_repos')(r)} repos</span>`;
        } },
      /* What we would charge. Shown, never scored: a generated price must not
         reorder the ranking. */
      { t: 'Day rate', v: bx('day_rate'), r: true,
        render: r => `&euro;${bx('day_rate')(r).toLocaleString()}`
          + `<span class="csub">&euro;${Math.round(bx('annual_cost')(r) / 1000)}k a year</span>` },
      { t: 'Score', v: bx('value'), r: true,
        render: r => `<span class="score">${bx('value')(r).toFixed(0)}</span>` },
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
