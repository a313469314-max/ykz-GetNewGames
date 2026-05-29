import { describe, expect, it } from "vitest";
import { toCsv } from "../src/utils/csv.js";

describe("csv", () => {
  const rows = [
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
  ];

  it("keeps the default csv schema unchanged", () => {
    expect(toCsv(rows).split("\r\n")[0]).toBe(
      "statDate,productId,productName,productIcon,stableProductIcon,firstSeen,type,platformName,detailUrl,fetchedAt"
    );
  });

  it("can include company names for the company export", () => {
    expect(toCsv(rows, { includeCompanyName: true }).split("\r\n")[0]).toBe(
      "statDate,productId,productName,companyName,productIcon,stableProductIcon,firstSeen,type,platformName,detailUrl,fetchedAt"
    );
  });
});
