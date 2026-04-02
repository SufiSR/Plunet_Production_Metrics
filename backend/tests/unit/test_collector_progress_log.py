from __future__ import annotations

import logging

import pytest

from app.services.collector_progress_log import log_every_n


def test_log_every_n_emits_on_first_last_and_step(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    log = logging.getLogger("test_progress")
    for i in range(1, 26):
        log_every_n(log, prefix="step", index=i, total=25, step=10)
    messages = [r.message for r in caplog.records]
    assert messages == [
        "step 1/25",
        "step 10/25",
        "step 20/25",
        "step 25/25",
    ]


def test_log_every_n_no_emit_when_total_zero(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    log = logging.getLogger("test_progress2")
    log_every_n(log, prefix="x", index=1, total=0)
    assert caplog.records == []
