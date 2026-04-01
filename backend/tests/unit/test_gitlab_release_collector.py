from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.base import Base
from app.models.merge_request import MergeRequest
from app.models.release import Release
from app.models.repository import Repository
from app.services.gitlab_release_collector import (
    _deduplicate_merge_requests,
    _effective_commit_sha,
    _extract_jira_key,
    _hours_between,
    _is_customer_release,
    _lookback_from,
    _map_merge_requests_to_customer_releases,
    _markers_regex,
    _parse_merge_request,
    _reconcile_repository_releases,
    _sync_first_commit_timestamps,
    GitLabTagsClient,
    parse_tag_version,
)


def test_parse_tag_version_semver_with_prerelease() -> None:
    parsed = parse_tag_version("v10.2.3-rc.1")
    assert parsed.major == 10
    assert parsed.minor == 2
    assert parsed.patch == 3
    assert parsed.pre_release == "rc.1"


def test_parse_tag_version_non_semver_returns_none_fields() -> None:
    parsed = parse_tag_version("release-2026-03")
    assert parsed.major is None
    assert parsed.minor is None
    assert parsed.patch is None
    assert parsed.pre_release is None


def test_customer_release_false_for_configured_markers() -> None:
    marker_re = _markers_regex(["rc", "beta"])
    assert _is_customer_release("v10.1.0-rc.1", marker_re) is False
    assert _is_customer_release("v10.1.0-beta", marker_re) is False


def test_customer_release_true_for_final_version() -> None:
    marker_re = _markers_regex(["rc", "beta"])
    assert _is_customer_release("v10.1.0", marker_re) is True


def test_extract_jira_key_prefers_title_over_branch_description() -> None:
    jira_key, jira_key_source = _extract_jira_key(
        title="DEVOPS-433 implement collector",
        source_branch="feature/DEVOPS-999-something",
        description="fallback DEVOPS-888",
    )
    assert jira_key == "DEVOPS-433"
    assert jira_key_source == "title"


def test_extract_jira_key_falls_back_to_branch_then_description() -> None:
    jira_key, jira_key_source = _extract_jira_key(
        title="no issue key here",
        source_branch="feature/DEVOPS-777-fast-path",
        description="also has DEVOPS-666",
    )
    assert jira_key == "DEVOPS-777"
    assert jira_key_source == "branch"

    jira_key, jira_key_source = _extract_jira_key(
        title="no key",
        source_branch="feature/no-key",
        description="References DEVOPS-555 in details.",
    )
    assert jira_key == "DEVOPS-555"
    assert jira_key_source == "description"


def test_effective_commit_sha_prefers_merge_then_squash() -> None:
    assert _effective_commit_sha("abc123", "def456") == "abc123"
    assert _effective_commit_sha(None, "def456") == "def456"
    assert _effective_commit_sha("", "def456") == "def456"
    assert _effective_commit_sha(None, None) is None


def test_deduplicate_merge_requests_by_gitlab_id() -> None:
    merge_requests = [
        {"gitlab_mr_id": 42, "merged_at": "2026-03-31T08:00:00+00:00", "target_branch": "master"},
        {"gitlab_mr_id": 17, "merged_at": "2026-03-31T09:00:00+00:00", "target_branch": "10.x"},
        {"gitlab_mr_id": 42, "merged_at": "2026-03-31T08:00:00+00:00", "target_branch": "11.x"},
    ]
    deduplicated = _deduplicate_merge_requests(merge_requests)

    assert len(deduplicated) == 2
    ids = [item["gitlab_mr_id"] for item in deduplicated]
    assert ids == [17, 42]


def test_parse_merge_request_prefers_iid_for_gitlab_mr_id() -> None:
    parsed = _parse_merge_request(
        {
            "id": 9001,
            "iid": 42,
            "target_branch": "master",
            "created_at": "2026-03-31T08:00:00Z",
            "merged_at": "2026-03-31T09:00:00Z",
        }
    )
    assert parsed is not None
    assert parsed["gitlab_mr_id"] == 42


def test_hours_between_rounds_to_two_decimals() -> None:
    start = datetime(2026, 3, 31, 8, 0, tzinfo=timezone.utc)
    end = datetime(2026, 3, 31, 9, 20, 6, tzinfo=timezone.utc)
    assert str(_hours_between(start, end)) == "1.34"


def test_lookback_from_returns_utc_midnight_timestamp() -> None:
    lookback = _lookback_from(7)
    assert lookback.tzinfo == timezone.utc
    assert lookback.hour == 0
    assert lookback.minute == 0
    assert lookback.second == 0


