/** Main Jira delivery workflows used in active vs passive bottleneck reports. */
export const MAIN_DELIVERY_WORKFLOWS = [
  {
    catalogKey: "plunet_cloud",
    label: "Plunet Cloud Workflow",
    purpose:
      "Separate Jira workflow for Bug and Improvement issues (including sub-tasks), with its own status names and active/passive queue mapping.",
    issueTypes: "Bug, Improvement",
  },
  {
    catalogKey: "standard_plunet",
    label: "Standard Plunet Workflow",
    purpose:
      "Primary Jira workflow for Analysis, Epic, TechSupport, and Development Subtask issues. Status history is mapped to active work vs product, dev, and QA queue time for that issue family.",
    issueTypes: "Analysis, Epic, TechSupport, Development Subtask",
  },
] as const;

/** Display order for main delivery workflow sections in bottleneck reports. */
export const MAIN_DELIVERY_WORKFLOW_ORDER = MAIN_DELIVERY_WORKFLOWS.map((workflow) => workflow.catalogKey);

export const MAIN_DELIVERY_WORKFLOW_LABELS = MAIN_DELIVERY_WORKFLOWS.map((workflow) => workflow.label);
