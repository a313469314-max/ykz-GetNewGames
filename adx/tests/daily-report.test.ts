import { describe, expect, it } from "vitest";
import { buildDailyReportText } from "../src/reporting/daily-report.js";

describe("daily report", () => {
  it("builds a grouped text report similar to the youtube project style", () => {
    const report = buildDailyReportText("2026-05-18", [
      {
        statDate: "2026-05-18",
        productId: "1",
        productName: "战术小队",
        productIcon: "",
        stableProductIcon: "",
        firstSeen: "",
        type: 7,
        platformName: "抖音小游戏",
        detailUrl: "https://example.com/1",
        fetchedAt: "2026-05-18T02:24:20.195Z"
      },
      {
        statDate: "2026-05-18",
        productId: "2",
        productName: "末日救世主",
        productIcon: "",
        stableProductIcon: "",
        firstSeen: "",
        type: 2,
        platformName: "微信小游戏",
        detailUrl: "https://example.com/2",
        fetchedAt: "2026-05-18T02:24:20.195Z"
      }
    ]);

    expect(report).toContain("DataEye 新品日报 (2026-05-18)");
    expect(report).toContain("本次共发现 2 个新品");
    expect(report).toContain("抖音小游戏 (新增 1 个)");
    expect(report).toContain("- 战术小队: https://example.com/1");
    expect(report).toContain("微信小游戏 (新增 1 个)");
  });
});
