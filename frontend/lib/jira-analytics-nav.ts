export type JiraAnalyticsSectionId =
  | "portfolio"
  | "features"
  | "flow"
  | "bottlenecks"
  | "teams"
  | "customers"
  | "dora"
  | "quality";

export interface JiraAnalyticsReportLink {
  href: string;
  title: string;
  question: string;
  description?: string;
  implemented?: boolean;
}

export interface JiraAnalyticsSection {
  id: JiraAnalyticsSectionId;
  label: string;
  reports: JiraAnalyticsReportLink[];
}

export const JIRA_ANALYTICS_SECTIONS: JiraAnalyticsSection[] = [
  {
    id: "portfolio",
    label: "Portfolio investment",
    reports: [
      {
        href: "/analytics/investment/categories",
        title: "Investment categories",
        question: "Where is engineering capacity going over time?",
        implemented: true,
      },
      {
        href: "/analytics/investment/ranking",
        title: "Feature investment ranking",
        question: "Which features consumed the most capacity?",
        implemented: true,
      },
      {
        href: "/analytics/investment/feature-audit",
        title: "Feature investment audit",
        question: "Which features consumed booked and calculated investment by month, issue, and role?",
        implemented: true,
      },
      {
        href: "/analytics/investment/by-theme",
        title: "Investment by theme",
        question: "Which roadmap themes absorb most investment?",
        implemented: true,
      },
    ],
  },
  {
    id: "features",
    label: "Feature costs",
    reports: [
      {
        href: "/analytics/features",
        title: "Feature worklog hours",
        question: "Allocated Jira worklog and overhead hours by PMGT feature and Other bucket.",
        implemented: true,
      },
      {
        href: "/analytics/features/families",
        title: "Feature family worklog hours",
        question: "Which managed feature families consume the most capacity?",
        implemented: true,
      },
      {
        href: "/analytics/features/without-feature",
        title: "Issues without feature",
        question: "Which work consumes capacity outside PMGT families?",
        implemented: true,
      },
      {
        href: "/analytics/features/risk",
        title: "Feature delivery risk",
        question: "Which features are too large or risky?",
        implemented: true,
      },
    ],
  },
  {
    id: "flow",
    label: "Feature flow",
    reports: [
      {
        href: "/analytics/flow/lifecycle",
        title: "Lifecycle funnel",
        question: "How long from idea to completion?",
        implemented: true,
      },
      {
        href: "/analytics/flow/promised-vs-actual",
        title: "Promised vs actual",
        question: "Where do roadmap promises fail?",
        implemented: true,
      },
      {
        href: "/analytics/flow/idea-aging",
        title: "Idea aging",
        question: "How long do features wait before starting?",
        implemented: true,
      },
      {
        href: "/analytics/flow/size-vs-speed",
        title: "Size vs speed",
        question: "Do larger features take disproportionately longer?",
        implemented: true,
      },
      {
        href: "/analytics/flow/roadmap-reliability",
        title: "Roadmap reliability",
        question: "Can Product keep delivery commitments?",
        implemented: true,
      },
    ],
  },
  {
    id: "bottlenecks",
    label: "Bottlenecks",
    reports: [
      {
        href: "/analytics/bottlenecks/status-waiting",
        title: "Status waiting time",
        question: "Where do issues spend most of their lifetime?",
        implemented: true,
      },
      {
        href: "/analytics/bottlenecks/active-vs-passive",
        title: "Active vs passive time",
        question: "Which workflows are mostly waiting?",
        implemented: true,
      },
      {
        href: "/analytics/bottlenecks/active-vs-passive-trend",
        title: "Active vs passive trend",
        question: "Is passive workflow time improving or degrading by quarter?",
        implemented: true,
      },
      {
        href: "/analytics/bottlenecks/thrashing",
        title: "Workflow thrashing",
        question: "Which tickets bounce and reopen?",
        implemented: true,
      },
    ],
  },
  {
    id: "teams",
    label: "Team execution",
    reports: [
      {
        href: "/analytics/teams/heatmap",
        title: "Work allocation heatmap",
        question: "Who worked on which features and topics?",
        implemented: true,
      },
      {
        href: "/analytics/teams/planned-vs-unplanned",
        title: "Roadmap focus",
        question: "How much roadmap work do teams deliver compared with small features and unrelated bugs?",
        implemented: true,
      },
      {
        href: "/analytics/teams/availability-vs-booked",
        title: "Capacity utilization",
        question: "How do HRWorks available hours compare with Jira booked hours?",
        implemented: true,
      },
      {
        href: "/analytics/teams/capacity-forecast",
        title: "Capacity Forecast",
        question: "How much Dev and QA availability do teams have in upcoming months?",
        implemented: true,
      },
      {
        href: "/analytics/teams/real-interruption-ratio",
        title: "Real interruption ratio",
        question: "Which teams start likely unplanned work after creation, escalation, or late activity?",
        implemented: true,
      },
      {
        href: "/analytics/teams/throughput",
        title: "Throughput stability",
        question: "Which teams finish work predictably?",
        implemented: true,
      },
      {
        href: "/analytics/teams/bus-factor",
        title: "Bus factor",
        question: "Where is one person a single point of failure?",
        implemented: true,
      },
      {
        href: "/analytics/teams/health",
        title: "Engineering health index",
        question: "How healthy is delivery execution per team?",
        implemented: true,
      },
      {
        href: "/analytics/teams/comparison",
        title: "Team comparison",
        question: "How did focused teams change over the past six months?",
        implemented: true,
      },
    ],
  },
  {
    id: "customers",
    label: "Customer effort",
    reports: [
      {
        href: "/analytics/customers/effort",
        title: "Customer effort",
        question: "Which customers consume disproportionate capacity?",
        implemented: true,
      },
    ],
  },
  {
    id: "dora",
    label: "DORA metrics",
    reports: [
      {
        href: "/analytics/dora",
        title: "DORA overview",
        question: "How are the four DORA metrics performing right now?",
        implemented: true,
      },
      {
        href: "/analytics/dora/deployment-frequency",
        title: "Deployment frequency",
        question: "How often do customer releases ship?",
        implemented: true,
      },
      {
        href: "/analytics/dora/lead-time",
        title: "Median lead time",
        question: "How long from commit to customer release?",
        implemented: true,
      },
      {
        href: "/analytics/dora/change-failure-rate",
        title: "Change failure rate",
        question: "What share of releases introduced production issues?",
        implemented: true,
      },
      {
        href: "/analytics/dora/mttr-alpha",
        title: "MTTR Alpha",
        question: "How fast do we restore service after production failures?",
        implemented: true,
      },
    ],
  },
  {
    id: "quality",
    label: "Data quality",
    reports: [
      {
        href: "/analytics/data-quality",
        title: "Data quality dashboard",
        question: "Can we trust the analytics output?",
        implemented: true,
      },
    ],
  },
];

export function sectionForPath(pathname: string): JiraAnalyticsSection | undefined {
  if (pathname.startsWith("/analytics/investment")) return JIRA_ANALYTICS_SECTIONS.find((s) => s.id === "portfolio");
  if (pathname.startsWith("/analytics/features")) return JIRA_ANALYTICS_SECTIONS.find((s) => s.id === "features");
  if (pathname.startsWith("/analytics/flow")) return JIRA_ANALYTICS_SECTIONS.find((s) => s.id === "flow");
  if (pathname.startsWith("/analytics/bottlenecks")) return JIRA_ANALYTICS_SECTIONS.find((s) => s.id === "bottlenecks");
  if (pathname.startsWith("/analytics/teams")) return JIRA_ANALYTICS_SECTIONS.find((s) => s.id === "teams");
  if (pathname.startsWith("/analytics/customers")) return JIRA_ANALYTICS_SECTIONS.find((s) => s.id === "customers");
  if (pathname.startsWith("/analytics/dora")) return JIRA_ANALYTICS_SECTIONS.find((s) => s.id === "dora");
  if (pathname.startsWith("/analytics/data-quality")) return JIRA_ANALYTICS_SECTIONS.find((s) => s.id === "quality");
  return undefined;
}
