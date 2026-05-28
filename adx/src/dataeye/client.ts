import { access } from "node:fs/promises";
import { chromium } from "playwright";
import { DATAEYE_HOME_URL, STORAGE_STATE_PATH, getAppAuthSnapshot } from "./auth.js";
import { signDataEyeRequest } from "./sign.js";
import type { DataEyeNewProductDay, DataEyeResponseEnvelope, FetchDailyNewGamesResult } from "./types.js";

const API_URL = "https://adxray.dataeye.com/product/listTopNewProductDay";
const LOGIN_REQUIRED_STATUS = new Set([401, 403, 412, 509, 510]);

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

function hasLoginExpiredHint(payload: unknown): boolean {
  const text = JSON.stringify(payload ?? "").toLowerCase();
  return ["未登录", "login", "userkey", "token", "请登录"].some((token) => text.includes(token.toLowerCase()));
}

export async function fetchDailyNewGames(): Promise<FetchDailyNewGamesResult> {
  try {
    await access(STORAGE_STATE_PATH);
  } catch {
    throw new LoginRequiredError("未找到 .auth/dataeye-state.json，请先执行 `npm run login`。");
  }

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ storageState: STORAGE_STATE_PATH });
  const page = await context.newPage();

  try {
    await page.goto(DATAEYE_HOME_URL, { waitUntil: "domcontentloaded" });
    const appAuth = await getAppAuthSnapshot(page);
    const token = appAuth.userKey?.trim();
    const deHeaderS = appAuth.deHeaderS?.trim();

    if (appAuth.isLogin !== "1" || !token) {
      throw new LoginRequiredError();
    }

    const thisTimes = Math.floor(Date.now() / 100).toString();
    const signedParams = { thisTimes };
    const sign = signDataEyeRequest(signedParams);

    const response = await context.request.post(API_URL, {
      form: {
        ...signedParams,
        token,
        sign
      },
      headers: {
        "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
        ...(deHeaderS ? { s: deHeaderS } : {})
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

    const days = unwrapDays(payload);
    if (!Array.isArray(days) || days.length === 0) {
      throw new Error("接口返回成功，但未解析到最近 14 天新品数据。");
    }

    return {
      loginValid: true,
      days
    };
  } finally {
    await context.close();
    await browser.close();
  }
}