def test_list_merge_request_commits_paginates() -> None:
    client = GitLabTagsClient(base_url="https://gitlab.example.com", token="dummy")
    responses = [
        [{"id": "c1"}, {"id": "c2"}],
        [{"id": "c3"}],
    ]

    def fake_get_json(url: str, *, params: dict[str, int] | None = None) -> object:
        assert "merge_requests/42/commits" in url
        assert params is not None
        return responses[params["page"] - 1]

    try:
        client._get_json = fake_get_json  # type: ignore[method-assign]
        commits = client.list_merge_request_commits("group/project", merge_request_iid=42, per_page=2)
        assert [item["id"] for item in commits] == ["c1", "c2", "c3"]
    finally:
        client.close()


def test_list_commit_tag_refs_paginates() -> None:
    client = GitLabTagsClient(base_url="https://gitlab.example.com", token="dummy")
    responses = [
        [{"name": "v1.0.0", "type": "tag"}, {"name": "v1.0.1", "type": "tag"}],
        [{"name": "v1.0.2", "type": "tag"}],
    ]

    def fake_get_json(url: str, *, params: dict[str, object] | None = None) -> object:
        assert "repository/commits/abc123/refs" in url
        assert params is not None
        assert params["type"] == "tag"
        return responses[int(params["page"]) - 1]

    try:
        client._get_json = fake_get_json  # type: ignore[method-assign]
        refs = client.list_commit_tag_refs("group/project", commit_sha="abc123", per_page=2)
        assert [item["name"] for item in refs] == ["v1.0.0", "v1.0.1", "v1.0.2"]
    finally:
        client.close()


def test_list_merged_merge_requests_sends_updated_after_and_filters_by_merged_at() -> None:
    client = GitLabTagsClient(base_url="https://gitlab.example.com", token="dummy")
    captured_params: list[dict[str, object]] = []
    responses = [
        [
            {
                "id": 1,
                "iid": 1,
                "target_branch": "main",
                "created_at": "2026-04-01T08:00:00Z",
                "merged_at": "2026-04-01T10:00:00Z",
            },
            {
                "id": 2,
                "iid": 2,
                "target_branch": "main",
                "created_at": "2026-03-01T08:00:00Z",
                "merged_at": "2026-03-01T09:00:00Z",
            },
        ]
    ]

    def fake_get_json(url: str, *, params: dict[str, object] | None = None) -> object:
        assert "merge_requests" in url
        assert params is not None
        captured_params.append(params)
        return responses[0]

    try:
        client._get_json = fake_get_json  # type: ignore[method-assign]
        merge_requests = client.list_merged_merge_requests(
            "group/project",
            target_branch="main",
            lookback_days=7,
            per_page=100,
        )
    finally:
        client.close()

    assert len(merge_requests) == 1
    assert merge_requests[0]["gitlab_mr_id"] == 1
    assert "updated_after" in captured_params[0]


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False)
    return maker()


def test_sync_first_commit_recomputes_for_mrs_in_lookback_window() -> None:
    """MRs with first_commit_at set are still refreshed when merged/updated in lookback."""

    class StubGitLab:
        def __init__(self) -> None:
            self.calls = 0

        def list_merge_request_commits(
            self,
            project_path: str,
            *,
            merge_request_iid: int,
            per_page: int = 100,
        ) -> list[dict[str, str]]:
            _ = (project_path, merge_request_iid, per_page)
            self.calls += 1
            return [
                {"committed_date": "2026-04-01T07:00:00Z"},
                {"committed_date": "2026-04-01T11:00:00Z"},
            ]

    recent = datetime.now(timezone.utc) - timedelta(days=1)
    with _session() as db:
        db.add(
            Repository(
                id=1,
                gitlab_id=1,
                name="repo",
                path="operations/dora-metrics",
                default_branch="main",
                active=True,
            )
        )
        db.add(
            MergeRequest(
                id=20,
                repository_id=1,
                gitlab_mr_id=99,
                target_branch="main",
                created_at=datetime(2026, 4, 1, 6, 0, tzinfo=timezone.utc),
                merged_at=recent,
                updated_at=recent,
                first_commit_at=datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
            )
        )
        db.commit()
        repo = db.get(Repository, 1)
        assert repo is not None
        mr = db.get(MergeRequest, 20)
        assert mr is not None
        stub = StubGitLab()
        updated_rows = _sync_first_commit_timestamps(
            db,
            stub,  # type: ignore[arg-type]
            repository=repo,
            project_path="operations/dora-metrics",
            cooldown_seconds=0.0,
            per_page=100,
            lookback_days=30,
        )
        db.commit()
        db.refresh(mr)

    assert updated_rows == 1
    assert stub.calls == 1
    assert mr.first_commit_at is not None
    got = mr.first_commit_at
    if got.tzinfo is None:
        got = got.replace(tzinfo=timezone.utc)
    assert got == datetime(2026, 4, 1, 7, 0, tzinfo=timezone.utc)


