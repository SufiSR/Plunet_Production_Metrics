from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import SessionDep, require_admin_session
from app.schemas.jira_feature_family_admin import (
    FeatureFamilyCreate,
    FeatureFamilyDetailResponse,
    FeatureFamilyFeatureListResponse,
    FeatureFamilyListResponse,
    FeatureFamilyMembersPut,
    FeatureFamilyPatch,
    FeatureFamilySuggestionDecisionRequest,
    FeatureFamilySuggestionsResponse,
)
from app.services.admin_jira_feature_families_service import (
    accept_feature_family_suggestion,
    create_feature_family,
    get_feature_family_detail,
    list_feature_families,
    list_feature_family_features,
    list_feature_family_suggestions,
    patch_feature_family,
    put_feature_family_members,
    reject_feature_family_suggestion,
)

router = APIRouter()
AdminSessionDep = Annotated[None, Depends(require_admin_session)]


@router.get("/jira-feature-families", response_model=FeatureFamilyListResponse)
def get_feature_families(
    _auth: AdminSessionDep,
    db: SessionDep,
) -> FeatureFamilyListResponse:
    return list_feature_families(db)


@router.post(
    "/jira-feature-families",
    response_model=FeatureFamilyDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_feature_family(
    body: FeatureFamilyCreate,
    _auth: AdminSessionDep,
    db: SessionDep,
) -> FeatureFamilyDetailResponse:
    try:
        detail = create_feature_family(db, body)
        db.commit()
        return detail
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/jira-feature-families/features", response_model=FeatureFamilyFeatureListResponse)
def get_feature_family_features(
    _auth: AdminSessionDep,
    db: SessionDep,
    search: Annotated[str | None, Query(max_length=255)] = None,
    unassigned_only: bool = False,
) -> FeatureFamilyFeatureListResponse:
    return list_feature_family_features(db, search=search, unassigned_only=unassigned_only)


@router.get("/jira-feature-families/suggestions", response_model=FeatureFamilySuggestionsResponse)
def get_feature_family_suggestions(
    _auth: AdminSessionDep,
    db: SessionDep,
) -> FeatureFamilySuggestionsResponse:
    return list_feature_family_suggestions(db)


@router.post(
    "/jira-feature-families/suggestions/{suggestion_id}/accept",
    response_model=FeatureFamilyDetailResponse,
)
def post_accept_feature_family_suggestion(
    suggestion_id: str,
    body: FeatureFamilySuggestionDecisionRequest,
    _auth: AdminSessionDep,
    db: SessionDep,
) -> FeatureFamilyDetailResponse:
    try:
        detail = accept_feature_family_suggestion(db, suggestion_id, reason=body.reason)
        db.commit()
        return detail
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion not found",
        ) from None
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/jira-feature-families/suggestions/{suggestion_id}/reject",
    response_model=FeatureFamilySuggestionsResponse,
)
def post_reject_feature_family_suggestion(
    suggestion_id: str,
    body: FeatureFamilySuggestionDecisionRequest,
    _auth: AdminSessionDep,
    db: SessionDep,
) -> FeatureFamilySuggestionsResponse:
    try:
        response = reject_feature_family_suggestion(db, suggestion_id, reason=body.reason)
        db.commit()
        return response
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion not found",
        ) from None
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/jira-feature-families/{family_id}", response_model=FeatureFamilyDetailResponse)
def get_feature_family(
    family_id: int,
    _auth: AdminSessionDep,
    db: SessionDep,
) -> FeatureFamilyDetailResponse:
    try:
        return get_feature_family_detail(db, family_id)
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family not found",
        ) from None


@router.patch("/jira-feature-families/{family_id}", response_model=FeatureFamilyDetailResponse)
def patch_feature_family_endpoint(
    family_id: int,
    body: FeatureFamilyPatch,
    _auth: AdminSessionDep,
    db: SessionDep,
) -> FeatureFamilyDetailResponse:
    try:
        detail = patch_feature_family(db, family_id, body)
        db.commit()
        return detail
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family not found",
        ) from None


@router.put(
    "/jira-feature-families/{family_id}/members",
    response_model=FeatureFamilyDetailResponse,
)
def put_feature_family_members_endpoint(
    family_id: int,
    body: FeatureFamilyMembersPut,
    _auth: AdminSessionDep,
    db: SessionDep,
) -> FeatureFamilyDetailResponse:
    try:
        detail = put_feature_family_members(db, family_id, body)
        db.commit()
        return detail
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family not found",
        ) from None
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

