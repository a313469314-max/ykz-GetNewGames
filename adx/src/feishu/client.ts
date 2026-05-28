import { readdir, readFile, stat } from "node:fs/promises";
import { join } from "node:path";

const REPORT_FILE_PREFIX = "dataeye_new_games_";
const REPORT_FILE_SUFFIX = ".txt";

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
    return join(outputDir, `${REPORT_FILE_PREFIX}${explicitDate}${REPORT_FILE_SUFFIX}`);
  }

  const fileNames = await readdir(outputDir).catch(() => []);
  const candidates = fileNames
    .filter((fileName) => fileName.startsWith(REPORT_FILE_PREFIX) && fileName.endsWith(REPORT_FILE_SUFFIX))
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
