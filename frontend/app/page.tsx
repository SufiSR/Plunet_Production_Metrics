import { HeaderBar } from "./components/header/HeaderBar";
import { MetricGrid } from "./components/dashboard/MetricGrid";
import { TrendOverviewSection } from "./components/dashboard/TrendOverviewSection";
import { StaleBanner } from "./components/dashboard/StaleBanner";
import { MetricModal } from "./components/dashboard/MetricModal";
import { SiteFooter } from "./components/SiteFooter";
import { PeriodSelector } from "./components/header/PeriodSelector";

export default function HomePage() {
  return (
    <div className="bg-background text-on-background min-h-screen flex flex-col">
      <HeaderBar />
      <main className="max-w-[1440px] mx-auto px-6 py-8 md:px-8 space-y-10 flex-1 w-full">
        <div className="space-y-4">
          <div className="flex justify-end">
            <PeriodSelector />
          </div>
          <StaleBanner />
        </div>
        <MetricGrid />
        <TrendOverviewSection />
      </main>
      <SiteFooter />
      <MetricModal />
    </div>
  );
}
