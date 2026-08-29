# Opportunity Radar — UI

React + TypeScript app, built with Vite into **one HTML file** so the
deliverable stays what it always was: `ui/index.html`, opened by double-click,
no server, no network.

```
ui/
  app.html            Vite entry: fonts, an empty <script id="opradar-data"> tag, #root
  src/
    main.tsx          reads the data tag (or fetches ./payload.json in dev) and mounts <App/>
    App.tsx           header, nav tabs, footer; every screen stays mounted so filters survive a tab switch
    data.ts           payload types + `indexer()` for the columnar tables
    styles.css        the whole stylesheet (design tokens at the top)
    components/       DataTable (sort/page), Charts (HBar, Cols, HBar2), Kpi/Kv
    screens/          one file per section: Brief, Radar (+Timeline), Companies, Overview,
                      Quality, Postings, Bench, Talent, Candidates
  dist/app.html       BUILD OUTPUT, committed: the template `python -m opradar.ui` fills
  index.html          GENERATED, git-ignored: dist/app.html + the data
  payload.json        GENERATED, git-ignored: the same data as a file, for `npm run dev`
```

## Day to day

| I changed…                 | Run                                                    |
|----------------------------|--------------------------------------------------------|
| the data / the pipeline    | `python -m opradar.ui` (no Node needed)                |
| anything under `ui/src`    | `cd ui && npm run build`, then `python -m opradar.ui`  |
| …and want live reload      | `python -m opradar.ui` once, then `cd ui && npm run dev` |

First time only: `cd ui && npm install`.

`npm run build` type-checks (`tsc --noEmit`, strict) and then bundles. Commit
`dist/app.html` with your change so teammates without Node still get the new UI.

## How the data gets in

`app.html` ships an empty `<script id="opradar-data" type="application/json">`.
`opradar.ui.render()` drops the compact JSON payload (~4 MB, `</` escaped) into
it; `main.tsx` does one `JSON.parse` and renders. Nothing is fetched at
runtime except the Google Fonts stylesheet, and the page works without it.

The Ask box on the Briefing tab probes `/ask` on the same origin and only
shows itself when `python -m opradar.ask` is serving the page.

## Conventions worth keeping

- Tables are columnar (`cols` + array rows) and rows are never copied into
  objects — that is what keeps a 4 MB payload fast. Use `indexer(cols)` to get
  typed accessors.
- `DataTable` keys rows by object identity, not by a column: company names are
  not unique.
- Sort, filter and percentile arithmetic mirror `opradar.score` exactly; the
  weight sliders re-run the scorer's geometric mean in the browser, they do not
  approximate it.
