import {
  normalizeStatusWaitingPriority,
  STATUS_WAITING_PRIORITY_COLUMNS,
} from "@/lib/status-waiting-priorities";
import { condenseStatusWaitingStatus, hasStatusWaitingCondensation } from "@/lib/status-waiting-status-condensation";
import type { StatusWaitingDataPoint } from "@/types/jira-analytics";

export interface StatusWaitingDrilldownIssue {
  issue_id: number;
  issue_key: string;
  issue_type: string;
  days: number;
}

const DRILLDOWN_LIMIT = 10;

export function buildStatusWaitingDrilldownByPriority(
  points: StatusWaitingDataPoint[],
  status: string,
  options: {
    selectedIssueTypes: string[];
    catalogKey?: string;
    limit?: number;
  },
): Record<string, StatusWaitingDrilldownIssue[]> {
  const selected = new Set(options.selectedIssueTypes);
  const useCondensedStatuses = hasStatusWaitingCondensation(options.catalogKey);
  const limit = options.limit ?? DRILLDOWN_LIMIT;

  const byPriorityIssue = new Map<string, Map<number, StatusWaitingDrilldownIssue>>();

  for (const point of points) {
    if (!selected.has(point.issue_type)) continue;
    const pointStatus = useCondensedStatuses
      ? condenseStatusWaitingStatus(options.catalogKey, point.status)
      : point.status;
    if (pointStatus !== status) continue;

    const priority = normalizeStatusWaitingPriority(point.priority);
    let byIssue = byPriorityIssue.get(priority);
    if (!byIssue) {
      byIssue = new Map();
      byPriorityIssue.set(priority, byIssue);
    }
    const existing = byIssue.get(point.issue_id);
    if (existing) {
      existing.days += point.days;
      if (!existing.issue_key && point.issue_key) {
        existing.issue_key = point.issue_key;
      }
      continue;
    }
    byIssue.set(point.issue_id, {
      issue_id: point.issue_id,
      issue_key: point.issue_key ?? "",
      issue_type: point.issue_type,
      days: point.days,
    });
  }

  const result: Record<string, StatusWaitingDrilldownIssue[]> = {};
  const priorityOrder: string[] = [...STATUS_WAITING_PRIORITY_COLUMNS];
  const extraPriorities = [...byPriorityIssue.keys()].filter((priority) => !priorityOrder.includes(priority));
  for (const priority of [...priorityOrder, ...extraPriorities.sort()]) {
    const byIssue = byPriorityIssue.get(priority);
    if (!byIssue?.size) continue;
    result[priority] = [...byIssue.values()]
      .map((issue) => ({ ...issue, days: round2(issue.days) }))
      .sort((a, b) => b.days - a.days || a.issue_key.localeCompare(b.issue_key))
      .slice(0, limit);
  }
  return result;
}

function round2(value: number): number {
  return Math.round(value * 100) / 100;
}
