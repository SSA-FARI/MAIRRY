export function formatDate(value: string | null): string {
  if (!value) {
    return "날짜 미정";
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return value;
  }
  const [year, month, day] = value.split("-");
  return `${year}.${month}.${day}`;
}
