"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { JIRA_ANALYTICS_SECTIONS } from "@/lib/jira-analytics-nav";

export type BottleneckReportId = "status-waiting" | "active-vs-passive" | "active-vs-passive-trend" | "thrashing";

interface WorkflowLineageItem {
  label: string;
  purpose: string;
  issueTypes: string;
}

interface BottleneckReportLayoutProps {
  activeReport: BottleneckReportId;
  title: string;
  description: string;
  eyebrow?: string;
  controls?: ReactNode;
  metrics?: ReactNode;
  readingTip: string;
  /** Optional extra lineage steps (e.g. main workflow definitions). */
  lineageSteps?: string[];
  mainWorkflowLineage?: WorkflowLineageItem[];
  children: ReactNode;
}

const BOTTLENECK_REPORTS: Record<BottleneckReportId, { href: string; label: string; detail: string }> = {
  "status-waiting": {
    href: "/analytics/bottlenecks/status-waiting",
    label: "Status waiting",
    detail: "Workflow statuses where issues spend the most time.",
  },
  "active-vs-passive": {
    href: "/analytics/bottlenecks/active-vs-passive",
    label: "Active vs passive",
    detail: "Active work compared with queue, review, QA, and blocked time.",
  },
  "active-vs-passive-trend": {
    href: "/analytics/bottlenecks/active-vs-passive-trend",
    label: "Quarterly trend",
    detail: "Whether passive workflow time is improving or degrading.",
  },
  thrashing: {
    href: "/analytics/bottlenecks/thrashing",
    label: "Workflow thrashing",
    detail: "Tickets with status churn, reopens, and ping-pong movement.",
  },
};

const POPULATION_STEPS = [
  "Jira workflow status history provides interval-level evidence for where issues wait or move.",
  "Workflow sync maps projects and issue types to the relevant delivery workflows before report aggregation.",
  "Status classification and curated workflow catalogs separate active work, queues, review, QA, blocked, and done states.",
  "Date filters reshape the prepared workflow evidence without changing the underlying status-transition source data.",
];

export function BottleneckReportLayout({
  activeReport,
  title,
  description,
  eyebrow = "Bottlenecks",
  controls,
  metrics,
  readingTip,
  lineageSteps,
  mainWorkflowLineage,
  children,
}: BottleneckReportLayoutProps) {
  const populationSteps = lineageSteps ?? POPULATION_STEPS;
  const section = JIRA_ANALYTICS_SECTIONS.find((item) => item.id === "bottlenecks");

  return (
    <div className="space-y-6">
      <section className="analytics-hero-panel p-6 md:p-8">
        <div className="analytics-hero-accent analytics-hero-accent--bottleneck" aria-hidden />
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
                <h3 className="mt-1 text-lg font-editorial font-bold text-on-surface">
                  Bottleneck reports
                </h3>
              </div>
              <span className="rounded-full border border-outline-variant/30 bg-surface-container-lowest px-2.5 py-1 text-xs font-medium text-on-surface-variant">
                {section?.reports.length ?? 3}
              </span>
            </div>
            <nav className="space-y-2" aria-label="Bottleneck reports">
              {(Object.keys(BOTTLENECK_REPORTS) as BottleneckReportId[]).map((id) => {
                const report = BOTTLENECK_REPORTS[id];
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
            <h3 className="mt-2 text-xl font-editorial font-bold text-on-surface">
              Workflow movement with traceable status evidence.
            </h3>
            <ol className="mt-4 space-y-3">
              {populationSteps.map((step, index) => (
                <li key={step} className="grid grid-cols-[2rem_1fr] gap-3 text-sm leading-6 text-on-surface-variant">
                  <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-xs font-bold tabular-nums text-primary">
                    {index + 1}
                  </span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
            {mainWorkflowLineage && mainWorkflowLineage.length > 0 ? (
              <div className="mt-6 space-y-3 border-t border-outline-variant/28 pt-5">
                <p className="text-xs font-label uppercase tracking-[0.16em] text-on-surface-variant">
                  Main delivery workflows
                </p>
                {mainWorkflowLineage.map((workflow) => (
                  <div
                    key={workflow.label}
                    className="rounded-xl border border-outline-variant/28 bg-surface-container-low/60 p-3"
                  >
                    <p className="text-sm font-semibold text-on-surface">{workflow.label}</p>
                    <p className="mt-1 text-sm leading-6 text-on-surface-variant">{workflow.purpose}</p>
                    <p className="mt-2 text-xs text-on-surface-variant">
                      Issue types: {workflow.issueTypes}
                    </p>
                  </div>
                ))}
              </div>
            ) : null}
          </section>

          <section className="elevated-panel rounded-[1.5rem] p-5">
            <p className="text-xs font-label uppercase tracking-[0.18em] text-on-surface-variant">Reading tip</p>
            <p className="mt-2 text-sm leading-6 text-on-surface-variant">{readingTip}</p>
          </section>
        </div>
      </div>
    </div>
  );
}

export function BottleneckMetricCard({
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
