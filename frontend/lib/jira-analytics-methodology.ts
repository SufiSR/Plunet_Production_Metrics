/**
 * Per-report methodology copy shown on analytics detail pages.
 * Keep aligned with backend: app/jira_analytics/reports/, allocation/, feature_hours_service.py
 */

export interface ReportMethodology {
  id: string;
  title: string;
  /** One paragraph: what question this report answers */
  overview: string;
  dataSources: string[];
  included: string[];
  presented: string[];
  limitations?: string[];
}

const EXCLUDED_PROJECTS =
  "Jira projects ACT, DIM, ITS, JIRATESTS, PLU, and SE are excluded everywhere in Jira Analytics.";

const SYNC_FRESHNESS =
  "Numbers use data from the latest Jira analytics ingestion (issues, worklogs, status history, custom fields) and, where noted, HR Works monthly hours.";

const FEATURE_MEMBERSHIP =
  "PMGT feature families: work is attributed to a feature root when the issue is linked via feature membership (epic/parent hierarchy under a PMGT root).";

const ALLOCATION_OVERVIEW =
  "Allocated time combines direct Jira worklogs with monthly HR Works capacity for indirect roles. Jira user assignments are the source of truth for role, team, reporting exclusion, and optional allocation overrides.";

const ALLOCATION_DIRECT =
  "Direct worklog time is counted from Jira worklogs in the selected calendar period. Only users with an active role assignment on the worklog date are included; reporting-excluded users are omitted.";

const ALLOCATION_INDIRECT = [
  "Direct roles such as Developer, QA, UX, and support-style roles contribute only the hours they booked in Jira.",
  "Indirect roles such as Product Owner, Product Manager, System Architect, and Head of Dev use HR Works monthly hours. Their allocatable percentage can be overridden per user; the remaining share is stored as shared overhead.",
  "Team-scoped indirect roles distribute allocatable time only across that team’s direct work. Global roles distribute allocatable time across all in-scope direct work.",
  "Allocated rows are proportional: first by project-level direct hours, then by feature/topic direct hours within each project.",
];

const ALLOCATION_REBUILD =
  "Run allocation rebuild after sync when worklogs, Jira user assignments, reporting exclusions, or HR Works hours change (POST /api/jira-analytics/allocation/rebuild).";

const ALLOCATED_TIME_NOTE =
  "This report uses allocated time from monthly_allocated_effort, so totals can include both direct Jira worklogs and indirect HR Works capacity.";

const DIRECT_TIME_NOTE =
  "This report uses direct Jira worklog time only. It does not include indirect HR Works allocation or shared overhead.";

const NO_TIME_ALLOCATION_NOTE =
  "This report does not use time allocation; it is based on Jira issue dates, status history, release data, or quality checks as noted below.";

const ELAPSED_STATUS_TIME_NOTE =
  "Status interval durations are elapsed wall-clock time from Jira timestamps, shown as calendar days and including nights/weekends.";

const TOPIC_TYPES =
  "Topics are classified as feature, tech_support, unassigned_bug, issue_without_feature, shared_overhead, or unclassified from issue type and feature membership. Indirect allocated rows keep the same feature or generic topic as their allocation target.";

