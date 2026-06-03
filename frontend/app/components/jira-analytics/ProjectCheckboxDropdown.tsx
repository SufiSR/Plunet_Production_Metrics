"use client";

import { useEffect, useId, useRef, useState } from "react";

export interface ProjectOption {
  key: string;
  name?: string | null;
}

interface ProjectCheckboxDropdownProps {
  projects: ProjectOption[];
  /** `null` means all projects are selected (no API filter). */
  selectedKeys: string[] | null;
  onChange: (selectedKeys: string[] | null) => void;
  disabled?: boolean;
}

export function ProjectCheckboxDropdown({
  projects,
  selectedKeys,
  onChange,
  disabled = false,
}: ProjectCheckboxDropdownProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const listId = useId();
  const allKeys = projects.map((project) => project.key);
  const effectiveSelected = selectedKeys ?? allKeys;
  const allSelected =
    projects.length > 0 &&
    (selectedKeys === null || selectedKeys.length === projects.length);

  useEffect(() => {
    if (!open) return;
    const handlePointerDown = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [open]);

  const summaryLabel =
    projects.length === 0
      ? "No projects"
      : allSelected
        ? `All projects (${projects.length})`
        : `${effectiveSelected.length} of ${projects.length} selected`;

  const setAll = (checked: boolean) => {
    onChange(checked ? null : []);
  };

  const toggleProject = (key: string, checked: boolean) => {
    const current = selectedKeys ?? allKeys;
    if (checked) {
      const next = [...new Set([...current, key])];
      onChange(next.length === projects.length ? null : next);
      return;
    }
    const next = current.filter((item) => item !== key);
    onChange(next.length === 0 ? [] : next);
  };

  return (
    <div ref={containerRef} className="relative min-w-[16rem]">
      <span className="text-xs font-medium text-on-surface-variant">Jira projects</span>
      <button
        type="button"
        disabled={disabled || projects.length === 0}
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => setOpen((value) => !value)}
        className="analytics-filter-input mt-1 flex w-full items-center justify-between text-left disabled:cursor-not-allowed disabled:opacity-60"
      >
        <span className="truncate">{summaryLabel}</span>
        <span className="ml-2 text-on-surface-variant" aria-hidden>
          {open ? "▲" : "▼"}
        </span>
      </button>
      {open && projects.length > 0 ? (
        <div
          id={listId}
          className="analytics-section-panel absolute z-30 mt-1 max-h-64 w-full overflow-y-auto rounded-xl p-2 shadow-lg"
        >
          <label className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-surface-container-low">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={(event) => setAll(event.target.checked)}
              className="size-4 rounded border-outline-variant/50"
            />
            <span className="font-medium text-on-surface">All projects</span>
          </label>
          <div className="my-1 border-t border-outline-variant/28" />
          {projects.map((project) => {
            const checked = effectiveSelected.includes(project.key);
            return (
              <label
                key={project.key}
                className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-surface-container-low"
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={(event) => toggleProject(project.key, event.target.checked)}
                  className="size-4 rounded border-outline-variant/50"
                />
                <span className="truncate text-on-surface">
                  {project.name ? `${project.key} — ${project.name}` : project.key}
                </span>
              </label>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
