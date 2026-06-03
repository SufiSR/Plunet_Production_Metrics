/** Display order for status-waiting priority columns (aligned with backend catalog). */
export const STATUS_WAITING_PRIORITY_COLUMNS = [
  "Blocker",
  "Critical",
  "Major",
  "Normal",
  "Minor",
] as const;

const PRIORITY_ALIASES: Record<string, (typeof STATUS_WAITING_PRIORITY_COLUMNS)[number]> = {
  highest: "Critical",
  high: "Major",
  medium: "Normal",
  low: "Minor",
  lowest: "Minor",
  trivial: "Minor",
};

export function normalizeStatusWaitingPriority(priority: string): string {
  const trimmed = priority.trim();
  if (!trimmed) return "Unknown";
  const alias = PRIORITY_ALIASES[trimmed.toLowerCase()];
  if (alias) return alias;
  if ((STATUS_WAITING_PRIORITY_COLUMNS as readonly string[]).includes(trimmed)) {
    return trimmed;
  }
  return trimmed;
}
