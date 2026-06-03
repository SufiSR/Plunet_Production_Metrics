"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { PeriodSelector } from "@/app/components/header/PeriodSelector";
import { SyncStatusPill } from "@/app/components/header/SyncStatusPill";
import { StaleBanner } from "@/app/components/dashboard/StaleBanner";
import { DoraHeroKpiStrip } from "@/app/components/dora-analytics/DoraHeroKpiStrip";
import { DORA_REPORTS, type DoraReportId } from "@/lib/dora-analytics-config";

interface DoraReportLayoutProps {
  activeReport: DoraReportId;
  title: string;
  description: string;
  children?: ReactNode;
}

export function DoraReportLayout({
  activeReport,
  title,
  description,
  children,
}: DoraReportLayoutProps) {
  const isOverview = activeReport === "overview";

  return (
    <div className="space-y-4">
      <section className="analytics-hero-panel rounded-2xl p-4 md:p-5">
        <div className="analytics-hero-accent analytics-hero-accent--dora" aria-hidden />

        <div className="relative space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="text-[10px] font-label uppercase tracking-[0.2em] text-on-surface-variant">
              DORA metrics
            </span>
            <div className="flex flex-wrap items-center gap-2">
              <PeriodSelector />
              <SyncStatusPill />
            </div>
          </div>

          {isOverview ? (
            <div className="space-y-1">
              <h2 className="text-2xl font-editorial font-bold tracking-tight text-on-surface md:text-3xl">
                {title}
              </h2>
              <p className="max-w-3xl text-sm leading-6 text-on-surface-variant line-clamp-2">
                {description}
              </p>
            </div>
          ) : null}

          <nav
            className="flex gap-1 overflow-x-auto rounded-xl border border-outline-variant/28 bg-surface-container-low/60 p-1"
            aria-label="DORA reports"
          >
            {DORA_REPORTS.map((report) => {
              const active = report.id === activeReport;
              return (
                <Link
                  key={report.id}
                  href={report.href}
                  className={`shrink-0 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                    active
                      ? "bg-surface-container-lowest text-primary shadow-sm"
                      : "text-on-surface-variant hover:bg-surface-container-lowest/80 hover:text-on-surface"
                  }`}
                >
                  {report.id === "overview" ? "Overview" : report.title}
                </Link>
              );
            })}
          </nav>

          <StaleBanner />
          <DoraHeroKpiStrip activeReport={activeReport} />
        </div>
      </section>

      {children ? <div className="space-y-4">{children}</div> : null}

      {isOverview ? (
        <p className="text-xs text-on-surface-variant">
          Select a metric tab above for trend charts and drilldowns. Combined dashboard:{" "}
          <Link href="/" className="font-semibold text-primary hover:underline">
            home page
          </Link>
          .
        </p>
      ) : null}
    </div>
  );
}