export const REPORT_METHODOLOGY: Record<string, ReportMethodology> = {
  "investment-categories": {
    id: "investment-categories",
    title: "Investment categories",
    overview:
      "Shows how total allocated engineering capacity (direct + indirect) is distributed across investment categories per calendar month.",
    dataSources: ["monthly_allocated_effort", "HR Works (indirect roles)", "Jira worklogs (direct base)"],
    included: [
      EXCLUDED_PROJECTS,
      ALLOCATED_TIME_NOTE,
      "Direct Jira worklogs are counted as booked; indirect roles use HR Works monthly hours spread by the allocation rules.",
      "Categories: feature → feature; tech_support → support; unassigned_bug → bugs_without_feature; issue_without_feature → small_improvements; shared_overhead → shared_overhead; unclassified → unclassified.",
      "Optional filters: allocation month, Jira projects, and team from Jira user assignments.",
    ],
    presented: [
      "Stacked time series by month: hours per investment category.",
      "Chart keys: feature, support, bugs_without_feature, small_improvements, shared_overhead, unclassified.",
    ],
    limitations: [ALLOCATION_REBUILD, "Does not show pre-allocation worklog-only views (see Feature worklog hours)."],
  },

  "investment-ranking": {
    id: "investment-ranking",
    title: "Feature investment ranking",
    overview: "Ranks PMGT features by total allocated hours (direct + indirect) in the selected period.",
    dataSources: ["monthly_allocated_effort (feature topics only)"],
    included: [
      EXCLUDED_PROJECTS,
      ALLOCATED_TIME_NOTE,
      ALLOCATION_OVERVIEW,
      "Feature cost aggregation for topic_type = feature only.",
      "Top 50 features by default (API limit).",
    ],
    presented: [
      "Table: rank, feature name/key, direct_* and allocated_* role columns, total hours.",
      "Sorted by total descending.",
    ],
    limitations: [ALLOCATION_REBUILD],
  },

  "investment-by-theme": {
    id: "investment-by-theme",
    title: "Investment by theme",
    overview: "Allocated hours on feature work grouped by PMGT Product values.",
    dataSources: ["monthly_allocated_effort", "jira_feature_root", "jira_issue_detail.pmgt_product"],
    included: [
      EXCLUDED_PROJECTS,
      ALLOCATED_TIME_NOTE,
      ALLOCATION_OVERVIEW,
      "Feature topics only; grouping value from the PMGT root Product field, or Unknown if missing.",
      "All allocation kinds on those rows (direct + indirect).",
    ],
    presented: ["Table: theme name, total hours (rounded). Sorted by hours descending."],
    limitations: [ALLOCATION_REBUILD, "Grouping accuracy depends on Product field population in Jira."],
  },

  "feature-worklog-hours": {
    id: "feature-worklog-hours",
    title: "Feature worklog hours",
    overview:
      "Allocated Jira worklog and overhead hours by PMGT feature, Other bucket, and month.",
    dataSources: ["monthly_allocated_effort", "feature membership", "worklog role assignments from settings"],
    included: [
      EXCLUDED_PROJECTS,
      SYNC_FRESHNESS,
      FEATURE_MEMBERSHIP,
      ALLOCATED_TIME_NOTE,
      "Worklogs mapped to users/roles via Jira user assignments; reporting-excluded users omitted.",
      "Rows: PMGT feature roots, plus rolled-up “Other bug / feature / misc” buckets for non-feature work and allocated overhead.",
      "Filters: last N months, optional role and team.",
    ],
    presented: [
      "Matrix: rows × months with hours; chart of selected row; drilldown lists contributing issues and worklogs.",
      "Delivery progress % when computable from child issue statuses.",
    ],
    limitations: [
      "Feature-only ranking pages still filter to PMGT feature topics; use the audit and category views for generic bucket reconciliation.",
      "Indirect or non-production roles may be excluded from matrix role filter logic.",
    ],
  },

  "feature-detail": {
    id: "feature-detail",
    title: "Single feature cost",
    overview: "Allocated cost breakdown for one PMGT feature (same logic as Feature investment ranking, filtered).",
    dataSources: ["monthly_allocated_effort"],
    included: [
      EXCLUDED_PROJECTS,
      ALLOCATED_TIME_NOTE,
      ALLOCATION_OVERVIEW,
      "Filter: feature_key from URL.",
    ],
    presented: ["Same columns as Feature investment ranking for the selected feature only."],
    limitations: [ALLOCATION_REBUILD],
  },

  "issues-without-feature": {
    id: "issues-without-feature",
    title: "Issues without feature",
    overview: "Direct worklog hours on issues that are not linked to any PMGT feature root.",
    dataSources: ["monthly_topic_effort_base (pre-allocation direct hours)"],
    included: [
      EXCLUDED_PROJECTS,
      DIRECT_TIME_NOTE,
      ALLOCATION_DIRECT,
      "feature_root_id is null; aggregated per issue_key in the period.",
      "Flags: missing_feature_high_effort (>40h), missing_feature_many_people (>3 contributors).",
    ],
    presented: [
      "Table: issue key, type, team, hours, contributor count, flags.",
      "Sorted by hours descending.",
    ],
    limitations: [
      "Direct hours only — not full allocated cost.",
      "Fixing membership + rebuild changes feature vs operational splits elsewhere.",
    ],
  },

  "feature-risk": {
    id: "feature-risk",
    title: "Feature delivery risk",
    overview: "Heuristic risk score combining feature size (hours) and lifecycle duration.",
    dataSources: ["monthly_allocated_effort (totals)", "feature lifecycle"],
    included: [
      EXCLUDED_PROJECTS,
      ALLOCATED_TIME_NOTE,
      "risk_score = min(100, total_hours/10 + production_duration_days/5) per feature.",
      "production_duration_days uses production duration from the first worklog date to the last worklog date.",
    ],
    presented: [
      "Table: feature_key, feature_title, status, hours, production_duration_days, lifecycle_duration_days, idle_before_work_days, risk_score.",
      "Default order is risk_score descending; columns can be sorted in the table.",
    ],
    limitations: [
      "Simplified index — not a forecast model.",
      "Features without worklogs have no production duration yet, so risk uses hours only until work starts.",
    ],
  },

  lifecycle: {
    id: "lifecycle",
    title: "Feature lifecycle",
    overview: "Phase durations for each PMGT feature root from creation through start and completion.",
    dataSources: ["Jira feature roots", "issue fields", "first worklog per root issue"],
    included: [
      EXCLUDED_PROJECTS,
      FEATURE_MEMBERSHIP,
      NO_TIME_ALLOCATION_NOTE,
      "Start date priority: actual_start → start_date → first worklog on root → else idea phase only.",
      "End date only when resolvable: actual_end → resolved_at_jira → done/closed status + updated_at.",
      "idea_to_start_days, start_to_done_days, total_duration_days (calendar days, UTC).",
      "date_source / end_date_source columns document which field was used.",
    ],
    presented: [
      "Table: feature key/name, phase day counts, status, team, date sources.",
      "Open features: start_to_done and total_duration omitted when no reliable end.",
    ],
    limitations: ["Missing custom dates fall back to worklogs or leave phases blank."],
  },

  "promised-vs-actual": {
    id: "promised-vs-actual",
    title: "Promised vs actual delivery",
    overview: "Compares promised delivery date to actual completion for features that have a promise set.",
    dataSources: ["jira_issue_detail.promised_delivery_date", "actual_end / resolved_at_jira"],
    included: [
      EXCLUDED_PROJECTS,
      NO_TIME_ALLOCATION_NOTE,
      "Only feature roots with promised_delivery_date populated.",
      "delay_days = actual date − promised (negative or zero = on time or early).",
    ],
    presented: ["Table: feature, promised, actual, delay_days, team, status."],
    limitations: ["Features without promise or without actual end show null delay."],
  },

  "idea-aging": {
    id: "idea-aging",
    title: "Idea aging",
    overview: "Features waiting between creation and work start (idea → start), derived from lifecycle.",
    dataSources: ["Same as Feature lifecycle"],
    included: [
      EXCLUDED_PROJECTS,
      NO_TIME_ALLOCATION_NOTE,
      "Subset of lifecycle where idea_to_start_days is known.",
      "Default: all ages; API supports min_age_days.",
    ],
    presented: ["Table includes waiting_days (= idea_to_start), sorted longest first."],
    limitations: ["Start detection quality depends on actual_start / start_date / first worklog."],
  },

  "size-vs-speed": {
    id: "size-vs-speed",
    title: "Size vs speed",
    overview:
      "Relates allocated feature size (hours) to active delivery span and end-to-end lifecycle duration, with comparable intensity KPIs.",
    dataSources: [
      "monthly_allocated_effort totals",
      "feature lifecycle",
      "first/last worklog on feature membership (same as Feature risk)",
    ],
    included: [
      EXCLUDED_PROJECTS,
      ALLOCATED_TIME_NOTE,
      "One row per feature with total allocated hours.",
      "lifecycle_days: lifecycle total_duration_days (created → completion when end is known).",
      "duration_days (legacy alias): same value as lifecycle_days for backward compatibility.",
      "production_duration_days: calendar days from first to last worklog on the feature tree.",
      "hours_per_production_day = hours / production_duration_days when duration > 0.",
      "hours_per_lifecycle_day = hours / lifecycle_days when lifecycle_days > 0.",
    ],
    presented: [
      "Table: feature_key, feature_name, hours, production_duration_days, hours_per_production_day, lifecycle_days, hours_per_lifecycle_day.",
    ],
    limitations: [
      ALLOCATION_REBUILD,
      "Correlation is descriptive, not normalized by team or scope.",
      "Zero-day production span yields null hours_per_production_day (same-day first/last worklog).",
      "Open features may have production duration but null lifecycle_days.",
    ],
  },

  "roadmap-reliability": {
    id: "roadmap-reliability",
    title: "Roadmap reliability",
    overview: "Share of promised features delivered on time vs late vs still open.",
    dataSources: ["Promised vs actual dataset"],
    included: [
      EXCLUDED_PROJECTS,
      NO_TIME_ALLOCATION_NOTE,
      "on_time: delay_days ≤ 0; delayed: delay_days > 0; still_open: no actual date.",
      "reliability = on_time / (on_time + delayed + still_open).",
    ],
    presented: ["Summary counts + underlying promised vs actual table."],
    limitations: ["Only features with a promise date are in the denominator."],
  },

  "status-waiting": {
    id: "status-waiting",
    title: "Status waiting time",
    overview:
      "How long issues spend in each workflow status (from changelog intervals), split into curated main delivery workflows and selected specialist workflows.",
    dataSources: [
      "jira_issue_status_transition",
      "jira_workflow",
      "jira_project_workflow_mapping",
      "Jira workflow search + project statuses API (workflow sync)",
    ],
    included: [
      EXCLUDED_PROJECTS,
      NO_TIME_ALLOCATION_NOTE,
      ELAPSED_STATUS_TIME_NOTE,
      "Main workflows: Plunet Cloud Workflow (Bug and Improvement families, including sub-tasks) and Standard Plunet Workflow (Analysis, Epic, TechSupport, Development Subtask).",
      "Other workflows: product_discovery, Design, Autotest, Regular Test, and Test Result workflows.",
      "Standard Plunet and Plunet Cloud workflows condense legacy status names into current labels and use fixed delivery order.",
      "Status variants like 'In Arbeit (!)' merge; Done excluded.",
      "Optional date range clips interval overlap.",
    ],
    presented: [
      "Global filters: date range and Jira projects (all selected by default) apply to every workflow.",
      "Optional checkbox loads other workflows (off by default to keep queries fast).",
      "Global statistic toggle switches priority columns between median and average elapsed days.",
      "Main workflows: dynamic issue-type pills under each headline; table columns Blocker → Critical → Major → Normal → Minor, then Average and Issue Count.",
      "Other workflows: project chips plus the same column layout.",
    ],
    limitations: [
      "Requires a Jira analytics sync to refresh workflow scheme mappings.",
      "Team-managed projects may have limited workflow scheme API coverage.",
      "Date filter clips interval overlap; partial intervals count only the overlapping elapsed calendar days.",
    ],
  },

  "active-vs-passive": {
    id: "active-vs-passive",
    title: "Active vs passive time",
    overview: "Splits issue-created cohort workflow elapsed time into active work vs queue buckets for detailed team and issue drilldown.",
    dataSources: ["Jira status intervals", "workflow sync mappings", "Jira worklogs and user assignments for team attribution"],
    included: [
      EXCLUDED_PROJECTS,
      NO_TIME_ALLOCATION_NOTE,
      ELAPSED_STATUS_TIME_NOTE,
      "Issue cohort is selected by Jira issue created date.",
      "Each status interval is classified as Active Work, Product Queue, Dev Queue, or QA Queue using the curated workflow catalog.",
      "Team attribution uses PMGT team metadata where available, then contributor team evidence from Jira worklogs and assignments.",
    ],
    presented: ["Workflow cards with team elapsed-day totals, expandable issue rows, and issue timeline drilldown for the selected created-date cohort."],
    limitations: [
      "This detail report is not a trend view because all rows are aggregated into the selected cohort window.",
      "Use Active vs passive trend to compare improvement or degradation by quarter.",
    ],
  },

  "active-vs-passive-trend": {
    id: "active-vs-passive-trend",
    title: "Active vs passive trend",
    overview:
      "Shows whether passive workflow elapsed time is improving or degrading by quarter using status interval overlap inside each quarter.",
    dataSources: ["Jira status intervals", "workflow sync mappings", "Jira worklogs and user assignments for team attribution"],
    included: [
      EXCLUDED_PROJECTS,
      NO_TIME_ALLOCATION_NOTE,
      ELAPSED_STATUS_TIME_NOTE,
      "Date basis is status interval overlap, not issue created date.",
      "Each interval is clipped to the quarter where the waiting or active elapsed time occurred.",
      "Active Work is compared with Product Queue, Dev Queue, and QA Queue.",
      "Team attribution matches the Active vs passive detail report.",
    ],
    presented: [
      "Quarterly passive share trend, active/passive elapsed-day stacks, latest-quarter KPI cards, and quarter/team/workflow table with deltas.",
    ],
    limitations: [
      "Open intervals continue until current time or issue resolution, so the current quarter can move as data refreshes.",
      "Quarterly aggregation is directional and should be paired with the detail report for issue-level root cause analysis.",
    ],
  },

  thrashing: {
    id: "thrashing",
    title: "Workflow thrashing",
    overview: "Issues with excessive status churn, reopens, and ping-pong transitions.",
    dataSources: ["jira_issue_status_transitions"],
    included: [
      EXCLUDED_PROJECTS,
      NO_TIME_ALLOCATION_NOTE,
      "thrash_score = status_changes + reopens×3 + ping_pong×2.",
      "Reopen: transition from done/closed/resolved to another status.",
      "Ping-pong: A→B→A pattern on status names.",
      "Only status transitions within the selected from/to window are counted.",
      "QA issues whose title contains AutoTest or TestResult are excluded.",
      "Default filter min_score ≥ 3 on this page; API default 0.",
      "Default date range: same calendar day one year ago through today.",
    ],
    presented: [
      "Top 100 issues: issue_key, summary, status_changes, reopens, ping_pong_count, thrash_score.",
    ],
    limitations: ["Score is a relative index, not normalized by issue age or type."],
  },

  heatmap: {
    id: "heatmap",
    title: "Work allocation heatmap",
    overview:
      "Developer and QA allocated hours grouped by assigned team, then topic, then individual.",
    dataSources: ["monthly_allocated_effort", "jira_user_role_assignment"],
    included: [
      EXCLUDED_PROJECTS,
      ALLOCATED_TIME_NOTE,
      ALLOCATION_OVERVIEW,
      "Roles: Developer and QA only (excludes support, PO/PM, architects, UX, shared overhead).",
      "Team = user's assigned team for the allocation month (not issue team).",
      "Direct worklog plus indirect topic allocation; excludes shared_overhead.",
      "Topic = feature key and name when present, otherwise topic type label.",
    ],
    presented: [
      "Grouped view: team → topic → person hours.",
      "Flat table (up to 2000 rows): team, topic, person, hours.",
    ],
    limitations: [ALLOCATION_REBUILD],
  },

  "planned-vs-unplanned": {
    id: "planned-vs-unplanned",
    title: "Planned vs unplanned",
    overview: "Team-month split between planned feature work and unplanned support/bugs/non-feature work.",
    dataSources: ["monthly_allocated_effort"],
    included: [
      EXCLUDED_PROJECTS,
      ALLOCATED_TIME_NOTE,
      ALLOCATION_OVERVIEW,
      "Planned: topic_type feature.",
      "Unplanned: tech_support, unassigned_bug, issue_without_feature.",
      "interruption_ratio = unplanned / (planned + unplanned).",
    ],
    presented: ["Table: team, month, planned_hours, unplanned_hours, interruption_ratio."],
    limitations: [ALLOCATION_REBUILD, "Shared overhead and unclassified are excluded from this ratio."],
  },

  "availability-vs-booked": {
    id: "availability-vs-booked",
    title: "Capacity utilization",
    overview:
      "Compares HR Works planned availability with direct Jira booked hours for Developer and QA roles by assigned team, month, and person.",
    dataSources: ["jira_user_monthly_hrworks_hours", "monthly_topic_effort_base", "jira_user_role_assignment"],
    included: [
      EXCLUDED_PROJECTS,
      DIRECT_TIME_NOTE,
      SYNC_FRESHNESS,
      "Availability = HR Works planned_working_hours for users assigned as Developer or QA in the month.",
      "Booked = direct Jira worklog hours from monthly_topic_effort_base for Developer and QA only.",
      "Team = user's assigned team for the month, not issue team.",
      "Teams with zero HR Works planned availability in the selected period are excluded.",
      "utilization_ratio = booked_hours / available_hours. The ratio is n/a when availability is zero.",
    ],
    presented: [
      "Monthly chart: one stacked bar per team, with booked hours filled and remaining availability as the lighter segment.",
      "Team drilldown: selected-period totals expandable from team to individual.",
      "Person table: month, team, person, role, available hours, booked hours, and ratio.",
    ],
    limitations: [
      "Uses monthly HR Works availability, not weekly availability.",
      ALLOCATION_REBUILD,
    ],
  },

  "capacity-forecast": {
    id: "capacity-forecast",
    title: "Capacity Forecast",
    overview:
      "Shows available HR Works capacity for Developer and QA roles by assigned team, person, and month across the recent and forecast window.",
    dataSources: ["jira_user_monthly_hrworks_hours", "jira_user_role_assignment"],
    included: [
      SYNC_FRESHNESS,
      "Capacity = HR Works planned_working_hours for users assigned as Developer or QA in the month.",
      "HR Works availability is already reduced by out-of-office, vacation, holidays, and part-time schedules.",
      "Team = user's assigned team for the month, not issue team.",
      "Focused teams: Team Tantrum, Team World, Cosmic Coders, and FreeDevs.",
      "Default window: previous month, current month, and next five months.",
    ],
    presented: [
      "Landing view: side-by-side stacked monthly capacity charts for focused teams (excluding FreeDevs) with a shared Y scale.",
      "Operational matrix: people rows by month, split into Development and QA sections.",
      "Cross-team trend: monthly total capacity by team.",
    ],
    limitations: ["Future months require HR Works forecast rows; missing rows appear as absent/zero capacity."],
  },

  "real-interruption-ratio": {
    id: "real-interruption-ratio",
    title: "Real interruption ratio",
    overview:
      "Estimates likely unplanned starts from active-start timing, topic classification, and Jira changelog evidence.",
    dataSources: ["jira_issue_status_transition", "monthly_allocated_effort", "raw Jira changelog JSON"],
    included: [
      EXCLUDED_PROJECTS,
      ALLOCATED_TIME_NOTE,
      "Counts issues that start in active statuses and separates roadmap hours from interrupting tech support, bugs, and issues without feature.",
      "High/medium confidence interruptions count in the numerator; weak activity-only evidence is surfaced separately.",
    ],
    presented: [
      "Monthly team series by count or time basis, summary table, and issue-level evidence rows.",
    ],
    limitations: [
      "Focused on Team Tantrum, Team World, and Cosmic Coders.",
      "When raw changelog history is missing, evidence quality is lower.",
    ],
  },

  throughput: {
    id: "throughput",
    title: "Throughput stability",
    overview: "Resolved issue counts per ISO week and a simple predictability score per team.",
    dataSources: ["Jira issues with resolved_at_jira", "team on issue detail"],
    included: [
      EXCLUDED_PROJECTS,
      NO_TIME_ALLOCATION_NOTE,
      "Count of resolved issues per team per calendar week in optional date range.",
      "predictability = max(0, 1 − stddev/avg) capped at 1 when avg > 0.",
    ],
    presented: ["Table: team, avg_done_per_week, stddev, predictability."],
    limitations: ["Uses resolution timestamp, not status category; includes all resolved issue types."],
  },

  "bus-factor": {
    id: "bus-factor",
    title: "Bus factor",
    overview: "Single-contributor concentration on PMGT features using direct worklog hours only.",
    dataSources: ["monthly_topic_effort_base (feature-linked direct hours)"],
    included: [
      EXCLUDED_PROJECTS,
      DIRECT_TIME_NOTE,
      ALLOCATION_DIRECT,
      "Per feature: share of hours from top contributor; risk band low/medium/high/extreme by share thresholds.",
    ],
    presented: ["Table: feature, top_contributor, share, contributor count, risk."],
    limitations: ["Direct hours only — ignores indirect allocated roles."],
  },

  "engineering-health": {
    id: "engineering-health",
    title: "Engineering health index",
    overview:
      "Composite team/month delivery health score combining flow efficiency, roadmap focus, interruption pressure, throughput predictability, and work-shape risk.",
    dataSources: [
      "Planned vs unplanned (allocated hours)",
      "Real interruption ratio",
      "Active vs passive workflow elapsed time",
      "Throughput stability",
      "Feature delivery risk",
    ],
    included: [
      EXCLUDED_PROJECTS,
      ALLOCATED_TIME_NOTE,
      "Default window is the last six months; API supports from, to, and team filters.",
      "Focused teams: Team Tantrum, Team World, Cosmic Coders; FreeDevs is included when assignment/component data exists.",
      "Weights: flow efficiency 25%, roadmap focus 20%, interruption health 20%, throughput predictability 20%, work-shape health 15%.",
      "flow_efficiency = active_work_hours / (active_work_hours + queue_hours) × 100, using Active vs passive elapsed wall-clock status dwell time for issues created in that calendar month.",
      "focus_health = 50 + 50 × roadmap_focus, where roadmap_focus = roadmap_hours / (roadmap_hours + continuous_improvement_hours).",
      "interruption_health = (1 − time_interruption_ratio) × 100 from Real interruption ratio, with roadmap_focus × 100 as fallback when real-interruption evidence is unavailable.",
      "execution_predictability = throughput predictability × 100 per calendar month, where predictability = 1 − weekly throughput stddev / average weekly throughput.",
      "work_shape_health = 100 − weighted average feature risk score, weighted by allocated feature hours for the team/month.",
      "Missing components lower confidence; a team/month is not scored when less than half of the configured component weight is available.",
      "Workforce Strength is shown as non-scored context: Dev/QA planned HR Works hours and Jira booked-hour utilization.",
    ],
    presented: [
      "Score cards by team, Workforce Strength context, monthly trend chart, latest component bars, raw component metrics, confidence, biggest drag, and second drag.",
    ],
    limitations: [
      "Flow efficiency and throughput predictability are range-level signals repeated across months.",
      "Flow-efficiency active/queue fields are elapsed calendar time from Jira status intervals, not booked work or HR Works capacity.",
      "Real interruption has richer evidence for Team Tantrum, Team World, and Cosmic Coders; other teams fall back to roadmap-focus interruption where needed.",
      ALLOCATION_REBUILD,
    ],
  },

  "team-comparison": {
    id: "team-comparison",
    title: "Team comparison",
    overview:
      "Six-month comparison of the focused engineering teams using the Engineering Health Index components and trend deltas.",
    dataSources: ["Engineering health index"],
    included: [
      EXCLUDED_PROJECTS,
      "Uses the same weighted health model, confidence rules, and focused team set as the Engineering Health Index.",
      "The comparison highlights latest score, six-month delta, best dimension, and worst dimension per team.",
      "Workforce Strength is capacity context only: Dev/QA planned HR Works hours compared with direct Jira booked hours.",
    ],
    presented: [
      "Score cards, Workforce Strength context, health trend, latest component breakdown, six-month comparison table, and raw component metrics.",
    ],
    limitations: [
      "Interpret trend direction together with confidence and raw metrics; single-month changes can reflect missing component coverage.",
    ],
  },

  "customer-effort": {
    id: "customer-effort",
    title: "Customer effort",
    overview: "Allocated hours attributed to customers listed on linked issues via Jira customfield_10123.",
    dataSources: ["monthly_allocated_effort", "jira_issue_detail.customers"],
    included: [
      EXCLUDED_PROJECTS,
      ALLOCATED_TIME_NOTE,
      ALLOCATION_OVERVIEW,
      "Default view uses the last twelve months.",
      "Issues with no customer field are counted as unattributed and excluded from ranking.",
      "Hours split equally when multiple customers are listed on one issue.",
    ],
    presented: [
      "Summary metrics, customer ranking chart, monthly/yearly trend, and topic breakdown table (feature, bugfix, support, improvement, other).",
    ],
    limitations: [
      ALLOCATION_REBUILD,
      "Customer field completeness drives accuracy; equal split is not billing truth.",
    ],
  },

  "dora-overview": {
    id: "dora-overview",
    title: "DORA overview",
    overview: "Summary cards for deployment frequency, lead time, change failure rate, and MTTR Alpha — same metrics as the home dashboard.",
    dataSources: ["Metric snapshots", "GitLab releases", "merge requests", "production bugs"],
    included: [
      NO_TIME_ALLOCATION_NOTE,
      "Uses the same /metrics/current pipeline as the home dashboard.",
      "Respects the selected period (30d, quarterly, yearly) from the page toolbar.",
    ],
    presented: ["Four KPI cards with DORA level badges, trend percentage, and modal drilldown."],
    limitations: ["Combined trend chart and contextual drilldowns live on each metric-specific DORA page."],
  },

  "dora-deployment-frequency": {
    id: "dora-deployment-frequency",
    title: "Deployment frequency",
    overview: "Customer-release cadence trend with deployment swimlane timeline.",
    dataSources: ["Metric snapshots", "GitLab release timeline"],
    included: [
      NO_TIME_ALLOCATION_NOTE,
      "Weekly deploy rate from customer-release tags after repository/version filters.",
    ],
    presented: ["KPI card, area trend chart, release swimlane by version lane."],
    limitations: ["Release volume can be low in short windows; read together with lead time and CFR."],
  },

  "dora-lead-time": {
    id: "dora-lead-time",
    title: "Median lead time",
    overview: "Median lead time with dev/review vs release-wait breakdown and release drilldown.",
    dataSources: ["Metric snapshots", "merge requests", "GitLab releases"],
    included: [
      NO_TIME_ALLOCATION_NOTE,
      "Release-only MR exclusions from admin config apply.",
      "Optional branch/stream disaggregation on the trend chart.",
    ],
    presented: ["KPI card, stacked or disaggregated trend, per-release drilldown panel."],
    limitations: ["Medians can mask outliers; use release drilldown for individual MR context."],
  },

  "dora-change-failure-rate": {
    id: "dora-change-failure-rate",
    title: "Change failure rate",
    overview: "Share of customer releases linked to production bugs, with failed-release drilldown.",
    dataSources: ["Metric snapshots", "production bugs", "bug-release linkage"],
    included: [NO_TIME_ALLOCATION_NOTE, "Healthy production bug scope per configuration."],
    presented: ["KPI card, CFR trend, failed-release and linked-issue drilldown."],
    limitations: ["Small release counts make percentages volatile."],
  },

  "dora-mttr-alpha": {
    id: "dora-mttr-alpha",
    title: "MTTR Alpha",
    overview: "Median recovery time from bug creation to first fix release, with incident drilldown.",
    dataSources: ["Metric snapshots", "production bugs", "GitLab releases"],
    included: [NO_TIME_ALLOCATION_NOTE, "Critical/Blocker scope per configuration."],
    presented: ["KPI card, recovery trend, time-to-fix spread, incident drilldown."],
    limitations: ["Depends on accurate bug-to-fix-release mapping."],
  },

  "data-quality": {
    id: "data-quality",
    title: "Data quality",
    overview: "Automated checks that reduce trust in analytics when they fail.",
    dataSources: ["Worklogs", "role assignments", "topic base", "feature membership", "issue detail"],
    included: [
      EXCLUDED_PROJECTS,
      NO_TIME_ALLOCATION_NOTE,
      "Examples: worklogs without user, no role assignments, unclassified direct hours, issues missing team, features without membership coverage.",
      "Severity and affected_hours where applicable.",
    ],
    presented: ["Table of checks: label, count, severity, affected hours."],
    limitations: ["Passing here does not guarantee business correctness of custom fields."],
  },
};

