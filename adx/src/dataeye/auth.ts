import { access, mkdir } from "node:fs/promises";
import { dirname, isAbsolute, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium, type BrowserContext, type Page } from "playwright";
import dotenv from "dotenv";
import type { AppAuthSnapshot } from "./types.js";

dotenv.config({ quiet: true });

export const DATAEYE_HOME_URL = "https://adxray.dataeye.com/index/home";
export const DATAEYE_OVERSEAS_HOME_URL = "https://oversea-v2.dataeye.com/dashboard/home";

export const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
export const ADX_PROJECT_ROOT = resolve(REPO_ROOT, "adx");
export const AUTH_DIR = resolve(REPO_ROOT, ".auth");
export const LEGACY_STORAGE_STATE_PATH = resolve(ADX_PROJECT_ROOT, ".auth/dataeye-state.json");

function isLegacyDefaultStorageStatePath(value: string): boolean {
  const normalized = value.replace(/\\/g, "/").replace(/^\.\//, "");
  return normalized === ".auth/dataeye-state.json";
}

export function resolveDataEyeStorageStatePath(value = process.env.DATAEYE_STORAGE_STATE): string {
  const configuredPath = value?.trim();
  if (!configuredPath || isLegacyDefaultStorageStatePath(configuredPath)) {
    return resolve(AUTH_DIR, "dataeye-state.json");
  }

  return isAbsolute(configuredPath) ? configuredPath : resolve(ADX_PROJECT_ROOT, configuredPath);
}

export const STORAGE_STATE_PATH = resolveDataEyeStorageStatePath();

const LOGIN_TIMEOUT_MS = 5 * 60 * 1000;
const APP_SNAPSHOT_RETRY_COUNT = 3;

function isExecutionContextDestroyed(error: unknown): boolean {
  return error instanceof Error && error.message.includes("Execution context was destroyed");
}

async function clickLoginEntryIfPresent(page: Page): Promise<void> {
  const candidates = [
    page.getByRole("link", { name: /登录/i }),
    page.getByRole("button", { name: /登录/i }),
    page.locator("text=登录").first()
  ];

  for (const locator of candidates) {
    if ((await locator.count()) > 0 && (await locator.first().isVisible().catch(() => false))) {
      await locator.first().click({ timeout: 2_000 }).catch(() => undefined);
      return;
    }
  }
}

async function fillFirstVisible(page: Page, selectors: string[], value: string): Promise<boolean> {
  for (const selector of selectors) {
    const locator = page.locator(selector).first();
    if ((await locator.count()) === 0) {
      continue;
    }

    if (!(await locator.isVisible().catch(() => false))) {
      continue;
    }

    await locator.fill(value);
    return true;
  }

  return false;
}

export async function getAppAuthSnapshot(page: Page): Promise<AppAuthSnapshot> {
  for (let attempt = 0; attempt < APP_SNAPSHOT_RETRY_COUNT; attempt += 1) {
    try {
      await page.waitForLoadState("domcontentloaded");
      return await page.evaluate(() => ({
        isLogin: typeof window.App?.isLogin === "undefined" ? null : String(window.App?.isLogin ?? ""),
        userKey: typeof window.App?.userKey === "undefined" ? null : String(window.App?.userKey ?? ""),
        deHeaderS: typeof window.deHeaderS === "undefined" ? null : String(window.deHeaderS ?? "")
      }));
    } catch (error) {
      if (!isExecutionContextDestroyed(error) || attempt === APP_SNAPSHOT_RETRY_COUNT - 1) {
        throw error;
      }

      await page.waitForTimeout(500);
    }
  }

  throw new Error("读取 DataEye 页面登录态失败。");
}

export async function isDataEyeLoggedIn(page: Page): Promise<boolean> {
  const snapshot = await getAppAuthSnapshot(page);
  return snapshot.isLogin === "1" && Boolean(snapshot.userKey);
}

export async function saveStorageState(context: BrowserContext): Promise<void> {
  await mkdir(dirname(STORAGE_STATE_PATH), { recursive: true });
  await context.storageState({ path: STORAGE_STATE_PATH });
}

export async function resolveExistingStorageStatePath(): Promise<string | undefined> {
  const candidates = [STORAGE_STATE_PATH, LEGACY_STORAGE_STATE_PATH];
  for (const candidate of candidates) {
    try {
      await access(candidate);
      return candidate;
    } catch {
      // Try the next migration candidate.
    }
  }

  return undefined;
}

async function createLoginContext(browser: Awaited<ReturnType<typeof chromium.launch>>): Promise<BrowserContext> {
  const existingState = await resolveExistingStorageStatePath();
  if (!existingState) {
    return browser.newContext();
  }

  try {
    return await browser.newContext({ storageState: existingState });
  } catch {
    return browser.newContext();
  }
}

export async function warmRelatedDataEyeSites(context: BrowserContext): Promise<void> {
  const page = await context.newPage();
  try {
    await page.goto(DATAEYE_OVERSEAS_HOME_URL, { waitUntil: "domcontentloaded", timeout: 30_000 }).catch(() => undefined);
    await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => undefined);
  } finally {
    await page.close();
  }
}

export async function runInteractiveLogin(): Promise<void> {
  const browser = await chromium.launch({ headless: false });
  const context = await createLoginContext(browser);
  const page = await context.newPage();

  try {
    await page.goto(DATAEYE_HOME_URL, { waitUntil: "domcontentloaded" });
    await clickLoginEntryIfPresent(page);

    const account = process.env.DATAEYE_ACCOUNT?.trim();
    const password = process.env.DATAEYE_PASSWORD?.trim();

    if (account) {
      await fillFirstVisible(
        page,
        [
          'input[name="email"]',
          'input[name="account"]',
          'input[name="username"]',
          'input[type="email"]',
          'input[placeholder*="邮箱"]',
          'input[placeholder*="账号"]',
          'input[placeholder*="手机号"]'
        ],
        account
      );
    }

    if (password) {
      await fillFirstVisible(
        page,
        [
          'input[name="password"]',
          'input[type="password"]',
          'input[placeholder*="密码"]'
        ],
        password
      );
    }

    console.log("请在打开的浏览器中完成验证码并登录。");
    console.log("登录成功后，程序会自动校验登录态并保存到 .auth/dataeye-state.json。");

    await page.waitForFunction(
      () => window.App?.isLogin === "1" && Boolean(window.App?.userKey),
      undefined,
      { timeout: LOGIN_TIMEOUT_MS }
    );

    if (!(await isDataEyeLoggedIn(page))) {
      throw new Error("检测到页面流程结束，但登录态校验未通过。");
    }

    await warmRelatedDataEyeSites(context);
    await saveStorageState(context);
    console.log("登录成功，已保存登录态。");
  } catch (error) {
    throw new Error(
      `登录失败：${
        error instanceof Error
          ? error.message
          : "请确认你已在 5 分钟内完成验证码和登录，并且页面存在 window.App.isLogin / userKey。"
      }`
    );
  } finally {
    await browser.close();
  }
}
