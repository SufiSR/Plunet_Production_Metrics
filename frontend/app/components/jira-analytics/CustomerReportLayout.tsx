"use client";

import type { ReactNode } from "react";

interface CustomerReportLayoutProps {
  title: string;
  description: string;
  eyebrow?: string;
  controls?: ReactNode;
  metrics?: ReactNode;
  children: ReactNode;
}

const POPULATION_STEPS = [
  "Jira custom field customfield_10123 stores customer names on linked issues.",
  "Monthly allocation rows carry booked hours by issue, topic type, and month.",
  "When multiple customers are listed on one issue, hours are split equally across them.",
  "This report aggregates attributed hours; issues without a customer remain visible as unattributed capacity.",
];

export function CustomerReportLayout({
  title,
  description,
  eyebrow = "Customer effort",
  controls,
  metrics,
  children,
}: CustomerReportLayoutProps) {
  return (
    <div className="space-y-6">
      <section className="analytics-hero-panel p-6 md:p-8">
        <div className="analytics-hero-accent analytics-hero-accent--customer" aria-hidden />
        <div className="relative space-y-5">
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
      </section>

      <div className="min-w-0 space-y-6">
        {controls}
        {children}
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_24rem]">
          <section className="analytics-section-panel rounded-[1.5rem] p-5 shadow-sm">
            <p className="text-xs font-label uppercase tracking-[0.18em] text-primary">Data lineage</p>
            <h3 className="mt-2 text-xl font-editorial font-bold text-on-surface">Customer field to allocated hours.</h3>
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
              Use the ranking chart for disproportionate demand, the trend for month-over-month shifts, and the topic
              columns to see whether effort is feature, bugfix, or support work.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}

export function CustomerMetricCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="elevated-panel rounded-[1.25rem] p-4 backdrop-blur">
      <p className="text-xs font-label uppercase tracking-[0.18em] text-on-surface-variant">{label}</p>
      <p className="mt-2 text-3xl font-editorial font-bold tabular-nums text-on-surface">{value}</p>
      <p className="mt-1 text-sm text-on-surface-variant">{detail}</p>
    </div>
  );
}
