import type { StatusWaitingDataPoint, StatusWaitingPriorityRow } from "@/types/jira-analytics";
import {
  normalizeStatusWaitingPriority,
  STATUS_WAITING_PRIORITY_COLUMNS,
} from "@/lib/status-waiting-priorities";
import {
  condenseStatusWaitingStatus,
  hasStatusWaitingCondensation,
  orderStatusWaitingStatuses,
} from "@/lib/status-waiting-status-condensation";

function orderStatuses(statuses: Set<string>, statusOrder: string[]): string[] {
  const declared = statusOrder.filter((status) => statuses.has(status));
  const remaining = [...statuses].filter((status) => !declared.includes(status));
  remaining.sort((a, b) => a.localeCompare(b));
  return [...declared, ...remaining];
}

function median(values: number[]): number {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 1) return sorted[mid];
  return (sorted[mid - 1] + sorted[mid]) / 2;
}

export function aggregateStatusWaitingPoints(
  points: StatusWaitingDataPoint[],
  options: {
    selectedIssueTypes: string[];
    statusOrder?: string[];
    catalogKey?: string;
  },
): { rows: StatusWaitingPriorityRow[]; priorityColumns: string[] } {
  const selected = new Set(options.selectedIssueTypes);
  const useCondensedStatuses = hasStatusWaitingCondensation(options.catalogKey);
  const filtered = points.filter((point) => selected.has(point.issue_type));

  const daysByStatusPriorityIssue = new Map<string, Map<string, Map<number, number>>>();
  const issuesByStatus = new Map<string, Set<number>>();

  for (const point of filtered) {
    const status = useCondensedStatuses
      ? condenseStatusWaitingStatus(options.catalogKey, point.status)
      : point.status;
    const priority = normalizeStatusWaitingPriority(point.priority);
    let byPriority = daysByStatusPriorityIssue.get(status);
    if (!byPriority) {
      byPriority = new Map();
      daysByStatusPriorityIssue.set(status, byPriority);
    }
    let byIssue = byPriority.get(priority);
    if (!byIssue) {
      byIssue = new Map();
      byPriority.set(priority, byIssue);
    }
    byIssue.set(point.issue_id, (byIssue.get(point.issue_id) ?? 0) + point.days);

    let issues = issuesByStatus.get(status);
    if (!issues) {
      issues = new Set();
      issuesByStatus.set(status, issues);
    }
    issues.add(point.issue_id);
  }

  const durationsByStatusPriority = new Map<string, Map<string, number[]>>();
  const allDaysByStatus = new Map<string, number[]>();
  for (const [status, byPriorityIssue] of daysByStatusPriorityIssue.entries()) {
    const byPriority = new Map<string, number[]>();
    const allDays: number[] = [];
    for (const [priority, byIssue] of byPriorityIssue.entries()) {
      const issueTotals = [...byIssue.values()];
      byPriority.set(priority, issueTotals);
      allDays.push(...issueTotals);
    }
    durationsByStatusPriority.set(status, byPriority);
    allDaysByStatus.set(status, allDays);
  }

  const priorityColumns = [...STATUS_WAITING_PRIORITY_COLUMNS];
  const statusNames = new Set(durationsByStatusPriority.keys());
  const condensedOrder = orderStatusWaitingStatuses(options.catalogKey, statusNames);
  const orderedStatuses =
    condensedOrder ?? orderStatuses(statusNames, options.statusOrder ?? []);

  const rows: StatusWaitingPriorityRow[] = [];
  for (const status of orderedStatuses) {
    const byPriority = durationsByStatusPriority.get(status);
    const allDays = allDaysByStatus.get(status);
    if (!byPriority || !allDays?.length) continue;

    const medianByPriority: Record<string, number | null> = {};
    const averageByPriority: Record<string, number | null> = {};
    for (const priority of priorityColumns) {
      const durations = byPriority.get(priority);
      medianByPriority[priority] = durations?.length ? round2(median(durations)) : null;
      averageByPriority[priority] = durations?.length
        ? round2(durations.reduce((sum, value) => sum + value, 0) / durations.length)
        : null;
    }

    rows.push({
      status,
      unique_issue_count: issuesByStatus.get(status)?.size ?? 0,
      average_days_all_priorities: round2(
        allDays.reduce((sum, value) => sum + value, 0) / allDays.length,
      ),
      median_by_priority: medianByPriority,
      average_by_priority: averageByPriority,
    });
  }

  return { rows, priorityColumns };
}

function round2(value: number): number {
  return Math.round(value * 100) / 100;
}
