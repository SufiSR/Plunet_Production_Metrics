"use client";

import { AnalyticsFilterPanel, FilterField, filterInputClassName } from "@/app/components/jira-analytics/AnalyticsReportControls";

interface FeatureHoursFiltersProps {
  months: number;
  role: string;
  team: string;
  availableRoles: string[];
  availableTeams: string[];
  onMonthsChange: (months: number) => void;
  onRoleChange: (role: string) => void;
  onTeamChange: (team: string) => void;
}

const ROLE_LABELS: Record<string, string> = {
  "": "All roles",
  pm: "PM",
  dev: "Development",
  qa: "QA",
  sup: "Support",
  unmapped: "Unmapped",
};

export function FeatureHoursFilters({
  months,
  role,
  team,
  availableRoles,
  availableTeams,
  onMonthsChange,
  onRoleChange,
  onTeamChange,
}: FeatureHoursFiltersProps) {
  return (
    <AnalyticsFilterPanel title="Filters" description="Tune the feature cost lens before drilling into rows.">
      <FilterField label="Months">
        <select
          className={filterInputClassName("min-w-[120px]")}
          value={months}
          onChange={(e) => onMonthsChange(Number(e.target.value))}
        >
          {[3, 6, 12, 18, 24].map((value) => (
            <option key={value} value={value}>
              Last {value} months
            </option>
          ))}
        </select>
      </FilterField>
      <FilterField label="Role">
        <select
          className={filterInputClassName("min-w-[160px]")}
          value={role}
          onChange={(e) => onRoleChange(e.target.value)}
        >
          <option value="">{ROLE_LABELS[""]}</option>
          {availableRoles.map((value) => (
            <option key={value} value={value}>
              {ROLE_LABELS[value] ?? value}
            </option>
          ))}
        </select>
      </FilterField>
      <FilterField label="Team">
        <select
          className={filterInputClassName("min-w-[180px]")}
          value={team}
          onChange={(e) => onTeamChange(e.target.value)}
        >
          <option value="">All teams</option>
          {availableTeams.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
      </FilterField>
    </AnalyticsFilterPanel>
  );
}
