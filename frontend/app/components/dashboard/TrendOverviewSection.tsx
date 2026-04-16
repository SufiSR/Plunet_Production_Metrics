"use client";

import { useUIStore } from "@/lib/store";
import { CfrReleaseDrilldownPanel } from "./CfrReleaseDrilldownPanel";
import { DeploymentSwimlaneTimeline } from "./DeploymentSwimlaneTimeline";
import { ReleaseDrilldownPanel } from "./ReleaseDrilldownPanel";
import { TrendChart } from "./TrendChart";

/**
 * Single switch (in TrendChart) drives which metric is plotted and which
 * secondary visualization appears below: swimlane for deployments, drill-down
 * for lead time, failed-release drill-down for CFR, nothing for MTTR Alpha for now.
 */
export function TrendOverviewSection() {
  const trendMetric = useUIStore((s) => s.trendOverviewMetric);

  return (
    <div className="space-y-10">
      <TrendChart />
      {trendMetric === "deployment_frequency" && <DeploymentSwimlaneTimeline />}
      {trendMetric === "lead_time_for_changes" && <ReleaseDrilldownPanel />}
      {trendMetric === "change_failure_rate" && <CfrReleaseDrilldownPanel />}
    </div>
  );
}
