"use client";

import { EngineeringHealthReport } from "@/app/components/jira-analytics/EngineeringHealthReport";
import { JiraAnalyticsShell } from "@/app/components/jira-analytics/JiraAnalyticsShell";

export default function Page() {
  return (
    <JiraAnalyticsShell title="Engineering health index" description="" hidePageHeader hideMethodology>
      <EngineeringHealthReport activeReport="health" />
    </JiraAnalyticsShell>
  );
}
