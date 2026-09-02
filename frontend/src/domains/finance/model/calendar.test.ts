import { describe, expect, it } from "vitest";
import { buildCalendarCells, shiftCalendarMonth } from "./calendar";

describe("payment calendar utilities", () => {
  it("builds a six-week calendar including adjacent month dates", () => {
    const cells = buildCalendarCells({ year: 2026, month: 9, day: 1 });
    expect(cells).toHaveLength(42);
    expect(cells[0]).toEqual({ isoDate: "2026-08-30", day: 30, inCurrentMonth: false });
    expect(cells.at(-1)).toEqual({ isoDate: "2026-10-10", day: 10, inCurrentMonth: false });
  });

  it("handles leap years", () => {
    const cells = buildCalendarCells({ year: 2028, month: 2, day: 1 });
    expect(cells.some((cell) => cell.isoDate === "2028-02-29" && cell.inCurrentMonth)).toBe(true);
  });

  it("moves across year boundaries", () => {
    expect(shiftCalendarMonth({ year: 2026, month: 12, day: 1 }, 1)).toEqual({
      year: 2027,
      month: 1,
      day: 1,
    });
    expect(shiftCalendarMonth({ year: 2027, month: 1, day: 1 }, -1)).toEqual({
      year: 2026,
      month: 12,
      day: 1,
    });
  });
});
