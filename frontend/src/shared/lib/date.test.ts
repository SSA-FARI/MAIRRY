import { describe, expect, it } from "vitest";
import { formatDate } from "./date";

describe("formatDate", () => {
  it("formats an ISO date", () => {
    expect(formatDate("2027-04-30")).toBe("2027.04.30");
  });

  it("returns the original value when the format is not ISO date", () => {
    expect(formatDate("2027년 4월 30일")).toBe("2027년 4월 30일");
    expect(formatDate("즉시")).toBe("즉시");
  });

  it("shows an unset label for null", () => {
    expect(formatDate(null)).toBe("날짜 미정");
  });
});
