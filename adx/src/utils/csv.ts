import type { NormalizedNewGame } from "../dataeye/types.js";

const CSV_HEADERS: Array<keyof NormalizedNewGame> = [
  "statDate",
  "productId",
  "productName",
  "productIcon",
  "stableProductIcon",
  "firstSeen",
  "type",
  "platformName",
  "detailUrl",
  "fetchedAt"
];

const COMPANY_CSV_HEADERS: Array<keyof NormalizedNewGame> = [
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

interface CsvOptions {
  includeCompanyName?: boolean;
}

function escapeCsvCell(value: string | number | undefined): string {
  const text = String(value ?? "");
  if (/[",\r\n]/.test(text)) {
    return `"${text.replace(/"/g, "\"\"")}"`;
  }

  return text;
}

export function toCsv(rows: NormalizedNewGame[], options: CsvOptions = {}): string {
  const headers = options.includeCompanyName ? COMPANY_CSV_HEADERS : CSV_HEADERS;
  const header = headers.join(",");
  const body = rows.map((row) => headers.map((headerKey) => escapeCsvCell(row[headerKey])).join(","));
  return [header, ...body].join("\r\n");
}

export const UTF8_BOM = "\uFEFF";
