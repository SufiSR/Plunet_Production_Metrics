"use client";

import { createContext, Suspense, useContext, type ReactNode } from "react";
import { useSearchParams } from "next/navigation";
import { isAnalyticsEmbedStyle } from "@/lib/analytics-embed-style";

const AnalyticsEmbedStyleContext = createContext(false);

function AnalyticsEmbedStyleProviderInner({ children }: { children: ReactNode }) {
  const searchParams = useSearchParams();
  const isEmbed = isAnalyticsEmbedStyle(searchParams);
  return (
    <AnalyticsEmbedStyleContext.Provider value={isEmbed}>{children}</AnalyticsEmbedStyleContext.Provider>
  );
}

export function AnalyticsEmbedStyleProvider({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={children}>
      <AnalyticsEmbedStyleProviderInner>{children}</AnalyticsEmbedStyleProviderInner>
    </Suspense>
  );
}

export function useAnalyticsEmbedStyle(): boolean {
  return useContext(AnalyticsEmbedStyleContext);
}
