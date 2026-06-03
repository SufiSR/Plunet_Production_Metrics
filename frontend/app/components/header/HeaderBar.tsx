"use client";

import Link from "next/link";
import { SyncStatusPill } from "./SyncStatusPill";
import { ThemeToggle } from "../ui/ThemeToggle";

export function HeaderBar() {
  return (
    <header className="bg-surface-container-lowest/80 backdrop-blur-xl w-full top-0 sticky z-50 border-b border-outline-variant/10 transition-colors duration-200 dark:bg-surface-container/95 dark:border-outline-variant/45">
      <div className="flex items-center justify-between px-6 py-3 w-full max-w-[1440px] mx-auto">
        {/* Left: Brand */}
        <div className="flex items-center">
          <span className="text-xl font-editorial font-bold tracking-tighter text-primary select-none">
            DORA Metrics
          </span>
        </div>

        {/* Right: Sync status + Theme toggle */}
        <div className="flex items-center gap-3">
          <Link
            href="/analytics"
            className="text-xs font-label text-on-surface-variant hover:text-primary whitespace-nowrap"
          >
            Jira Analytics
          </Link>
          <SyncStatusPill />
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
