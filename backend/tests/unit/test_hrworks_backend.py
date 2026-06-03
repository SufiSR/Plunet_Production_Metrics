from __future__ import annotations

from datetime import date
from decimal import Decimal

import httpx
import pytest
import respx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import app.hrworks.sync_pipeline as hrworks_sync_pipeline
import app.jira_analytics.allocation as allocation_module
from app.config_schema import ConfigurationSchema
from app.hrworks.client import HrworksClient
from app.hrworks.collector import HrworksCounts, collect_hrworks_monthly_hours, resolve_sync_months
from app.hrworks.extractors import (
    extract_month_record,
    minutes_to_hours,
    parse_working_times_by_email,
)
from app.hrworks.periods import (
    MonthWindow,
    default_hrworks_sync_month_windows,
    incremental_month_windows,
    is_person_eligible_for_month,
    iter_month_windows,
)
from app.hrworks.person_mapping import (
    hrworks_response_email_matches_person,
    load_jira_users_with_email,
    to_hrworks_person_email,
)
from app.hrworks.roster import parse_master_data_person
from app.hrworks.sync_pipeline import run_hrworks_sync
from app.jira_analytics.models import HrworksPersonRoster, JiraUser, JiraUserMonthlyHrworksHours
from app.models.base import Base


def _mock_master_data(base: str, persons: list[dict[str, object]]) -> None:
    def _handler(request: httpx.Request) -> httpx.Response:
        page = request.url.params.get("page", "1")
        if page != "1":
            return httpx.Response(200, json={"persons": []})
        return httpx.Response(200, json={"persons": persons})

    respx.get(f"{base}/persons/master-data").mock(side_effect=_handler)


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with maker() as session:
        yield session


def test_to_hrworks_person_email_maps_non_plunet_domains() -> None:
    assert to_hrworks_person_email("josef.radix@edvk.de") == "josef.radix@plunet.com"
    assert to_hrworks_person_email("Person.One@plunet.com") == "person.one@plunet.com"
    assert to_hrworks_person_email("  A@Other.ORG  ") == "a@plunet.com"


def test_hrworks_response_email_matches_person_accepts_departed_suffix() -> None:
    person_id = "sophie.halbeisen@plunet.com"
    assert hrworks_response_email_matches_person(person_id, person_id)
    assert hrworks_response_email_matches_person(
        "sophie.halbeisen@plunet.comausgeschieden1",
        person_id,
    )
    assert not hrworks_response_email_matches_person(
        "other.person@plunet.com",
        person_id,
    )


def test_minutes_to_hours_conversion() -> None:
    assert minutes_to_hours(60) == Decimal("1.00")
    assert minutes_to_hours(8160) == Decimal("136.00")


def test_parse_working_times_by_email() -> None:
    list_payload = [
        {
            "sufian.reiter@plunet.com": [
                {
                    "beginDate": "2026-05-01",
                    "endDate": "2026-05-31",
                    "targetWorkingTimeMinutes": 8160,
                    "workingTimeMinutes": 120,
                }
            ]
        }
    ]
    dict_payload = {
        "sufian.reiter@plunet.com": [
            {
                "beginDate": "2026-05-01",
                "endDate": "2026-05-31",
                "targetWorkingTimeMinutes": 8160,
                "workingTimeMinutes": 120,
            }
        ]
    }
    assert len(parse_working_times_by_email(list_payload)["sufian.reiter@plunet.com"]) == 1
    assert len(parse_working_times_by_email(dict_payload)["sufian.reiter@plunet.com"]) == 1


def test_extract_month_record() -> None:
    parsed = extract_month_record(
        {
            "beginDate": "2026-05-01",
            "endDate": "2026-05-31",
            "targetWorkingTimeMinutes": 60,
            "workingTimeMinutes": 30,
        }
    )
    assert parsed is not None
    month_start, month_end, planned, clocked = parsed
    assert month_start == date(2026, 5, 1)
    assert month_end == date(2026, 5, 31)
    assert planned == Decimal("1.00")
    assert clocked == Decimal("0.50")


def test_iter_month_windows_from_2024_to_current() -> None:
    windows = iter_month_windows(date(2024, 1, 1), date(2024, 3, 1))
    assert len(windows) == 3
    assert windows[0].month_start == date(2024, 1, 1)
    assert windows[-1].month_start == date(2024, 3, 1)


