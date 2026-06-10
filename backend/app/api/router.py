from __future__ import annotations

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.api import (
    admin_config,
    admin_data_health,
    admin_hrworks,
    admin_jira_analytics,
    admin_jira_feature_families,
    admin_jira_users,
    admin_people_data_users,
    admin_raw_tables,
    auth,
    jira_analytics_reports,
    metrics_public,
    repositories_public,
    sync_public,
)
from app.api.deps import SessionDep
from app.schemas.health import ComponentHealth, HealthResponse
from app.services.health_service import build_health_response

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(admin_config.router, prefix="/admin", tags=["admin"])
api_router.include_router(admin_data_health.router, prefix="/admin", tags=["admin"])
api_router.include_router(admin_raw_tables.router, prefix="/admin", tags=["admin"])
api_router.include_router(admin_jira_users.router, prefix="/admin", tags=["admin"])
api_router.include_router(admin_people_data_users.router, prefix="/admin", tags=["admin"])
api_router.include_router(admin_jira_feature_families.router, prefix="/admin", tags=["admin"])
api_router.include_router(admin_jira_analytics.router, prefix="/admin", tags=["admin"])
api_router.include_router(admin_hrworks.router, prefix="/admin", tags=["admin"])
api_router.include_router(metrics_public.router, prefix="/metrics", tags=["metrics"])
api_router.include_router(
    jira_analytics_reports.router,
    prefix="/jira-analytics",
    tags=["jira-analytics"],
)
api_router.include_router(repositories_public.router, prefix="/repositories", tags=["repositories"])
api_router.include_router(sync_public.router, prefix="/sync", tags=["sync"])


@api_router.get("/health", response_model=HealthResponse)
def api_health(db: SessionDep) -> JSONResponse:
    try:
        body = build_health_response(db)
    except Exception:
        body = HealthResponse(
            status="DOWN",
            components={
                "database": ComponentHealth(status="DOWN"),
                "gitlab": ComponentHealth(status="DOWN"),
                "jira": ComponentHealth(status="DOWN"),
            },
        )
    code = status.HTTP_200_OK if body.status == "UP" else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=code, content=body.model_dump(mode="json"))
