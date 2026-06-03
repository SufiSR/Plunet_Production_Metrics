import { ReactNode } from "react";
import { AdminSidebar } from "@/app/components/admin/AdminSidebar";
import { SiteFooter } from "@/app/components/SiteFooter";

type AdminLayoutProps = {
  children: ReactNode;
};

export default function AdminLayout({ children }: AdminLayoutProps) {
  return (
    <div className="bg-background text-on-background min-h-screen flex">
      <AdminSidebar />
      <div className="ml-64 flex-1 min-h-screen min-w-0 flex flex-col">
        <main className="flex-1 w-full max-w-[1440px] mx-auto px-6 py-8 md:px-8 overflow-y-auto">
          {children}
        </main>
        <SiteFooter />
      </div>
    </div>
  );
}
