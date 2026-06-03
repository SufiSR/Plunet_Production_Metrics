import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import AdminRawTablesPage from "@/app/admin_legacy/raw-tables/page";

const pushMock = jest.fn();
const meMock = jest.fn();
const useAdminRawTableRowsMock = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

jest.mock("@/lib/admin-api-client", () => ({
  adminApiClient: {
    me: (...args: unknown[]) => meMock(...args),
  },
}));

jest.mock("@/lib/hooks", () => ({
  useAdminRawTableRows: (...args: unknown[]) => useAdminRawTableRowsMock(...args),
}));

describe("AdminRawTablesPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    meMock.mockResolvedValue({ role: "admin" });
    useAdminRawTableRowsMock.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        table: "repository",
        columns: [
          { key: "name", label: "Name", sortable: true },
          { key: "path", label: "Path", sortable: true },
        ],
        rows: [{ name: "Platform", path: "group/platform" }],
        pagination: {
          page: 0,
          size: 20,
          total_elements: 1,
          total_pages: 1,
          has_next: false,
          has_previous: false,
        },
      },
    });
  });

  it("renders table rows", async () => {
    render(<AdminRawTablesPage />);
    await waitFor(() => expect(screen.getByText("Raw Data")).toBeTruthy());
    expect(screen.getByText("Platform")).toBeTruthy();
    expect(screen.getByText("group/platform")).toBeTruthy();
  });

  it("supports sorting click", async () => {
    render(<AdminRawTablesPage />);
    await waitFor(() => expect(screen.getByText("Raw Data")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "Name" }));
    expect(useAdminRawTableRowsMock).toHaveBeenCalled();
  });

  it("redirects non-admin users", async () => {
    meMock.mockResolvedValue({ role: null });
    render(<AdminRawTablesPage />);
    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/admin/login"));
  });
});
