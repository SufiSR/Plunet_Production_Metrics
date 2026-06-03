"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ADMIN_NEW_NAV_GROUPS } from "@/lib/admin-new-nav";
import { adminApiClient } from "@/lib/admin-api-client";
import { ThemeToggle } from "@/app/components/ui/ThemeToggle";

function isActive(pathname: string | null, href: string): boolean {
  if (!pathname) return false;
  if (href === "/admin") return pathname === "/admin";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AdminNewSidebar() {
  const pathname = usePathname();
  const router = useRouter();

  async function handleLogout() {
    try {
      await adminApiClient.logout();
    } catch {
      // ignore
    }
    router.push("/admin/login");
  }

  return (
    <aside className="h-screen w-64 fixed left-0 top-0 bg-surface-container-lowest flex flex-col z-50 border-r border-outline-variant/25 shadow-sm">
      <div className="px-6 py-6 mb-2">
        <div className="text-primary font-editorial font-bold text-xl tracking-tighter select-none">
          Plunet Metrics
        </div>
        <div className="text-on-surface font-editorial text-sm font-medium mt-1">Admin Console</div>
      </div>

      <nav className="flex-1 px-3 overflow-y-auto space-y-6">
        {ADMIN_NEW_NAV_GROUPS.map((group) => (
          <div key={group.id}>
            <p className="px-4 mb-1 text-[10px] font-editorial font-bold uppercase tracking-widest text-outline">
              {group.label}
            </p>
            <div className="space-y-1">
              {group.items.map(({ href, icon, label }) => {
                const active = isActive(pathname, href);
                return (
                  <Link
                    key={href}
                    href={href}
                    className={[
                      "flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-editorial font-medium transition-colors",
                      active
                        ? "bg-surface-container text-primary"
                        : "text-on-surface-variant hover:bg-surface-container hover:text-on-surface",
                    ].join(" ")}
                  >
                    <span className="material-symbols-outlined text-xl leading-none">{icon}</span>
                    {label}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="px-3 pb-6 space-y-1">
        <div className="flex items-center justify-between px-4 py-2">
          <span className="text-[10px] font-editorial uppercase tracking-widest text-outline">Theme</span>
          <ThemeToggle />
        </div>
        <button
          type="button"
          onClick={() => void handleLogout()}
          className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-editorial font-medium text-on-surface-variant hover:bg-surface-container hover:text-error transition-colors"
        >
          <span className="material-symbols-outlined text-xl leading-none">logout</span>
          Logout
        </button>
      </div>
    </aside>
  );
}
