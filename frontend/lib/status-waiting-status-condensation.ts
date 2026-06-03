import {
  condensePlunetCloudStatus,
  orderPlunetCloudStatuses,
} from "@/lib/plunet-cloud-status-condensation";
import {
  condenseStandardPlunetStatus,
  orderStandardPlunetStatuses,
} from "@/lib/standard-plunet-status-condensation";

export function condenseStatusWaitingStatus(catalogKey: string | undefined, status: string): string {
  if (catalogKey === "plunet_cloud") return condensePlunetCloudStatus(status);
  if (catalogKey === "standard_plunet") return condenseStandardPlunetStatus(status);
  return status;
}

export function orderStatusWaitingStatuses(
  catalogKey: string | undefined,
  statuses: Iterable<string>,
): string[] | null {
  if (catalogKey === "plunet_cloud") return orderPlunetCloudStatuses(statuses);
  if (catalogKey === "standard_plunet") return orderStandardPlunetStatuses(statuses);
  return null;
}

export function hasStatusWaitingCondensation(catalogKey: string | undefined): boolean {
  return catalogKey === "plunet_cloud" || catalogKey === "standard_plunet";
}
