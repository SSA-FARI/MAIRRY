const CALENDAR_DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;

export interface CalendarDate {
  year: number;
  month: number;
  day: number;
}

export function parseCalendarDate(value: string): CalendarDate | null {
  const match = CALENDAR_DATE_PATTERN.exec(value);
  if (!match) return null;
  const date = { year: Number(match[1]), month: Number(match[2]), day: Number(match[3]) };
  const local = new Date(date.year, date.month - 1, date.day);
  return local.getFullYear() === date.year &&
    local.getMonth() === date.month - 1 &&
    local.getDate() === date.day
    ? date
    : null;
}

function dayNumber(date: CalendarDate): number {
  return Math.floor(Date.UTC(date.year, date.month - 1, date.day) / 86_400_000);
}

export function calendarDayDifference(value: string, now = new Date()): number | null {
  const target = parseCalendarDate(value);
  if (!target) return null;
  return (
    dayNumber(target) -
    dayNumber({ year: now.getFullYear(), month: now.getMonth() + 1, day: now.getDate() })
  );
}

export function formatDayStatus(
  value: string,
  now = new Date(),
): {
  label: string;
  overdue: boolean;
} {
  const difference = calendarDayDifference(value, now);
  if (difference === null) return { label: "날짜 확인 필요", overdue: false };
  if (difference === 0) return { label: "D-Day", overdue: false };
  if (difference > 0) return { label: `D-${difference}`, overdue: false };
  return { label: `D+${Math.abs(difference)}`, overdue: true };
}

export function formatShortDate(value: string): string {
  const date = parseCalendarDate(value);
  return date
    ? `${String(date.month).padStart(2, "0")}.${String(date.day).padStart(2, "0")}`
    : value;
}

export function formatWeddingDate(value: string): string {
  const date = parseCalendarDate(value);
  return date ? `${date.month}월 ${date.day}일 결혼식` : "결혼일 확인 필요";
}

export function monthKey(value: string): string {
  const date = parseCalendarDate(value);
  return date ? `${date.year}년 ${date.month}월` : "날짜 미정";
}

export function isInCurrentMonth(value: string, now = new Date()): boolean {
  const date = parseCalendarDate(value);
  return date?.year === now.getFullYear() && date.month === now.getMonth() + 1;
}
