import { notFound } from "next/navigation";
import { AnalyticsReportPage } from "@/app/components/jira-analytics/AnalyticsReportPage";
import { reportPaths } from "@/lib/jira-analytics-api";

const RESERVED_FEATURE_ROUTES = new Set(["cost", "without-feature", "risk"]);

interface FeatureDetailPageProps {
  params: {
    featureKey: string;
  };
}

export default function FeatureDetailPage({ params }: FeatureDetailPageProps) {
  const featureKey = params.featureKey;

  if (RESERVED_FEATURE_ROUTES.has(featureKey)) {
    notFound();
  }

  return (
    <AnalyticsReportPage
      title={`Feature: ${featureKey}`}
      description="Allocated cost breakdown for this PMGT feature."
      apiPath={reportPaths.featureCost}
      defaultParams={{ featureKey }}
    />
  );
}
