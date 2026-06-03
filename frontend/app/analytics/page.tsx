"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { JiraAnalyticsShell } from "@/app/components/jira-analytics/JiraAnalyticsShell";
import { fetchAnalyticsReport, fetchDataQuality, reportPaths } from "@/lib/jira-analytics-api";
import { JIRA_ANALYTICS_SECTIONS, type JiraAnalyticsReportLink, type JiraAnalyticsSectionId } from "@/lib/jira-analytics-nav";
import type { AnalyticsReportResponse, DataQualityResponse } from "@/types/jira-analytics";

type SignalState = "loading" | "ready" | "error";

interface OverviewSignals {
  state: SignalState;
  averageHealth: number | null;
  worstDrag: string | null;
  dataCoverage: number | null;
  dataWarnings: number | null;
  scoredMonths: string | null;
}

interface DecisionTile {
  id: JiraAnalyticsSectionId;
  eyebrow: string;
  title: string;
  description: string;
  href: string;
  action: string;
  metric: string;
}

const FALLBACK_SIGNALS: OverviewSignals = {
  state: "loading",
  averageHealth: null,
  worstDrag: null,
  dataCoverage: null,
  dataWarnings: null,
  scoredMonths: null,
};

const DECISION_TILES: DecisionTile[] = [
  {
    id: "teams",
    eyebrow: "Executive pulse",
    title: "Start with engineering health",
    description: "See the latest team score, confidence, capacity context, and the delivery dimension dragging each team down.",
    href: "/analytics/teams/health",
    action: "Open health index",
    metric: "Health, confidence, drag",
  },
  {
    id: "bottlenecks",
    eyebrow: "Flow pressure",
    title: "Find where work is waiting",
    description: "Separate active work from queue time and jump straight to the workflow statuses that absorb delivery time.",
    href: "/analytics/bottlenecks/status-waiting",
    action: "Inspect bottlenecks",
    metric: "Queue time, passive time",
  },
  {
    id: "portfolio",
    eyebrow: "Investment lens",
    title: "Explain where capacity went",
    description: "Move from portfolio categories to themes and feature ranking when leadership asks what consumed the month.",
    href: "/analytics/investment/categories",
    action: "Explore investment",
    metric: "Capacity by category",
  },
  {
    id: "quality",
    eyebrow: "Trust gate",
    title: "Check if the story is reliable",
    description: "Review missing mappings, unclassified hours, and other warnings before making decisions from the reports.",
    href: "/analytics/data-quality",
    action: "Review data quality",
    metric: "Warnings, coverage",
  },
];

const RECOMMENDED_REPORTS = [
  "/analytics/teams/health",
  "/analytics/bottlenecks/status-waiting",
  "/analytics/teams/heatmap",
  "/analytics/features/risk",
  "/analytics/data-quality",
];

const SECTION_INTROS: Record<JiraAnalyticsSectionId, string> = {
  portfolio: "Budget conversations and capacity allocation.",
  features: "Feature cost, orphan work, and delivery risk.",
  flow: "Idea age, lifecycle duration, and roadmap reliability.",
  bottlenecks: "Queue time, waiting states, and workflow churn.",
  teams: "Focus, interruptions, utilization, health, and throughput.",
  customers: "Customer-specific demand and disproportionate effort.",
  dora: "DORA deployment, lead time, failure rate, and recovery metrics.",
  quality: "Data confidence before operational decisions.",
};

