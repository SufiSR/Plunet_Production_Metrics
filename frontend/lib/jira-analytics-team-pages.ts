import type { TeamReportId } from "@/app/components/jira-analytics/TeamReportLayout";

export interface TeamPageCopy {
  heroTitle: string;
  heroDescription: string;
  readingTip: string;
  lineageTitle?: string;
}

export const TEAM_PAGE_COPY: Record<TeamReportId, TeamPageCopy> = {
  heatmap: {
    heroTitle: "See who worked on what, by team and topic.",
    heroDescription:
      "A allocation heatmap for developers and QA: assigned team, topic slice, and allocated hours in the selected months.",
    readingTip:
      "Start with the busiest team rows, then drill into person-level cells when you need evidence for staffing or focus conversations.",
  },
  "planned-vs-unplanned": {
    heroTitle: "Measure roadmap focus against improvement work.",
    heroDescription:
      "Monthly roadmap hours as a share of roadmap plus continuous-improvement work for the focused engineering teams.",
    readingTip:
      "Use the chart for direction over time; use the table when you need the exact hours behind a single month.",
  },
  "availability-vs-booked": {
    heroTitle: "Compare available hours with what was booked.",
    heroDescription:
      "HRWorks availability and clocked time against Jira logged hours by team and person for Developer and QA roles.",
    readingTip:
      "Expand a team to inspect person-level utilization before drawing conclusions about over- or under-booking.",
  },
  "capacity-forecast": {
    heroTitle: "Forecast Dev and QA capacity ahead.",
    heroDescription:
      "Available Development and QA hours by assigned team and person across recent and upcoming months.",
    readingTip:
      "Read the team trend first, then the person table when you need to validate who drives the forecast gap.",
  },
  "real-interruption-ratio": {
    heroTitle: "Spot work that likely interrupted delivery.",
    heroDescription:
      "Interruption evidence from active-start timing and changelog signals for roadmap-started issues by team and month.",
    readingTip:
      "Switch to issue evidence when a month looks noisy; count and time bases answer different questions.",
  },
  throughput: {
    heroTitle: "See whether throughput is steady or volatile.",
    heroDescription:
      "Resolved issues per week and a predictability score by team for the selected period.",
    readingTip:
      "Low predictability with stable volume often points to flow or scope churn rather than capacity alone.",
  },
  "bus-factor": {
    heroTitle: "Find single-person dependency risk.",
    heroDescription:
      "Direct worklog concentration by person and topic—where one contributor carries most of the hours.",
    readingTip:
      "Prioritize topics where one person holds most direct hours and the team has few alternate contributors.",
  },
  health: {
    heroTitle: "Score delivery health with explainable components.",
    heroDescription:
      "Composite team/month health from flow efficiency, roadmap focus, interruption pressure, predictability, and work-shape risk.",
    readingTip:
      "Read the headline score, then the component breakdown to see which dimension drags health down.",
    lineageTitle: "Composite score built from prepared team signals.",
  },
  comparison: {
    heroTitle: "Compare focused teams over six months.",
    heroDescription:
      "Side-by-side health trends, deltas, strongest dimensions, and biggest drags for the focused engineering teams.",
    readingTip:
      "Use deltas and strongest/weakest components to compare teams without over-weighting a single month.",
    lineageTitle: "Same health model, compared across focused teams.",
  },
};

export const TEAM_LINEAGE_STEPS = [
  "Jira worklogs and user role assignments identify who logged time and which team they belonged to in each month.",
  "Monthly allocation rebuild classifies effort into topics (features, support, bugs, improvements, overhead).",
  "HRWorks monthly hours feed availability, utilization, and capacity forecast views for Developer and QA roles.",
  "Page filters reshape the prepared monthly datasets; nightly sync refreshes the underlying evidence.",
];
