import { describe, expect, it } from "vitest";
import { mapPlatformName, normalizeNewGames, toStableProductIcon } from "../src/dataeye/normalize.js";

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
      stableProductIcon: "https://cdn.example.com/icon.png",
      platformName: "抖音小游戏",
      detailUrl: "https://adxray.dataeye.com/index/home#/Product/Detail/123"
    });
  });
});

