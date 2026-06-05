import { mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { resolveReportPath } from "../src/feishu/client.js";

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
});
