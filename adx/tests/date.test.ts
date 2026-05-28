import { describe, expect, it } from "vitest";
import { getPreviousShanghaiDate, pickTargetDay } from "../src/utils/date.js";

const sampleDays = [
  { statDate: "2026-05-16", products: [] },
  { statDate: "2026-05-18", products: [] },
  { statDate: "2026-05-17", products: [] }
];

describe("date selection", () => {
  it("uses the previous Shanghai date when --date is omitted", () => {
    const now = new Date("2026-05-19T12:00:00.000Z");

    expect(getPreviousShanghaiDate(now)).toBe("2026-05-18");
    expect(pickTargetDay(sampleDays, undefined, now).statDate).toBe("2026-05-18");
  });

  it("uses the previous Shanghai date across UTC day boundaries", () => {
    const now = new Date("2026-05-18T16:30:00.000Z");

    expect(getPreviousShanghaiDate(now)).toBe("2026-05-18");
    expect(pickTargetDay(sampleDays, undefined, now).statDate).toBe("2026-05-18");
  });

  it("selects the requested date when it exists", () => {
    expect(pickTargetDay(sampleDays, "2026-05-17").statDate).toBe("2026-05-17");
  });

  it("throws a clear error when the requested date is out of range", () => {
    expect(() => pickTargetDay(sampleDays, "2026-05-01")).toThrow(
      "DataEye 当前入口仅返回最近 14 天每日新品，请选择最近 14 天内的日期。"
    );
  });
});