export default function JiraAnalyticsOverviewPage() {
  const [signals, setSignals] = useState<OverviewSignals>(FALLBACK_SIGNALS);

  useEffect(() => {
    let cancelled = false;

    async function loadSignals() {
      setSignals((current) => ({ ...current, state: "loading" }));
      try {
        const [health, quality] = await Promise.all([
          fetchAnalyticsReport(reportPaths.engineeringHealth, {}),
          fetchDataQuality(),
        ]);
        if (cancelled) return;
        setSignals(signalsFromResponses(health, quality));
      } catch {
        if (cancelled) return;
        setSignals({ ...FALLBACK_SIGNALS, state: "error" });
      }
    }

    void loadSignals();
    return () => {
      cancelled = true;
    };
  }, []);

  const reportsByHref = useMemo(() => {
    const entries = JIRA_ANALYTICS_SECTIONS.flatMap((section) => section.reports.map((report) => [report.href, report] as const));
    return new Map(entries);
  }, []);

  const recommendedReports = RECOMMENDED_REPORTS.flatMap((href) => {
    const report = reportsByHref.get(href);
    return report ? [report] : [];
  });

  return (
    <JiraAnalyticsShell title="Jira Analytics" description="" hidePageHeader>
      <div className="space-y-8">
        <section className="analytics-hero-panel rounded-[1.5rem] p-6 md:p-8">
          <div className="analytics-hero-accent analytics-hero-accent--overview" aria-hidden />
          <div className="relative grid gap-8 xl:grid-cols-[1.2fr_0.8fr]">
            <div className="max-w-4xl space-y-6">
              <div className="inline-flex rounded-full border border-outline-variant/35 bg-surface-container-low px-3 py-1 text-xs font-label uppercase tracking-[0.22em] text-on-surface-variant">
                Analytics command center
              </div>
              <div className="space-y-4">
                <h2 className="max-w-3xl text-4xl font-editorial font-bold tracking-tight text-on-surface md:text-6xl">
                  Know where delivery needs attention first.
                </h2>
                <p className="max-w-2xl text-base text-on-surface-variant md:text-lg">
                  Start with the operational pulse, then drill into investment, flow, bottlenecks, teams, DORA metrics, and the trustworthiness of the data.
                </p>
              </div>
              <div className="flex flex-wrap gap-3">
                <Link
                  href="/analytics/teams/health"
                  className="rounded-full bg-primary px-5 py-3 text-sm font-semibold text-on-primary transition hover:opacity-90"
                >
                  Start with health
                </Link>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
              <SignalCard
                label="Engineering health"
                value={formatScore(signals.averageHealth, signals.state)}
                detail={signals.worstDrag ? `Biggest drag: ${humanizeKey(signals.worstDrag)}` : "Weighted team delivery score"}
              />
              <SignalCard
                label="Data confidence"
                value={formatPercent(signals.dataCoverage, signals.state)}
                detail={signals.dataWarnings === null ? "Warnings load from data quality" : `${signals.dataWarnings} active data warning${signals.dataWarnings === 1 ? "" : "s"}`}
              />
              <SignalCard
                label="Scored coverage"
                value={signals.scoredMonths ?? fallbackValue(signals.state)}
                detail="Team-months with enough source data"
              />
            </div>
          </div>
        </section>

        <section className="grid gap-4 lg:grid-cols-4">
          {DECISION_TILES.map((tile) => (
            <DecisionTileCard key={tile.id} tile={tile} />
          ))}
        </section>

        <section className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
          <div className="analytics-section-panel rounded-[1.25rem] p-5">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-label uppercase tracking-[0.18em] text-primary">Recommended path</p>
                <h2 className="mt-1 text-xl font-editorial font-bold text-on-surface">The fastest route to signal</h2>
              </div>
              <span className="rounded-full border border-outline-variant/30 bg-surface-container-low px-3 py-1 text-xs font-medium text-on-surface-variant">5 reports</span>
            </div>
            <div className="space-y-3">
              {recommendedReports.map((report, index) => (
                <RecommendedReportLink key={report.href} report={report} index={index + 1} />
              ))}
            </div>
          </div>

          <div className="analytics-section-panel rounded-[1.25rem] p-5">
            <p className="text-xs font-label uppercase tracking-[0.18em] text-on-surface-variant">How to use this cockpit</p>
            <h2 className="mt-2 text-2xl font-editorial font-bold text-on-surface">Ask sharper questions before opening a table.</h2>
            <div className="mt-5 grid gap-3 md:grid-cols-2">
              <PromptCard question="Are we spending capacity on the right things?" href="/analytics/investment/categories" label="Investment categories" />
              <PromptCard question="Which teams need help right now?" href="/analytics/teams/health" label="Engineering health" />
              <PromptCard question="Where is work waiting instead of moving?" href="/analytics/bottlenecks/active-vs-passive" label="Active vs passive" />
              <PromptCard question="Can we trust this month of analytics?" href="/analytics/data-quality" label="Data quality" />
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div>
            <p className="text-xs font-label uppercase tracking-[0.18em] text-primary">Report library</p>
            <h2 className="mt-1 text-2xl font-editorial font-bold text-on-surface">Drill into the full analytics map</h2>
          </div>
          <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-4">
            {JIRA_ANALYTICS_SECTIONS.map((section) => (
              <ReportSectionCard key={section.id} sectionId={section.id} label={section.label} reports={section.reports} />
            ))}
          </div>
        </section>
      </div>
    </JiraAnalyticsShell>
  );
}

function SignalCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <article className="rounded-2xl border border-outline-variant/30 bg-surface-container-lowest p-4 shadow-sm dark:border-outline-variant/45 dark:bg-surface-container-high/90">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-on-surface-variant">{label}</p>
          <p className="mt-2 text-3xl font-editorial font-bold text-on-surface">{value}</p>
        </div>
        <span className="rounded-full border border-outline-variant/30 bg-surface-container-lowest px-2.5 py-1 text-xs font-semibold text-on-surface-variant">Live</span>
      </div>
      <p className="mt-3 text-xs text-on-surface-variant">{detail}</p>
    </article>
  );
}

