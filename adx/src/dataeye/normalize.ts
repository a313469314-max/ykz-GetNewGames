import type { DataEyeNewProductDay, NormalizedNewGame } from "./types.js";

const PLATFORM_MAP: Record<string, string> = {
  "1": "iOS",
  "2": "微信小游戏",
  "4": "QQ小游戏",
  "5": "H5",
  "6": "PC",
  "7": "抖音小游戏",
  "22": "快手小游戏"
};

export function mapPlatformName(type: number | string | undefined): string {
  if (type === undefined) {
    return "unknown:undefined";
  }

  const normalized = String(type);
  return PLATFORM_MAP[normalized] ?? `unknown:${normalized}`;
}

export function toStableProductIcon(productIcon?: string): string {
  if (!productIcon) {
    return "";
  }

  try {
    const url = new URL(productIcon);
    url.search = "";
    return url.toString();
  } catch {
    return productIcon.split("?")[0];
  }
}

export function getProductCompanyName(product: {
  companyName?: unknown;
  mainCompany?: unknown;
  company?: unknown;
  publisherName?: unknown;
  developerName?: unknown;
}): string {
  const value =
    product.companyName ??
    product.mainCompany ??
    product.company ??
    product.publisherName ??
    product.developerName ??
    "";

  return String(value).trim();
}

export function normalizeNewGames(day: DataEyeNewProductDay, fetchedAt: string): NormalizedNewGame[] {
  const deduped = new Map<string, NormalizedNewGame>();

  for (const product of day.products ?? []) {
    const productId = String(product.productId ?? "").trim();
    if (!productId) {
      continue;
    }

    const type = typeof product.type === "number" ? product.type : Number(product.type ?? NaN);
    const normalizedType = Number.isNaN(type) ? String(product.type ?? "") : type;
    const row: NormalizedNewGame = {
      statDate: day.statDate,
      productId,
      productName: String(product.productName ?? "").trim(),
      companyName: getProductCompanyName(product),
      productIcon: String(product.productIcon ?? "").trim(),
      stableProductIcon: toStableProductIcon(product.productIcon),
      firstSeen: String(product.firstSeen ?? "").trim(),
      type: normalizedType,
      platformName: mapPlatformName(normalizedType),
      detailUrl: `https://adxray.dataeye.com/index/home#/Product/Detail/${productId}`,
      fetchedAt
    };

    deduped.set(`${row.statDate}:${row.productId}`, row);
  }

  return [...deduped.values()];
}

export function applyProductCompanyNames(
  games: NormalizedNewGame[],
  companyNamesByProductId: ReadonlyMap<string, string>
): NormalizedNewGame[] {
  return games.map((game) => ({
    ...game,
    companyName: companyNamesByProductId.get(game.productId)?.trim() || game.companyName || ""
  }));
}
