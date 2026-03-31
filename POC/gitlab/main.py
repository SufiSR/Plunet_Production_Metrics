"""
Entry point for the GitLab tags POC.

Usage:
    python main.py

Requires a .env file (copy from .env.example).
Output is written to ./output/ as JSON.
"""

from config import get_config
from gitlab_client import (
    compute_lead_time_from_mrs_and_tags,
    enrich_mr_first_commit_timestamps,
    fetch_merged_merge_requests_for_branches,
    fetch_project_tags,
)
from output import write_json


def main() -> None:
    config = get_config()

    result = fetch_project_tags(
        base_url=config["GITLAB_URL"],
        token=config["GITLAB_TOKEN"],
        project_path=config["project_path"],
        per_page=config["per_page"],
        lookback_years=config["lookback_years"],
        non_customer_release_markers=config["non_customer_release_markers"],
    )

    mr_result = fetch_merged_merge_requests_for_branches(
        base_url=config["GITLAB_URL"],
        token=config["GITLAB_TOKEN"],
        project_path=config["project_path"],
        target_branches=config["target_branches"],
        per_page=config["per_page"],
        lookback_years=config["lookback_years"],
    )

    print("Enriching MRs with first_commit_at …")
    enriched_mrs = enrich_mr_first_commit_timestamps(
        base_url=config["GITLAB_URL"],
        token=config["GITLAB_TOKEN"],
        project_path=config["project_path"],
        merge_requests=mr_result["merge_requests"],
    )
    first_commit_covered = sum(1 for mr in enriched_mrs if mr.get("first_commit_at"))

    lead_time_result = compute_lead_time_from_mrs_and_tags(
        base_url=config["GITLAB_URL"],
        token=config["GITLAB_TOKEN"],
        project_path=config["project_path"],
        merge_requests=enriched_mrs,
        tags=result["tags"],
    )

    print(
        f"Tags: {result['total_raw']} total, "
        f"{result['total']} in lookback window "
        f"(from {result['lookback_from']})"
    )
    print(
        f"Merged MRs: {mr_result['total_raw']} total, "
        f"{mr_result['total']} in lookback window "
        f"(target_branches={mr_result['target_branches']})"
    )
    print(
        f"first_commit_at coverage: {first_commit_covered}/{len(enriched_mrs)} MRs"
    )
    print(
        f"Lead-time matches: {lead_time_result['matched']}/"
        f"{lead_time_result['total_merge_requests']}"
    )

    combined = {
        "project_path": config["project_path"],
        "base_url": config["GITLAB_URL"].rstrip("/"),
        "lookback_years": config["lookback_years"],
        "target_branches": config["target_branches"],
        "tags": result,
        "merge_requests": mr_result,
        "lead_time": lead_time_result,
    }
    write_json(combined, output_dir="output", prefix="gitlab_lead_time")


if __name__ == "__main__":
    main()
