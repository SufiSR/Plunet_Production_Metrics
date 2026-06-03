"use client";

import type { AdminConfigPatch, AdminConfigResponse } from "@/types/admin";

const HRWORKS_DOW_OPTIONS = [
  { value: "mon", label: "Monday" },
  { value: "tue", label: "Tuesday" },
  { value: "wed", label: "Wednesday" },
  { value: "thu", label: "Thursday" },
  { value: "fri", label: "Friday" },
  { value: "sat", label: "Saturday" },
  { value: "sun", label: "Sunday" },
];

function CronNumberInput({
  id,
  label,
  value,
  min,
  max,
  onChange,
}: {
  id: string;
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="space-y-2">
      <label
        htmlFor={id}
        className="text-[10px] font-editorial font-bold uppercase tracking-[0.1em] text-outline px-1 block"
      >
        {label}
      </label>
      <input
        id={id}
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full px-4 py-3 bg-surface-container-low border-b-2 border-transparent focus:bg-surface-container-lowest focus:border-primary focus:outline-none font-editorial text-on-surface"
      />
    </div>
  );
}

interface SchedulersSettingsSectionProps {
  config: AdminConfigResponse;
  patch: AdminConfigPatch;
  onPatch: (updates: AdminConfigPatch) => void;
}

export function SchedulersSettingsSection({ config, patch, onPatch }: SchedulersSettingsSectionProps) {
  const v = <K extends keyof AdminConfigResponse>(key: K) =>
    (patch[key as keyof AdminConfigPatch] ?? config[key]) as AdminConfigResponse[K];

  const doraHour = v("sync_cron_hour") as number;
  const doraMinute = v("sync_cron_minute") as number;
  const doraLookback = v("lookback_days") as number;
  const hwDow = v("hrworks_sync_cron_day_of_week") as string;
  const hwHour = v("hrworks_sync_cron_hour") as number;
  const hwMinute = v("hrworks_sync_cron_minute") as number;
  const jaHour = v("jira_analytics_sync_cron_hour") as number;
  const jaMinute = v("jira_analytics_sync_cron_minute") as number;
  const jaLookback = v("jira_analytics_scheduled_lookback_days") as number;

  return (
    <div className="space-y-8">
      <section className="elevated-panel p-8 rounded-2xl">
        <h2 className="text-xl font-editorial font-semibold text-on-surface mb-1">DORA nightly pipeline</h2>
        <p className="text-sm text-on-surface-variant mb-6">
          GitLab, Jira bugs, linking, and metric snapshots. All times UTC.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <CronNumberInput
            id="dora_sync_hour"
            label="Hour (0–23)"
            value={doraHour}
            min={0}
            max={23}
            onChange={(val) => onPatch({ sync_cron_hour: val })}
          />
          <CronNumberInput
            id="dora_sync_minute"
            label="Minute (0–59)"
            value={doraMinute}
            min={0}
            max={59}
            onChange={(val) => onPatch({ sync_cron_minute: val })}
          />
          <CronNumberInput
            id="dora_lookback"
            label="GitLab/Jira lookback (days)"
            value={doraLookback}
            min={1}
            max={3650}
            onChange={(val) => onPatch({ lookback_days: val })}
          />
        </div>
        <p className="text-[10px] text-outline mt-4 italic">
          Runs daily at {String(doraHour).padStart(2, "0")}:{String(doraMinute).padStart(2, "0")} UTC.
        </p>
      </section>

      <section className="elevated-panel p-8 rounded-2xl">
        <h2 className="text-xl font-editorial font-semibold text-on-surface mb-1">HRWorks capacity</h2>
        <p className="text-sm text-on-surface-variant mb-6">Weekly incremental sync of available hours.</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="space-y-2">
            <label
              htmlFor="hrworks_dow"
              className="text-[10px] font-editorial font-bold uppercase tracking-[0.1em] text-outline px-1 block"
            >
              Day of week
            </label>
            <select
              id="hrworks_dow"
              value={hwDow}
              onChange={(e) => onPatch({ hrworks_sync_cron_day_of_week: e.target.value })}
              className="w-full px-4 py-3 bg-surface-container-low border-b-2 border-transparent focus:border-primary focus:outline-none font-editorial text-on-surface"
            >
              {HRWORKS_DOW_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
          <CronNumberInput
            id="hrworks_hour"
            label="Hour (0–23)"
            value={hwHour}
            min={0}
            max={23}
            onChange={(val) => onPatch({ hrworks_sync_cron_hour: val })}
          />
          <CronNumberInput
            id="hrworks_minute"
            label="Minute (0–59)"
            value={hwMinute}
            min={0}
            max={59}
            onChange={(val) => onPatch({ hrworks_sync_cron_minute: val })}
          />
        </div>
      </section>

      <section className="elevated-panel p-8 rounded-2xl">
        <h2 className="text-xl font-editorial font-semibold text-on-surface mb-1">Jira Analytics warehouse</h2>
        <p className="text-sm text-on-surface-variant mb-6">
          Scheduled sync uses the default lookback below. Manual runs can override days on the ingestion page.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <CronNumberInput
            id="ja_sync_hour"
            label="Hour (0–23)"
            value={jaHour}
            min={0}
            max={23}
            onChange={(val) => onPatch({ jira_analytics_sync_cron_hour: val })}
          />
          <CronNumberInput
            id="ja_sync_minute"
            label="Minute (0–59)"
            value={jaMinute}
            min={0}
            max={59}
            onChange={(val) => onPatch({ jira_analytics_sync_cron_minute: val })}
          />
          <CronNumberInput
            id="ja_lookback"
            label="Default updated-after (days)"
            value={jaLookback}
            min={1}
            max={3650}
            onChange={(val) => onPatch({ jira_analytics_scheduled_lookback_days: val })}
          />
        </div>
        <p className="text-[10px] text-outline mt-4 italic">
          JQL: <code className="text-[9px]">updated &gt;= today - {jaLookback} days</code> (plus project exclusions).
          Runs daily at {String(jaHour).padStart(2, "0")}:{String(jaMinute).padStart(2, "0")} UTC.
        </p>
      </section>
    </div>
  );
}
