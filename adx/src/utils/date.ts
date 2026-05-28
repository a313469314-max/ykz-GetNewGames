import type { DataEyeNewProductDay } from "../dataeye/types.js";

export const SHANGHAI_TIME_ZONE = "Asia/Shanghai";
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const ONE_DAY_MS = 24 * 60 * 60 * 1000;

export function assertDateInput(value: string): string {
  if (!DATE_RE.test(value)) {
    throw new Error("`--date` 必须是 YYYY-MM-DD 格式。");
  }

  const parsed = new Date(`${value}T00:00:00+08:00`);
  if (Number.isNaN(parsed.getTime())) {
    throw new Error("`--date` 不是有效日期。");
  }

  const [year, month, day] = value.split("-").map(Number);
  if (month < 1 || month > 12) {
    throw new Error("`--date` 不是有效日期。");
  }

  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate();
  if (day < 1 || day > daysInMonth) {
    throw new Error("`--date` 不是有效日期。");
  }

  return value;
}

export function getLatestStatDate(days: DataEyeNewProductDay[]): string {
  const statDates = days.map((day) => day.statDate).filter(Boolean);
  if (statDates.length === 0) {
    throw new Error("接口未返回可用的 statDate。");
  }

  return [...statDates].sort((left, right) => right.localeCompare(left))[0];
}

function pad2(value: number): string {
  return String(value).padStart(2, "0");
}

function formatUtcDate(date: Date): string {
  return `${date.getUTCFullYear()}-${pad2(date.getUTCMonth() + 1)}-${pad2(date.getUTCDate())}`;
}

export function getShanghaiDate(value = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: SHANGHAI_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit"
  }).formatToParts(value);

  const partMap = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${partMap.year}-${partMap.month}-${partMap.day}`;
}

export function getPreviousShanghaiDate(value = new Date()): string {
  const [year, month, day] = getShanghaiDate(value).split("-").map(Number);
  const shanghaiDateAsUtcMidnight = Date.UTC(year, month - 1, day);
  return formatUtcDate(new Date(shanghaiDateAsUtcMidnight - ONE_DAY_MS));
}

export function pickTargetDay(
  days: DataEyeNewProductDay[],
  requestedDate?: string,
  now = new Date()
): DataEyeNewProductDay {
  if (days.length === 0) {
    throw new Error("DataEye 接口未返回任何新品数据。");
  }

  const targetDate = requestedDate ? assertDateInput(requestedDate) : getPreviousShanghaiDate(now);
  const target = days.find((day) => day.statDate === targetDate);

  if (!target) {
    throw new Error("DataEye 当前入口仅返回最近 14 天每日新品，请选择最近 14 天内的日期。");
  }

  return target;
}
