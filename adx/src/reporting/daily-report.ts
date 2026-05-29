import { mkdir, writeFile } from "node:fs/promises";
import type { NormalizedNewGame } from "../dataeye/types.js";

export const REPORT_OUTPUT_DIR = "output";

interface BuildDailyReportTextOptions {
  includeCompanyName?: boolean;
  title?: string;
}

interface WriteDailyReportOptions {
  filenamePrefix?: string;
}

function formatReportItem(item: NormalizedNewGame, includeCompanyName: boolean): string {
  const companyName = item.companyName?.trim();
  const companyLabel = includeCompanyName && companyName ? `（${companyName}）` : "";
  return `- ${item.productName}${companyLabel}: ${item.detailUrl}`;
}

export function buildDailyReportText(
  targetDate: string,
  games: NormalizedNewGame[],
  options: BuildDailyReportTextOptions = {}
): string {
  const grouped = new Map<string, NormalizedNewGame[]>();

  const sortedGames = [...games].sort((left, right) => {
    if (left.platformName !== right.platformName) {
      return left.platformName.localeCompare(right.platformName, "zh-CN");
    }

    return left.productName.localeCompare(right.productName, "zh-CN");
  });

  for (const game of sortedGames) {
    const items = grouped.get(game.platformName) ?? [];
    items.push(game);
    grouped.set(game.platformName, items);
  }

  const lines = [options.title ?? `DataEye 新品日报 (${targetDate})`];

  if (games.length === 0) {
    lines.push("本次未发现新品条目。");
    return lines.join("\n");
  }

  lines.push(`本次共发现 ${games.length} 个新品，按平台整理如下：`);
  lines.push("");

  const platformNames = [...grouped.keys()];
  for (const [index, platformName] of platformNames.entries()) {
    const items = grouped.get(platformName) ?? [];
    lines.push(`${platformName} (新增 ${items.length} 个)`);
    for (const item of items) {
      lines.push(formatReportItem(item, options.includeCompanyName ?? false));
    }

    if (index !== platformNames.length - 1) {
      lines.push("");
    }
  }

  return lines.join("\n");
}

export async function writeDailyReport(
  targetDate: string,
  reportText: string,
  options: WriteDailyReportOptions = {}
): Promise<string> {
  await mkdir(REPORT_OUTPUT_DIR, { recursive: true });
  const filenamePrefix = options.filenamePrefix ?? "dataeye_new_games";
  const reportPath = `${REPORT_OUTPUT_DIR}/${filenamePrefix}_${targetDate}.txt`;
  await writeFile(reportPath, reportText, "utf8");
  return reportPath;
}
