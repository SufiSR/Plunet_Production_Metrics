"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { adminApiClient } from "@/lib/admin-api-client";
import { ThemeToggle } from "@/app/components/ui/ThemeToggle";

const NAV_ITEMS = [
  { href: "/admin/config", icon: "settings", label: "Configuration" },
];

export function AdminSidebar() {
  const pathname = usePathname();
  const router = useRouter();

  async function handleLogout() {
    try {
      await adminApiClient.logout();
    } catch {
      // ignore — redirect regardless
    }
    router.push("/admin/login");
  }

  return (
    <aside className="h-screen w-64 fixed left-0 top-0 bg-surface-container-lowest flex flex-col z-50">
      {/* Brand */}
      <div className="px-6 py-6 mb-2">
        <div className="text-primary font-editorial font-bold text-xl tracking-tighter select-none">
          Admin Console
        </div>
        <div className="text-on-surface-variant font-editorial text-[10px] uppercase tracking-widest mt-1">
          Editorial Engineering
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 space-y-1">
        {NAV_ITEMS.map(({ href, icon, label }) => {
          const isActive = pathname?.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={[
                "flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-editorial font-medium transition-colors",
                isActive
                  ? "bg-surface-container text-primary"
                  : "text-on-surface-variant hover:bg-surface-container hover:text-on-surface",
              ].join(" ")}
            >
              <span className="material-symbols-outlined text-xl leading-none">
                {icon}
              </span>
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Bottom actions */}
      <div className="px-3 pb-6 space-y-1">
        <div className="flex items-center justify-between px-4 py-2">
          <span className="text-[10px] font-editorial uppercase tracking-widest text-outline">
            Theme
          </span>
          <ThemeToggle />
        </div>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-editorial font-medium text-on-surface-variant hover:bg-surface-container hover:text-error transition-colors"
        >
          <span className="material-symbols-outlined text-xl leading-none">
            logout
          </span>
          Logout
        </button>
      </div>
    </aside>
  );
}
