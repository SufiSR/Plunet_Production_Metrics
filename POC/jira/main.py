"""
Entry point for the Jira POC.

Usage:
    python main.py

Requires a .env file (copy from .env.example).
Output is written to the ./output/ directory as a JSON file.

If a GitLab lead-time JSON file is present in ../gitlab/output/, MTTR Alpha is
computed automatically by linking Jira bugs (Critical+) to their fix releases via:
  1. MR jira_key match (primary)
  2. Jira fix_versions → GitLab tag name (fallback)
"""

import json
from pathlib import Path

from config import get_config
from jira_client import compute_mttr_alpha, fetch_production_bugs
from output import write_json

_GITLAB_OUTPUT_DIR = Path(__file__).parent.parent / "gitlab" / "output"


def _load_latest_gitlab_lead_time() -> dict | None:
    """Return the parsed JSON of the most recent gitlab_lead_time_*.json file, or None."""
    if not _GITLAB_OUTPUT_DIR.exists():
        return None
    candidates = sorted(_GITLAB_OUTPUT_DIR.glob("gitlab_lead_time_*.json"), reverse=True)
    if not candidates:
        return None
    latest = candidates[0]
    print(f"Loading GitLab lead-time data from: {latest.name}")
    with open(latest, encoding="utf-8") as fh:
        return json.load(fh)


def _build_gitlab_mappings(gitlab_data: dict) -> tuple[dict[str, tuple[str, str]], dict[str, str]]:
    """
    Build two lookup dicts from the GitLab lead-time JSON:

    mr_jira_key_to_tag: {jira_key: (tag_name, tag_committed_date)}
        Only MRs with match_status="matched" contribute.

    tag_name_to_date: {tag_name: committed_date}
        All customer_release=true tags.
    """
    mr_jira_key_to_tag: dict[str, tuple[str, str]] = {}
    for record in gitlab_data.get("lead_time", {}).get("lead_time_records", []):
        jira_key = record.get("jira_key")
        tag = record.get("first_customer_tag")
        tag_date = record.get("first_customer_tag_date")
        if jira_key and tag and tag_date and record.get("match_status") == "matched":
            # Keep earliest tag when the same jira_key appears on multiple branches
            if jira_key not in mr_jira_key_to_tag:
                mr_jira_key_to_tag[jira_key] = (tag, tag_date)
            else:
                existing_date = mr_jira_key_to_tag[jira_key][1]
                if tag_date < existing_date:
                    mr_jira_key_to_tag[jira_key] = (tag, tag_date)

    tag_name_to_date: dict[str, str] = {}
    for tag in gitlab_data.get("tags", {}).get("tags", []):
        if tag.get("customer_release") and tag.get("name") and tag.get("committed_date"):
            tag_name_to_date[tag["name"]] = tag["committed_date"]

    return mr_jira_key_to_tag, tag_name_to_date


def main() -> None:
    config = get_config()

    result = fetch_production_bugs(
        jira_url=config["JIRA_URL"],
        username=config["JIRA_USERNAME"],
        token=config["JIRA_TOKEN"],
        lookback_years=config["lookback_years"],
        indicator_cf_ids=config["production_bug_indicator_cf_ids"],
        excluded_projects=config["excluded_projects"],
    )

    gitlab_data = _load_latest_gitlab_lead_time()
    if gitlab_data:
        mr_key_map, tag_date_map = _build_gitlab_mappings(gitlab_data)
        print(
            f"GitLab mappings built: {len(mr_key_map)} MR jira_key entries, "
            f"{len(tag_date_map)} customer release tags"
        )
        mttr_alpha = compute_mttr_alpha(
            bugs=result["bugs"],
            mr_jira_key_to_tag=mr_key_map,
            tag_name_to_date=tag_date_map,
        )
        result["mttr_alpha"] = mttr_alpha
        print(
            f"MTTR Alpha: {mttr_alpha['resolved']}/{mttr_alpha['total_eligible']} "
            f"eligible bugs resolved "
            f"({mttr_alpha['coverage_pct']}% coverage)"
        )
        if mttr_alpha["aggregate"]["median_hours"] is not None:
            print(
                f"  Median: {mttr_alpha['aggregate']['median_hours']}h  "
                f"P75: {mttr_alpha['aggregate']['p75_hours']}h  "
                f"P90: {mttr_alpha['aggregate']['p90_hours']}h"
            )
    else:
        print(
            "No GitLab lead-time output found — skipping MTTR Alpha computation.\n"
            "Run the GitLab POC first, then re-run this script."
        )

    write_json(result, output_dir="output")


if __name__ == "__main__":
    main()
