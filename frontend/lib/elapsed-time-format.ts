const HOURS_PER_DAY = 24;

export function hoursToElapsedDays(hours: number): number {
  return hours / HOURS_PER_DAY;
}

export function formatElapsedDays(hours: number, maximumFractionDigits = 1): string {
  return `${new Intl.NumberFormat(undefined, {
    maximumFractionDigits,
    minimumFractionDigits: maximumFractionDigits,
  }).format(hoursToElapsedDays(hours))} d`;
}

export function formatElapsedDaysDelta(hours: number | null, maximumFractionDigits = 1): string {
  if (hours === null) return "n/a";
  const sign = hours > 0 ? "+" : "";
  return `${sign}${formatElapsedDays(hours, maximumFractionDigits)}`;
}

export function formatElapsedTimeWithHours(hours: number, maximumFractionDigits = 1): string {
  return `${formatElapsedDays(hours, maximumFractionDigits)} (${new Intl.NumberFormat(undefined, {
    maximumFractionDigits: 0,
  }).format(hours)} h)`;
}

export const ELAPSED_TIME_NOTE = "Elapsed wall-clock time, includes nights/weekends.";
