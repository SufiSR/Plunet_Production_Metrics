from __future__ import annotations

TEAM_NAME_NORMALIZATIONS: dict[str, str] = {
    "tantrum": "Team Tantrum",
    "team tantrum": "Team Tantrum",
    "world": "Team World",
    "team world": "Team World",
    "cop": "CoP",
    "freedevs": "FreeDevs",
    "freeguys": "FreeDevs",
    "free guys": "FreeDevs",
    "free devs": "FreeDevs",
    "free dev": "FreeDevs",
}


def normalize_team_name(team: object) -> str | None:
    raw = str(team or "").strip()
    if not raw:
        return None
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) > 1:
        normalized = ", ".join(
            TEAM_NAME_NORMALIZATIONS.get(part.lower(), part) for part in parts if part
        )
        return normalized or None
    return TEAM_NAME_NORMALIZATIONS.get(raw.lower(), raw)


def normalized_team_name(team: object) -> str:
    return normalize_team_name(team) or "Unknown"
