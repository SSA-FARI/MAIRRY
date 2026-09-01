import { describe, expect, it } from "vitest";
import {
  calendarDayDifference,
  formatDayStatus,
  formatShortDate,
  isInCurrentMonth,
  parseCalendarDate,
} from "./date";

describe("calendar date utilities", () => {
  const now = new Date(2026, 11, 31, 23, 59);

  it("calculates today, future, past and year boundaries without parsing UTC timestamps", () => {
    expect(calendarDayDifference("2026-12-31", now)).toBe(0);
    expect(formatDayStatus("2027-01-01", now)).toEqual({ label: "D-1", overdue: false });
    expect(formatDayStatus("2026-12-30", now)).toEqual({ label: "D+1", overdue: true });
  });

  it("validates calendar dates and formats month and day", () => {
    expect(parseCalendarDate("2026-02-29")).toBeNull();
    expect(parseCalendarDate("2028-02-29")).toEqual({ year: 2028, month: 2, day: 29 });
    expect(formatShortDate("2028-02-09")).toBe("02.09");
  });

  it("uses the browser calendar month", () => {
    expect(isInCurrentMonth("2026-12-01", now)).toBe(true);
    expect(isInCurrentMonth("2027-01-01", now)).toBe(false);
  });
});
