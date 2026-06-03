from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def _pk_bigint() -> BigInteger:
    return BigInteger().with_variant(Integer, "sqlite")


class JiraProject(Base):
    __tablename__ = "jira_project"
    __table_args__ = (
        Index("ix_jira_project_category_name", "category_name"),
        UniqueConstraint("jira_project_id", name="uq_jira_project_jira_project_id"),
        UniqueConstraint("key", name="uq_jira_project_key"),
    )

    id: Mapped[int] = mapped_column(_pk_bigint(), primary_key=True, autoincrement=True)
    jira_project_id: Mapped[str] = mapped_column(String(64), nullable=False)
    key: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    category_name: Mapped[str | None] = mapped_column(String(255))
    raw_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class JiraUser(Base):
    __tablename__ = "jira_user"
    __table_args__ = (UniqueConstraint("account_id", name="uq_jira_user_account_id"),)

    id: Mapped[int] = mapped_column(_pk_bigint(), primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    email_address: Mapped[str | None] = mapped_column(String(255))
    active: Mapped[bool | None] = mapped_column(Boolean)
    reporting_excluded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    time_zone: Mapped[str | None] = mapped_column(String(100))
    account_type: Mapped[str | None] = mapped_column(String(50))
    raw_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class JiraIssue(Base):
    __tablename__ = "jira_issue"
    __table_args__ = (
        Index("ix_jira_issue_project_issue_type", "project_id", "issue_type_name"),
        Index("ix_jira_issue_status_updated", "status_name", "updated_at_jira"),
        Index("ix_jira_issue_created_at_jira", "created_at_jira"),
        Index("ix_jira_issue_resolved_at_jira", "resolved_at_jira"),
        Index("ix_jira_issue_parent_issue_id", "parent_issue_id"),
        UniqueConstraint("jira_issue_id", name="uq_jira_issue_jira_issue_id"),
        UniqueConstraint("key", name="uq_jira_issue_key"),
    )

    id: Mapped[int] = mapped_column(_pk_bigint(), primary_key=True, autoincrement=True)
    jira_issue_id: Mapped[str] = mapped_column(String(64), nullable=False)
    key: Mapped[str] = mapped_column(String(50), nullable=False)
    self_url: Mapped[str | None] = mapped_column(Text)
    project_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("jira_project.id", ondelete="SET NULL")
    )
    issue_type_id: Mapped[str | None] = mapped_column(String(64))
    issue_type_name: Mapped[str | None] = mapped_column(String(100))
    issue_type_hierarchy_level: Mapped[int | None] = mapped_column(Integer)
    summary: Mapped[str | None] = mapped_column(String(1024))
    description_text: Mapped[str | None] = mapped_column(Text)
    description_adf: Mapped[dict | None] = mapped_column(JSON)
    status_id: Mapped[str | None] = mapped_column(String(64))
    status_name: Mapped[str | None] = mapped_column(String(100))
    status_category_key: Mapped[str | None] = mapped_column(String(64))
    status_category_name: Mapped[str | None] = mapped_column(String(100))
    resolution_id: Mapped[str | None] = mapped_column(String(64))
    resolution_name: Mapped[str | None] = mapped_column(String(100))
    priority_id: Mapped[str | None] = mapped_column(String(64))
    priority_name: Mapped[str | None] = mapped_column(String(100))
    assignee_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("jira_user.id", ondelete="SET NULL")
    )
    creator_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("jira_user.id", ondelete="SET NULL")
    )
    reporter_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("jira_user.id", ondelete="SET NULL")
    )
    parent_issue_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("jira_issue.id", ondelete="SET NULL")
    )
    parent_jira_issue_id: Mapped[str | None] = mapped_column(String(64))
    parent_key: Mapped[str | None] = mapped_column(String(50))
    created_at_jira: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at_jira: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at_jira: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_fields_json: Mapped[dict | None] = mapped_column(JSON)
    raw_issue_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class JiraIssueDetail(Base):
    __tablename__ = "jira_issue_detail"
    __table_args__ = (
        Index("ix_jira_issue_detail_promised_delivery_date", "promised_delivery_date"),
        Index("ix_jira_issue_detail_promised_sold_on", "promised_sold_on"),
        Index("ix_jira_issue_detail_delivery_status", "delivery_status"),
        Index("ix_jira_issue_detail_team_name", "team_name"),
        Index("ix_jira_issue_detail_epic_link_key", "epic_link_key"),
    )

    issue_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("jira_issue.id", ondelete="CASCADE"), primary_key=True
    )
    promised_delivery_date: Mapped[datetime | None] = mapped_column(Date)
    customer_transparency: Mapped[str | None] = mapped_column(String(255))
    external_issue_url: Mapped[str | None] = mapped_column(Text)
    to_be_verified_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("jira_user.id", ondelete="SET NULL")
    )
    solution: Mapped[str | None] = mapped_column(Text)
    promised_sold_on: Mapped[datetime | None] = mapped_column(Date)
    target_branches: Mapped[list | None] = mapped_column(JSON)
    documentation: Mapped[list | None] = mapped_column(JSON)
    version_value: Mapped[str | None] = mapped_column(String(255))
    epic_thema: Mapped[str | None] = mapped_column(String(255))
    maintainer_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("jira_user.id", ondelete="SET NULL")
    )
    design: Mapped[str | None] = mapped_column(Text)
    goals: Mapped[str | None] = mapped_column(Text)
    delivery_status: Mapped[str | None] = mapped_column(String(255))
    pmgt_product: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON)
    external_issue_id: Mapped[str | None] = mapped_column(String(255))
    epic_link_key: Mapped[str | None] = mapped_column(String(50))
    epic_link_issue_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("jira_issue.id", ondelete="SET NULL")
    )
    ux_required: Mapped[str | None] = mapped_column(String(50))
    start_date: Mapped[datetime | None] = mapped_column(Date)
    change_type: Mapped[str | None] = mapped_column(String(255))
    change_risk: Mapped[str | None] = mapped_column(String(255))
    change_reason: Mapped[str | None] = mapped_column(String(255))
    actual_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    customer_priority: Mapped[str | None] = mapped_column(String(255))
    actual_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    team_id: Mapped[str | None] = mapped_column(String(128))
    team_name: Mapped[str | None] = mapped_column(String(255))
    customers: Mapped[list | None] = mapped_column(JSON)
    labels: Mapped[list | None] = mapped_column(JSON)
    components: Mapped[list | None] = mapped_column(JSON)
    affects_versions: Mapped[list | None] = mapped_column(JSON)
    fix_versions: Mapped[list | None] = mapped_column(JSON)
    raw_required_fields_json: Mapped[dict | None] = mapped_column(JSON)


