import {
  downloadFeatureInvestmentAuditExport,
  fetchFeatureInvestmentAudit,
  fetchFeatureInvestmentAuditIssues,
} from "@/lib/jira-analytics-api";
import {
  lastSixMonths,
  lastTwoYearsToDate,
  lastYear,
  thisYearToDate,
} from "@/lib/jira-analytics-dates";

describe("feature investment audit API client", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("builds report and drilldown query parameters", async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ filters: {}, summary: {}, table: [], series: [] }),
    });
    global.fetch = fetchMock;

    await fetchFeatureInvestmentAudit({
      from: "2026-01-01",
      to: "2026-06-01",
      team: "Team Tantrum",
      familyId: "42",
      featureKey: "PMGT-1",
    });
    await fetchFeatureInvestmentAuditIssues({
      from: "2026-05-01",
      to: "2026-05-01",
      featureKey: "PMGT-1",
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/jira-analytics/features/investment-audit?from=2026-01-01&to=2026-06-01&team=Team+Tantrum&family_id=42&feature_key=PMGT-1",
      expect.objectContaining({ cache: "no-store" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/jira-analytics/features/investment-audit/drilldown/issues?from=2026-05-01&to=2026-05-01&feature_key=PMGT-1",
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("builds investment audit export query parameters", async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      blob: async () => new Blob(["xlsx"]),
    });
    global.fetch = fetchMock;

    await downloadFeatureInvestmentAuditExport({
      from: "2026-01-01",
      to: "2026-06-01",
      familyId: "42",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/jira-analytics/features/investment-audit/export.xlsx?from=2026-01-01&to=2026-06-01&family_id=42",
      expect.objectContaining({
        headers: {
          Accept: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        },
      }),
    );
  });
});

describe("normalized feature cost date presets", () => {
  beforeEach(() => {
    jest.useFakeTimers().setSystemTime(new Date("2026-06-01T10:00:00Z").getTime());
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("builds calendar-year presets", () => {
    expect(lastSixMonths()).toEqual({ from: "2025-12-01", to: "2026-05-31" });
    expect(thisYearToDate()).toEqual({ from: "2026-01-01", to: "2026-05-31" });
    expect(lastYear()).toEqual({ from: "2025-01-01", to: "2025-12-31" });
    expect(lastTwoYearsToDate()).toEqual({ from: "2025-01-01", to: "2026-05-31" });
  });
});
