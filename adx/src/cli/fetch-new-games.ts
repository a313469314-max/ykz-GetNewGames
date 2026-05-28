import { mkdir, writeFile } from "node:fs/promises";
import { parseArgs } from "node:util";
import dotenv from "dotenv";
import { runInteractiveLogin } from "../dataeye/auth.js";
import { fetchDailyNewGames, LoginRequiredError } from "../dataeye/client.js";
import { normalizeNewGames } from "../dataeye/normalize.js";
import { buildDailyReportText, writeDailyReport } from "../reporting/daily-report.js";
import { pickTargetDay } from "../utils/date.js";
import { UTF8_BOM, toCsv } from "../utils/csv.js";

dotenv.config({ quiet: true });

const OUTPUT_DIR = "data/daily-new-games";

async function fetchWithInteractiveRecovery(): ReturnType<typeof fetchDailyNewGames> {
  try {
    return await fetchDailyNewGames();
  } catch (error) {
    if (!(error instanceof LoginRequiredError)) {
      throw error;
    }

    console.log("检测到 DataEye 登录态异常，正在打开浏览器登录页。");
    console.log("请完成验证码和登录，登录成功后程序会自动继续抓取。");

    await runInteractiveLogin();
    return fetchDailyNewGames();
  }
}

async function main(): Promise<void> {
  const { values } = parseArgs({
    options: {
      date: {
        type: "string"
      }
    },
    allowPositionals: false
  });

  try {
    const fetchResult = await fetchWithInteractiveRecovery();
    const targetDay = pickTargetDay(fetchResult.days, values.date);
    const fetchedAt = new Date().toISOString();
    const normalizedRows = normalizeNewGames(targetDay, fetchedAt);

    await mkdir(OUTPUT_DIR, { recursive: true });

    const jsonPath = `${OUTPUT_DIR}/${targetDay.statDate}.json`;
    const csvPath = `${OUTPUT_DIR}/${targetDay.statDate}.csv`;
    const reportText = buildDailyReportText(targetDay.statDate, normalizedRows);

    await writeFile(jsonPath, `${JSON.stringify(normalizedRows, null, 2)}\n`, "utf8");
    await writeFile(csvPath, `${UTF8_BOM}${toCsv(normalizedRows)}`, "utf8");
    const reportPath = await writeDailyReport(targetDay.statDate, reportText);

    console.log(`目标日期：${targetDay.statDate}`);
    console.log(`新游数量：${normalizedRows.length}`);
    console.log(`登录态有效：${fetchResult.loginValid ? "是" : "否"}`);
    console.log(`输出文件：${jsonPath}`);
    console.log(`输出文件：${csvPath}`);
    console.log(`日报文件：${reportPath}`);
  } catch (error) {
    console.error(error instanceof Error ? error.message : "采集失败。");
    process.exitCode = 1;
  }
}

void main();
