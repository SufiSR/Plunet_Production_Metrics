"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { fetchFeatureHoursMatrix } from "@/lib/jira-analytics-api";

const JiraAnalyticsContext = createContext<string>("");

export function JiraAnalyticsProvider({ children }: { children: React.ReactNode }) {
  const [jiraBaseUrl, setJiraBaseUrl] = useState("");

  useEffect(() => {
    void fetchFeatureHoursMatrix({ months: 1 })
      .then((m) => setJiraBaseUrl(m.jira_base_url))
      .catch(() => setJiraBaseUrl(""));
  }, []);

  return (
    <JiraAnalyticsContext.Provider value={jiraBaseUrl}>{children}</JiraAnalyticsContext.Provider>
  );
}

export function useJiraBaseUrl(): string {
  return useContext(JiraAnalyticsContext);
}
