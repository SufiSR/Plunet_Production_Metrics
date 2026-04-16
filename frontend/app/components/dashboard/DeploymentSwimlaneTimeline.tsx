"use client";

import { useMemo, useState } from "react";
import { useReleaseTimeline } from "@/lib/hooks";
import type { ReleaseTimelineItem } from "@/types/api";

type Lane = "major" | "minor" | "patch" | "unknown";

const LANE_ORDER: Lane[] = ["major", "minor", "patch", "unknown"];
const LANE_LABEL: Record<Lane, string> = {
  major: "Major",
  minor: "Minor",
  patch: "Patch",
  unknown: "Unknown",
};

function inferLane(item: ReleaseTimelineItem): Lane {
  if (item.version_major === null || item.version_minor === null || item.version_patch === null) {
    return "unknown";
  }
  if (item.version_patch > 0) return "patch";
  if (item.version_minor > 0) return "minor";
  return "major";
}

function formatDateTime(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function hueForMajor(major: number | null): number {
  if (major === 10) return 222; // blues
  if (major === 9) return 28; // oranges
  if (major === 8) return 158; // greens
  if (major === null) return 250;
  return (major * 37) % 360;
}

function dotColor(item: ReleaseTimelineItem): string {
  const hue = hueForMajor(item.version_major);
  const minor = item.version_minor ?? 0;
  const patch = item.version_patch ?? 0;
  let lightness = 42;
  if (patch > 0) {
    lightness = 62 + (patch % 3) * 2;
  } else if (minor > 0) {
    lightness = 50 + (minor % 3) * 3;
  }
  return `hsl(${hue} 78% ${lightness}%)`;
}

export function DeploymentSwimlaneTimeline() {
  const { data, isLoading, isError } = useReleaseTimeline();
  const [selected, setSelected] = useState<ReleaseTimelineItem | null>(null);

  const events = useMemo(() => {
    const raw = data?.items ?? [];
    return [...raw].sort(
      (a, b) => new Date(a.committed_at).getTime() - new Date(b.committed_at).getTime()
    );
  }, [data]);

  const bounds = useMemo(() => {
    if (events.length === 0) return null;
    const min = new Date(events[0].committed_at).getTime();
    const max = new Date(events[events.length - 1].committed_at).getTime();
    const span = Math.max(max - min, 1);
    return { min, max, span };
  }, [events]);

  const timelineGeometry = useMemo(() => {
    if (!bounds) return null;
    const msPerYear = 365 * 24 * 60 * 60 * 1000;
    const yearsCovered = Math.max(bounds.span / msPerYear, 1);
    const viewportWidthPx = 960;
    const canvasWidthPx = Math.ceil(viewportWidthPx * yearsCovered);
    const pxPerMs = canvasWidthPx / bounds.span;
    return { viewportWidthPx, canvasWidthPx, pxPerMs };
  }, [bounds]);

  const lanesToRender = useMemo(
    () => LANE_ORDER.filter((lane) => events.some((item) => inferLane(item) === lane)),
    [events]
  );

  const yearTicks = useMemo(() => {
    if (!bounds || !timelineGeometry) return [];
    const ticks: Array<{ year: number; x: number }> = [];
    const minDate = new Date(bounds.min);
    const maxDate = new Date(bounds.max);
    for (let year = minDate.getUTCFullYear(); year <= maxDate.getUTCFullYear() + 1; year += 1) {
      const boundaryTs = Date.UTC(year, 0, 1, 0, 0, 0, 0);
      if (boundaryTs < bounds.min || boundaryTs > bounds.max) continue;
      const x = (bounds.max - boundaryTs) * timelineGeometry.pxPerMs;
      ticks.push({
        year,
        x: Math.max(0, Math.min(timelineGeometry.canvasWidthPx, x)),
      });
    }
    return ticks;
  }, [bounds, timelineGeometry]);

  return (
    <section className="bg-surface-container-lowest p-8 rounded-xl shadow-[40px_40px_40px_0px_rgba(25,28,29,0.04)] dark:shadow-[0px_4px_24px_0px_rgba(0,0,0,0.4)]">
      <div className="flex items-start justify-between mb-6 gap-4 flex-wrap">
        <div>
          <h2 className="text-2xl font-editorial font-bold tracking-tight text-on-surface">
            Deployment Swimlane Timeline
          </h2>
          <p className="text-xs font-editorial text-on-surface-variant uppercase tracking-widest mt-1">
            Release tags by commit date · {data?.total ?? 0} events
          </p>
        </div>
        <div className="flex items-center gap-4 text-xs text-on-surface-variant">
          <span className="inline-flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-primary" /> Customer</span>
          <span className="inline-flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full border border-outline bg-transparent" /> Non-customer</span>
        </div>
      </div>

      {isLoading ? (
        <div className="h-[260px] w-full bg-surface-container animate-pulse rounded-lg" />
      ) : isError ? (
        <div className="h-[180px] flex items-center justify-center text-sm text-error">
          Could not load deployment timeline data.
        </div>
      ) : events.length === 0 || !bounds || !timelineGeometry ? (
        <div className="h-[180px] flex items-center justify-center text-sm text-on-surface-variant">
          No release events found for the current timeline window.
        </div>
      ) : (
        <div className="space-y-5">
          <div className="overflow-x-auto pb-1">
            <div style={{ minWidth: `${timelineGeometry.viewportWidthPx}px`, width: `${timelineGeometry.canvasWidthPx}px` }}>
              <div className="relative h-8 mb-1">
                <div className="absolute left-24 right-0 top-6 h-px bg-outline-variant/50" />
                <div className="absolute left-24 right-0 top-0 bottom-0">
                  {yearTicks.map((tick) => (
                    <div
                      key={tick.year}
                      className="absolute top-0 bottom-0 pointer-events-none"
                      style={{ left: `${tick.x}px` }}
                    >
                      <span className="absolute -top-0.5 -translate-x-1/2 text-[10px] font-editorial uppercase tracking-widest text-on-surface-variant">
                        {tick.year}
                      </span>
                      <span className="absolute top-5 h-2 w-px bg-outline-variant/70 -translate-x-1/2" />
                    </div>
                  ))}
                </div>
              </div>
              {lanesToRender.map((lane) => (
                <div key={lane} className="relative h-14 border-b border-outline-variant/40 last:border-b-0">
                  <div className="absolute left-0 top-1/2 -translate-y-1/2 w-20 text-xs font-editorial uppercase tracking-wider text-on-surface-variant">
                    {LANE_LABEL[lane]}
                  </div>
                  <div className="absolute left-24 right-0 top-1/2 h-px bg-outline-variant/50" />
                  <div className="absolute left-24 right-0 top-0 bottom-0">
                    {events
                      .filter((item) => inferLane(item) === lane)
                      .map((item) => {
                        const x =
                          (bounds.max - new Date(item.committed_at).getTime()) * timelineGeometry.pxPerMs;
                        const fill = dotColor(item);
                        const style = {
                          left: `${Math.max(0, Math.min(timelineGeometry.canvasWidthPx, x)) - 6}px`,
                          backgroundColor: fill,
                          borderColor: fill,
                        };
                        const isSelected =
                          selected?.tag_name === item.tag_name &&
                          selected?.committed_at === item.committed_at;
                        return (
                          <button
                            key={`${item.repository_id}:${item.tag_name}:${item.committed_at}`}
                            type="button"
                            style={style}
                            title={`${item.tag_name} · ${formatDateTime(item.committed_at)}`}
                            onClick={() => setSelected(item)}
                            className={[
                              "absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full border transition-all",
                              item.customer_release ? "opacity-100" : "opacity-35",
                              isSelected ? "ring-2 ring-primary/40 scale-125" : "hover:scale-110",
                            ].join(" ")}
                          />
                        );
                      })}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between text-xs text-on-surface-variant">
            <span>{new Date(bounds.max).toLocaleDateString()}</span>
            <span>{new Date(bounds.min).toLocaleDateString()}</span>
          </div>

          <div className="rounded-lg border border-outline-variant/50 bg-surface-container p-4">
            {selected ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                <div>
                  <p className="text-[11px] uppercase tracking-wider text-on-surface-variant">Tag</p>
                  <p className="font-editorial font-bold text-on-surface">{selected.tag_name}</p>
                </div>
                <div>
                  <p className="text-[11px] uppercase tracking-wider text-on-surface-variant">Commit Date</p>
                  <p className="text-on-surface">{formatDateTime(selected.committed_at)}</p>
                </div>
                <div>
                  <p className="text-[11px] uppercase tracking-wider text-on-surface-variant">Version Type</p>
                  <p className="text-on-surface capitalize">{inferLane(selected)}</p>
                </div>
                <div>
                  <p className="text-[11px] uppercase tracking-wider text-on-surface-variant">Customer Release</p>
                  <p className="text-on-surface">{selected.customer_release ? "Yes" : "No"}</p>
                </div>
              </div>
            ) : (
              <p className="text-sm text-on-surface-variant">
                Select a dot to inspect release tag details.
              </p>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
