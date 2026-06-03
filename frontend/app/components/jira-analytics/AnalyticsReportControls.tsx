"use client";

import type { ReactNode } from "react";

export function AnalyticsFilterPanel({
  title = "Filters",
  description,
  children,
}: {
  title?: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section className="analytics-filter-panel p-4 md:p-5">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-label uppercase tracking-[0.18em] text-primary">{title}</p>
          {description ? <p className="mt-1 text-sm text-on-surface-variant">{description}</p> : null}
        </div>
      </div>
      <div className="flex flex-wrap items-end gap-3">{children}</div>
    </section>
  );
}

export function FilterField({
  label,
  hint,
  className = "",
  children,
}: {
  label: string;
  hint?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <label className={`flex min-w-[11rem] flex-col gap-1 ${className}`}>
      <span className="text-xs font-semibold text-on-surface-variant">{label}</span>
      {children}
      {hint ? <span className="text-[11px] text-on-surface-variant">{hint}</span> : null}
    </label>
  );
}

export function filterInputClassName(extra = ""): string {
  return `analytics-filter-input w-full ${extra}`;
}

export function SegmentToggle<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  return (
    <div className="analytics-filter-segment text-sm">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={`rounded-xl px-3 py-2 font-semibold transition ${
            option.value === value
              ? "bg-primary text-on-primary shadow-sm"
              : "text-on-surface-variant hover:text-on-surface"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

