"use client";

import { useCallback, useMemo, useState } from "react";
import { PeopleDataGate } from "@/app/components/jira-analytics/PeopleDataGate";
import type { AnalyticsReportResponse } from "@/types/jira-analytics";

interface RoleHours {
  dev_hours: number;
  qa_hours: number;
  total_hours: number;
}

interface HeatmapPerson extends RoleHours {
  person: string;
  hours: number;
}

interface HeatmapTopic extends RoleHours {
  topic: string;
  people: HeatmapPerson[];
}

interface HeatmapTeamGroup extends RoleHours {
  team: string;
  topics: HeatmapTopic[];
}

interface WorkAllocationHeatmapViewProps {
  data: AnalyticsReportResponse;
}

export function WorkAllocationHeatmapView({ data }: WorkAllocationHeatmapViewProps) {
  const groups = useMemo(() => parseHeatmapSeries(data.series), [data.series]);
  const restricted = data.summary?.people_data_restricted === true;
  const [expandedTeams, setExpandedTeams] = useState<Set<string>>(() => new Set());
  const [expandedTopics, setExpandedTopics] = useState<Set<string>>(() => new Set());

  const toggleTeam = useCallback((team: string) => {
    setExpandedTeams((current) => {
      const next = new Set(current);
      if (next.has(team)) {
        next.delete(team);
      } else {
        next.add(team);
      }
      return next;
    });
  }, []);

  const toggleTopic = useCallback((team: string, topic: string) => {
    const key = topicKey(team, topic);
    setExpandedTopics((current) => {
      const next = new Set(current);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }, []);

  if (!groups.length) {
    return (
      <p className="text-sm text-on-surface-variant">
        No developer or QA allocation in the selected period.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {groups.map((group) => {
        const teamExpanded = expandedTeams.has(group.team);
        return (
          <section
            key={group.team}
            className="rounded-xl border border-outline-variant/20 bg-surface-container-lowest"
          >
            <button
              type="button"
              onClick={() => toggleTeam(group.team)}
              aria-expanded={teamExpanded}
              className="flex w-full flex-wrap items-center justify-between gap-2 border-b border-outline-variant/28 px-4 py-3 text-left hover:bg-surface-container-low/60"
            >
              <span className="flex min-w-0 items-center gap-2">
                <span className="material-symbols-outlined text-[20px] text-on-surface-variant">
                  {teamExpanded ? "expand_more" : "chevron_right"}
                </span>
                <span className="text-sm font-editorial font-semibold text-on-surface">
                  {group.team}
                </span>
              </span>
              <RoleHoursSummary hours={group} className="text-xs" />
            </button>
            {teamExpanded ? (
              <div className="divide-y divide-outline-variant/10">
                {group.topics.map((topic) => {
                  const key = topicKey(group.team, topic.topic);
                  const topicExpanded = expandedTopics.has(key);
                  return (
                    <div key={key} className="px-2 py-1">
                      <button
                        type="button"
                        onClick={() => toggleTopic(group.team, topic.topic)}
                        aria-expanded={topicExpanded}
                        className="flex w-full flex-wrap items-center justify-between gap-2 rounded-lg px-2 py-2 text-left hover:bg-surface-container-low/80"
                      >
                        <span className="flex min-w-0 items-center gap-2">
                          <span className="material-symbols-outlined text-[18px] text-on-surface-variant">
                            {topicExpanded ? "expand_more" : "chevron_right"}
                          </span>
                          <span className="text-sm font-medium text-on-surface">{topic.topic}</span>
                        </span>
                        <RoleHoursSummary hours={topic} className="text-xs" />
                      </button>
                      {topicExpanded ? (
                        restricted ? (
                          <div className="mb-2 ml-7">
                            <PeopleDataGate restricted />
                          </div>
                        ) : (
                          <ul className="mb-2 ml-7 space-y-1 border-l border-outline-variant/28 pl-3">
                            {topic.people.map((person) => (
                              <li
                                key={`${key}-${person.person}`}
                                className="flex flex-wrap items-baseline justify-between gap-3 py-1 text-sm"
                              >
                                <span className="text-on-surface">{person.person}</span>
                                <span className="tabular-nums text-on-surface-variant">
                                  {formatPersonHours(person)}
                                </span>
                              </li>
                            ))}
                          </ul>
                        )
                      ) : null}
                    </div>
                  );
                })}
              </div>
            ) : null}
          </section>
        );
      })}
    </div>
  );
}

function RoleHoursSummary({
  hours,
  className = "",
}: {
  hours: RoleHours;
  className?: string;
}) {
  return (
    <span className={`tabular-nums text-on-surface-variant ${className}`.trim()}>
      Dev: {hours.dev_hours.toFixed(2)} h, QA: {hours.qa_hours.toFixed(2)} h
    </span>
  );
}

function formatPersonHours(person: HeatmapPerson): string {
  if (person.dev_hours > 0 && person.qa_hours > 0) {
    return `${person.hours.toFixed(2)} h (Dev: ${person.dev_hours.toFixed(2)}, QA: ${person.qa_hours.toFixed(2)})`;
  }
  if (person.qa_hours > 0) {
    return `${person.hours.toFixed(2)} h`;
  }
  return `${person.hours.toFixed(2)} h`;
}

function topicKey(team: string, topic: string): string {
  return `${team}::${topic}`;
}

function parseHeatmapSeries(series: Record<string, unknown>[]): HeatmapTeamGroup[] {
  const groups: HeatmapTeamGroup[] = [];
  for (const entry of series) {
    const team = stringValue(entry.team);
    if (!team) continue;
    const topicsRaw = entry.topics;
    if (!Array.isArray(topicsRaw)) continue;
    const topics: HeatmapTopic[] = [];
    for (const topicEntry of topicsRaw) {
      if (!topicEntry || typeof topicEntry !== "object") continue;
      const record = topicEntry as Record<string, unknown>;
      const topic = stringValue(record.topic);
      if (!topic) continue;
      const peopleRaw = record.people;
      if (!Array.isArray(peopleRaw)) continue;
      const people: HeatmapPerson[] = [];
      for (const personEntry of peopleRaw) {
        if (!personEntry || typeof personEntry !== "object") continue;
        const personRecord = personEntry as Record<string, unknown>;
        const person = stringValue(personRecord.person);
        const hours = numberValue(personRecord.hours);
        if (!person || hours === null || hours <= 0) continue;
        people.push({
          person,
          hours,
          dev_hours: numberValue(personRecord.dev_hours) ?? 0,
          qa_hours: numberValue(personRecord.qa_hours) ?? 0,
          total_hours: hours,
        });
      }
      if (!people.length) continue;
      const topicHours = parseRoleHours(record, people);
      topics.push({ topic, people, ...topicHours });
    }
    if (!topics.length) continue;
    const teamHours = parseRoleHours(entry, topics);
    groups.push({ team, topics, ...teamHours });
  }
  return groups;
}

function parseRoleHours(
  record: Record<string, unknown>,
  children: Array<{ dev_hours: number; qa_hours: number; hours?: number; total_hours?: number }>,
): RoleHours {
  const dev = numberValue(record.dev_hours);
  const qa = numberValue(record.qa_hours);
  const total = numberValue(record.total_hours);
  if (dev !== null && qa !== null) {
    return {
      dev_hours: dev,
      qa_hours: qa,
      total_hours: total ?? dev + qa,
    };
  }
  const devSum = children.reduce((sum, row) => sum + row.dev_hours, 0);
  const qaSum = children.reduce((sum, row) => sum + row.qa_hours, 0);
  return {
    dev_hours: devSum,
    qa_hours: qaSum,
    total_hours: total ?? devSum + qaSum,
  };
}

function stringValue(value: unknown): string | null {
  if (typeof value !== "string" || !value.trim()) return null;
  return value.trim();
}

function numberValue(value: unknown): number | null {
  if (typeof value !== "number" || Number.isNaN(value)) return null;
  return value;
}
