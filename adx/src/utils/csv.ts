import type { NormalizedNewGame } from "../dataeye/types.js";

const CSV_HEADERS: Array<keyof NormalizedNewGame> = [
  "statDate",
  "productId",
  "productName",
  "companyName",
  "productIcon",
  "stableProductIcon",
  "firstSeen",
  "type",
  "platformName",
  "detailUrl",
  "fetchedAt"
];

function escapeCsvCell(value: string | number | undefined): string {
  const text = String(value ?? "");
  if (/[",\r\n]/.test(text)) {
    return `"${text.replace(/"/g, "\"\"")}"`;
  }

  return text;
}

export function toCsv(rows: NormalizedNewGame[]): string {
  const header = CSV_HEADERS.join(",");
  const body = rows.map((row) => CSV_HEADERS.map((headerKey) => escapeCsvCell(row[headerKey])).join(","));
  return [header, ...body].join("\r\n");
}

export const UTF8_BOM = "\uFEFF";
