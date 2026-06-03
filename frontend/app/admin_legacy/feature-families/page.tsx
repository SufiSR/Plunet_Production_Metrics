"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useRouter } from "next/navigation";
import { adminApiClient } from "@/lib/admin-api-client";
import type {
  FeatureFamilyAdminItem,
  FeatureFamilyDetailResponse,
  FeatureFamilyFeatureItem,
  FeatureFamilySuggestionItem,
} from "@/types/admin";

interface FamilyDraft {
  name: string;
  description: string;
  matchTerms: string;
  active: boolean;
}

function emptyDraft(): FamilyDraft {
  return { name: "", description: "", matchTerms: "", active: true };
}

function draftFromFamily(family: FeatureFamilyAdminItem): FamilyDraft {
  return {
    name: family.name,
    description: family.description ?? "",
    matchTerms: [
      ...family.suggestion_keywords,
      ...(family.title_match_pattern ? [family.title_match_pattern] : []),
    ].join(", "),
    active: family.active,
  };
}

function termsFromDraft(value: string): string[] {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function formatDate(value: string | null): string {
  return value ?? "-";
}

export default function FeatureFamiliesAdminPage() {
  const router = useRouter();
  const [loaded, setLoaded] = useState(false);
  const [families, setFamilies] = useState<FeatureFamilyAdminItem[]>([]);
  const [features, setFeatures] = useState<FeatureFamilyFeatureItem[]>([]);
  const [suggestions, setSuggestions] = useState<FeatureFamilySuggestionItem[]>([]);
  const [selectedFamilyId, setSelectedFamilyId] = useState<number | null>(null);
  const [detail, setDetail] = useState<FeatureFamilyDetailResponse | null>(null);
  const [draft, setDraft] = useState<FamilyDraft>(() => emptyDraft());
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadDetail = useCallback(async (familyId: number) => {
    const nextDetail = await adminApiClient.getFeatureFamily(familyId);
    setDetail(nextDetail);
    setDraft(draftFromFamily(nextDetail.family));
    return nextDetail;
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedFamilyId(null);
    setDetail(null);
    setDraft(emptyDraft());
  }, []);

  const loadLists = useCallback(async () => {
    const [familyResp, featureResp, suggestionResp] = await Promise.all([
      adminApiClient.getFeatureFamilies(),
      adminApiClient.getFeatureFamilyFeatures({
        search: search || undefined,
        unassigned_only: true,
      }),
      adminApiClient.getFeatureFamilySuggestions(),
    ]);
    setFamilies(familyResp.items);
    setFeatures(featureResp.items);
    setSuggestions(suggestionResp.items);
    return familyResp.items;
  }, [search]);

  const reload = useCallback(async () => {
    const nextFamilies = await loadLists();
    if (selectedFamilyId) {
      const stillExists = nextFamilies.some((family) => family.id === selectedFamilyId);
      if (stillExists) {
        await loadDetail(selectedFamilyId);
      } else {
        clearSelection();
      }
    }
  }, [clearSelection, loadDetail, loadLists, selectedFamilyId]);

  useEffect(() => {
    (async () => {
      try {
        const me = await adminApiClient.me();
        if (me.role !== "admin") {
          router.push("/admin/login");
          return;
        }
        await reload();
        setLoaded(true);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load feature families");
        router.push("/admin/login");
      }
    })();
  }, [reload, router]);

  const selectFamily = useCallback(async (familyId: number) => {
    setError(null);
    setStatus(null);
    setSelectedFamilyId(familyId);
    await loadDetail(familyId);
  }, [loadDetail]);

  const startNewFamily = useCallback(() => {
    clearSelection();
    setStatus(null);
    setError(null);
  }, [clearSelection]);

  const saveFamily = useCallback(async () => {
    setError(null);
    setStatus("Saving family...");
    try {
      const body = {
        name: draft.name.trim(),
        description: draft.description.trim() || null,
        suggestion_keywords: termsFromDraft(draft.matchTerms),
        title_match_pattern: null,
      };
      if (selectedFamilyId) {
        await adminApiClient.patchFeatureFamily(selectedFamilyId, { ...body, active: draft.active });
      } else {
        await adminApiClient.createFeatureFamily(body);
      }
      clearSelection();
      await loadLists();
      setStatus("Saved. No family is selected.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
      setStatus(null);
    }
  }, [clearSelection, draft, loadLists, selectedFamilyId]);

  const assignFeature = useCallback(async (featureId: number) => {
    if (!detail) return;
    setError(null);
    setStatus("Assigning feature...");
    try {
      const featureRootIds = [
        ...detail.members.map((item) => item.feature_root_id),
        featureId,
      ];
      const nextDetail = await adminApiClient.putFeatureFamilyMembers(detail.family.id, {
        feature_root_ids: featureRootIds,
      });
      setDetail(nextDetail);
      setDraft(draftFromFamily(nextDetail.family));
      await reload();
      setStatus("Feature assigned.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Assignment failed");
      setStatus(null);
    }
  }, [detail, reload]);

  const removeFeature = useCallback(async (featureId: number) => {
    if (!detail) return;
    setError(null);
    setStatus("Removing feature...");
    try {
      const nextDetail = await adminApiClient.putFeatureFamilyMembers(detail.family.id, {
        feature_root_ids: detail.members
          .filter((item) => item.feature_root_id !== featureId)
          .map((item) => item.feature_root_id),
      });
      setDetail(nextDetail);
      setDraft(draftFromFamily(nextDetail.family));
      await reload();
      setStatus("Feature removed.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Remove failed");
      setStatus(null);
    }
  }, [detail, reload]);

  const acceptSuggestion = useCallback(async (suggestion: FeatureFamilySuggestionItem) => {
    setError(null);
    setStatus("Accepting suggestion...");
    try {
      const nextDetail = await adminApiClient.acceptFeatureFamilySuggestion(suggestion.suggestion_id);
      setSelectedFamilyId(nextDetail.family.id);
      setDetail(nextDetail);
      setDraft(draftFromFamily(nextDetail.family));
      await reload();
      setStatus("Suggestion accepted.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Accept failed");
      setStatus(null);
    }
  }, [reload]);

  const rejectSuggestion = useCallback(async (suggestion: FeatureFamilySuggestionItem) => {
    setError(null);
    setStatus("Rejecting suggestion...");
    try {
      const response = await adminApiClient.rejectFeatureFamilySuggestion(suggestion.suggestion_id);
      setSuggestions(response.items);
      setStatus("Suggestion rejected.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reject failed");
      setStatus(null);
    }
  }, []);

  const createFromSuggestion = useCallback(async (suggestion: FeatureFamilySuggestionItem) => {
    setError(null);
    setStatus("Creating family...");
    try {
      const created = await adminApiClient.createFeatureFamily({
        name: suggestion.feature_name,
        suggestion_keywords: suggestion.matched_tokens,
      });
      await adminApiClient.putFeatureFamilyMembers(created.family.id, {
        feature_root_ids: [suggestion.feature_root_id],
      });
      clearSelection();
      await loadLists();
      setStatus("Family created. No family is selected.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
      setStatus(null);
    }
  }, [clearSelection, loadLists]);

  const addSuggestionToSelected = useCallback(async (suggestion: FeatureFamilySuggestionItem) => {
    if (!detail) return;
    await assignFeature(suggestion.feature_root_id);
    await adminApiClient.rejectFeatureFamilySuggestion(suggestion.suggestion_id, "assigned manually");
    await reload();
  }, [assignFeature, detail, reload]);

  const visibleFeatures = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return features;
    return features.filter((feature) =>
      `${feature.root_key} ${feature.name} ${feature.team_name ?? ""}`.toLowerCase().includes(q),
    );
  }, [features, search]);

  if (!loaded) {
    return (
      <main className="pl-72 pr-10 py-10 text-on-surface-variant text-sm font-editorial">
        {error ?? "Loading..."}
      </main>
    );
  }

  return (
    <div className="w-full pb-24 space-y-8">
      <header className="space-y-3">
        <p className="text-[10px] font-editorial font-bold uppercase tracking-[0.1em] text-primary">
          Jira Analytics
        </p>
        <h1 className="text-5xl font-editorial font-bold tracking-tight text-on-surface">
          Feature families
        </h1>
        <p className="text-on-surface-variant text-sm max-w-3xl">
          Manage families, assign unassigned PMGT features, and review title-based suggestions.
        </p>
      </header>

      {status ? <p className="text-xs text-secondary">{status}</p> : null}
      {error ? <p className="text-xs text-error">{error}</p> : null}

      <section className="grid grid-cols-1 gap-6 2xl:grid-cols-[380px_minmax(360px,1fr)_minmax(360px,1fr)]">
        <Pane title="Families">
          <div className="flex justify-end">
            <button
              type="button"
              onClick={startNewFamily}
              className="px-3 py-2 rounded-lg bg-primary text-on-primary text-xs font-bold uppercase"
            >
              New family
            </button>
          </div>
          <div className="max-h-[24vh] space-y-2 overflow-y-auto pr-1">
            {families.map((family) => (
              <button
                key={family.id}
                type="button"
                onClick={() => void selectFamily(family.id)}
                className={[
                  "w-full rounded-xl border px-4 py-3 text-left transition-colors",
                  selectedFamilyId === family.id
                    ? "border-primary bg-primary-container/20"
                    : "border-outline-variant/40 hover:bg-surface-container-low",
                ].join(" ")}
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-on-surface">{family.name}</span>
                  <span className="text-xs text-on-surface-variant">{family.member_count}</span>
                </span>
                <span className="mt-1 block text-xs text-on-surface-variant">
                  {family.active ? "Active" : "Archived"}
                </span>
              </button>
            ))}
          </div>

          {detail ? (
            <div className="space-y-2 rounded-xl border border-outline-variant/30 bg-surface-container-low p-3">
              <h3 className="text-sm font-semibold text-on-surface">
                {detail.family.name} features
              </h3>
              <div className="max-h-[28vh] space-y-2 overflow-y-auto pr-1">
                {detail.members.map((feature) => (
                  <div
                    key={feature.feature_root_id}
                    className="flex items-start justify-between gap-2 rounded-lg bg-surface-container-lowest px-3 py-2"
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-on-surface">{feature.name}</div>
                      <div className="text-xs text-on-surface-variant">{feature.root_key}</div>
                    </div>
                    <button
                      type="button"
                      onClick={() => void removeFeature(feature.feature_root_id)}
                      className="rounded-md px-2 py-1 text-xs font-semibold text-error hover:bg-error-container/20"
                    >
                      Remove
                    </button>
                  </div>
                ))}
                {detail.members.length === 0 ? (
                  <p className="text-xs text-on-surface-variant">No features assigned.</p>
                ) : null}
              </div>
            </div>
          ) : null}

          <div className="space-y-3 rounded-xl border border-outline-variant/30 bg-surface-container-low p-3">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-on-surface">
                {detail ? "Edit family" : "Create family"}
              </h3>
              <button
                type="button"
                onClick={() => void saveFamily()}
                disabled={!draft.name.trim()}
                className="px-4 py-2 rounded-xl bg-primary text-on-primary text-xs font-bold uppercase disabled:opacity-50"
              >
                Save
              </button>
            </div>
            <TextInput
              label="Name"
              value={draft.name}
              onChange={(value) => setDraft((prev) => ({ ...prev, name: value }))}
            />
            <label className="space-y-1 text-xs text-on-surface-variant">
              <span>Description</span>
              <textarea
                value={draft.description}
                onChange={(event) => setDraft((prev) => ({ ...prev, description: event.target.value }))}
                className="w-full rounded-lg border border-outline-variant bg-surface px-3 py-2 text-on-surface"
                rows={2}
              />
            </label>
            <TextInput
              label="Suggestion terms"
              value={draft.matchTerms}
              placeholder="invoice, import, portal"
              help="Comma-separated terms used to suggest unassigned features by title."
              onChange={(value) => setDraft((prev) => ({ ...prev, matchTerms: value }))}
            />
            <label className="flex items-center gap-2 text-xs text-on-surface-variant">
              <input
                type="checkbox"
                checked={draft.active}
                onChange={(event) => setDraft((prev) => ({ ...prev, active: event.target.checked }))}
              />
              Active family
            </label>
          </div>
        </Pane>

        <Pane
          title="Unassigned Features"
          subtitle="Select a family first, then add features from this list."
        >
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search title, key, or team"
            className="w-full rounded-lg border border-outline-variant bg-surface px-3 py-2 text-sm text-on-surface"
          />
          <div className="max-h-[70vh] space-y-2 overflow-y-auto pr-1">
            {visibleFeatures.map((feature) => (
              <FeatureCard
                key={feature.feature_root_id}
                feature={feature}
                action={
                  <button
                    type="button"
                    disabled={!detail}
                    onClick={() => void assignFeature(feature.feature_root_id)}
                    className="rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-on-primary disabled:opacity-40"
                  >
                    Add
                  </button>
                }
              />
            ))}
            {visibleFeatures.length === 0 ? (
              <EmptyState>No unassigned features match the current search.</EmptyState>
            ) : null}
          </div>
        </Pane>

        <Pane
          title="Suggestions"
          subtitle="Only unassigned features are suggested. Accept, reject, or add to the selected family."
        >
          <div className="max-h-[78vh] space-y-2 overflow-y-auto pr-1">
            {suggestions.map((suggestion) => (
              <div
                key={suggestion.suggestion_id}
                className="rounded-xl border border-outline-variant/20 bg-surface-container-low p-3"
              >
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-on-surface">
                    {suggestion.feature_name}
                  </div>
                  <div className="text-xs text-on-surface-variant">
                    {suggestion.root_key} {"->"} {suggestion.family_name}
                  </div>
                  <div className="mt-1 text-xs text-on-surface-variant">
                    {suggestion.reason} · {Math.round(suggestion.confidence * 100)}%
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => void acceptSuggestion(suggestion)}
                    className="px-3 py-1.5 rounded-lg bg-primary text-on-primary text-xs font-semibold"
                  >
                    Accept
                  </button>
                  <button
                    type="button"
                    disabled={!detail}
                    onClick={() => void addSuggestionToSelected(suggestion)}
                    className="px-3 py-1.5 rounded-lg border border-outline-variant text-xs font-semibold disabled:opacity-40"
                  >
                    Add selected
                  </button>
                  <button
                    type="button"
                    onClick={() => void createFromSuggestion(suggestion)}
                    className="px-3 py-1.5 rounded-lg border border-outline-variant text-xs font-semibold"
                  >
                    New family
                  </button>
                  <button
                    type="button"
                    onClick={() => void rejectSuggestion(suggestion)}
                    className="px-3 py-1.5 rounded-lg border border-outline-variant text-xs font-semibold text-error"
                  >
                    Reject
                  </button>
                </div>
              </div>
            ))}
            {suggestions.length === 0 ? (
              <EmptyState>No suggestions waiting for review.</EmptyState>
            ) : null}
          </div>
        </Pane>
      </section>
    </div>
  );
}

