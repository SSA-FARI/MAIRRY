import { parseCalendarDate, type CalendarDate } from "./date";

export interface CalendarCell {
  isoDate: string;
  day: number;
  inCurrentMonth: boolean;
}

export function formatIsoDate(date: CalendarDate): string {
  return `${date.year}-${String(date.month).padStart(2, "0")}-${String(date.day).padStart(2, "0")}`;
}

export function calendarMonthFrom(value: string): CalendarDate | null {
  const date = parseCalendarDate(value);
  return date ? { ...date, day: 1 } : null;
}

export function currentCalendarMonth(now = new Date()): CalendarDate {
  return { year: now.getFullYear(), month: now.getMonth() + 1, day: 1 };
}

export function shiftCalendarMonth(month: CalendarDate, offset: number): CalendarDate {
  const shifted = new Date(month.year, month.month - 1 + offset, 1);
  return { year: shifted.getFullYear(), month: shifted.getMonth() + 1, day: 1 };
}

export function buildCalendarCells(month: CalendarDate): CalendarCell[] {
  const firstWeekday = new Date(month.year, month.month - 1, 1).getDay();
  const gridStart = new Date(month.year, month.month - 1, 1 - firstWeekday);
  return Array.from({ length: 42 }, (_, index) => {
    const value = new Date(
      gridStart.getFullYear(),
      gridStart.getMonth(),
      gridStart.getDate() + index,
    );
    const calendarDate = {
      year: value.getFullYear(),
      month: value.getMonth() + 1,
      day: value.getDate(),
    };
    return {
      isoDate: formatIsoDate(calendarDate),
      day: calendarDate.day,
      inCurrentMonth: calendarDate.year === month.year && calendarDate.month === month.month,
    };
  });
}
