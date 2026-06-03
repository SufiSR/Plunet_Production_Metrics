import { appendAnalyticsEmbedStyle, isAnalyticsEmbedStyle } from "@/lib/analytics-embed-style";

describe("isAnalyticsEmbedStyle", () => {
  it("returns true when style=embed", () => {
    expect(isAnalyticsEmbedStyle(new URLSearchParams("style=embed"))).toBe(true);
  });

  it("returns false for other styles", () => {
    expect(isAnalyticsEmbedStyle(new URLSearchParams("style=full"))).toBe(false);
    expect(isAnalyticsEmbedStyle(new URLSearchParams(""))).toBe(false);
  });
});

describe("appendAnalyticsEmbedStyle", () => {
  it("appends style=embed to a path", () => {
    expect(appendAnalyticsEmbedStyle("/analytics/investment/categories")).toBe(
      "/analytics/investment/categories?style=embed",
    );
  });

  it("merges with existing query params", () => {
    expect(appendAnalyticsEmbedStyle("/analytics/teams/heatmap?team=alpha")).toBe(
      "/analytics/teams/heatmap?team=alpha&style=embed",
    );
  });

  it("returns href unchanged when embed is disabled", () => {
    expect(appendAnalyticsEmbedStyle("/analytics", false)).toBe("/analytics");
  });
});
