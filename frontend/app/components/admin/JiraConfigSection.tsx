"use client";

import type { AdminConfigResponse, AdminConfigPatch } from "@/types/admin";
import { SecretInput } from "./SecretInput";
import { TagListInput } from "./TagListInput";

export type JiraConfigSectionMode = "full" | "secrets" | "rules";

interface JiraConfigSectionProps {
  config: AdminConfigResponse;
  patch: AdminConfigPatch;
  onPatch: (updates: AdminConfigPatch) => void;
  mode?: JiraConfigSectionMode;
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

export function JiraConfigSection({
  config,
  patch,
  onPatch,
  mode = "full",
}: JiraConfigSectionProps) {
  const v = (key: keyof AdminConfigResponse) =>
    (patch[key as keyof AdminConfigPatch] ?? config[key]) as string;
  const showSecrets = mode === "full" || mode === "secrets";
  const showRules = mode === "full" || mode === "rules";

  return (
    <section className="bg-surface-container-lowest p-10 rounded-2xl">
      <div className="flex justify-between items-start mb-10">
        <div>
          <h2 className="text-2xl font-editorial font-semibold tracking-tight text-on-surface mb-1">
            Jira {mode === "secrets" ? "connection" : "configuration"}
          </h2>
          <p className="text-sm text-on-surface-variant">
            {mode === "secrets"
              ? "Shared by the DORA Jira collector and Jira Analytics ingestion."
              : mode === "rules"
                ? "Query filters and custom fields for DORA metrics (CFR, MTTR, lead time)."
                : "Connect your Jira instance for bug tracking and worklog data."}
          </p>
        </div>
        <div className="flex items-center gap-2 bg-surface-container px-4 py-1.5 rounded-full">
          <span className="material-symbols-outlined text-primary text-sm leading-none">
            task_alt
          </span>
          <span className="text-xs font-editorial font-bold uppercase tracking-wider text-on-surface-variant">
            Jira
          </span>
        </div>
      </div>

      <div className="space-y-8">
        {showSecrets ? (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <TextInput
                id="jira_url"
                label="Instance URL"
                value={v("jira_url")}
                placeholder="https://company.atlassian.net"
                onChange={(val) => onPatch({ jira_url: val })}
              />
              <TextInput
                id="jira_username"
                label="Username / Email"
                value={v("jira_username")}
                placeholder="user@company.com"
                onChange={(val) => onPatch({ jira_username: val })}
              />
            </div>

            <SecretInput
              id="jira_token"
              label="API Token"
              hint={config.jira_token_hint ?? null}
              helpText="Generate at id.atlassian.com → Security → API tokens."
              onChange={(val) => {
                if (val) onPatch({ jira_token: val });
                else {
                  const next = { ...patch };
                  delete next.jira_token;
                  onPatch(next);
                }
              }}
            />
          </>
        ) : null}

        {showRules ? (
          <>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <TagListInput
            id="excluded_projects"
            label="Excluded Projects"
            values={
              (patch.excluded_projects ?? config.excluded_projects) as string[]
            }
            helpText="Project keys to exclude from all Jira queries"
            onChange={(vals) => onPatch({ excluded_projects: vals })}
          />
          <TagListInput
            id="ready_for_qa_status_names"
            label="Ready-for-QA Status Names"
            values={
              (patch.ready_for_qa_status_names ??
                config.ready_for_qa_status_names) as string[]
            }
            helpText="Jira status names that mark an issue as ready for QA"
            onChange={(vals) => onPatch({ ready_for_qa_status_names: vals })}
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <TagListInput
            id="production_bug_indicator_cf_ids"
            label="Production Bug CF IDs"
            values={
              (patch.production_bug_indicator_cf_ids ??
                config.production_bug_indicator_cf_ids) as string[]
            }
            helpText="Custom field IDs that indicate a production bug"
            onChange={(vals) =>
              onPatch({ production_bug_indicator_cf_ids: vals })
            }
          />
          <TagListInput
            id="mttr_alpha_priorities"
            label="MTTR Alpha Priorities"
            values={
              (patch.mttr_alpha_priorities ??
                config.mttr_alpha_priorities) as string[]
            }
            helpText="Jira priority names counted in MTTR Alpha calculation"
            onChange={(vals) => onPatch({ mttr_alpha_priorities: vals })}
          />
        </div>
          </>
        ) : null}
      </div>
    </section>
  );
}
