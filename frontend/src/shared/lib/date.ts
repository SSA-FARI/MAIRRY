export function formatDate(value: string | null): string {
  if (!value) {
    return "날짜 미정";
  }
  const [year, month, day] = value.split("-");
  return `${year}.${month}.${day}`;
}
