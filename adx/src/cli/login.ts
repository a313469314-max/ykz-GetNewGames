import { runInteractiveLogin, STORAGE_STATE_PATH } from "../dataeye/auth.js";

async function main(): Promise<void> {
  try {
    await runInteractiveLogin();
    console.log(`登录态文件：${STORAGE_STATE_PATH}`);
  } catch (error) {
    console.error(error instanceof Error ? error.message : "登录失败。");
    process.exitCode = 1;
  }
}

void main();

