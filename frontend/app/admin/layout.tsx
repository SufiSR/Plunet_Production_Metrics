import { ReactNode } from "react";
import { AdminSidebar } from "@/app/components/admin/AdminSidebar";

type AdminLayoutProps = {
  children: ReactNode;
};

export default function AdminLayout({ children }: AdminLayoutProps) {
  return (
    <div className="bg-background text-on-background min-h-screen flex">
      <AdminSidebar />
      <main className="ml-64 flex-1 min-h-screen overflow-y-auto">
        {children}
      </main>
    </div>
  );
}
