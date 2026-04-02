"use client";

import type { AdminConfigResponse, AdminConfigPatch } from "@/types/admin";

interface WebhookConfigSectionProps {
  config: AdminConfigResponse;
  patch: AdminConfigPatch;
  onPatch: (updates: AdminConfigPatch) => void;
}

export function WebhookConfigSection({
  config,
  patch,
  onPatch,
}: WebhookConfigSectionProps) {
  const url =
    patch.notifications_webhook_url !== undefined
      ? (patch.notifications_webhook_url ?? "")
      : (config.notifications_webhook_url ?? "");

  return (
    <section className="bg-surface-container-low p-8 rounded-2xl">
      <div className="flex items-start gap-6">
        <div className="w-12 h-12 bg-surface-container-lowest rounded-xl flex items-center justify-center shrink-0 shadow-sm">
          <span className="material-symbols-outlined text-primary text-2xl leading-none">
            webhook
          </span>
        </div>
        <div className="flex-1 min-w-0">
          <h2 className="text-lg font-editorial font-bold tracking-tight text-on-surface mb-1">
            Notifications Webhook
          </h2>
          <p className="text-sm text-on-surface-variant mb-6">
            Optional URL to receive sync completion and failure notifications.
          </p>
          <div className="space-y-2">
            <label
              htmlFor="notifications_webhook_url"
              className="text-[10px] font-editorial font-bold uppercase tracking-[0.1em] text-outline px-1 block"
            >
              Webhook URL
            </label>
            <input
              id="notifications_webhook_url"
              type="url"
              value={url}
              onChange={(e) =>
                onPatch({
                  notifications_webhook_url: e.target.value || null,
                })
              }
              placeholder="https://hooks.slack.com/services/…"
              className="w-full px-4 py-3 bg-surface-container border-b-2 border-transparent focus:bg-surface-container-lowest focus:border-primary focus:outline-none transition-all font-body text-sm text-on-surface placeholder:text-outline"
            />
          </div>
        </div>
      </div>
    </section>
  );
}
