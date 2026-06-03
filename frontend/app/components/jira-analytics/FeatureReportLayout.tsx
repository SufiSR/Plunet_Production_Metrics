"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { JIRA_ANALYTICS_SECTIONS } from "@/lib/jira-analytics-nav";

export type FeatureReportId = "hours" | "families" | "without-feature" | "risk";

interface FeatureReportLayoutProps {
  activeReport: FeatureReportId;
  title: string;
  description: string;
  eyebrow?: string;
  controls?: ReactNode;
  metrics?: ReactNode;
  children: ReactNode;
}

const FEATURE_REPORTS: Record<FeatureReportId, { href: string; label: string; detail: string }> = {
  hours: {
    href: "/analytics/features",
    label: "Feature hours",
    detail: "Feature and bucket worklog hours with drill-down.",
  },
  families: {
    href: "/analytics/features/families",
    label: "Feature families",
    detail: "Managed feature-family rollups with feature-level drill-down.",
  },
  "without-feature": {
    href: "/analytics/features/without-feature",
    label: "Without feature",
    detail: "Work consuming capacity outside PMGT feature families.",
  },
  risk: {
    href: "/analytics/features/risk",
    label: "Delivery risk",
    detail: "Feature size, duration, and workflow risk signals.",
  },
};

const POPULATION_STEPS = [
  "Jira worklogs provide the hour base by issue, contributor, role, team, and period.",
  "PMGT hierarchy fields link issues back to feature families where possible.",
  "Issues outside those families are grouped into explicit Other and without-feature buckets, including allocated overhead where applicable.",
  "Risk reports combine allocated effort with lifecycle and workflow signals to highlight follow-up candidates.",
];

export function FeatureReportLayout({
  activeReport,
  title,
  description,
  eyebrow = "Feature costs",
  controls,
  metrics,
  children,
}: FeatureReportLayoutProps) {
  const section = JIRA_ANALYTICS_SECTIONS.find((item) => item.id === "features");

  return (
    <div className="space-y-6">
      <section className="analytics-hero-panel p-6 md:p-8">
        <div className="analytics-hero-accent analytics-hero-accent--features" aria-hidden />
        <div className="relative grid gap-8 xl:grid-cols-[minmax(0,1fr)_28rem]">
          <div className="space-y-5">
            <span className="inline-flex rounded-full border border-outline-variant/35 bg-surface-container-low px-3 py-1 text-xs font-label uppercase tracking-[0.22em] text-on-surface-variant">
              {eyebrow}
            </span>
            <div className="space-y-3">
              <h2 className="max-w-4xl text-4xl font-editorial font-bold tracking-tight text-on-surface md:text-5xl">
                {title}
              </h2>
              <p className="max-w-3xl text-base leading-7 text-on-surface-variant">{description}</p>
            </div>
            {metrics ? <div className="grid gap-3 sm:grid-cols-3">{metrics}</div> : null}
          </div>

          <div className="analytics-hero-sidebar p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-label uppercase tracking-[0.18em] text-primary">Jump quickly</p>
                <h3 className="mt-1 text-lg font-editorial font-bold text-on-surface">Feature reports</h3>
              </div>
              <span className="rounded-full border border-outline-variant/30 bg-surface-container-lowest px-2.5 py-1 text-xs font-medium text-on-surface-variant">
                {section?.reports.length ?? 3}
              </span>
            </div>
            <nav className="space-y-2" aria-label="Feature reports">
              {(Object.keys(FEATURE_REPORTS) as FeatureReportId[]).map((id) => {
                const report = FEATURE_REPORTS[id];
                const active = id === activeReport;
                return (
                  <Link
                    key={id}
                    href={report.href}
                    className={`block rounded-2xl border p-3 transition ${
                      active
                        ? "border-primary/35 bg-primary/10 text-primary shadow-sm"
                        : "border-outline-variant/28 bg-surface-container-lowest/70 text-on-surface hover:border-primary/35 hover:bg-surface-container-lowest"
                    }`}
                  >
                    <span className="flex items-center justify-between gap-3">
                      <span className="font-semibold">{report.label}</span>
                      <span className="text-xs font-semibold">{active ? "Open" : "View"}</span>
                    </span>
                    <span className={`mt-1 block text-xs leading-5 ${active ? "text-primary/80" : "text-on-surface-variant"}`}>
                      {report.detail}
                    </span>
                  </Link>
                );
              })}
            </nav>
          </div>
        </div>
      </section>

      <div className="min-w-0 space-y-6">
        {controls}
        {children}
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_24rem]">
          <section className="analytics-section-panel rounded-[1.5rem] p-5 shadow-sm">
            <p className="text-xs font-label uppercase tracking-[0.18em] text-primary">Data lineage</p>
            <h3 className="mt-2 text-xl font-editorial font-bold text-on-surface">Feature-aware worklog data.</h3>
            <ol className="mt-4 space-y-3">
              {POPULATION_STEPS.map((step, index) => (
                <li key={step} className="grid grid-cols-[2rem_1fr] gap-3 text-sm leading-6 text-on-surface-variant">
                  <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-xs font-bold tabular-nums text-primary">
                    {index + 1}
                  </span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
          </section>

          <section className="elevated-panel rounded-[1.5rem] p-5">
            <p className="text-xs font-label uppercase tracking-[0.18em] text-on-surface-variant">Reading tip</p>
            <p className="mt-2 text-sm leading-6 text-on-surface-variant">
              Start with feature hours for allocated cost, check without-feature work for hygiene gaps, then use risk to prioritize follow-up.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}

export function FeatureMetricCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <article className="elevated-panel rounded-2xl p-4">
      <p className="text-xs font-medium uppercase tracking-[0.16em] text-on-surface-variant">{label}</p>
      <p className="mt-2 text-2xl font-editorial font-bold text-on-surface">{value}</p>
      <p className="mt-1 text-xs leading-5 text-on-surface-variant">{detail}</p>
    </article>
  );
}

