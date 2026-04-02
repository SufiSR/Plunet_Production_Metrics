"use client";

import type { AdminConfigResponse, AdminConfigPatch } from "@/types/admin";

interface SchedulerConfigSectionProps {
  config: AdminConfigResponse;
  patch: AdminConfigPatch;
  onPatch: (updates: AdminConfigPatch) => void;
}

export function SchedulerConfigSection({
  config,
  patch,
  onPatch,
}: SchedulerConfigSectionProps) {
  const hour =
    patch.sync_cron_hour ?? config.sync_cron_hour;
  const minute =
    patch.sync_cron_minute ?? config.sync_cron_minute;
  const lookback =
    patch.lookback_days ?? config.lookback_days;

  return (
    <section className="bg-surface-container-lowest p-10 rounded-2xl">
      <div className="flex justify-between items-start mb-10">
        <div>
          <h2 className="text-2xl font-editorial font-semibold tracking-tight text-on-surface mb-1">
            Scheduler
          </h2>
          <p className="text-sm text-on-surface-variant">
            Configure the nightly sync schedule and data lookback window.
          </p>
        </div>
        <div className="flex items-center gap-2 bg-surface-container px-4 py-1.5 rounded-full">
          <span className="material-symbols-outlined text-primary text-sm leading-none">
            schedule
          </span>
          <span className="text-xs font-editorial font-bold uppercase tracking-wider text-on-surface-variant">
            Cron
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        {/* Hour */}
        <div className="space-y-2">
          <label
            htmlFor="sync_cron_hour"
            className="text-[10px] font-editorial font-bold uppercase tracking-[0.1em] text-outline px-1 block"
          >
            Sync Hour (0–23)
          </label>
          <input
            id="sync_cron_hour"
            type="number"
            min={0}
            max={23}
            value={hour}
            onChange={(e) =>
              onPatch({ sync_cron_hour: Number(e.target.value) })
            }
            className="w-full px-4 py-3 bg-surface-container-low border-b-2 border-transparent focus:bg-surface-container-lowest focus:border-primary focus:outline-none transition-all font-editorial text-on-surface"
          />
        </div>

        {/* Minute */}
        <div className="space-y-2">
          <label
            htmlFor="sync_cron_minute"
            className="text-[10px] font-editorial font-bold uppercase tracking-[0.1em] text-outline px-1 block"
          >
            Sync Minute (0–59)
          </label>
          <input
            id="sync_cron_minute"
            type="number"
            min={0}
            max={59}
            value={minute}
            onChange={(e) =>
              onPatch({ sync_cron_minute: Number(e.target.value) })
            }
            className="w-full px-4 py-3 bg-surface-container-low border-b-2 border-transparent focus:bg-surface-container-lowest focus:border-primary focus:outline-none transition-all font-editorial text-on-surface"
          />
        </div>

        {/* Lookback */}
        <div className="space-y-2">
          <label
            htmlFor="lookback_days"
            className="text-[10px] font-editorial font-bold uppercase tracking-[0.1em] text-outline px-1 block"
          >
            Lookback Days
          </label>
          <input
            id="lookback_days"
            type="number"
            min={1}
            value={lookback}
            onChange={(e) =>
              onPatch({ lookback_days: Number(e.target.value) })
            }
            className="w-full px-4 py-3 bg-surface-container-low border-b-2 border-transparent focus:bg-surface-container-lowest focus:border-primary focus:outline-none transition-all font-editorial text-on-surface"
          />
        </div>
      </div>

      <p className="text-[10px] text-outline px-1 mt-4 italic">
        Sync runs daily at {String(hour).padStart(2, "0")}:
        {String(minute).padStart(2, "0")} UTC. Changes take effect after the
        next server restart or manual trigger.
      </p>
    </section>
  );
}
