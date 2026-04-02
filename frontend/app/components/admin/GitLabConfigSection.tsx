"use client";

import type { AdminConfigResponse, AdminConfigPatch } from "@/types/admin";
import { SecretInput } from "./SecretInput";
import { TagListInput } from "./TagListInput";

interface GitLabConfigSectionProps {
  config: AdminConfigResponse;
  patch: AdminConfigPatch;
  onPatch: (updates: AdminConfigPatch) => void;
}

function TextInput({
  id,
  label,
  value,
  placeholder,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  placeholder?: string;
  onChange: (v: string) => void;
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
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-4 py-3 bg-surface-container-low border-b-2 border-transparent focus:bg-surface-container-lowest focus:border-primary focus:outline-none transition-all font-body text-sm text-on-surface placeholder:text-outline"
      />
    </div>
  );
}

export function GitLabConfigSection({ config, patch, onPatch }: GitLabConfigSectionProps) {
  const v = (key: keyof AdminConfigResponse) =>
    (patch[key as keyof AdminConfigPatch] ?? config[key]) as string;

  return (
    <section className="bg-surface-container-lowest p-10 rounded-2xl">
      <div className="flex justify-between items-start mb-10">
        <div>
          <h2 className="text-2xl font-editorial font-semibold tracking-tight text-on-surface mb-1">
            GitLab Configuration
          </h2>
          <p className="text-sm text-on-surface-variant">
            Configure the repository provider for DORA metric extraction.
          </p>
        </div>
        <div className="flex items-center gap-2 bg-surface-container px-4 py-1.5 rounded-full">
          <span className="material-symbols-outlined text-primary text-sm leading-none">
            account_tree
          </span>
          <span className="text-xs font-editorial font-bold uppercase tracking-wider text-on-surface-variant">
            GitLab
          </span>
        </div>
      </div>

      <div className="space-y-8">
        <TextInput
          id="gitlab_url"
          label="Instance URL"
          value={v("gitlab_url")}
          placeholder="https://gitlab.company.com"
          onChange={(val) => onPatch({ gitlab_url: val })}
        />

        <SecretInput
          id="gitlab_token"
          label="Personal Access Token"
          hint={config.gitlab_token_hint ?? null}
          helpText="Requires 'api', 'read_repository', and 'read_user' scopes."
          onChange={(val) => {
            if (val) onPatch({ gitlab_token: val });
            else {
              const next = { ...patch };
              delete next.gitlab_token;
              onPatch(next);
            }
          }}
        />

        <TagListInput
          id="gitlab_project_paths"
          label="Project Paths"
          values={
            (patch.gitlab_project_paths ?? config.gitlab_project_paths) as string[]
          }
          helpText="One path per line, e.g. group/project-name"
          onChange={(vals) => onPatch({ gitlab_project_paths: vals })}
        />

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <TagListInput
            id="target_branches"
            label="Target Branches"
            values={
              (patch.target_branches ?? config.target_branches) as string[]
            }
            helpText="Branches tracked for deployment frequency"
            onChange={(vals) => onPatch({ target_branches: vals })}
          />
          <TagListInput
            id="non_customer_release_markers"
            label="Pre-release Markers"
            values={
              (patch.non_customer_release_markers ??
                config.non_customer_release_markers) as string[]
            }
            helpText="Tag suffixes excluded from customer release metrics"
            onChange={(vals) => onPatch({ non_customer_release_markers: vals })}
          />
        </div>
      </div>
    </section>
  );
}
