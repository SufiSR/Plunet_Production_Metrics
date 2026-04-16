import { HeaderBar } from "./components/header/HeaderBar";
import { MetricGrid } from "./components/dashboard/MetricGrid";
import { TrendOverviewSection } from "./components/dashboard/TrendOverviewSection";
import { StaleBanner } from "./components/dashboard/StaleBanner";
import { MetricModal } from "./components/dashboard/MetricModal";
import { LeadPostProductionTable } from "./components/dashboard/LeadPostProductionTable";

export default function HomePage() {
  return (
    <div className="bg-background text-on-background min-h-screen">
      <HeaderBar />
      <main className="max-w-[1440px] mx-auto px-6 py-8 md:px-8 space-y-10">
        <StaleBanner />
        <MetricGrid />
        <TrendOverviewSection />
        <LeadPostProductionTable />
      </main>
      <MetricModal />
    </div>
  );
}
