"use client";

interface UnsavedToastProps {
  count: number;
  onDiscard: () => void;
  onSave: () => void;
  isSaving: boolean;
}

export function UnsavedToast({ count, onDiscard, onSave, isSaving }: UnsavedToastProps) {
  if (count === 0) return null;

  return (
    <div className="fixed bottom-8 right-8 z-[100] flex items-center gap-4 bg-inverse-surface text-inverse-on-surface px-5 py-4 rounded-xl shadow-[0px_8px_32px_0px_rgba(0,0,0,0.25)] dark:shadow-[0px_8px_32px_0px_rgba(0,0,0,0.6)]">
      <div className="bg-primary/20 p-2 rounded-lg shrink-0">
        <span
          className="material-symbols-outlined text-primary leading-none"
          style={{ fontVariationSettings: "'FILL' 1" }}
        >
          info
        </span>
      </div>
      <div className="pr-2">
        <div className="text-xs font-editorial font-bold uppercase tracking-wider">
          Unsaved Changes
        </div>
        <div className="text-[10px] text-inverse-on-surface/70 mt-0.5">
          {count} field{count !== 1 ? "s" : ""} modified
        </div>
      </div>
      <div className="flex items-center gap-2 ml-2">
        <button
          type="button"
          onClick={onDiscard}
          className="text-[11px] font-editorial font-bold uppercase tracking-wider text-inverse-on-surface/60 hover:text-inverse-on-surface transition-colors px-2 py-1"
        >
          Discard
        </button>
        <button
          type="button"
          onClick={onSave}
          disabled={isSaving}
          className="text-[11px] font-editorial font-bold uppercase tracking-wider bg-primary text-on-primary px-4 py-1.5 rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {isSaving ? "Saving…" : "Save"}
        </button>
      </div>
    </div>
  );
}
