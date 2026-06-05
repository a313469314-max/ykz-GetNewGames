import { readdir, readFile, stat } from "node:fs/promises";
import { join } from "node:path";

const REPORT_FILE_REGEX = /^dataeye_new_games_company_(\d{4}-\d{2}-\d{2})\.txt$/;
const NORMAL_WEBHOOK_ENVS = ["ADX_FEISHU_WEBHOOK", "FEISHU_WEBHOOK"] as const;
const TEST_WEBHOOK_ENVS = ["ADX_FEISHU_TEST_WEBHOOK", "FEISHU_TEST_WEBHOOK"] as const;

interface FeishuWebhookResolution {
  envName: string;
  targetName: string;
  webhook: string;
}

function resolveFirstEnvValue(
  env: Record<string, string | undefined>,
  envNames: readonly string[]
): { envName: string; value: string } {
  for (const envName of envNames) {
    const value = env[envName]?.trim();
    if (value) {
      return { envName, value };
    }
  }

  return { envName: envNames[0], value: "" };
}

export function resolveFeishuWebhook(
  env: Record<string, string | undefined>,
  useTest = false
): FeishuWebhookResolution {
  const envNames = useTest ? TEST_WEBHOOK_ENVS : NORMAL_WEBHOOK_ENVS;
  const resolved = resolveFirstEnvValue(env, envNames);
  return {
    envName: resolved.envName,
    targetName: useTest ? "test webhook" : "normal webhook",
    webhook: resolved.value
  };
}

export async function sendFeishuTextReport(webhook: string, text: string): Promise<void> {
  const response = await fetch(webhook, {
    method: "POST",
    headers: {
      "content-type": "application/json"
    },
    body: JSON.stringify({
      msg_type: "text",
      content: {
        text
      }
    })
  });

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`飞书发送失败，HTTP ${response.status}${body ? `: ${body}` : ""}`);
  }
}

export async function resolveReportPath(outputDir: string, explicitDate?: string): Promise<string | null> {
  if (explicitDate) {
    return join(outputDir, `dataeye_new_games_company_${explicitDate}.txt`);
  }

  const fileNames = await readdir(outputDir).catch(() => []);
  const candidates = fileNames
    .filter((fileName) => REPORT_FILE_REGEX.test(fileName))
    .map((fileName) => join(outputDir, fileName));

  const cutoff = Date.now() - 6 * 60 * 60 * 1000;
  const withStats = await Promise.all(
    candidates.map(async (filePath) => ({
      filePath,
      stats: await stat(filePath)
    }))
  );

  const recent = withStats
    .filter((item) => item.stats.mtimeMs >= cutoff)
    .sort((left, right) => right.stats.mtimeMs - left.stats.mtimeMs);

  return recent[0]?.filePath ?? null;
}

export async function readReportText(reportPath: string): Promise<string> {
  return readFile(reportPath, "utf8");
}
