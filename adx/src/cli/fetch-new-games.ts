import { mkdir, writeFile } from "node:fs/promises";
import { parseArgs } from "node:util";
import dotenv from "dotenv";
import { runInteractiveLogin } from "../dataeye/auth.js";
import { fetchDailyNewGames, fetchProductCompanyNames, LoginRequiredError } from "../dataeye/client.js";
import { applyProductCompanyNames, normalizeNewGames } from "../dataeye/normalize.js";
import { buildDailyReportText, writeDailyReport } from "../reporting/daily-report.js";
import { pickTargetDay } from "../utils/date.js";
import { UTF8_BOM, toCsv } from "../utils/csv.js";

dotenv.config({ quiet: true });

const OUTPUT_DIR = "data/daily-new-games-company";

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

async function fetchCompanyNamesWithInteractiveRecovery(
  productIds: string[]
): ReturnType<typeof fetchProductCompanyNames> {
  try {
    return await fetchProductCompanyNames(productIds);
  } catch (error) {
    if (!(error instanceof LoginRequiredError)) {
      throw error;
    }

    console.log("补充厂商名时检测到 DataEye 登录态异常，正在打开浏览器登录页。");
    console.log("请完成验证码和登录，登录成功后程序会自动继续补充厂商名。");

    await runInteractiveLogin();
    return fetchProductCompanyNames(productIds);
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
    const companyNamesByProductId = await fetchCompanyNamesWithInteractiveRecovery(
      normalizedRows.map((row) => row.productId)
    );
    const rowsWithCompany = applyProductCompanyNames(normalizedRows, companyNamesByProductId);

    await mkdir(OUTPUT_DIR, { recursive: true });

    const jsonPath = `${OUTPUT_DIR}/${targetDay.statDate}.json`;
    const csvPath = `${OUTPUT_DIR}/${targetDay.statDate}.csv`;
    const reportText = buildDailyReportText(targetDay.statDate, rowsWithCompany);

    await writeFile(jsonPath, `${JSON.stringify(rowsWithCompany, null, 2)}\n`, "utf8");
    await writeFile(csvPath, `${UTF8_BOM}${toCsv(rowsWithCompany)}`, "utf8");
    const reportPath = await writeDailyReport(targetDay.statDate, reportText);

    const companyNameCount = rowsWithCompany.filter((row) => row.companyName?.trim()).length;

    console.log(`目标日期：${targetDay.statDate}`);
    console.log(`新游数量：${rowsWithCompany.length}`);
    console.log(`已补齐厂商名：${companyNameCount}/${rowsWithCompany.length}`);
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
