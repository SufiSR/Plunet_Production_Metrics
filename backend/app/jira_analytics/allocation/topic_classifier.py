from __future__ import annotations

TECH_SUPPORT_TYPES = frozenset({"TechSupport", "Tech Support"})


def classify_topic_type(
    *,
    feature_root_id: int | None,
    issue_type_name: str | None,
) -> str:
    if feature_root_id is not None:
        return "feature"
    name = (issue_type_name or "").strip()
    if name in TECH_SUPPORT_TYPES:
        return "tech_support"
    if name == "Bug":
        return "unassigned_bug"
    if name:
        return "issue_without_feature"
    return "unclassified"
