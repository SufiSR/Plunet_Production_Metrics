"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { FeatureMetricCard, FeatureReportLayout } from "@/app/components/jira-analytics/FeatureReportLayout";
import { JiraAnalyticsShell } from "@/app/components/jira-analytics/JiraAnalyticsShell";
import { FeatureDrilldownPanel } from "@/app/components/jira-analytics/FeatureDrilldownPanel";
import { FeatureHoursChart } from "@/app/components/jira-analytics/FeatureHoursChart";
import { FeatureHoursFilters } from "@/app/components/jira-analytics/FeatureHoursFilters";
import { FeatureHoursMatrixTable } from "@/app/components/jira-analytics/FeatureHoursMatrixTable";
import { ReportPageFrame } from "@/app/components/jira-analytics/ReportPageFrame";
import {
  fetchFeatureHoursDrilldown,
  fetchFeatureHoursMatrix,
} from "@/lib/jira-analytics-api";
import type {
  FeatureHoursDrilldownResponse,
  FeatureHoursMatrixResponse,
} from "@/types/jira-analytics";

export default function FeatureHoursPage() {
  const [months, setMonths] = useState(12);
  const [role, setRole] = useState("");
  const [team, setTeam] = useState("");
  const [matrix, setMatrix] = useState<FeatureHoursMatrixResponse | null>(null);
  const [matrixError, setMatrixError] = useState<string | null>(null);
  const [matrixLoading, setMatrixLoading] = useState(true);

  const [selectedRowId, setSelectedRowId] = useState<string | null>(null);
  const [drilldown, setDrilldown] = useState<FeatureHoursDrilldownResponse | null>(null);
  const [drilldownError, setDrilldownError] = useState<string | null>(null);
  const [drilldownLoading, setDrilldownLoading] = useState(false);
  const drilldownRegionRef = useRef<HTMLDivElement>(null);

  const loadMatrix = useCallback(async () => {
    setMatrixLoading(true);
    setMatrixError(null);
    try {
      const data = await fetchFeatureHoursMatrix({
        months,
        role: role || null,
        team: team || null,
      });
      setMatrix(data);
    } catch (err) {
      setMatrix(null);
      setMatrixError(err instanceof Error ? err.message : "Failed to load feature hours");
    } finally {
      setMatrixLoading(false);
    }
  }, [months, role, team]);

  const loadDrilldown = useCallback(
    async (rowId: string) => {
      setDrilldownLoading(true);
      setDrilldownError(null);
      try {
        const data = await fetchFeatureHoursDrilldown(rowId, {
          months,
          role: role || null,
          team: team || null,
        });
        setDrilldown(data);
      } catch (err) {
        setDrilldown(null);
        setDrilldownError(err instanceof Error ? err.message : "Failed to load drill-down");
      } finally {
        setDrilldownLoading(false);
      }
    },
    [months, role, team],
  );

  useEffect(() => {
    void loadMatrix();
  }, [loadMatrix]);

  useEffect(() => {
    if (!selectedRowId) {
      setDrilldown(null);
      setDrilldownError(null);
      return;
    }
    void loadDrilldown(selectedRowId);
  }, [selectedRowId, loadDrilldown]);

  useEffect(() => {
    if (!selectedRowId || drilldownLoading) return;
    drilldownRegionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    drilldownRegionRef.current?.focus({ preventScroll: true });
  }, [selectedRowId, drilldownLoading, drilldown, drilldownError]);

  const handleSelectRow = (rowId: string) => {
    setSelectedRowId((prev) => (prev === rowId ? null : rowId));
  };

  return (
    <JiraAnalyticsShell
      title="Feature worklog hours"
      description="PMGT features and Other buckets as rows; click any row for drill-down. Totals include allocated overhead according to the configured strategy."
      hidePageHeader
      hideMethodology
    >
      <FeatureReportLayout
        activeReport="hours"
        title="Understand feature cost before it becomes a surprise."
        description="A feature-aware cost view that combines PMGT feature families, Other buckets, monthly history, and issue-level drill-down."
        metrics={<FeatureHoursMetrics matrix={matrix} />}
        controls={
          matrix ? (
            <FeatureHoursFilters
              months={months}
              role={role}
              team={team}
              availableRoles={matrix.available_roles}
              availableTeams={matrix.available_teams}
              onMonthsChange={setMonths}
              onRoleChange={setRole}
              onTeamChange={setTeam}
            />
          ) : null
        }
      >
        <ReportPageFrame loading={matrixLoading} error={matrixError} empty={!matrix && !matrixLoading}>
          {matrix ? (
            <div className="space-y-6">
              <FeatureHoursChart periods={matrix.periods} rows={matrix.rows} />
              <FeatureHoursMatrixTable
                periods={matrix.periods}
                rows={matrix.rows}
                jiraBaseUrl={matrix.jira_base_url}
                selectedRowId={selectedRowId}
                onSelectRow={handleSelectRow}
              />
              <div ref={drilldownRegionRef} tabIndex={-1} className="outline-none">
                <FeatureDrilldownPanel
                  data={drilldown}
                  jiraBaseUrl={matrix.jira_base_url}
                  loading={drilldownLoading}
                  error={drilldownError}
                  onClose={() => setSelectedRowId(null)}
                />
              </div>
            </div>
          ) : null}
        </ReportPageFrame>
      </FeatureReportLayout>
    </JiraAnalyticsShell>
  );
}

function FeatureHoursMetrics({ matrix }: { matrix: FeatureHoursMatrixResponse | null }) {
  const rows = matrix?.rows ?? [];
  const featureRows = rows.filter((row) => row.row_type === "feature").length;
  const totalHours = rows.reduce((sum, row) => sum + row.total_hours, 0);
  const periods = matrix?.periods.length ?? 0;

  return (
    <>
      <FeatureMetricCard label="Feature rows" value={rows.length ? String(featureRows) : "Loading"} detail="PMGT families in scope" />
      <FeatureMetricCard label="Allocated hours" value={formatCompactHours(totalHours)} detail="Visible feature and bucket hours" />
      <FeatureMetricCard label="Periods" value={periods ? String(periods) : "Loading"} detail="Monthly buckets in view" />
    </>
  );
}

function formatCompactHours(value: number): string {
  if (!value) return "Loading";
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value)} h`;
}
