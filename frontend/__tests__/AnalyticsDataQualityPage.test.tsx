import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import DataQualityPage from "@/app/analytics/data-quality/page";

const fetchDataQualityMock = jest.fn();
const fetchDataQualityUserDrilldownMock = jest.fn();
const ignoreDataQualityUserMock = jest.fn();
const unignoreDataQualityUserMock = jest.fn();
const rebuildAllocationMock = jest.fn();
const fetchAllocationRebuildStatusMock = jest.fn();

jest.mock("next/link", () => {
  return ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  );
});

jest.mock("@/app/components/jira-analytics/JiraAnalyticsShell", () => ({
  JiraAnalyticsShell: ({ children, title }: { children: React.ReactNode; title: string }) => (
    <main>
      <h1>{title}</h1>
      {children}
    </main>
  ),
}));

jest.mock("@/lib/jira-analytics-api", () => ({
  fetchDataQuality: (...args: unknown[]) => fetchDataQualityMock(...args),
  fetchDataQualityUserDrilldown: (...args: unknown[]) => fetchDataQualityUserDrilldownMock(...args),
  ignoreDataQualityUser: (...args: unknown[]) => ignoreDataQualityUserMock(...args),
  unignoreDataQualityUser: (...args: unknown[]) => unignoreDataQualityUserMock(...args),
  rebuildAllocation: (...args: unknown[]) => rebuildAllocationMock(...args),
  fetchAllocationRebuildStatus: (...args: unknown[]) => fetchAllocationRebuildStatusMock(...args),
}));

const dataQualityResponse = {
  filters: {},
  summary: {},
  data_quality: {
    warnings: [
      {
        check_id: "worklog_users_without_assignment",
        label: "Worklog users without active role assignment",
        count: 1,
        ignored_count: 0,
        severity: "high",
      },
    ],
  },
};

const activeDrilldown = {
  check_id: "worklog_users_without_assignment",
  label: "Worklog users without active role assignment",
  active_count: 1,
  ignored_count: 0,
  users: [
    {
      user_id: 7,
      account_id: "acc-7",
      display_name: "DQ User",
      email_address: "dq.user@example.com",
      jira_active: true,
      reporting_excluded: false,
      role_name: null,
      team_name: null,
      worklog_count: 3,
      total_hours: 5,
      first_worklog_at: "2026-05-01T00:00:00Z",
      last_worklog_at: "2026-05-03T00:00:00Z",
      ignored: false,
      ignore_reason: null,
      can_ignore: true,
    },
  ],
};

describe("Analytics DataQualityPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    fetchDataQualityMock.mockResolvedValue(dataQualityResponse);
    fetchDataQualityUserDrilldownMock.mockResolvedValue(activeDrilldown);
    ignoreDataQualityUserMock.mockResolvedValue({
      ...activeDrilldown,
      active_count: 0,
      ignored_count: 1,
      users: [{ ...activeDrilldown.users[0], ignored: true }],
    });
  });

  it("shows user drilldowns and ignores a user in health", async () => {
    render(<DataQualityPage />);

    await waitFor(() => expect(screen.getByText("Worklog users without active role assignment")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "View users" }));

    await waitFor(() => expect(screen.getByText("DQ User")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "Ignore in health" }));

    await waitFor(() =>
      expect(ignoreDataQualityUserMock).toHaveBeenCalledWith("worklog_users_without_assignment", 7),
    );
    expect(fetchDataQualityMock).toHaveBeenCalledTimes(2);
    expect(screen.getAllByText("Ignored").length).toBeGreaterThan(0);
  });
});
