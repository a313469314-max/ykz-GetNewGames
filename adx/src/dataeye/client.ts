import { chromium, type BrowserContext } from "playwright";
import {
  DATAEYE_HOME_URL,
  STORAGE_STATE_PATH,
  getAppAuthSnapshot,
  resolveExistingStorageStatePath,
  saveStorageState,
  warmRelatedDataEyeSites
} from "./auth.js";
import { signDataEyeRequest, type SignParams } from "./sign.js";
import type { DataEyeNewProductDay, DataEyeResponseEnvelope, FetchDailyNewGamesResult } from "./types.js";

const DATAEYE_API_ORIGIN = "https://adxray.dataeye.com";
const DAILY_NEW_GAMES_API_PATH = "/product/listTopNewProductDay";
const PRODUCT_INFO_API_PATH = "/product/getProductInfo";
const LOGIN_REQUIRED_STATUS = new Set([401, 403, 412, 509, 510]);

interface DataEyeRequestSession {
  context: BrowserContext;
  token: string;
  deHeaderS?: string;
}

interface FetchProductCompanyNamesOptions {
  concurrency?: number;
}

export class LoginRequiredError extends Error {
  constructor(message = "登录态已失效，请重新执行 `npm run login`。") {
    super(message);
    this.name = "LoginRequiredError";
  }
}

function unwrapDays(payload: unknown): DataEyeNewProductDay[] {
  if (Array.isArray(payload)) {
    return payload as DataEyeNewProductDay[];
  }

  if (!payload || typeof payload !== "object") {
    return [];
  }

  const envelope = payload as DataEyeResponseEnvelope<DataEyeNewProductDay[]>;
  const nested = envelope.content ?? envelope.data ?? envelope.result ?? envelope.rows ?? envelope.list;
  return Array.isArray(nested) ? nested : [];
}

function unwrapContent(payload: unknown): unknown {
  if (!payload || typeof payload !== "object") {
    return payload;
  }

  const envelope = payload as DataEyeResponseEnvelope<unknown>;
  return envelope.content ?? envelope.data ?? envelope.result ?? envelope.rows ?? envelope.list ?? payload;
}

function hasLoginExpiredHint(payload: unknown): boolean {
  const text = JSON.stringify(payload ?? "").toLowerCase();
  return ["未登录", "login", "userkey", "token", "请登录"].some((token) => text.includes(token.toLowerCase()));
}

function getStringValue(value: unknown): string {
  return typeof value === "string" || typeof value === "number" ? String(value).trim() : "";
}

function getCompanyNameFromProductInfo(payload: unknown): string {
  if (!payload || typeof payload !== "object") {
    return "";
  }

  const productInfo = payload as Record<string, unknown>;
  return (
    getStringValue(productInfo.companyName) ||
    getStringValue(productInfo.mainCompany) ||
    getStringValue(productInfo.company) ||
    getStringValue(productInfo.publisherName) ||
    getStringValue(productInfo.developerName)
  );
}

async function withDataEyeRequestSession<T>(callback: (session: DataEyeRequestSession) => Promise<T>): Promise<T> {
  const storageStatePath = await resolveExistingStorageStatePath();
  if (!storageStatePath) {
    throw new LoginRequiredError("未找到 .auth/dataeye-state.json，请先执行 `npm run login`。");
  }

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ storageState: storageStatePath });
  const page = await context.newPage();

  try {
    await page.goto(DATAEYE_HOME_URL, { waitUntil: "domcontentloaded" });
    const appAuth = await getAppAuthSnapshot(page);
    const token = appAuth.userKey?.trim();
    const deHeaderS = appAuth.deHeaderS?.trim();

    if (appAuth.isLogin !== "1" || !token) {
      throw new LoginRequiredError();
    }

    if (storageStatePath !== STORAGE_STATE_PATH) {
      await warmRelatedDataEyeSites(context);
      await saveStorageState(context);
    }

    return await callback({ context, token, deHeaderS });
  } finally {
    await context.close();
    await browser.close();
  }
}

async function postDataEyeApi(
  session: DataEyeRequestSession,
  path: string,
  params: SignParams = {}
): Promise<unknown> {
  const thisTimes = Math.floor(Date.now() / 100).toString();
  const signedParams = { ...params, thisTimes };
  const sign = signDataEyeRequest(signedParams);

  const response = await session.context.request.post(`${DATAEYE_API_ORIGIN}${path}`, {
    form: {
      ...signedParams,
      token: session.token,
      sign
    },
    headers: {
      "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
      ...(session.deHeaderS ? { s: session.deHeaderS } : {})
    }
  });

  if (LOGIN_REQUIRED_STATUS.has(response.status())) {
    throw new LoginRequiredError();
  }

  const responseText = await response.text();
  let payload: unknown = responseText;
  try {
    payload = JSON.parse(responseText);
  } catch {
    payload = responseText;
  }

  if (hasLoginExpiredHint(payload)) {
    throw new LoginRequiredError();
  }

  return payload;
}

async function mapWithConcurrency<T>(
  items: T[],
  concurrency: number,
  iteratee: (item: T) => Promise<void>
): Promise<void> {
  let nextIndex = 0;
  const workerCount = Math.max(1, Math.min(concurrency, items.length));

  await Promise.all(
    Array.from({ length: workerCount }, async () => {
      while (nextIndex < items.length) {
        const item = items[nextIndex];
        nextIndex += 1;
        await iteratee(item);
      }
    })
  );
}

export async function fetchDailyNewGames(): Promise<FetchDailyNewGamesResult> {
  return withDataEyeRequestSession(async (session) => {
    const payload = await postDataEyeApi(session, DAILY_NEW_GAMES_API_PATH);

    const days = unwrapDays(payload);
    if (!Array.isArray(days) || days.length === 0) {
      throw new Error("接口返回成功，但未解析到最近 14 天新品数据。");
    }

    return {
      loginValid: true,
      days
    };
  });
}

export async function fetchProductCompanyNames(
  productIds: string[],
  options: FetchProductCompanyNamesOptions = {}
): Promise<Map<string, string>> {
  const uniqueProductIds = [...new Set(productIds.map((productId) => productId.trim()).filter(Boolean))];
  const companyNames = new Map<string, string>();

  if (uniqueProductIds.length === 0) {
    return companyNames;
  }

  await withDataEyeRequestSession(async (session) => {
    await mapWithConcurrency(uniqueProductIds, options.concurrency ?? 4, async (productId) => {
      const payload = await postDataEyeApi(session, PRODUCT_INFO_API_PATH, { productId });
      companyNames.set(productId, getCompanyNameFromProductInfo(unwrapContent(payload)));
    });
  });

  return companyNames;
}