function Pane({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-2xl bg-surface-container-lowest p-5 border border-outline-variant space-y-4">
      <div>
        <h2 className="text-xl font-editorial font-semibold text-on-surface">{title}</h2>
        {subtitle ? <p className="text-sm text-on-surface-variant">{subtitle}</p> : null}
      </div>
      {children}
    </section>
  );
}

function TextInput({
  label,
  value,
  placeholder,
  help,
  onChange,
}: {
  label: string;
  value: string;
  placeholder?: string;
  help?: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="space-y-1 text-xs text-on-surface-variant">
      <span>{label}</span>
      <input
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-lg border border-outline-variant bg-surface px-3 py-2 text-on-surface"
      />
      {help ? <span className="block text-[11px] leading-4">{help}</span> : null}
    </label>
  );
}

function FeatureCard({
  feature,
  action,
}: {
  feature: FeatureFamilyFeatureItem;
  action: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-outline-variant/20 bg-surface-container-low p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-on-surface">{feature.name}</div>
          <div className="text-xs text-on-surface-variant">
            {feature.root_key} · {feature.team_name ?? "No team"} · {feature.delivery_progress ?? "No progress"}
          </div>
          <div className="text-xs text-on-surface-variant">
            {formatDate(feature.start_date)} {"->"} {formatDate(feature.target_end_date)}
          </div>
        </div>
        <div className="shrink-0">{action}</div>
      </div>
    </div>
  );
}

function EmptyState({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-xl border border-dashed border-outline-variant/30 p-6 text-center text-sm text-on-surface-variant">
      {children}
    </p>
  );
}
