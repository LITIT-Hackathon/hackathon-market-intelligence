/** 12345 -> "12,345"; null/undefined -> "". */
export const fmt = (n: number | null | undefined): string =>
  n === null || n === undefined ? "" : n.toLocaleString("en-US");

/** 0.2845 -> "28%", 0.034 -> "3.4%" */
export const pct = (n: number): string => (n * 100).toFixed(n < 0.1 ? 1 : 0) + "%";

/** Python's f"{x * 100:.Nf}%" */
export const pct1 = (n: number): string => (n * 100).toFixed(1) + "%";
export const pct2 = (n: number): string => (n * 100).toFixed(2) + "%";

export const plural = (n: number, one: string, many: string): string =>
  `${n} ${n === 1 ? one : many}`;