def test_incremental_month_windows_includes_past_current_and_forecast() -> None:
    windows = incremental_month_windows(
        past_months=3,
        forecast_months=6,
        today=date(2026, 5, 15),
    )
    assert [window.month_start for window in windows] == [
        date(2026, 2, 1),
        date(2026, 3, 1),
        date(2026, 4, 1),
        date(2026, 5, 1),
        date(2026, 6, 1),
        date(2026, 7, 1),
        date(2026, 8, 1),
        date(2026, 9, 1),
        date(2026, 10, 1),
        date(2026, 11, 1),
    ]


def test_resolve_sync_months_incremental_uses_rolling_window() -> None:
    config = ConfigurationSchema()
    config.hrworks.incremental_months_back = 3
    config.hrworks.incremental_forecast_months = 6
    windows = resolve_sync_months(
        config=config,
        incremental=True,
        start_date=None,
        end_date=None,
    )
    expected = incremental_month_windows(
        past_months=3,
        forecast_months=6,
        today=date.today(),
    )
    assert windows == expected


def test_default_hrworks_sync_month_windows() -> None:
    windows = default_hrworks_sync_month_windows(today=date(2026, 5, 15))
    assert len(windows) == 35
    assert windows[0].month_start == date(2024, 1, 1)
    assert windows[11].month_start == date(2024, 12, 1)
    assert windows[12].month_start == date(2025, 1, 1)
    assert windows[23].month_start == date(2025, 12, 1)
    assert windows[24].month_start == date(2026, 1, 1)
    assert windows[-1].month_start == date(2026, 11, 1)


def test_resolve_sync_months_default() -> None:
    config = ConfigurationSchema()
    windows = resolve_sync_months(
        config=config,
        incremental=False,
        start_date=None,
        end_date=None,
    )
    assert len(windows) >= 24
    assert windows[0].month_start == date(2024, 1, 1)


def test_is_person_eligible_for_month_respects_join_and_leave() -> None:
    month = MonthWindow(month_start=date(2024, 6, 1), month_end=date(2024, 6, 30))
    assert is_person_eligible_for_month(join_date=date(2024, 1, 1), leave_date=None, month=month)
    assert not is_person_eligible_for_month(
        join_date=date(2024, 7, 1), leave_date=None, month=month
    )
    assert is_person_eligible_for_month(
        join_date=date(2020, 1, 1), leave_date=date(2024, 6, 15), month=month
    )
    assert not is_person_eligible_for_month(
        join_date=date(2020, 1, 1), leave_date=date(2024, 5, 31), month=month
    )


def test_parse_master_data_person() -> None:
    parsed = parse_master_data_person(
        {
            "personId": "josef.radix@plunet.com",
            "email": "josef.radix@plunet.com",
            "joinDate": "2020-01-01",
            "leaveDate": "2025-03-31",
            "isActive": False,
        }
    )
    assert parsed is not None
    assert parsed.person_id == "josef.radix@plunet.com"
    assert parsed.leave_date == date(2025, 3, 31)


@respx.mock
def test_hrworks_client_authentication_and_working_times_query(db_session: Session) -> None:
    base = "https://api.hrworks.de/v2"
    respx.post(f"{base}/authentication").respond(200, json={"token": "abc123"})
    route = respx.get(f"{base}/working-times")
    route.respond(
        200,
        json=[
            {
                "person.one@plunet.com": [
                    {
                        "beginDate": "2026-05-01",
                        "endDate": "2026-05-31",
                        "targetWorkingTimeMinutes": 60,
                        "workingTimeMinutes": 30,
                    }
                ]
            }
        ],
    )

    with HrworksClient(base, "access", "secret") as client:
        payload = client.fetch_working_times(
            begin_date="2026-05-01",
            end_date="2026-05-31",
            person_emails=["person.one@plunet.com"],
        )

    assert isinstance(payload, list)
    request = route.calls[0].request
    assert "persons=person.one@plunet.com" in str(request.url)
    assert "%40" not in str(request.url)
    assert "interval=months" in str(request.url)


@respx.mock
def test_load_jira_users_requires_account_id_and_dedupes_email(db_session: Session) -> None:
    db_session.add_all(
        [
            JiraUser(account_id="acc-1", email_address="a@plunet.com"),
            JiraUser(account_id="acc-2", email_address="A@plunet.com"),
            JiraUser(account_id="", email_address="b@plunet.com"),
            JiraUser(account_id="acc-4", email_address=None),
        ]
    )
    db_session.commit()

    users = load_jira_users_with_email(db_session)

    assert len(users) == 1
    assert users[0][1] == "a@plunet.com"


