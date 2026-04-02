"use client";

import { useState } from "react";

interface SecretInputProps {
  id: string;
  label: string;
  hint: string | null;
  placeholder?: string;
  helpText?: string;
  onChange: (value: string) => void;
}

/**
 * A password input that shows a masked hint when not edited.
 * Only reports a new value to `onChange` when the user types.
 * If cleared back to empty, it does NOT send an empty string —
 * the parent should treat an empty draft as "unchanged".
 */
export function SecretInput({
  id,
  label,
  hint,
  placeholder = "Enter new value to replace",
  helpText,
  onChange,
}: SecretInputProps) {
  const [visible, setVisible] = useState(false);
  const [draft, setDraft] = useState("");

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const v = e.target.value;
    setDraft(v);
    onChange(v);
  }

  const displayPlaceholder = hint
    ? `Current: ${hint} — type to replace`
    : placeholder;

  return (
    <div className="space-y-2">
      <label
        htmlFor={id}
        className="text-[10px] font-editorial font-bold uppercase tracking-[0.1em] text-outline px-1 block"
      >
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          type={visible ? "text" : "password"}
          value={draft}
          onChange={handleChange}
          placeholder={displayPlaceholder}
          autoComplete="new-password"
          className="w-full px-4 py-3 pr-10 bg-surface-container-low border-b-2 border-transparent focus:bg-surface-container-lowest focus:border-primary focus:outline-none transition-all font-mono text-sm tracking-widest text-on-surface placeholder:text-outline placeholder:font-body placeholder:tracking-normal"
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-outline hover:text-primary transition-colors"
          aria-label={visible ? "Hide token" : "Show token"}
        >
          <span className="material-symbols-outlined text-xl leading-none">
            {visible ? "visibility_off" : "visibility"}
          </span>
        </button>
      </div>
      {helpText && (
        <p className="text-[10px] text-outline px-1 italic">{helpText}</p>
      )}
    </div>
  );
}
