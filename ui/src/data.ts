/* The payload `opradar.ui` builds. Tables are columnar -- a `cols` list and
   rows that are plain arrays -- because that is what keeps 4 MB of embedded
   JSON small and fast; `indexer()` turns a column name into an accessor so the
   screens never index rows by number. */

export type Cell =
  | string
  | number
  | boolean
  | null
  | number[]
  | string[]
  | Record<string, number>
  | TimelineAd[];
export type Row = Cell[];
export interface Table {
  cols: string[];
  rows: Row[];
}

export interface TimelineAd {
  title: string;
  url: string;
  age: number;
  family: string;
  live: boolean | null;
  posted: string | null;
  gone: number | null;
}

export interface Meta {
  generated: string;
  snapshot: string;
  scope: string;
  postings_total: number;
  postings_shown: number;
  companies_total: number;
  it_postings: number;
  it_companies_3plus: number;
  competitor_it_share: number;
  median_age: number;
  stale_share: number;
  entities: number;
  raw_employers: number;
  tech_coverage_it: number;
}

export type Bar = [string, number];
export type FlagBar = [string, number, boolean];

export interface Charts {
  kldb_groups: FlagBar[];
  classes: FlagBar[];
  tech: Bar[];
  domains: Bar[];
  levels: Bar[];
  months: Bar[];
  age_buckets: Bar[];
  regions: [string, number, number | null][];
}

export interface Quality {
  entity: {
    raw_employer_strings: number;
    resolved_entities: number;
    collapse_ratio: number;
    companies_with_multiple_name_variants: number;
    largest_variant_clusters: { company: string; variants: string[] }[];
  };
  nulls: Record<string, number>;
  classification: {
    competitor_companies: number;
    competitor_postings: number;
    competitor_posting_share: number;
    noise_companies: number;
    needs_review: number;
    needs_review_examples?: { company: string; postings: number; sectors: number; regions: number }[];
  };
  technology: { tech_coverage: number; it_tech_coverage: number };
  seniority: { derived_mix: Record<string, number>; raw_unknown_share: number };
}

export interface Talent {
  meta: {
    candidates: number;
    openings: number;
    skill_vocabulary: number;
    tech_candidates: number;
    mean_pool: number;
    mean_skills: number;
    bridge_pct: number;
    bridge_coverage: number;
    bridge_shared: unknown;
    bridge_missing: unknown;
  };
  charts: {
    role_family: Bar[];
    seniority: Bar[];
    experience: Bar[];
    industry: Bar[];
    education: Bar[];
    skill_family: Bar[];
    supply_demand: [string, number, number, number][];
    tension_top: Bar[];
    tension_bottom: Bar[];
    role_demand: Bar[];
  };
  dicts: { skills: string[] };
  candidates: Table;
  skills: Table;
  quality: {
    labelled_pairs: number;
    labels_per_opening: { mean: number };
    satisfy_documented_rule: number;
    mean_qualified_pool: number;
    labelled_share_of_pool: number;
    same_seniority: number;
    same_role: number;
  };
  options: { roles: string[]; seniority: string[]; industries: string[]; families: string[] };
}

export interface Radar extends Table {
  meta: {
    ranked: number;
    channels: number;
    config_hash: string;
    weights: Record<string, number>;
    floor: number;
  };
  validation: {
    v1_rho: number;
    v1_verdict: string;
    v2: string;
    v3_min: number;
    v3_k: number;
    v3_verdict: string;
  };
}

export interface Bench {
  meta: { size: number; cells: number; thin_cells: number; german_speakers: number; people_rho: number };
  /** true when bench_sim.parquet supplied the day rate / rating / GitHub columns */
  simulated: boolean;
  cand_cols: string[];
  cand_rows: Row[];
  cells: [string, string, string, number, number, number, number, number, number][];
  supply_vs_pull: [string, number, number][];
  gap: [string, number, number][];
}

export interface CohortRow {
  key: string;
  name: string;
  rank: number | null;
  it_n?: number;
  now_it_stock?: number;
  now_aged_open?: number;
  now_it_flow_28?: number;
}

export interface Brief {
  crawl_date: string;
  board_date: string | null;
  headline: string;
  cohorts: {
    stalled: CohortRow[];
    stalled_n: number;
    accelerating: CohortRow[];
    accelerating_n: number;
    quiet: CohortRow[];
    quiet_n: number;
    stuck: CohortRow[];
    stuck_n: number;
    observed_n: number;
  };
  demand: { tech: { name: string; weight: number }[]; families: { name: string; weight: number }[] };
  ours: {
    companies_ranked: number;
    companies_with_live_roles: number;
    companies_with_nothing_to_staff: number;
    people_we_could_place: number;
    roles_our_bench_covers: number;
    roles_live_in_our_crawl: number;
    ads_read_in_full?: number;
    ads_saying_they_buy_external_help?: number;
    ads_with_a_blocker_we_cannot_meet?: number;
  };
  calls: { rank: number | null; name: string; why: string }[];
  narration: { paragraphs: string[]; model: string } | null;
  examples: string[];
}

export interface Payload {
  meta: Meta;
  dicts: {
    companies: string[];
    groups: string[];
    levels: string[];
    seniority: string[];
    regions: string[];
    tech: string[];
  };
  postings: Table;
  companies: Table;
  charts: Charts;
  quality: Quality;
  talent: Talent | null;
  options: { classes: string[]; seniority: string[]; regions: string[]; tech: string[] };
  radar: Radar | null;
  bench: Bench | null;
  brief: Brief | null;
}

/** Column-name accessor factory for a columnar table. */
export function indexer(cols: string[]) {
  const idx: Record<string, number> = {};
  cols.forEach((c, i) => (idx[c] = i));
  return <T extends Cell = Cell>(name: string): ((r: Row) => T) => {
    const i = idx[name];
    if (i === undefined) throw new Error(`unknown column ${name}`);
    return (r: Row) => r[i] as T;
  };
}

/** Dictionary-encoded string: an index into a vocabulary, or null. */
export const dict = (vocab: string[], i: number | null | undefined): string | null =>
  i === null || i === undefined ? null : vocab[i];

/** Built page: the payload sits in a JSON script tag. Dev server: fetch it. */
export async function loadPayload(): Promise<Payload> {
  const el = document.getElementById("opradar-data");
  const text = el?.textContent?.trim();
  if (text) return JSON.parse(text) as Payload;
  const res = await fetch("./payload.json").catch(() => null);
  if (!res || !res.ok) {
    throw new Error(
      "This page has no data in it. Run `python -m opradar.ui` to build ui/index.html " +
        "(it also writes ui/payload.json for `npm run dev`).",
    );
  }
  return (await res.json()) as Payload;
}
