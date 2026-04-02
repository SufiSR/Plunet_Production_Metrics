"use client";

import { useState } from "react";

interface TagListInputProps {
  id: string;
  label: string;
  values: string[];
  helpText?: string;
  onChange: (values: string[]) => void;
}

/**
 * Editable tag-list input for comma-separated or newline-delimited string arrays.
 * Renders as a textarea; splits on comma or newline for the array value.
 */
export function TagListInput({ id, label, values, helpText, onChange }: TagListInputProps) {
  const [raw, setRaw] = useState(values.join("\n"));

  function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const text = e.target.value;
    setRaw(text);
    const parsed = text
      .split(/[\n,]/)
      .map((s) => s.trim())
      .filter(Boolean);
    onChange(parsed);
  }

  return (
    <div className="space-y-2">
      <label
        htmlFor={id}
        className="text-[10px] font-editorial font-bold uppercase tracking-[0.1em] text-outline px-1 block"
      >
        {label}
      </label>
      <textarea
        id={id}
        rows={3}
        value={raw}
        onChange={handleChange}
        className="w-full px-4 py-3 bg-surface-container-low border-b-2 border-transparent focus:bg-surface-container-lowest focus:border-primary focus:outline-none transition-all font-body text-sm text-on-surface placeholder:text-outline resize-none"
        placeholder="One per line or comma-separated"
      />
      {helpText && (
        <p className="text-[10px] text-outline px-1 italic">{helpText}</p>
      )}
    </div>
  );
}