class JiraIssueFieldValue(Base):
    __tablename__ = "jira_issue_field_value"
    __table_args__ = (
        Index("ix_jira_issue_field_value_field_text", "field_id", "value_text"),
        Index("ix_jira_issue_field_value_field_date", "field_id", "value_date"),
        UniqueConstraint("issue_id", "field_id", name="uq_jira_issue_field_value_issue_field"),
    )

    id: Mapped[int] = mapped_column(_pk_bigint(), primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("jira_issue.id", ondelete="CASCADE"), nullable=False
    )
    field_id: Mapped[str] = mapped_column(String(100), nullable=False)
    field_name: Mapped[str | None] = mapped_column(String(255))
    schema_type: Mapped[str | None] = mapped_column(String(100))
    schema_custom: Mapped[str | None] = mapped_column(String(255))
    value_text: Mapped[str | None] = mapped_column(Text)
    value_number: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    value_date: Mapped[datetime | None] = mapped_column(Date)
    value_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    value_json: Mapped[dict | list | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class JiraWorklog(Base):
    __tablename__ = "jira_worklog"
    __table_args__ = (
        Index("ix_jira_worklog_author_started", "author_user_id", "started_at"),
        Index("ix_jira_worklog_issue_started", "issue_id", "started_at"),
        Index("ix_jira_worklog_started_at", "started_at"),
        UniqueConstraint("issue_id", "jira_worklog_id", name="uq_jira_worklog_issue_worklog"),
    )

    id: Mapped[int] = mapped_column(_pk_bigint(), primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("jira_issue.id", ondelete="CASCADE"), nullable=False
    )
    jira_worklog_id: Mapped[str] = mapped_column(String(64), nullable=False)
    author_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("jira_user.id", ondelete="SET NULL")
    )
    author_account_id: Mapped[str | None] = mapped_column(String(128))
    author_display_name: Mapped[str | None] = mapped_column(String(255))
    author_email_address: Mapped[str | None] = mapped_column(String(255))
    comment_text: Mapped[str | None] = mapped_column(Text)
    comment_adf: Mapped[dict | None] = mapped_column(JSON)
    created_at_jira: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at_jira: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    time_spent_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class JiraIssueStatusTransition(Base):
    __tablename__ = "jira_issue_status_transition"
    __table_args__ = (
        Index("ix_jira_issue_status_transition_issue_changed", "issue_id", "changed_at"),
        Index("ix_jira_issue_status_transition_to_status_changed", "to_status_name", "changed_at"),
        UniqueConstraint(
            "issue_id",
            "jira_history_id",
            "history_item_index",
            name="uq_jira_issue_status_transition_history_item",
        ),
    )

    id: Mapped[int] = mapped_column(_pk_bigint(), primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("jira_issue.id", ondelete="CASCADE"), nullable=False
    )
    jira_history_id: Mapped[str] = mapped_column(String(64), nullable=False)
    history_item_index: Mapped[int] = mapped_column(Integer, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("jira_user.id", ondelete="SET NULL")
    )
    changed_by_display_name: Mapped[str | None] = mapped_column(String(255))
    from_status_id: Mapped[str | None] = mapped_column(String(64))
    from_status_name: Mapped[str | None] = mapped_column(String(100))
    to_status_id: Mapped[str | None] = mapped_column(String(64))
    to_status_name: Mapped[str | None] = mapped_column(String(100))
    raw_item_json: Mapped[dict | None] = mapped_column(JSON)


