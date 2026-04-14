export interface MetricExplanation {
  key: string;
  title: string;
  description: string;
  unitLabel: string;
  doraThresholds: {
    elite: string;
    high: string;
    medium: string;
    low: string;
  };
  icon: string; // Material Symbols icon name
}

export const METRIC_EXPLANATIONS: Record<string, MetricExplanation> = {
  deployment_frequency: {
    key: "deployment_frequency",
    title: "Deployment Frequency",
    description:
      "How often the team deploys code to production, displayed as a weekly rate. Higher is better. While elite DORA teams deploy daily, a healthy rate for low-volume teams is 1+ deploy per week.",
    unitLabel: "deploys / week",
    doraThresholds: {
      elite: "Multiple times per day",
      high: "Once per day to once per week",
      medium: "Once per week to once per month",
      low: "Less than once per month",
    },
    icon: "rocket_launch",
  },
  lead_time_for_changes: {
    key: "lead_time_for_changes",
    title: "Lead Time for Changes",
    description:
      "The time from code commit to running in production. Measures the speed of the delivery pipeline. Shorter is better.",
    unitLabel: "hours",
    doraThresholds: {
      elite: "Less than 1 hour",
      high: "1 day to 1 week",
      medium: "1 week to 1 month",
      low: "More than 6 months",
    },
    icon: "schedule",
  },
  change_failure_rate: {
    key: "change_failure_rate",
    title: "Change Failure Rate",
    description:
      "The percentage of deployments that cause a production failure requiring a hotfix or rollback. Lower is better.",
    unitLabel: "%",
    doraThresholds: {
      elite: "0–5%",
      high: "5–10%",
      medium: "10–15%",
      low: "15–100%",
    },
    icon: "emergency",
  },
  mttr_alpha: {
    key: "mttr_alpha",
    title: "MTTR Alpha",
    description:
      "Mean Time to Restore — the time it takes to recover from a production failure. Measured as time from the first failing commit to the first successful fix-deployment. Lower is better.",
    unitLabel: "minutes",
    doraThresholds: {
      elite: "Less than 1 hour",
      high: "Less than 1 day",
      medium: "1 day to 1 week",
      low: "More than 6 months",
    },
    icon: "history",
  },
  lead_post_production: {
    key: "lead_post_production",
    title: "Lead Post-Production",
    description:
      "Time from merge to customer-facing release tag. Captures the delay between code landing in main and the customer receiving it. Shorter is better.",
    unitLabel: "days",
    doraThresholds: {
      elite: "Same day",
      high: "1–3 days",
      medium: "1–2 weeks",
      low: "More than 1 month",
    },
    icon: "local_shipping",
  },
};
