from __future__ import annotations

from unittest.mock import MagicMock

import app.scheduler as scheduler_mod
from app.config_schema import ConfigurationSchema


def test_stop_scheduler_noop_when_none(monkeypatch) -> None:
    monkeypatch.setattr(scheduler_mod, "_scheduler", None)
    scheduler_mod.stop_scheduler()
    assert scheduler_mod.get_scheduler() is None


def test_start_scheduler_returns_running_instance(monkeypatch) -> None:
    monkeypatch.setattr(scheduler_mod, "_scheduler", None)
    cfg = ConfigurationSchema()
    try:
        sched = scheduler_mod.start_scheduler(cfg)
        assert sched.running is True
        again = scheduler_mod.start_scheduler(cfg)
        assert again is sched
    finally:
        scheduler_mod.stop_scheduler()
    assert scheduler_mod.get_scheduler() is None


def test_reschedule_nightly_sync_when_not_running(monkeypatch) -> None:
    mock_sched = MagicMock()
    mock_sched.running = False
    monkeypatch.setattr(scheduler_mod, "_scheduler", mock_sched)
    scheduler_mod.reschedule_nightly_sync(ConfigurationSchema())
    mock_sched.reschedule_job.assert_not_called()