@respx.mock
def test_collect_hrworks_monthly_hours_upserts_by_user_and_month(db_session: Session) -> None:
    user = JiraUser(account_id="acc-1", email_address="Person.One@plunet.com")
    db_session.add(user)
    db_session.commit()

    base = "https://api.hrworks.de/v2"
    respx.post(f"{base}/authentication").respond(200, json={"token": "abc123"})
    _mock_master_data(
        base,
        [
            {
                "personId": "person.one@plunet.com",
                "joinDate": "2020-01-01",
                "isActive": True,
            }
        ],
    )
    respx.get(f"{base}/working-times").respond(
        200,
        json={
            "person.one@plunet.com": [
                {
                    "beginDate": "2026-05-01",
                    "endDate": "2026-05-31",
                    "targetWorkingTimeMinutes": 60,
                    "workingTimeMinutes": 30,
                }
            ]
        },
    )

    config = ConfigurationSchema()
    counts = collect_hrworks_monthly_hours(
        db_session,
        config=config,
        access_key="access",
        secret_access_key="secret",
        months=iter_month_windows(date(2026, 5, 1), date(2026, 5, 1)),
    )

    assert counts.rows_upserted == 1
    row = db_session.execute(select(JiraUserMonthlyHrworksHours)).scalar_one()
    assert row.jira_user_id == user.id
    assert row.month_start == date(2026, 5, 1)
    assert row.planned_working_hours == Decimal("1.00")
    assert row.clocked_working_hours == Decimal("0.50")
    assert counts.months_upserted == {date(2026, 5, 1)}


