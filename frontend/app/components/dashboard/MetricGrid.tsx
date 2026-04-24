"use client";

import { useMetricsCurrent } from "@/lib/hooks";
import { MetricCard } from "./MetricCard";

const METRICS = [
  {
    key: "deployment_frequency",
    label: "Deployment Frequency",
    icon: "rocket_launch",
  },
  {
    key: "lead_time_for_changes",
    label: "Median Lead Time",
    icon: "schedule",
  },
  {
    key: "change_failure_rate",
    label: "Failure Rate",
    icon: "emergency",
  },
  {
    key: "mttr_alpha",
    label: "MTTR Alpha",
    icon: "history",
  },
] as const;

export function MetricGrid() {
  const { data, isLoading, isError } = useMetricsCurrent();

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-6">
      {METRICS.map(({ key, label, icon }) => (
        <MetricCard
          key={key}
          metricKey={key}
          label={label}
          icon={icon}
          data={data?.[key]}
          isLoading={isLoading}
          isError={isError}
          generatedAt={data?.generated_at}
        />
      ))}
    </div>
  );
}
