import { mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { resolveFeishuWebhook, resolveReportPath } from "../src/feishu/client.js";

describe("resolveReportPath", () => {
  it("does not match historical base report files", async () => {
    const dir = join(tmpdir(), `adx-feishu-${Date.now()}-base-only`);
    await mkdir(dir, { recursive: true });
    await writeFile(join(dir, "dataeye_new_games_2026-05-28.txt"), "base", "utf8");

    await expect(resolveReportPath(dir)).resolves.toBeNull();
  });

  it("matches the company report file name", async () => {
    const dir = join(tmpdir(), `adx-feishu-${Date.now()}-company`);
    await mkdir(dir, { recursive: true });
    const mainPath = join(dir, "dataeye_new_games_company_2026-05-28.txt");
    await writeFile(mainPath, "main", "utf8");

    await expect(resolveReportPath(dir, "2026-05-28")).resolves.toBe(mainPath);
  });

  it("uses the normal AdX webhook by default", () => {
    const resolved = resolveFeishuWebhook(
      {
        ADX_FEISHU_WEBHOOK: "https://example.com/normal",
        ADX_FEISHU_TEST_WEBHOOK: "https://example.com/test"
      },
      false
    );

    expect(resolved).toEqual({
      envName: "ADX_FEISHU_WEBHOOK",
      targetName: "normal webhook",
      webhook: "https://example.com/normal"
    });
  });

  it("uses the AdX test webhook in test mode", () => {
    const resolved = resolveFeishuWebhook(
      {
        ADX_FEISHU_WEBHOOK: "https://example.com/normal",
        ADX_FEISHU_TEST_WEBHOOK: "https://example.com/test"
      },
      true
    );

    expect(resolved).toEqual({
      envName: "ADX_FEISHU_TEST_WEBHOOK",
      targetName: "test webhook",
      webhook: "https://example.com/test"
    });
  });

  it("does not fall back to the normal webhook in test mode", () => {
    const resolved = resolveFeishuWebhook({ ADX_FEISHU_WEBHOOK: "https://example.com/normal" }, true);

    expect(resolved).toEqual({
      envName: "ADX_FEISHU_TEST_WEBHOOK",
      targetName: "test webhook",
      webhook: ""
    });
  });
});
