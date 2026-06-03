export const FOCUSED_ENGINEERING_TEAMS = [
  "Team Tantrum",
  "Team World",
  "Cosmic Coders",
  "FreeDevs",
] as const;

export type FocusedEngineeringTeam = (typeof FOCUSED_ENGINEERING_TEAMS)[number];
