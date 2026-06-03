"use client";

import type { ReportMethodology } from "@/lib/jira-analytics-methodology";

interface ReportMethodologyPanelProps {
  methodology: ReportMethodology;
}

function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="list-disc pl-5 space-y-1.5 text-sm text-on-surface-variant">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

export function ReportMethodologyPanel({ methodology }: ReportMethodologyPanelProps) {
  return (
    <details
      className="rounded-xl border border-outline-variant/25 bg-surface-container-low/40 group"
    >
      <summary className="cursor-pointer list-none [&::-webkit-details-marker]:hidden px-4 py-3 flex items-center justify-between gap-3 select-none">
        <span className="text-sm font-medium text-on-surface">
          How this is populated
        </span>
        <span
          className="text-xs text-on-surface-variant group-open:rotate-180 transition-transform"
          aria-hidden
        >
          ▼
        </span>
      </summary>
      <div className="px-4 pb-4 space-y-4 border-t border-outline-variant/28">
        <p className="text-sm text-on-surface pt-3">{methodology.overview}</p>

        <section>
          <h2 className="text-xs font-label uppercase tracking-wide text-on-surface-variant mb-2">
            Data sources
          </h2>
          <BulletList items={methodology.dataSources} />
        </section>

        <section>
          <h2 className="text-xs font-label uppercase tracking-wide text-on-surface-variant mb-2">
            What is included
          </h2>
          <BulletList items={methodology.included} />
        </section>

        <section>
          <h2 className="text-xs font-label uppercase tracking-wide text-on-surface-variant mb-2">
            What you see on this page
          </h2>
          <BulletList items={methodology.presented} />
        </section>

        {methodology.limitations && methodology.limitations.length > 0 ? (
          <section>
            <h2 className="text-xs font-label uppercase tracking-wide text-on-surface-variant mb-2">
              Limitations &amp; caveats
            </h2>
            <BulletList items={methodology.limitations} />
          </section>
        ) : null}
      </div>
    </details>
  );
}
