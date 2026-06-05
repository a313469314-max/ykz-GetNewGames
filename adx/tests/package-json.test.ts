import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const currentDir = dirname(fileURLToPath(import.meta.url));
const packageJsonPath = resolve(currentDir, "../package.json");

describe("package.json scripts", () => {
  it("does not expose fetch:new-games:company", async () => {
    const packageJson = JSON.parse(await readFile(packageJsonPath, "utf8")) as {
      scripts?: Record<string, string>;
    };

    expect(packageJson.scripts).toBeDefined();
    expect(packageJson.scripts).not.toHaveProperty("fetch:new-games:company");
    expect(packageJson.scripts).toHaveProperty("fetch:new-games", "tsx src/cli/fetch-new-games.ts");
  });
});
