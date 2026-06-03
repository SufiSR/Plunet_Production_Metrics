"use client";

import { UnsavedToast } from "@/app/components/admin/UnsavedToast";
import { AdminConfigAlerts } from "@/app/components/admin-new/AdminConfigAlerts";
import { AdminConfigLoading } from "@/app/components/admin-new/AdminConfigLoading";
import { AdminNewPageHeader } from "@/app/components/admin-new/AdminNewPageHeader";
import { SchedulersSettingsSection } from "@/app/components/admin-new/SchedulersSettingsSection";
import { useAdminConfigForm } from "@/lib/hooks/use-admin-config-form";
import { useAdminSession } from "@/lib/hooks/use-admin-session";

export default function AdminNewSchedulersPage() {
  const { ready } = useAdminSession("/admin/schedulers");
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
        eyebrow="Operations"
        title="Schedulers"
        description="All automated ingestion schedules in one place. Times are UTC. Saving applies changes to the running scheduler when the backend is up."
      />

      <AdminConfigAlerts saveState={saveState} saveError={saveError} />

      <SchedulersSettingsSection config={config} patch={patch} onPatch={handlePatch} />

      <UnsavedToast
        count={unsavedCount}
        onDiscard={handleDiscard}
        onSave={() => void handleSave()}
        isSaving={saveState === "saving"}
      />
    </div>
  );
}
