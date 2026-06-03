"use client";

import { GitLabConfigSection } from "@/app/components/admin/GitLabConfigSection";
import { JiraConfigSection } from "@/app/components/admin/JiraConfigSection";
import { UnsavedToast } from "@/app/components/admin/UnsavedToast";
import { AdminConfigAlerts } from "@/app/components/admin-new/AdminConfigAlerts";
import { AdminConfigLoading } from "@/app/components/admin-new/AdminConfigLoading";
import { AdminNewPageHeader } from "@/app/components/admin-new/AdminNewPageHeader";
import { HrworksSecretsCard } from "@/app/components/admin-new/HrworksSecretsCard";
import { useAdminConfigForm } from "@/lib/hooks/use-admin-config-form";
import { useAdminSession } from "@/lib/hooks/use-admin-session";

export default function AdminNewSecretsPage() {
  const { ready } = useAdminSession("/admin/secrets");
  const {
    config,
    patch,
    loadError,
    saveState,
    saveError,
    unsavedCount,
    handlePatch,
    handleDiscard,
    handleSave,
  } = useAdminConfigForm();

  if (!ready) {
    return (
      <div className="flex items-center justify-center min-h-[40vh]">
        <div className="h-12 w-12 rounded-full border-4 border-primary/30 border-t-primary animate-spin" />
      </div>
    );
  }

  if (loadError) {
    return <p className="text-on-surface-variant">{loadError}</p>;
  }

  if (!config) {
    return <AdminConfigLoading />;
  }

  return (
    <div className="w-full pb-32">
      <AdminNewPageHeader
        eyebrow="Connections"
        title="Secrets & credentials"
        description="Authentication material only. Ingestion rules, schedules, and webhooks live under each pipeline page."
      />

      <AdminConfigAlerts saveState={saveState} saveError={saveError} />

      <div className="space-y-8">
        <GitLabConfigSection config={config} patch={patch} onPatch={handlePatch} mode="secrets" />
        <JiraConfigSection config={config} patch={patch} onPatch={handlePatch} mode="secrets" />
        <HrworksSecretsCard />
      </div>

      <UnsavedToast
        count={unsavedCount}
        onDiscard={handleDiscard}
        onSave={() => void handleSave()}
        isSaving={saveState === "saving"}
      />
    </div>
  );
}
