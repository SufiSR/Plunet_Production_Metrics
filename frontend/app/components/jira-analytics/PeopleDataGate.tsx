"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface PeopleDataGateProps {
  restricted?: boolean;
  title?: string;
  description?: string;
  children?: React.ReactNode;
}

export function PeopleDataGate({
  restricted,
  title = "Individual data is restricted",
  description = "Sign in with a people-data account to view names and person-level hours.",
  children,
}: PeopleDataGateProps) {
  const pathname = usePathname();
  if (!restricted) return <>{children}</>;
  const href = `/analytics/login?next=${encodeURIComponent(pathname || "/analytics")}`;
  return (
    <div className="rounded-xl border border-outline-variant/30 bg-surface-container-low px-4 py-4">
      <h3 className="font-editorial text-base font-semibold text-on-surface">{title}</h3>
      <p className="mt-1 text-sm text-on-surface-variant">{description}</p>
      <Link
        href={href}
        className="mt-3 inline-flex rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary hover:opacity-90"
      >
        Sign in
      </Link>
    </div>
  );
}
