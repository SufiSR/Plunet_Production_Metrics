/** Condense legacy Standard Plunet workflow statuses (aligned with backend catalog). */

const STANDARD_PLUNET_STATUS_GROUPS: ReadonlyArray<readonly [string, readonly string[]]> = [
  ["Backlog", ["Backlog", "Ready to start", "Ready for development", "Ready for Development"]],
  ["Assigned - Ready to start", ["Assigned - Ready to start", "Assigned - ready to start"]],
  ["In Progress", ["In Progress", "In Arbeit", "Development"]],
  ["Reopened", ["Reopened"]],
  ["Solved - Ready for approval", ["Solved - Ready for approval"]],
  ["Waiting for input", ["Waiting for input"]],
  ["Ready for code review", ["Ready for code review", "Ready for Code Review"]],
  ["Code review", ["Code review", "Code Review"]],
  ["Ready for QA", ["Ready for QA"]],
  ["Test", ["Test"]],
];

const STANDARD_PLUNET_STATUS_ALIASES = new Map<string, string>();
for (const [canonical, aliases] of STANDARD_PLUNET_STATUS_GROUPS) {
  for (const alias of [canonical, ...aliases]) {
    STANDARD_PLUNET_STATUS_ALIASES.set(alias.trim().toLowerCase(), canonical);
  }
}

export function condenseStandardPlunetStatus(status: string): string {
  const condensed = STANDARD_PLUNET_STATUS_ALIASES.get(status.trim().toLowerCase());
  return condensed ?? status;
}

export function standardPlunetStatusDisplayOrder(): string[] {
  return STANDARD_PLUNET_STATUS_GROUPS.map(([canonical]) => canonical);
}

export function orderStandardPlunetStatuses(statuses: Iterable<string>): string[] {
  const order = standardPlunetStatusDisplayOrder();
  const present = new Set(statuses);
  const declared = order.filter((status) => present.has(status));
  const remaining = [...present]
    .filter((status) => !order.includes(status))
    .sort((left, right) => left.localeCompare(right));
  return [...declared, ...remaining];
}