const PATH_TO_METHODOLOGY_ID: Record<string, string> = {
  "/analytics/investment/categories": "investment-categories",
  "/analytics/investment/ranking": "investment-ranking",
  "/analytics/investment/by-theme": "investment-by-theme",
  "/analytics/features": "feature-worklog-hours",
  "/analytics/features/without-feature": "issues-without-feature",
  "/analytics/features/risk": "feature-risk",
  "/analytics/flow/lifecycle": "lifecycle",
  "/analytics/flow/promised-vs-actual": "promised-vs-actual",
  "/analytics/flow/idea-aging": "idea-aging",
  "/analytics/flow/size-vs-speed": "size-vs-speed",
  "/analytics/flow/roadmap-reliability": "roadmap-reliability",
  "/analytics/bottlenecks/status-waiting": "status-waiting",
  "/analytics/bottlenecks/active-vs-passive": "active-vs-passive",
  "/analytics/bottlenecks/active-vs-passive-trend": "active-vs-passive-trend",
  "/analytics/bottlenecks/thrashing": "thrashing",
  "/analytics/teams/heatmap": "heatmap",
  "/analytics/teams/planned-vs-unplanned": "planned-vs-unplanned",
  "/analytics/teams/availability-vs-booked": "availability-vs-booked",
  "/analytics/teams/capacity-forecast": "capacity-forecast",
  "/analytics/teams/real-interruption-ratio": "real-interruption-ratio",
  "/analytics/teams/throughput": "throughput",
  "/analytics/teams/bus-factor": "bus-factor",
  "/analytics/teams/health": "engineering-health",
  "/analytics/teams/comparison": "team-comparison",
  "/analytics/customers/effort": "customer-effort",
  "/analytics/dora": "dora-overview",
  "/analytics/dora/deployment-frequency": "dora-deployment-frequency",
  "/analytics/dora/lead-time": "dora-lead-time",
  "/analytics/dora/change-failure-rate": "dora-change-failure-rate",
  "/analytics/dora/mttr-alpha": "dora-mttr-alpha",
  "/analytics/data-quality": "data-quality",
};

const FEATURE_SUBPATHS = new Set(["cost", "without-feature", "risk"]);

export function getMethodologyByPath(pathname: string): ReportMethodology | undefined {
  const normalized = pathname.replace(/\/$/, "") || "/";
  const direct = PATH_TO_METHODOLOGY_ID[normalized];
  if (direct) return REPORT_METHODOLOGY[direct];

  const featureDetail = /^\/analytics\/features\/([^/]+)$/.exec(normalized);
  if (featureDetail && !FEATURE_SUBPATHS.has(featureDetail[1])) {
    return REPORT_METHODOLOGY["feature-detail"];
  }

  return undefined;
}

export function getMethodologyById(id: string): ReportMethodology | undefined {
  return REPORT_METHODOLOGY[id];
}