def test_run_hrworks_sync_rebuilds_allocation_for_upserted_months(monkeypatch) -> None:
    class DummySession:
        def __enter__(self) -> object:
            return object()

        def __exit__(self, *_args: object) -> None:
            return None

    rebuilt_months: list[list[date]] = []

    def fake_collect(*_args: object, **_kwargs: object) -> HrworksCounts:
        return HrworksCounts(
            months_seen=3,
            rows_upserted=2,
            months_upserted={date(2026, 5, 1), date(2026, 6, 1)},
        )

    def fake_rebuild(_db: object, *, period_months: list[date], **_kwargs: object) -> dict[str, object]:
        rebuilt_months.append(period_months)
        return {
            "periods": [month.isoformat() for month in period_months],
            "topic_rows": 4,
            "allocation_rows": 8,
        }

    monkeypatch.setattr(hrworks_sync_pipeline, "_create_log", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(hrworks_sync_pipeline, "_update_log", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(hrworks_sync_pipeline, "_finish_log", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(hrworks_sync_pipeline, "collect_hrworks_monthly_hours", fake_collect)
    monkeypatch.setattr(allocation_module, "rebuild_monthly_allocation", fake_rebuild)

    result = run_hrworks_sync(
        session_factory=DummySession,
        config=ConfigurationSchema(),
        access_key="access",
        secret_access_key="secret",
        months=iter_month_windows(date(2026, 5, 1), date(2026, 7, 1)),
    )

    assert result["status"] == "success"
    assert rebuilt_months == [[date(2026, 5, 1), date(2026, 6, 1)]]
    runtime = result["pipeline_runtime"]
    assert runtime["allocation_period_months"] == ["2026-05-01", "2026-06-01"]
    assert runtime["phases"]["allocation"]["status"] == "success"
    assert runtime["phases"]["allocation"]["records_processed"]["allocation_rows"] == 8


@respx.mock
def test_collect_hrworks_emits_progress_snapshots(db_session: Session) -> None:
    user = JiraUser(account_id="acc-1", email_address="Person.One@plunet.com")
    db_session.add(user)
    db_session.commit()

    base = "https://api.hrworks.de/v2"
    respx.post(f"{base}/authentication").respond(200, json={"token": "abc123"})
    _mock_master_data(
        base,
        [
            {
                "personId": "person.one@plunet.com",
                "joinDate": "2020-01-01",
                "isActive": True,
            }
        ],
    )
    respx.get(f"{base}/working-times").respond(
        200,
        json={
            "person.one@plunet.com": [
                {
                    "beginDate": "2026-05-01",
                    "endDate": "2026-05-31",
                    "targetWorkingTimeMinutes": 60,
                    "workingTimeMinutes": 30,
                }
            ]
        },
    )

    snapshots: list[dict] = []

    collect_hrworks_monthly_hours(
        db_session,
        config=ConfigurationSchema(),
        access_key="access",
        secret_access_key="secret",
        months=iter_month_windows(date(2026, 5, 1), date(2026, 5, 1)),
        on_progress=snapshots.append,
    )

    assert snapshots
    assert snapshots[0]["step"] == "roster"
    assert any(s.get("step") == "ingesting" for s in snapshots)
    assert snapshots[-1]["step"] == "done"
    assert snapshots[-1]["rows_upserted"] == 1


@respx.mock
def test_collect_hrworks_maps_external_jira_email_to_plunet_person_id(
    db_session: Session,
) -> None:
    user = JiraUser(account_id="acc-52", email_address="josef.radix@edvk.de")
    db_session.add(user)
    db_session.commit()

    base = "https://api.hrworks.de/v2"
    respx.post(f"{base}/authentication").respond(200, json={"token": "abc123"})
    _mock_master_data(
        base,
        [
            {
                "personId": "josef.radix@plunet.com",
                "joinDate": "2020-01-01",
                "leaveDate": "2025-12-31",
                "isActive": True,
            }
        ],
    )
    route = respx.get(f"{base}/working-times")
    route.respond(
        200,
        json={
            "josef.radix@plunet.com": [
                {
                    "beginDate": "2024-01-01",
                    "endDate": "2024-01-31",
                    "targetWorkingTimeMinutes": 9600,
                    "workingTimeMinutes": 9000,
                }
            ]
        },
    )

    config = ConfigurationSchema()
    counts = collect_hrworks_monthly_hours(
        db_session,
        config=config,
        access_key="access",
        secret_access_key="secret",
        months=iter_month_windows(date(2024, 1, 1), date(2024, 1, 1)),
    )

    assert counts.rows_upserted == 1
    assert counts.unknown_emails == []
    request = route.calls[0].request
    assert "persons=josef.radix@plunet.com" in str(request.url)
    row = db_session.execute(select(JiraUserMonthlyHrworksHours)).scalar_one()
    assert row.jira_user_id == user.id
    assert row.planned_working_hours == Decimal("160.00")


@respx.mock
def test_collect_hrworks_accepts_ausgeschieden_working_times_key(
    db_session: Session,
) -> None:
    user = JiraUser(account_id="acc-dep", email_address="sophie.halbeisen@plunet.com")
    db_session.add(user)
    db_session.commit()

    base = "https://api.hrworks.de/v2"
    respx.post(f"{base}/authentication").respond(200, json={"token": "abc123"})
    _mock_master_data(
        base,
        [
            {
                "personId": "sophie.halbeisen@plunet.com",
                "joinDate": "2020-01-01",
                "leaveDate": None,
                "isActive": True,
            }
        ],
    )
    respx.get(f"{base}/working-times").respond(
        200,
        json={
            "sophie.halbeisen@plunet.comausgeschieden1": [
                {
                    "beginDate": "2026-05-01",
                    "endDate": "2026-05-31",
                    "targetWorkingTimeMinutes": 9600,
                    "workingTimeMinutes": 9000,
                }
            ]
        },
    )

    counts = collect_hrworks_monthly_hours(
        db_session,
        config=ConfigurationSchema(),
        access_key="access",
        secret_access_key="secret",
        months=iter_month_windows(date(2026, 5, 1), date(2026, 5, 1)),
    )

    assert counts.rows_upserted == 1
    assert counts.unknown_emails == []


@respx.mock
def test_collect_skips_person_left_before_sync_month(db_session: Session) -> None:
    user = JiraUser(account_id="acc-old", email_address="former@plunet.com")
    db_session.add(user)
    db_session.commit()

    base = "https://api.hrworks.de/v2"
    respx.post(f"{base}/authentication").respond(200, json={"token": "abc123"})
    _mock_master_data(
        base,
        [
            {
                "personId": "former@plunet.com",
                "joinDate": "2018-01-01",
                "leaveDate": "2019-12-31",
                "isActive": False,
            }
        ],
    )
    route = respx.get(f"{base}/working-times")
    route.respond(200, json={})

    config = ConfigurationSchema()
    counts = collect_hrworks_monthly_hours(
        db_session,
        config=config,
        access_key="access",
        secret_access_key="secret",
        months=iter_month_windows(date(2024, 1, 1), date(2024, 1, 1)),
    )

    assert counts.rows_upserted == 0
    assert counts.api_calls == 0
    assert route.call_count == 0
    roster = db_session.execute(select(HrworksPersonRoster)).scalar_one()
    assert roster.leave_date == date(2019, 12, 31)
    assert roster.jira_user_id == user.id
