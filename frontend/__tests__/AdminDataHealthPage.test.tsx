import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import AdminDataHealthPage from "@/app/admin_legacy/data-health/page";

const pushMock = jest.fn();
const meMock = jest.fn();
const useAdminDataHealthMock = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

jest.mock("next/link", () => {
  return ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  );
});

jest.mock("@/lib/admin-api-client", () => ({
  adminApiClient: {
    me: (...args: unknown[]) => meMock(...args),
  },
}));

jest.mock("@/lib/hooks", () => ({
  useAdminDataHealth: (...args: unknown[]) => useAdminDataHealthMock(...args),
}));

describe("AdminDataHealthPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    meMock.mockResolvedValue({ role: "admin" });
  });

  it("renders summary and tables when data is loaded", async () => {
    useAdminDataHealthMock.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        generated_at: "2026-04-22T10:00:00Z",
        summary: {
          total_bugs: 10,
          healthy_bugs: 8,
          healthy_bugs_pct: 80,
          unmatched_mr_count: 2,
          version_mismatch_count: 1,
        },
        jira_health_breakdown: [
          { healthy: true, healthmemo: "post-production", count: 8, share_pct: 80 },
          { healthy: false, healthmemo: "missing versions", count: 2, share_pct: 20 },
        ],
        unmatched_merge_requests: [
          {
            repository_id: 1,
            repository_path: "group/repo",
            gitlab_mr_id: 42,
            title: "MR",
            merged_at: "2026-04-20T00:00:00Z",
            jira_key: "DEVOPS-1",
            reason: "missing_jira_key",
            gitlab_merge_request_url: "https://gitlab.example.com/group/repo/-/merge_requests/42",
            jira_browse_url: "https://plunet.atlassian.net/browse/DEVOPS-1",
          },
        ],
        unmatched_merge_requests_pagination: {
          page: 0,
          size: 20,
          total_elements: 1,
          total_pages: 1,
          has_next: false,
          has_previous: false,
        },
        version_mismatches: [
          {
            jira_key: "DEVOPS-2",
            summary: "Mismatch",
            healthmemo: "memo",
            affects_versions: ["99.0.0"],
            fix_versions: [],
            unmatched_versions: ["99.0.0"],
            reason: "jira_versions_not_found_in_release_tags",
            jira_browse_url: "https://plunet.atlassian.net/browse/DEVOPS-2",
          },
        ],
        version_mismatches_pagination: {
          page: 0,
          size: 20,
          total_elements: 1,
          total_pages: 1,
          has_next: false,
          has_previous: false,
        },
      },
    });

    render(<AdminDataHealthPage />);

    await waitFor(() => expect(screen.getByText("Data Health")).toBeTruthy());
    expect(screen.getByText("Healthy Bugs")).toBeTruthy();
    expect(screen.getByText("8 / 10 issues")).toBeTruthy();
    expect(screen.getByText("Unmatched Merge Requests")).toBeTruthy();
    expect(screen.getAllByText("Version Mismatches").length).toBeGreaterThan(0);
    expect(screen.getByText("DEVOPS-2")).toBeTruthy();
  });

  it("renders load failure state", async () => {
    useAdminDataHealthMock.mockReturnValue({
      isLoading: false,
      error: new Error("boom"),
      data: null,
    });

    render(<AdminDataHealthPage />);

    await waitFor(() => expect(screen.getByText("boom")).toBeTruthy());
  });

  it("redirects non-admin users to login", async () => {
    meMock.mockResolvedValue({ role: null });
    useAdminDataHealthMock.mockReturnValue({
      isLoading: true,
      error: null,
      data: null,
    });

    render(<AdminDataHealthPage />);

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/admin/login"));
  });
});