class JiraSprint(Base):
    __tablename__ = "jira_sprint"
    __table_args__ = (UniqueConstraint("jira_sprint_id", name="uq_jira_sprint_jira_sprint_id"),)

    id: Mapped[int] = mapped_column(_pk_bigint(), primary_key=True, autoincrement=True)
    jira_sprint_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    state: Mapped[str | None] = mapped_column(String(50))
    board_id: Mapped[int | None] = mapped_column(BigInteger)
    goal: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    complete_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_json: Mapped[dict | None] = mapped_column(JSON)


class JiraIssueSprint(Base):
    __tablename__ = "jira_issue_sprint"

    issue_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("jira_issue.id", ondelete="CASCADE"), primary_key=True
    )
    sprint_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("jira_sprint.id", ondelete="CASCADE"), primary_key=True
    )
    source_field_id: Mapped[str] = mapped_column(
        String(100), nullable=False, default="customfield_10020"
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class JiraIssueRelation(Base):
    __tablename__ = "jira_issue_relation"
    __table_args__ = (
        Index("ix_jira_issue_relation_source_issue_id", "source_issue_id"),
        Index("ix_jira_issue_relation_target_issue_id", "target_issue_id"),
        Index("ix_jira_issue_relation_target_key", "target_key"),
        Index("ix_jira_issue_relation_source_type", "relation_source", "link_type_name"),
        Index("ix_jira_issue_relation_feature_membership", "is_feature_membership_edge"),
        Index(
            "uq_jira_issue_relation_jira_link_id",
            "source_issue_id",
            "jira_link_id",
            unique=True,
            postgresql_where=sa.text("jira_link_id IS NOT NULL"),
            sqlite_where=sa.text("jira_link_id IS NOT NULL"),
        ),
        Index(
            "uq_jira_issue_relation_direct_identity",
            "source_issue_id",
            "target_key",
            "relation_source",
            "link_type_name",
            "direction",
            unique=True,
            postgresql_where=sa.text("jira_link_id IS NULL"),
            sqlite_where=sa.text("jira_link_id IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(_pk_bigint(), primary_key=True, autoincrement=True)
    source_issue_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("jira_issue.id", ondelete="CASCADE"), nullable=False
    )
    target_issue_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("jira_issue.id", ondelete="SET NULL")
    )
    target_jira_issue_id: Mapped[str | None] = mapped_column(String(64))
    target_key: Mapped[str | None] = mapped_column(String(50))
    relation_source: Mapped[str] = mapped_column(String(50), nullable=False)
    jira_link_id: Mapped[str | None] = mapped_column(String(64))
    link_type_id: Mapped[str | None] = mapped_column(String(64))
    link_type_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    direction: Mapped[str] = mapped_column(String(30), nullable=False, default="undirected")
    inward_description: Mapped[str | None] = mapped_column(String(255))
    outward_description: Mapped[str | None] = mapped_column(String(255))
    is_hierarchy_edge: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_feature_membership_edge: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    raw_json: Mapped[dict | None] = mapped_column(JSON)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class JiraFeatureRoot(Base):
    __tablename__ = "jira_feature_root"
    __table_args__ = (
        Index("ix_jira_feature_root_project_type", "root_project_key", "root_issue_type_name"),
        Index("ix_jira_feature_root_active", "active"),
        UniqueConstraint("root_issue_id", name="uq_jira_feature_root_root_issue_id"),
    )

    id: Mapped[int] = mapped_column(_pk_bigint(), primary_key=True, autoincrement=True)
    root_issue_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("jira_issue.id", ondelete="CASCADE"), nullable=False
    )
    root_key: Mapped[str] = mapped_column(String(50), nullable=False)
    root_project_key: Mapped[str] = mapped_column(String(50), nullable=False)
    root_issue_type_name: Mapped[str | None] = mapped_column(String(100))
    name: Mapped[str | None] = mapped_column(String(1024))
    detection_rule: Mapped[str] = mapped_column(String(100), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class JiraFeatureMembership(Base):
    __tablename__ = "jira_feature_membership"
    __table_args__ = (
        Index("ix_jira_feature_membership_member_issue_id", "member_issue_id"),
        Index("ix_jira_feature_membership_root_depth", "feature_root_id", "depth"),
    )

    feature_root_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("jira_feature_root.id", ondelete="CASCADE"), primary_key=True
    )
    member_issue_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("jira_issue.id", ondelete="CASCADE"), primary_key=True
    )
    depth: Mapped[int] = mapped_column(Integer, nullable=False)
    path_issue_keys: Mapped[list] = mapped_column(JSON, nullable=False)
    path_relation_ids: Mapped[list | None] = mapped_column(JSON)
    inclusion_reason: Mapped[str] = mapped_column(String(100), nullable=False)
    nearest_parent_issue_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("jira_issue.id", ondelete="SET NULL")
    )
    direct_relation_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("jira_issue_relation.id", ondelete="SET NULL")
    )
    contains_cycle: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class JiraFeatureFamily(Base):
    __tablename__ = "jira_feature_family"
    __table_args__ = (
        Index("ix_jira_feature_family_active", "active"),
        UniqueConstraint("name", name="uq_jira_feature_family_name"),
    )

    id: Mapped[int] = mapped_column(_pk_bigint(), primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    suggestion_keywords: Mapped[list | None] = mapped_column(JSON)
    title_match_pattern: Mapped[str | None] = mapped_column(String(512))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class JiraFeatureFamilyMember(Base):
    __tablename__ = "jira_feature_family_member"
    __table_args__ = (
        Index("ix_jira_feature_family_member_family", "family_id"),
        UniqueConstraint("feature_root_id", name="uq_jira_feature_family_member_feature_root"),
    )

    family_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("jira_feature_family.id", ondelete="CASCADE"), primary_key=True
    )
    feature_root_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("jira_feature_root.id", ondelete="CASCADE"), primary_key=True
    )
    created_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class JiraFeatureFamilySuggestionDecision(Base):
    __tablename__ = "jira_feature_family_suggestion_decision"
    __table_args__ = (
        Index("ix_jira_feature_family_suggestion_decision_family", "family_id"),
        Index("ix_jira_feature_family_suggestion_decision_feature", "feature_root_id"),
        UniqueConstraint(
            "family_id",
            "feature_root_id",
            "suggestion_fingerprint",
            name="uq_jira_feature_family_suggestion_decision",
        ),
    )

    id: Mapped[int] = mapped_column(_pk_bigint(), primary_key=True, autoincrement=True)
    family_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("jira_feature_family.id", ondelete="CASCADE"), nullable=False
    )
    feature_root_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("jira_feature_root.id", ondelete="CASCADE"), nullable=False
    )
    suggestion_fingerprint: Mapped[str] = mapped_column(String(255), nullable=False)
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(1024))
    decided_by: Mapped[str | None] = mapped_column(String(255))
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class HrworksPersonRoster(Base):
    """Cached HRworks master-data roster for join/leave eligibility and Jira mapping."""

    __tablename__ = "hrworks_person_roster"
    __table_args__ = (
        Index("ix_hrworks_person_roster_jira_user_id", "jira_user_id"),
        Index("ix_hrworks_person_roster_leave_date", "leave_date"),
        UniqueConstraint("person_id", name="uq_hrworks_person_roster_person_id"),
    )

    id: Mapped[int] = mapped_column(_pk_bigint(), primary_key=True, autoincrement=True)
    person_id: Mapped[str] = mapped_column(String(255), nullable=False)
    hrworks_uuid: Mapped[str | None] = mapped_column(String(64))
    personnel_number: Mapped[str | None] = mapped_column(String(64))
    business_email: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    join_date: Mapped[date | None] = mapped_column(Date)
    leave_date: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    jira_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("jira_user.id", ondelete="SET NULL")
    )
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class JiraUserMonthlyHrworksHours(Base):
    __tablename__ = "jira_user_monthly_hrworks_hours"
    __table_args__ = (
        Index("ix_jira_user_monthly_hrworks_hours_month_start", "month_start"),
        Index(
            "ix_jira_user_monthly_hrworks_hours_user_month",
            "jira_user_id",
            "month_start",
        ),
        UniqueConstraint(
            "jira_user_id",
            "month_start",
            name="uq_jira_user_monthly_hrworks_hours_user_month",
        ),
    )

    id: Mapped[int] = mapped_column(_pk_bigint(), primary_key=True, autoincrement=True)
    jira_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("jira_user.id", ondelete="CASCADE"), nullable=False
    )
    month_start: Mapped[datetime] = mapped_column(Date, nullable=False)
    month_end: Mapped[datetime] = mapped_column(Date, nullable=False)
    planned_working_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    clocked_working_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AllocationRoleRule(Base):
    __tablename__ = "allocation_role_rule"
    __table_args__ = (UniqueConstraint("role_name", name="uq_allocation_role_rule_role_name"),)

    id: Mapped[int] = mapped_column(_pk_bigint(), primary_key=True, autoincrement=True)
    role_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_direct_production_role: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_indirect_role: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    overhead_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    allocation_scope: Mapped[str] = mapped_column(String(50), nullable=False)
    allocation_base: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="direct_production_hours",
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class JiraUserRoleAssignment(Base):
    __tablename__ = "jira_user_role_assignment"
    __table_args__ = (
        Index("ix_jira_user_role_assignment_account_valid", "user_account_id", "valid_from"),
        Index("ix_jira_user_role_assignment_jira_user_valid", "jira_user_id", "valid_from"),
    )

    id: Mapped[int] = mapped_column(_pk_bigint(), primary_key=True, autoincrement=True)
    jira_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("jira_user.id", ondelete="CASCADE")
    )
    user_account_id: Mapped[str | None] = mapped_column(String(128))
    user_email: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role_name: Mapped[str] = mapped_column(String(100), nullable=False)
    team_id: Mapped[str | None] = mapped_column(String(128))
    team_name: Mapped[str | None] = mapped_column(String(255))
    allocatable_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    allocation_scope: Mapped[str | None] = mapped_column(String(50))
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class JiraDataQualityUserIgnore(Base):
    __tablename__ = "jira_data_quality_user_ignore"
    __table_args__ = (
        UniqueConstraint("check_id", "jira_user_id", name="uq_jira_data_quality_user_ignore_check_user"),
        Index("ix_jira_data_quality_user_ignore_check_active", "check_id", "active"),
    )

    id: Mapped[int] = mapped_column(_pk_bigint(), primary_key=True, autoincrement=True)
    check_id: Mapped[str] = mapped_column(String(100), nullable=False)
    jira_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("jira_user.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class MonthlyTopicEffortBase(Base):
    __tablename__ = "monthly_topic_effort_base"
    __table_args__ = (
        Index("ix_monthly_topic_effort_base_period_topic", "period_month", "topic_type"),
        Index("ix_monthly_topic_effort_base_period_feature", "period_month", "feature_root_id"),
    )

    id: Mapped[int] = mapped_column(_pk_bigint(), primary_key=True, autoincrement=True)
    period_month: Mapped[date] = mapped_column(Date, nullable=False)
    feature_root_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("jira_feature_root.id", ondelete="SET NULL")
    )
    feature_key: Mapped[str | None] = mapped_column(String(50))
    feature_name: Mapped[str | None] = mapped_column(String(1024))
    issue_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("jira_issue.id", ondelete="CASCADE"), nullable=False
    )
    issue_key: Mapped[str] = mapped_column(String(50), nullable=False)
    issue_type_name: Mapped[str | None] = mapped_column(String(100))
    summary: Mapped[str | None] = mapped_column(String(1024))
    team_id: Mapped[str | None] = mapped_column(String(128))
    team_name: Mapped[str | None] = mapped_column(String(255))
    user_account_id: Mapped[str | None] = mapped_column(String(128))
    display_name: Mapped[str | None] = mapped_column(String(255))
    role_name: Mapped[str | None] = mapped_column(String(100))
    topic_type: Mapped[str] = mapped_column(String(50), nullable=False)
    direct_hours: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    refreshed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MonthlyAllocatedEffort(Base):
    __tablename__ = "monthly_allocated_effort"
    __table_args__ = (
        Index("ix_monthly_allocated_effort_period_kind", "period_month", "allocation_kind"),
        Index("ix_monthly_allocated_effort_period_feature", "period_month", "feature_root_id"),
    )

    id: Mapped[int] = mapped_column(_pk_bigint(), primary_key=True, autoincrement=True)
    period_month: Mapped[date] = mapped_column(Date, nullable=False)
    topic_type: Mapped[str] = mapped_column(String(50), nullable=False)
    feature_root_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("jira_feature_root.id", ondelete="SET NULL")
    )
    feature_key: Mapped[str | None] = mapped_column(String(50))
    feature_name: Mapped[str | None] = mapped_column(String(1024))
    issue_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("jira_issue.id", ondelete="SET NULL")
    )
    issue_key: Mapped[str | None] = mapped_column(String(50))
    team_id: Mapped[str | None] = mapped_column(String(128))
    team_name: Mapped[str | None] = mapped_column(String(255))
    source_user_email: Mapped[str] = mapped_column(String(255), nullable=False)
    source_display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_role_name: Mapped[str] = mapped_column(String(100), nullable=False)
    allocation_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    allocation_basis_hours: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    allocation_percentage: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    rule_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


DEFAULT_WORKFLOW_ISSUE_TYPE_KEY = "__default__"


class JiraWorkflow(Base):
    __tablename__ = "jira_workflow"
    __table_args__ = (
        UniqueConstraint("jira_entity_id", name="uq_jira_workflow_jira_entity_id"),
        UniqueConstraint("name", name="uq_jira_workflow_name"),
    )

    id: Mapped[int] = mapped_column(_pk_bigint(), primary_key=True, autoincrement=True)
    jira_entity_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status_order_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    raw_json: Mapped[dict | None] = mapped_column(JSON)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class JiraProjectWorkflowMapping(Base):
    __tablename__ = "jira_project_workflow_mapping"
    __table_args__ = (
        Index("ix_jira_project_workflow_mapping_workflow_id", "workflow_id"),
    )

    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("jira_project.id", ondelete="CASCADE"), primary_key=True
    )
    issue_type_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workflow_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("jira_workflow.id", ondelete="CASCADE"), nullable=False
    )
    issue_type_name: Mapped[str | None] = mapped_column(String(100))
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WorkflowStatusClassification(Base):
    __tablename__ = "workflow_status_classification"

    status_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    status_class: Mapped[str] = mapped_column(String(50), nullable=False)
