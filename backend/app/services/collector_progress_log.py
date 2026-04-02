"""Shared helpers for long-running collector loops (docker log heartbeat)."""

from __future__ import annotations

import logging

PROGRESS_STEP = 10


def log_every_n(
    logger: logging.Logger,
    *,
    prefix: str,
    index: int,
    total: int,
    step: int = PROGRESS_STEP,
) -> None:
    """Emit *prefix index/total* at first item, every *step* items, and on the last item."""
    if total <= 0:
        return
    if index == 1 or index % step == 0 or index == total:
        logger.info("%s %s/%s", prefix, index, total)
