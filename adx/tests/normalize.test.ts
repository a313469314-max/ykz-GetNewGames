import { describe, expect, it } from "vitest";
import {
  applyProductCompanyNames,
  getProductCompanyName,
  mapPlatformName,
  normalizeNewGames,
  toStableProductIcon
} from "../src/dataeye/normalize.js";

describe("normalize", () => {
  it("maps known and unknown platform types", () => {
    expect(mapPlatformName(1)).toBe("iOS");
    expect(mapPlatformName(2)).toBe("微信小游戏");
    expect(mapPlatformName(22)).toBe("快手小游戏");
    expect(mapPlatformName(999)).toBe("unknown:999");
  });

  it("strips query params from product icon", () => {
    expect(toStableProductIcon("https://cdn.example.com/icon.png?auth_key=secret&x=1")).toBe(
      "https://cdn.example.com/icon.png"
    );
  });

  it("reads company names from known product fields", () => {
    expect(getProductCompanyName({ companyName: "广州万维在线科技有限公司" })).toBe("广州万维在线科技有限公司");
    expect(getProductCompanyName({ mainCompany: "测试主体" })).toBe("测试主体");
    expect(getProductCompanyName({ publisherName: "测试发行商" })).toBe("测试发行商");
  });

  it("normalizes rows and deduplicates by statDate + productId", () => {
    const rows = normalizeNewGames(
      {
        statDate: "2026-05-18",
        productNum: 2,
        products: [
          {
            productId: 123,
            productName: "测试游戏",
            productIcon: "https://cdn.example.com/icon.png?auth_key=secret",
            firstSeen: "2026-05-18 10:00:00",
            type: 7
          },
          {
            productId: 123,
            productName: "测试游戏重复",
            companyName: "测试公司",
            productIcon: "https://cdn.example.com/icon.png?auth_key=secret",
            firstSeen: "2026-05-18 10:05:00",
            type: 7
          }
        ]
      },
      "2026-05-18T02:30:00.000Z"
    );

    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      statDate: "2026-05-18",
      productId: "123",
      productName: "测试游戏重复",
      companyName: "测试公司",
      stableProductIcon: "https://cdn.example.com/icon.png",
      platformName: "抖音小游戏",
      detailUrl: "https://adxray.dataeye.com/index/home#/Product/Detail/123"
    });
  });

  it("applies company names fetched from product details", () => {
    const rows = applyProductCompanyNames(
      [
        {
          statDate: "2026-05-18",
          productId: "123",
          productName: "测试游戏",
          productIcon: "",
          stableProductIcon: "",
          firstSeen: "",
          type: 7,
          platformName: "抖音小游戏",
          detailUrl: "https://example.com/123",
          fetchedAt: "2026-05-18T02:30:00.000Z"
        }
      ],
      new Map([["123", "详情公司"]])
    );

    expect(rows[0].companyName).toBe("详情公司");
  });
});
