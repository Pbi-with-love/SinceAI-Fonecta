import { describe, it, expect } from "vitest";
import { parseHours } from "./parse-hours";

describe("parseHours", () => {
  it("parses 'mở 10 tới 2 thôi' as 10:00–14:00", () => {
    expect(parseHours("mở 10 tới 2 thôi")).toEqual({ closed: false, open: "10:00", close: "14:00" });
  });
  it("parses '10:00 - 14:00'", () => {
    expect(parseHours("10:00 - 14:00")).toEqual({ closed: false, open: "10:00", close: "14:00" });
  });
  it("parses closed", () => {
    expect(parseHours("đóng cửa")).toEqual({ closed: true });
  });
  it("rejects garbage", () => {
    expect(parseHours("hello")).toBeNull();
  });
});
