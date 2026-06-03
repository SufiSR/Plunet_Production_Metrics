"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAnalyticsEmbedStyle } from "@/app/components/jira-analytics/AnalyticsEmbedStyleProvider";
import { SiteFooter } from "@/app/components/SiteFooter";
import { ThemeToggle } from "@/app/components/ui/ThemeToggle";
import { ReportMethodologyPanel } from "@/app/components/jira-analytics/ReportMethodologyPanel";
import { appendAnalyticsEmbedStyle } from "@/lib/analytics-embed-style";
import { getMethodologyByPath } from "@/lib/jira-analytics-methodology";
import { JIRA_ANALYTICS_SECTIONS } from "@/lib/jira-analytics-nav";

interface JiraAnalyticsShellProps {
  title: string;
  description?: string;
  children: React.ReactNode;
  hidePageHeader?: boolean;
  hideMethodology?: boolean;
}

export function JiraAnalyticsShell({
  title,
  description,
  children,
  hidePageHeader = false,
  hideMethodology = false,
}: JiraAnalyticsShellProps) {
  const pathname = usePathname();
  const isEmbed = useAnalyticsEmbedStyle();
  const methodology = getMethodologyByPath(pathname);
  const navHref = (href: string) => (isEmbed ? appendAnalyticsEmbedStyle(href) : href);

  return (
    <div
      className="bg-background text-on-background min-h-screen flex flex-col"
      data-analytics-embed={isEmbed ? "" : undefined}
    >
      {!isEmbed ? (
        <header className="bg-surface-container-lowest/95 backdrop-blur-xl w-full top-0 sticky z-50 border-b border-outline-variant/25 dark:bg-surface-container/95 dark:border-outline-variant/45">
          <div className="flex items-center justify-between px-6 py-3 w-full max-w-[1600px] mx-auto gap-4">
            <div className="flex items-center min-w-0">
              <Link
                href={navHref("/analytics")}
                className="text-xl font-editorial font-bold tracking-tighter text-primary select-none hover:opacity-80 shrink-0"
              >
                Plunet Metrics - Production
              </Link>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <ThemeToggle />
            </div>
          </div>
          <nav
            className="border-t border-outline-variant/20 overflow-x-auto"
            aria-label="Analytics sections"
          >
            <div className="flex gap-1 px-4 py-2 max-w-[1600px] mx-auto">
              <Link
                href={navHref("/analytics")}
                className={`text-xs font-label px-3 py-1.5 rounded-full whitespace-nowrap ${
                  pathname === "/analytics"
                    ? "bg-primary/15 text-primary"
                    : "text-on-surface-variant hover:text-primary"
                }`}
              >
                Overview
              </Link>
              {JIRA_ANALYTICS_SECTIONS.map((section) => {
                const active = section.reports.some(
                  (r) => pathname === r.href || pathname.startsWith(`${r.href}/`),
                );
                const firstHref = section.reports[0]?.href ?? "/analytics";
                return (
                  <Link
                    key={section.id}
                    href={navHref(firstHref)}
                    className={`text-xs font-label px-3 py-1.5 rounded-full whitespace-nowrap ${
                      active ? "bg-primary/15 text-primary" : "text-on-surface-variant hover:text-primary"
                    }`}
                  >
                    {section.label}
                  </Link>
                );
              })}
              <Link
                href="/admin"
                className="text-xs font-label px-3 py-1.5 rounded-full whitespace-nowrap text-on-surface-variant hover:text-primary"
              >
                Admin
              </Link>
            </div>
          </nav>
        </header>
      ) : null}

      <main
        className={`max-w-[1600px] mx-auto flex-1 w-full space-y-6 ${
          isEmbed ? "px-4 py-4 md:px-5" : "px-6 py-8 md:px-8"
        }`}
      >
        {!hidePageHeader ? (
          <div className="space-y-2">
            <h1 className="text-2xl font-editorial font-bold text-on-surface">{title}</h1>
            {description ? (
              <p className="text-sm text-on-surface-variant max-w-3xl">{description}</p>
            ) : null}
          </div>
        ) : null}
        {!hideMethodology && methodology ? <ReportMethodologyPanel methodology={methodology} /> : null}
        {children}
      </main>
      {!isEmbed ? <SiteFooter /> : null}
    </div>
  );
}
