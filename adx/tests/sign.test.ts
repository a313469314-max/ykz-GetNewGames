import { createHash } from "node:crypto";
import { describe, expect, it } from "vitest";
import { signDataEyeRequest, toSignPayload } from "../src/dataeye/sign.js";

describe("DataEye sign", () => {
  it("normalizes, sorts, and joins params before signing", () => {
    const payload = toSignPayload({
      token: " token-value ",
      thisTimes: "12345",
      tags: [" ios ", "wx"],
      ignored: undefined
    });

    expect(payload).toBe("tags=ios,wx&thisTimes=12345&token=token-value");
  });

  it("returns uppercase md5 signature", () => {
    const expected = createHash("md5")
      .update("thisTimes=12345&token=abc&key=g:%w0k7&q1v9^tRnLz!M")
      .digest("hex")
      .toUpperCase();

    expect(
      signDataEyeRequest({
        token: "abc",
        thisTimes: "12345"
      })
    ).toBe(expected);
  });
});

