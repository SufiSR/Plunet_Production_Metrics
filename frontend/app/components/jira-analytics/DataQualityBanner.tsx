"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchDataQuality } from "@/lib/jira-analytics-api";
import type { DataQualityResponse } from "@/types/jira-analytics";

export function DataQualityBanner() {
  const [data, setData] = useState<DataQualityResponse | null>(null);

  useEffect(() => {
    void fetchDataQuality()
      .then(setData)
      .catch(() => setData(null));
  }, []);

  const warnings = data?.data_quality?.warnings ?? [];
  if (warnings.length === 0) return null;

  const high = warnings.filter((w) => w.severity === "high").length;

  return (
    <div
      className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm flex flex-wrap items-center justify-between gap-2"
      role="status"
    >
      <span className="text-on-surface">
        {warnings.length} data quality {warnings.length === 1 ? "issue" : "issues"}
        {high > 0 ? ` (${high} high severity)` : ""} may affect report accuracy.
      </span>
      <Link href="/analytics/data-quality" className="text-primary font-medium hover:underline text-xs">
        View data quality
      </Link>
    </div>
  );
}