function DecisionTileCard({ tile }: { tile: DecisionTile }) {
  return (
    <Link
      href={tile.href}
      className="analytics-section-panel group min-h-[18rem] rounded-[1.25rem] p-5 transition hover:-translate-y-0.5 hover:border-outline/50 hover:bg-surface-container hover:shadow-sm"
    >
      <div className="flex h-full flex-col justify-between gap-6">
        <div>
          <p className="text-xs font-label uppercase tracking-[0.18em] text-on-surface-variant">{tile.eyebrow}</p>
          <h2 className="mt-3 text-2xl font-editorial font-bold text-on-surface">{tile.title}</h2>
          <p className="mt-3 text-sm leading-6 text-on-surface-variant">{tile.description}</p>
        </div>
        <div>
          <p className="mb-3 rounded-full bg-surface-container-low/80 px-3 py-1 text-xs font-medium text-on-surface-variant">
            {tile.metric}
          </p>
          <span className="text-sm font-semibold text-primary group-hover:underline">{tile.action}</span>
        </div>
      </div>
    </Link>
  );
}

function RecommendedReportLink({ report, index }: { report: JiraAnalyticsReportLink; index: number }) {
  return (
    <Link
      href={report.href}
      className="grid grid-cols-[2.25rem_1fr_auto] items-center gap-3 rounded-xl border border-outline-variant/20 bg-surface-container-low p-3 transition hover:border-primary/40 hover:bg-surface-container"
    >
      <span className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/10 text-sm font-bold tabular-nums text-primary">
        {index}
      </span>
      <span>
        <span className="block text-sm font-semibold text-on-surface">{report.title}</span>
        <span className="mt-0.5 line-clamp-1 block text-xs text-on-surface-variant">{report.question}</span>
      </span>
      <span className="text-xs font-semibold text-primary">Open</span>
    </Link>
  );
}

function PromptCard({ question, href, label }: { question: string; href: string; label: string }) {
  return (
    <Link
      href={href}
      className="analytics-section-panel rounded-xl p-4 transition hover:border-outline/50 hover:bg-surface-container"
    >
      <p className="text-sm font-semibold text-on-surface">{question}</p>
      <p className="mt-3 text-xs text-on-surface-variant">{label}</p>
    </Link>
  );
}

function ReportSectionCard({
  sectionId,
  label,
  reports,
}: {
  sectionId: JiraAnalyticsSectionId;
  label: string;
  reports: JiraAnalyticsReportLink[];
}) {
  const primaryReport = reports[0];

  return (
    <article className="analytics-section-panel rounded-[1.25rem] p-5">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-editorial font-bold text-on-surface">{label}</h3>
          <p className="mt-1 text-xs leading-5 text-on-surface-variant">{SECTION_INTROS[sectionId]}</p>
        </div>
        <span className="rounded-full bg-surface-container-high px-2.5 py-1 text-xs font-medium text-on-surface-variant">
          {reports.length}
        </span>
      </div>
      {primaryReport ? (
        <Link
          href={primaryReport.href}
          className="mb-3 block rounded-xl bg-primary/10 p-3 text-sm font-semibold text-primary transition hover:bg-primary/15"
        >
          Start: {primaryReport.title}
        </Link>
      ) : null}
      <div className="space-y-2">
        {reports.slice(1).map((report) => (
          <Link
            key={report.href}
            href={report.href}
            className="block rounded-lg border border-outline-variant/28 px-3 py-2 text-sm text-on-surface transition hover:border-primary/40 hover:text-primary"
          >
            {report.title}
          </Link>
        ))}
      </div>
    </article>
  );
}

function signalsFromResponses(health: AnalyticsReportResponse, quality: DataQualityResponse): OverviewSignals {
  const scored = numberValue(health.summary.scored_team_months);
  const total = numberValue(health.summary.total_team_months);
  const activeWarnings = activeDataQualityWarningCount(quality);

  return {
    state: "ready",
    averageHealth: numberValue(health.summary.average_health_index),
    worstDrag: stringValue(health.summary.worst_drag),
    dataCoverage: dataConfidenceFromWarnings(activeWarnings),
    dataWarnings: activeWarnings,
    scoredMonths: scored !== null && total !== null ? `${scored} / ${total}` : null,
  };
}

function activeDataQualityWarningCount(quality: DataQualityResponse): number {
  return (quality.data_quality.warnings ?? []).filter((warning) => warning.count > 0).length;
}

function dataConfidenceFromWarnings(activeWarnings: number): number {
  return activeWarnings === 0 ? 1 : 0;
}

function numberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function fallbackValue(state: SignalState): string {
  if (state === "loading") return "Loading";
  if (state === "error") return "Offline";
  return "No data";
}

function formatScore(value: number | null, state: SignalState): string {
  return value === null ? fallbackValue(state) : value.toFixed(1);
}

function formatPercent(value: number | null, state: SignalState): string {
  return value === null ? fallbackValue(state) : `${(value * 100).toFixed(0)}%`;
}

function humanizeKey(value: string): string {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
