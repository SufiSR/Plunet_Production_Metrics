export function lastTwelveMonths(): { from: string; to: string } {
  const today = new Date();
  const from = new Date(today.getFullYear(), today.getMonth() - 11, 1);
  return { from: formatIsoDate(from), to: formatIsoDate(today) };
}

export function previousMonthYearWindow(): { from: string; to: string } {
  const to = lastCompletedMonthEnd();
  const from = new Date(to.getFullYear() - 1, to.getMonth(), 1);
  return { from: formatIsoDate(from), to: formatIsoDate(to) };
}

export function lastSixMonths(): { from: string; to: string } {
  const to = lastCompletedMonthEnd();
  const from = new Date(to.getFullYear(), to.getMonth() - 5, 1);
  return { from: formatIsoDate(from), to: formatIsoDate(to) };
}

export function thisYearToDate(): { from: string; to: string } {
  const to = lastCompletedMonthEnd();
  return { from: formatIsoDate(new Date(to.getFullYear(), 0, 1)), to: formatIsoDate(to) };
}

export function lastYear(): { from: string; to: string } {
  const today = new Date();
  const year = today.getFullYear() - 1;
  return { from: `${year}-01-01`, to: `${year}-12-31` };
}

export function lastTwoYearsToDate(): { from: string; to: string } {
  const to = lastCompletedMonthEnd();
  return {
    from: formatIsoDate(new Date(to.getFullYear() - 1, 0, 1)),
    to: formatIsoDate(to),
  };
}

/** Calendar window covering the current quarter and the three prior quarters. */
export function lastFourQuartersRange(): { from: string; to: string } {
  const today = new Date();
  const currentQuarterStart = new Date(today.getFullYear(), Math.floor(today.getMonth() / 3) * 3, 1);
  const from = new Date(currentQuarterStart);
  from.setMonth(from.getMonth() - 9);
  return { from: formatIsoDate(from), to: formatIsoDate(today) };
}

export function formatIsoDate(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function lastCompletedMonthEnd(): Date {
  const today = new Date();
  return new Date(today.getFullYear(), today.getMonth(), 0);
}
