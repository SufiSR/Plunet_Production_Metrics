/** Condense legacy Plunet Cloud workflow statuses (aligned with backend catalog). */

const PLUNET_CLOUD_STATUS_GROUPS: ReadonlyArray<readonly [string, readonly string[]]> = [
  ["In preparation", ["In preparation"]],
  ["Backlog", ["Backlog", "Auf Entwicklungsplan"]],
  ["Description Update", ["Description Update", "Description update", "Check - Issue Description"]],
  ["Refinement", ["Refinement", "Feature Request Meeting Review"]],
  [
    "Ready for Development",
    ["Ready for Development", "Assigned - Ready to start", "Ready to start"],
  ],
  ["Development", ["Development", "In Arbeit", "In Progress"]],
  ["Waiting for input", ["Waiting for input"]],
  ["Ready for Code Review", ["Ready for Code Review", "Solved - Ready for approval"]],
  ["Code review", ["Code review", "Code Review"]],
  ["Ready for QA", ["Ready for QA"]],
  ["Test", ["Test"]],
  ["Testing blocked", ["Testing blocked"]],
  ["Ready to merge", ["Ready to merge"]],
  ["Merging", ["Merging"]],
  ["Reopened", ["Reopened"]],
];

const PLUNET_CLOUD_STATUS_ALIASES = new Map<string, string>();
for (const [canonical, aliases] of PLUNET_CLOUD_STATUS_GROUPS) {
  for (const alias of [canonical, ...aliases]) {
    PLUNET_CLOUD_STATUS_ALIASES.set(alias.trim().toLowerCase(), canonical);
  }
}

export function condensePlunetCloudStatus(status: string): string {
  const condensed = PLUNET_CLOUD_STATUS_ALIASES.get(status.trim().toLowerCase());
  return condensed ?? status;
}

export function plunetCloudStatusDisplayOrder(): string[] {
  return PLUNET_CLOUD_STATUS_GROUPS.map(([canonical]) => canonical);
}

export function orderPlunetCloudStatuses(statuses: Iterable<string>): string[] {
  const order = plunetCloudStatusDisplayOrder();
  const present = new Set(statuses);
  const declared = order.filter((status) => present.has(status));
  const remaining = [...present]
    .filter((status) => !order.includes(status))
    .sort((left, right) => left.localeCompare(right));
  return [...declared, ...remaining];
}
