"use client";

type PhaseBlock = {
  status?: string;
  message?: string | null;
};

type PipelineRuntime = {
  current_phase?: string;
  phases?: Record<string, PhaseBlock>;
  errors?: string[];
  progress?: { message?: string };
};

const PHASE_LABELS: Record<string, string> = {
  ingestion: "Ingestion",
  workflow_sync: "Workflow sync",
  feature_membership: "Feature membership",
  allocation: "Allocation",
  complete: "Complete",
  gitlab: "GitLab",
  jira: "Jira",
  derivations: "Derivations",
  snapshots: "Snapshots",
};

function phaseIcon(status?: string): string {
  if (status === "running") return "sync";
  if (status === "success") return "check_circle";
  if (status === "failed") return "error";
  return "radio_button_unchecked";
}

interface PipelineRuntimeTimelineProps {
  runtime: PipelineRuntime | null | undefined;
  phaseOrder?: string[];
}

export function PipelineRuntimeTimeline({ runtime, phaseOrder }: PipelineRuntimeTimelineProps) {
  if (!runtime?.phases) return null;
  const keys = phaseOrder ?? Object.keys(runtime.phases);

  return (
    <div className="rounded-xl border border-outline-variant/20 p-3 text-xs space-y-1.5">
      {runtime.current_phase ? (
        <p className="text-[10px] uppercase tracking-wider text-on-surface-variant">
          Current: {runtime.current_phase}
        </p>
      ) : null}
      {keys.map((key) => {
        const block = runtime.phases?.[key];
        const status = block?.status ?? "pending";
        return (
          <div key={key} className="space-y-0.5">
            <div className="flex justify-between gap-2 text-on-surface-variant">
              <span className="flex items-center gap-1">
                <span className={`material-symbols-outlined text-sm ${status === "running" ? "animate-spin" : ""}`}>
                  {phaseIcon(status)}
                </span>
                {PHASE_LABELS[key] ?? key}
              </span>
              <span className="uppercase text-[10px]">{status}</span>
            </div>
            {status === "running" && block?.message ? (
              <p className="text-[11px] text-on-surface-variant pl-5">{block.message}</p>
            ) : null}
            {status === "running" && key === "ingestion" && runtime.progress?.message ? (
              <p className="text-[11px] text-primary pl-5">{runtime.progress.message}</p>
            ) : null}
          </div>
        );
      })}
      {runtime.errors && runtime.errors.length > 0 ? (
        <p className="text-error text-[11px] pt-1">{runtime.errors[0]}</p>
      ) : null}
    </div>
  );
}
