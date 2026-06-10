export type AdminNewNavItem = {
  href: string;
  icon: string;
  label: string;
};

export type AdminNewNavGroup = {
  id: string;
  label: string;
  items: AdminNewNavItem[];
};

export const ADMIN_NEW_BASE = "/admin";

export const ADMIN_NEW_NAV_GROUPS: AdminNewNavGroup[] = [
  {
    id: "home",
    label: "Home",
    items: [
      { href: "/admin", icon: "dashboard", label: "Overview" },
      { href: "/admin/schedulers", icon: "schedule", label: "Schedulers" },
    ],
  },
  {
    id: "connections",
    label: "Connections",
    items: [{ href: "/admin/secrets", icon: "key", label: "Secrets & credentials" }],
  },
  {
    id: "ingestion",
    label: "Ingestion",
    items: [
      { href: "/admin/ingestion/dora", icon: "sync", label: "DORA nightly pipeline" },
      { href: "/admin/ingestion/hrworks", icon: "calendar_month", label: "HRWorks capacity" },
      { href: "/admin/ingestion/jira-analytics", icon: "analytics", label: "Jira Analytics warehouse" },
    ],
  },
  {
    id: "jira-analytics",
    label: "Jira Analytics setup",
    items: [
      { href: "/admin/jira-analytics/assignments", icon: "badge", label: "User & team assignments" },
      { href: "/admin/people-data-users", icon: "lock_person", label: "People-data users" },
      { href: "/admin/jira-analytics/feature-families", icon: "account_tree", label: "Feature families" },
    ],
  },
  {
    id: "dora-diagnostics",
    label: "DORA diagnostics",
    items: [
      { href: "/admin/dora/linkage-health", icon: "monitor_heart", label: "Linkage data health" },
      { href: "/admin/dora/raw-tables", icon: "table_view", label: "Raw data explorer" },
    ],
  },
];
