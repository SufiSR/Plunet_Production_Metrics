"use client";

import { GitLabConfigSection } from "@/app/components/admin/GitLabConfigSection";
import { JiraConfigSection } from "@/app/components/admin/JiraConfigSection";
import Link from "next/link";
import { WebhookConfigSection } from "@/app/components/admin/WebhookConfigSection";
import { UnsavedToast } from "@/app/components/admin/UnsavedToast";
import { AdminConfigAlerts } from "@/app/components/admin-new/AdminConfigAlerts";
import { AdminConfigLoading } from "@/app/components/admin-new/AdminConfigLoading";
import { AdminNewPageHeader } from "@/app/components/admin-new/AdminNewPageHeader";
import { DoraPipelineRunPanel } from "@/app/components/admin-new/DoraPipelineRunPanel";
import { useAdminConfigForm } from "@/lib/hooks/use-admin-config-form";
import { useAdminSession } from "@/lib/hooks/use-admin-session";

export default function AdminNewDoraIngestionPage() {
  const { ready } = useAdminSession("/admin/ingestion/dora");
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
        eyebrow="Ingestion"
        title="DORA nightly pipeline"
        description="GitLab and Jira collection for DORA metrics, cross-system linking, snapshots, and completion webhooks. Credentials are on the Secrets page."
      />

      <AdminConfigAlerts saveState={saveState} saveError={saveError} />

      <p className="text-sm text-on-surface-variant -mt-4 mb-6">
        Nightly schedule and DORA lookback:{" "}
        <Link href="/admin/schedulers" className="text-primary hover:underline">
          Schedulers
        </Link>
        .
      </p>

      <div className="space-y-8 mb-10">
        <DoraPipelineRunPanel />
        <GitLabConfigSection config={config} patch={patch} onPatch={handlePatch} mode="rules" />
        <JiraConfigSection config={config} patch={patch} onPatch={handlePatch} mode="rules" />
        <WebhookConfigSection config={config} patch={patch} onPatch={handlePatch} />
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
