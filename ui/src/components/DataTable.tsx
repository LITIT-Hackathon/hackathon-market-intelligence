import { useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { fmt } from "../format";

export interface Column<R> {
  /** header text */
  t: string;
  /** what this column actually measures, shown on hover. Columns carrying a
      derived or non-obvious number should always have one: the header has
      room for two words and the reader needs a sentence. */
  help?: string;
  /** the cell's value: sort key and, without `render`, the text shown */
  v: (r: R) => unknown;
  sortKey?: (r: R) => unknown;
  /** `pos` is the row's position within what the reader is looking at --
      a filtered list that starts at "3" reads like a bug */
  render?: (r: R, pos: number) => ReactNode;
  cls?: string;
  /** right-aligned numeric column */
  r?: boolean;
  /** first click sorts ascending */
  asc?: boolean;
}

interface Props<R extends object> {
  columns: Column<R>[];
  /** already filtered; sorting and paging happen here */
  rows: R[];
  sort?: number;
  dir?: 1 | -1;
  per?: number;
  rowClass?: (r: R) => string;
  onRowClick?: (r: R) => void;
  /** detail row rendered underneath a row, when it returns anything */
  expanded?: (r: R) => ReactNode;
  bodyId?: string;
  maxHeight?: string;
  /** extra class on the scroll wrapper, for tables that ARE the page */
  wrapClass?: string;
}

/* Rows are keyed by identity, not by any column: company names, for one, are
   not unique, and a duplicate key leaves React holding a stale <tr> after a
   re-sort. The payload's row arrays never change, so a lazily assigned id per
   object is a stable key for the life of the page. */
const ids = new WeakMap<object, number>();
let nextId = 0;
function keyOf(r: object): number {
  let id = ids.get(r);
  if (id === undefined) {
    id = ++nextId;
    ids.set(r, id);
  }
  return id;
}

interface Hint { text: string; x: number; y: number }

/** The header hint. Portalled to <body> so `.tw`'s overflow cannot clip it,
    and positioned under the header cell it belongs to. */
function HeadHint({ hint }: { hint: Hint }) {
  const pad = 12;
  const w = 280;
  const x = Math.min(Math.max(pad + w / 2, hint.x), window.innerWidth - pad - w / 2);
  return createPortal(
    <div className="thtip" style={{ left: x, top: hint.y + 8, width: w }} role="tooltip">
      {hint.text}
    </div>,
    document.body,
  );
}

function cmp(x: unknown, y: unknown, dir: number): number {
  if (x === null || x === undefined) return 1;
  if (y === null || y === undefined) return -1;
  if (typeof x === "string") return dir * x.localeCompare(y as string);
  return dir * (Number(x) - Number(y));
}

/** Sortable, paged table. Keeps the hand-written page's behaviour: nulls sort
    last either way, a header click on the sorted column flips it, paging
    resets on sort and clamps on filter. */
export function DataTable<R extends object>(props: Props<R>) {
  const { columns, rows, per = 100, rowClass, onRowClick, expanded, bodyId,
          maxHeight, wrapClass } = props;
  const [sort, setSort] = useState(Math.min(props.sort ?? 0, columns.length - 1));
  const [dir, setDir] = useState<1 | -1>(props.dir || -1);
  const [page, setPage] = useState(0);
  const [hint, setHint] = useState<Hint | null>(null);
  const tw = useRef<HTMLDivElement>(null);

  const sorted = useMemo(() => {
    const col = columns[sort];
    const key = col.sortKey || col.v;
    const out = rows.slice();
    out.sort((a, b) => cmp(key(a), key(b), dir));
    return out;
  }, [rows, columns, sort, dir]);

  const pages = Math.max(1, Math.ceil(sorted.length / per));
  const cur = Math.min(page, pages - 1);
  const slice = sorted.slice(cur * per, (cur + 1) * per);

  const clickHead = (i: number) => {
    if (sort === i) setDir((d) => (d < 0 ? 1 : -1));
    else {
      setSort(i);
      setDir(columns[i].asc ? 1 : -1);
    }
    setPage(0);
  };
  const turn = (d: number) => {
    setPage(cur + d);
    if (tw.current) tw.current.scrollTop = 0;
  };

  const style: CSSProperties | undefined = maxHeight ? { maxHeight } : undefined;
  return (
    <>
      <div className={wrapClass ? `tw ${wrapClass}` : "tw"} style={style} ref={tw}>
        <table>
          <thead>
            <tr>
              {columns.map((c, i) => (
                <th key={i} className={`${c.r ? "r" : ""}${c.help ? " has-help" : ""}`}
                  onClick={() => clickHead(i)}
                  onMouseEnter={c.help ? (e) => {
                    const b = e.currentTarget.getBoundingClientRect();
                    setHint({ text: c.help as string, x: b.left + b.width / 2, y: b.bottom });
                  } : undefined}
                  onMouseLeave={c.help ? () => setHint(null) : undefined}>
                  <span className="thl">{c.t}</span>
                  <span className="ar">{i === sort ? (dir < 0 ? "↓" : "↑") : ""}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody id={bodyId}>
            {slice.map((r, i) => (
              <RowPair
                key={keyOf(r)}
                r={r}
                pos={cur * per + i + 1}
                columns={columns}
                className={rowClass ? rowClass(r) : ""}
                onClick={onRowClick}
                detail={expanded ? expanded(r) : null}
              />
            ))}
          </tbody>
        </table>
      </div>
      {hint && <HeadHint hint={hint} />}
      <div className="pager">
        {pages > 1 && (
          <>
            <button disabled={cur === 0} onClick={() => turn(-1)}>Previous</button>
            <span>Page {cur + 1} of {fmt(pages)}</span>
            <button disabled={cur >= pages - 1} onClick={() => turn(1)}>Next</button>
          </>
        )}
      </div>
    </>
  );
}

function RowPair<R>({
  r, pos, columns, className, onClick, detail,
}: {
  r: R;
  pos: number;
  columns: Column<R>[];
  className: string;
  onClick?: (r: R) => void;
  detail: ReactNode;
}) {
  return (
    <>
      <tr className={className || undefined} onClick={onClick ? () => onClick(r) : undefined}>
        {columns.map((c, j) => (
          <td key={j} className={`${c.cls || ""}${c.r ? " r" : ""}` || undefined}>
            {c.render ? c.render(r, pos) : text(c.v(r))}
          </td>
        ))}
      </tr>
      {detail ? (
        <tr className="evrow">
          <td colSpan={columns.length}>{detail}</td>
        </tr>
      ) : null}
    </>
  );
}

function text(v: unknown): string {
  return v === null || v === undefined ? "" : String(v);
}

/** "<b>1,234</b> of 18,416 companies" -- lives in the controls row. */
export function Count({ n, total, noun, id }: { n: number; total: number; noun: string; id?: string }) {
  return (
    <span className="count" id={id}>
      <b>{fmt(n)}</b> of {fmt(total)} {noun}
    </span>
  );
}
