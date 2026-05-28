import { createHash } from "node:crypto";

const SIGN_SECRET = "g:%w0k7&q1v9^tRnLz!M";

type SignValue = string | number | boolean | Array<string | number | boolean> | undefined | null;

export type SignParams = Record<string, SignValue>;

function normalizeValue(value: Exclude<SignValue, undefined>): string {
  if (Array.isArray(value)) {
    return value.map((item) => String(item).trim()).join(",");
  }

  if (value === null) {
    return "";
  }

  return String(value).trim();
}

export function toSignPayload(params: SignParams): string {
  return Object.entries(params)
    .filter((entry): entry is [string, Exclude<SignValue, undefined>] => entry[1] !== undefined)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, value]) => `${key}=${normalizeValue(value)}`)
    .join("&");
}

export function signDataEyeRequest(params: SignParams): string {
  const payload = `${toSignPayload(params)}&key=${SIGN_SECRET}`;
  return createHash("md5").update(payload).digest("hex").toUpperCase();
}
