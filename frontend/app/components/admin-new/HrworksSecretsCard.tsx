export function HrworksSecretsCard() {
  return (
    <section className="elevated-panel p-8 rounded-2xl">
      <div className="flex items-start gap-3 mb-4">
        <span className="material-symbols-outlined text-primary">schedule</span>
        <div>
          <h2 className="text-xl font-editorial font-semibold text-on-surface">HRWorks credentials</h2>
          <p className="text-sm text-on-surface-variant mt-1 max-w-2xl">
            Access key and secret are loaded from environment variables (
            <code className="text-xs">ACCESSKEY</code>, <code className="text-xs">SECRETKEY</code> or{" "}
            <code className="text-xs">HRWORKS_*</code>). Runtime admin storage for HRWorks secrets is planned
            for a later phase.
          </p>
        </div>
      </div>
      <p className="text-xs text-outline">
        Used by: HRWorks capacity ingestion, availability vs booked reports, capacity forecast.
      </p>
    </section>
  );
}
