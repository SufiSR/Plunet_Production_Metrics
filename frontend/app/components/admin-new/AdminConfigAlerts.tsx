interface AdminConfigAlertsProps {
  saveState: "idle" | "saving" | "success" | "error";
  saveError: string | null;
}

export function AdminConfigAlerts({ saveState, saveError }: AdminConfigAlertsProps) {
  return (
    <>
      {saveState === "success" ? (
        <div
          role="status"
          className="flex items-center gap-3 px-4 py-3 rounded-xl bg-secondary-container text-on-secondary-container text-xs font-editorial mb-6"
        >
          <span className="material-symbols-outlined text-base shrink-0">check_circle</span>
          Configuration saved successfully.
        </div>
      ) : null}
      {saveState === "error" && saveError ? (
        <div
          role="alert"
          className="flex items-center gap-3 px-4 py-3 rounded-xl bg-error-container text-on-error-container text-xs font-editorial mb-6"
        >
          <span className="material-symbols-outlined text-base shrink-0">error</span>
          {saveError}
        </div>
      ) : null}
    </>
  );
}
