"use client";

import { useUIStore, type PeriodType } from "@/lib/store";

const PERIODS: { value: PeriodType; label: string }[] = [
  { value: "30d", label: "Last 30 Days" },
  { value: "quarterly", label: "Quarterly" },
  { value: "yearly", label: "Yearly" },
];

export function PeriodSelector() {
  const { period, setPeriod } = useUIStore();

  return (
    <div className="flex max-w-full items-center gap-1 overflow-x-auto rounded-lg bg-surface-container p-1">
      {PERIODS.map(({ value, label }) => {
        const isActive = period === value;
        return (
          <button
            key={value}
            onClick={() => setPeriod(value)}
            className={[
              "shrink-0 px-3 py-1 text-xs font-editorial font-bold rounded-md transition-all duration-150",
              isActive
                ? "bg-surface-container-lowest text-primary shadow-sm"
                : "text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface",
            ].join(" ")}
            aria-pressed={isActive}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
