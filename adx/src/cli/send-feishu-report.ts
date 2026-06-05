import { parseArgs } from "node:util";
import dotenv from "dotenv";
import { readReportText, resolveFeishuWebhook, resolveReportPath, sendFeishuTextReport } from "../feishu/client.js";
import { REPORT_OUTPUT_DIR } from "../reporting/daily-report.js";
import { assertDateInput } from "../utils/date.js";

dotenv.config({ quiet: true });

async function main(): Promise<void> {
  const { values } = parseArgs({
    options: {
      path: {
        type: "string"
      },
      date: {
        type: "string"
      },
      test: {
        type: "boolean",
        default: false
      }
    },
    allowPositionals: false
  });

  const { envName, targetName, webhook } = resolveFeishuWebhook(process.env, Boolean(values.test));
  if (!webhook) {
    console.error(`Missing ${envName}. Set it in .env or environment variables before sending.`);
    process.exitCode = 1;
    return;
  }

  const reportPath =
    values.path ??
    (await resolveReportPath(REPORT_OUTPUT_DIR, values.date ? assertDateInput(values.date) : undefined));

  if (!reportPath) {
    console.error("未找到可发送的日报文件。");
    process.exitCode = 1;
    return;
  }

  const text = await readReportText(reportPath);
  await sendFeishuTextReport(webhook, text);
  console.log(`Feishu report sent to ${targetName}: ${reportPath}`);
}

void main().catch((error) => {
  console.error(error instanceof Error ? error.message : "飞书发送失败。");
  process.exitCode = 1;
});
