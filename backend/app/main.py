from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import load_configuration
from app.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(_: FastAPI):
    config = load_configuration()
    start_scheduler(config)
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(title="DORA Metrics Backend", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