def test_map_merge_requests_clears_stale_fields_when_refs_disappear() -> None:
    class StubGitLab:
        def __init__(self) -> None:
            self.refs_by_sha: dict[str, list[dict[str, str]]] = {}

        def list_commit_tag_refs(
            self,
            project_path: str,
            *,
            commit_sha: str,
            per_page: int = 100,
        ) -> list[dict[str, str]]:
            _ = (project_path, per_page)
            return self.refs_by_sha.get(commit_sha, [])

    with _session() as db:
        db.add(
            Repository(
                id=1,
                gitlab_id=1,
                name="repo",
                path="operations/dora-metrics",
                default_branch="main",
                active=True,
            )
        )
        db.add(
            Release(
                id=10,
                repository_id=1,
                tag_name="v10.1.0",
                customer_release=True,
                commit_sha="a" * 40,
                committed_at=datetime(2026, 4, 1, 11, 0, tzinfo=timezone.utc),
            )
        )
        db.add(
            MergeRequest(
                id=20,
                repository_id=1,
                gitlab_mr_id=123,
                target_branch="main",
                created_at=datetime(2026, 4, 1, 8, 0, tzinfo=timezone.utc),
                merged_at=datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
                effective_commit_sha="deadbeef",
                first_commit_at=datetime(2026, 4, 1, 9, 0, tzinfo=timezone.utc),
            )
        )
        db.commit()

        gitlab = StubGitLab()
        gitlab.refs_by_sha["deadbeef"] = [{"type": "tag", "name": "v10.1.0"}]
        first_mapped = _map_merge_requests_to_customer_releases(
            db,
            gitlab,  # type: ignore[arg-type]
            repository=db.get(Repository, 1),
            project_path="operations/dora-metrics",
            cooldown_seconds=0.0,
            per_page=100,
        )
        db.commit()
        mr_after_first = db.get(MergeRequest, 20)
        assert mr_after_first is not None
        assert first_mapped == 1
        assert mr_after_first.lead_time_match_status == "matched"
        assert mr_after_first.first_customer_tag == "v10.1.0"
        assert mr_after_first.first_customer_tag_date is not None
        assert mr_after_first.release_wait_time_hours is not None
        assert mr_after_first.lead_time_hours is not None

        gitlab.refs_by_sha["deadbeef"] = []
        second_mapped = _map_merge_requests_to_customer_releases(
            db,
            gitlab,  # type: ignore[arg-type]
            repository=db.get(Repository, 1),
            project_path="operations/dora-metrics",
            cooldown_seconds=0.0,
            per_page=100,
        )
        db.commit()
        mr_after_second = db.get(MergeRequest, 20)

    assert second_mapped == 0
    assert mr_after_second is not None
    assert mr_after_second.lead_time_match_status == "no_tag_ref_found"
    assert mr_after_second.first_customer_tag is None
    assert mr_after_second.first_customer_tag_date is None
    assert mr_after_second.release_wait_time_hours is None
    assert mr_after_second.lead_time_hours is None


def test_reconcile_repository_releases_removes_tags_missing_upstream() -> None:
    with _session() as db:
        db.add(
            Repository(
                id=1,
                gitlab_id=1,
                name="repo",
                path="operations/dora-metrics",
                default_branch="main",
                active=True,
            )
        )
        db.add_all(
            [
                Release(
                    id=10,
                    repository_id=1,
                    tag_name="v10.1.0",
                    customer_release=True,
                    commit_sha="a" * 40,
                    committed_at=datetime(2026, 4, 1, 11, 0, tzinfo=timezone.utc),
                ),
                Release(
                    id=11,
                    repository_id=1,
                    tag_name="v10.2.0",
                    customer_release=True,
                    commit_sha="b" * 40,
                    committed_at=datetime(2026, 4, 2, 11, 0, tzinfo=timezone.utc),
                ),
            ]
        )
        db.commit()

        removed = _reconcile_repository_releases(
            db,
            repository_id=1,
            seen_tag_names={"v10.2.0"},
        )
        db.commit()
        remaining_tags = set(
            db.execute(select(Release.tag_name).where(Release.repository_id == 1)).scalars().all()
        )

    assert removed == 1
    assert remaining_tags == {"v10.2.0"}
