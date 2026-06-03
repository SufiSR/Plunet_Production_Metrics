import { MAIN_DELIVERY_WORKFLOW_ORDER } from "@/lib/jira-analytics-workflows";

/** Sort workflow sections so Plunet Cloud appears before Standard Plunet. */
export function sortMainDeliveryWorkflowSections<T extends { catalog_key: string }>(sections: T[]): T[] {
  const orderIndex = new Map<string, number>(MAIN_DELIVERY_WORKFLOW_ORDER.map((key, index) => [key, index]));
  return [...sections].sort((a, b) => {
    const left = orderIndex.get(a.catalog_key) ?? MAIN_DELIVERY_WORKFLOW_ORDER.length;
    const right = orderIndex.get(b.catalog_key) ?? MAIN_DELIVERY_WORKFLOW_ORDER.length;
    if (left !== right) return left - right;
    return a.catalog_key.localeCompare(b.catalog_key);
  });
}
