import "@testing-library/jest-dom";
import React from "react";
import { render, screen } from "@testing-library/react";
import { useSearchParams } from "next/navigation";
import { AnalyticsEmbedStyleProvider } from "@/app/components/jira-analytics/AnalyticsEmbedStyleProvider";
import { JiraAnalyticsShell } from "@/app/components/jira-analytics/JiraAnalyticsShell";

jest.mock("next/link", () => ({
  __esModule: true,
  default: ({ children, href }: { children: React.ReactNode; href: string }) => <a href={href}>{children}</a>,
}));

jest.mock("next/navigation", () => ({
  usePathname: () => "/analytics/investment/categories",
  useSearchParams: jest.fn(),
}));

jest.mock("@/app/components/SiteFooter", () => ({
  SiteFooter: () => <footer data-testid="site-footer" />,
}));

jest.mock("@/app/components/ui/ThemeToggle", () => ({
  ThemeToggle: () => <button type="button">Theme</button>,
}));

jest.mock("@/app/components/jira-analytics/ReportMethodologyPanel", () => ({
  ReportMethodologyPanel: () => null,
}));

const useSearchParamsMock = useSearchParams as jest.MockedFunction<typeof useSearchParams>;

function renderShell(search = "") {
  useSearchParamsMock.mockReturnValue(new URLSearchParams(search) as ReturnType<typeof useSearchParams>);
  return render(
    <AnalyticsEmbedStyleProvider>
      <JiraAnalyticsShell title="Investment categories">
        <p>Report body</p>
      </JiraAnalyticsShell>
    </AnalyticsEmbedStyleProvider>,
  );
}

describe("JiraAnalyticsShell", () => {
  it("shows top bar and section navigation by default", () => {
    renderShell();
    expect(screen.getByText("Plunet Metrics - Production")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Analytics sections" })).toBeInTheDocument();
    expect(screen.getByTestId("site-footer")).toBeInTheDocument();
    expect(screen.getByText("Report body")).toBeInTheDocument();
  });

  it("hides chrome when style=embed", () => {
    const { container } = renderShell("style=embed");
    expect(screen.queryByText("Plunet Metrics - Production")).not.toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Analytics sections" })).not.toBeInTheDocument();
    expect(screen.queryByTestId("site-footer")).not.toBeInTheDocument();
    expect(container.querySelector("[data-analytics-embed]")).toBeInTheDocument();
    expect(screen.getByText("Report body")).toBeInTheDocument();
  });
});
