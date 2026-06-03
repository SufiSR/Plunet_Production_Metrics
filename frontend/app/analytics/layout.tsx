import { AnalyticsEmbedStyleProvider } from "@/app/components/jira-analytics/AnalyticsEmbedStyleProvider";
import { JiraAnalyticsProvider } from "@/app/components/jira-analytics/JiraAnalyticsContext";

export default function AnalyticsLayout({ children }: { children: React.ReactNode }) {
  return (
    <JiraAnalyticsProvider>
      <AnalyticsEmbedStyleProvider>{children}</AnalyticsEmbedStyleProvider>
    </JiraAnalyticsProvider>
  );
}
