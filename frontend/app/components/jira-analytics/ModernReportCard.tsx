"use client";

import type { ReactNode } from "react";

export function ModernReportCard({
  eyebrow,
  title,
  description,
  action,
  children,
  className = "",
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`analytics-section-panel overflow-hidden rounded-[1.5rem] shadow-sm ${className}`}>
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-outline-variant/30 bg-surface-container-low px-5 py-4 dark:border-outline-variant/40 dark:bg-surface-container-high">
        <div>
          {eyebrow ? (
            <p className="text-xs font-label uppercase tracking-[0.18em] text-primary">{eyebrow}</p>
          ) : null}
          <h3 className="mt-1 text-xl font-editorial font-bold text-on-surface">{title}</h3>
          {description ? <p className="mt-1 max-w-3xl text-sm leading-6 text-on-surface-variant">{description}</p> : null}
        </div>
        {action}
      </div>
      <div className="p-4 md:p-5">{children}</div>
    </section>
  );
}

export function EmptyCardMessage({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-outline-variant/30 bg-surface-container-low p-6 text-sm text-on-surface-variant">
      {children}
    </div>
  );
}

