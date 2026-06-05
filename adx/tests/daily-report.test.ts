import { describe, expect, it } from "vitest";
import { buildDailyReportText } from "../src/reporting/daily-report.js";

describe("daily report", () => {
  it("shows company names by default", () => {
    const report = buildDailyReportText("2026-05-18", [
      {
        statDate: "2026-05-18",
        productId: "1",
        productName: "战术小队",
        companyName: "战术公司",
        productIcon: "",
        stableProductIcon: "",
        firstSeen: "",
        type: 7,
        platformName: "抖音小游戏",
        detailUrl: "https://example.com/1",
        fetchedAt: "2026-05-18T02:24:20.195Z"
      }
    ]);

    expect(report).toContain("DataEye 新品日报 (2026-05-18)");
    expect(report).toContain("- 战术小队（战术公司）: https://example.com/1");
  });

  it("does not render empty parentheses when companyName is missing", () => {
    const report = buildDailyReportText("2026-05-18", [
      {
        statDate: "2026-05-18",
        productId: "2",
        productName: "末日救世主",
        companyName: "   ",
        productIcon: "",
        stableProductIcon: "",
        firstSeen: "",
        type: 2,
        platformName: "微信小游戏",
        detailUrl: "https://example.com/2",
        fetchedAt: "2026-05-18T02:24:20.195Z"
      }
    ]);

    expect(report).toContain("- 末日救世主: https://example.com/2");
    expect(report).not.toContain("末日救世主（）");
  });
});
