"""Unit tests for lead time branch/stream breakdown (DEVOPS-510)."""

from datetime import datetime, timezone
from decimal import Decimal

from app.config_schema import ConfigurationSchema
from app.services.lead_time_breakdown import (
    _MrLeadRow,
    change_stream_for_target_branch,
    lead_time_bucket_dict,
    primary_feature_branch,
)


def test_primary_and_stream_mapping() -> None:
    cfg = ConfigurationSchema()
    assert primary_feature_branch(cfg) == "master"
    assert change_stream_for_target_branch("master", cfg) == "feature"
    assert change_stream_for_target_branch("10.x", cfg) == "patch"
    assert change_stream_for_target_branch("unknown-feature", cfg) == "other"


def test_lead_time_bucket_dict_stream() -> None:
    cfg = ConfigurationSchema()
    rows = [
        _MrLeadRow(
            target_branch="master",
            lead_time_hours=Decimal("10"),
            release_wait_time_hours=Decimal("4"),
            first_customer_tag_date=datetime(2026, 1, 15, tzinfo=timezone.utc),
        ),
        _MrLeadRow(
            target_branch="10.x",
            lead_time_hours=Decimal("20"),
            release_wait_time_hours=Decimal("5"),
            first_customer_tag_date=datetime(2026, 1, 16, tzinfo=timezone.utc),
        ),
    ]
    out = lead_time_bucket_dict(rows, mode="stream", config=cfg)
    assert "feature" in out and "patch" in out
    assert out["feature"]["sample_count"] == 1
    assert out["patch"]["sample_count"] == 1
    assert out["feature"]["median_lead_time_minutes"] == 600


def test_lead_time_bucket_dict_branch() -> None:
    cfg = ConfigurationSchema()
    rows = [
        _MrLeadRow(
            target_branch="master",
            lead_time_hours=Decimal("8"),
            release_wait_time_hours=Decimal("2"),
            first_customer_tag_date=datetime(2026, 2, 1, tzinfo=timezone.utc),
        ),
    ]
    out = lead_time_bucket_dict(rows, mode="branch", config=cfg)
    assert "master" in out
    assert out["master"]["sample_count"] == 1
