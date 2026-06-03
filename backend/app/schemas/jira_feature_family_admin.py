from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class FeatureFamilyFeatureItem(BaseModel):
    feature_root_id: int
    root_key: str
    name: str
    start_date: str | None = None
    target_end_date: str | None = None
    delivery_progress: str | None = None
    team_name: str | None = None
    total_hours: float = Field(ge=0, default=0)
    assigned_family_id: int | None = None
    assigned_family_name: str | None = None


class FeatureFamilyAdminItem(BaseModel):
    id: int
    name: str
    description: str | None = None
    suggestion_keywords: list[str] = Field(default_factory=list)
    title_match_pattern: str | None = None
    active: bool
    member_count: int = 0
    created_at: str | None = None
    updated_at: str | None = None


class FeatureFamilyListResponse(BaseModel):
    items: list[FeatureFamilyAdminItem]


class FeatureFamilyDetailResponse(BaseModel):
    family: FeatureFamilyAdminItem
    members: list[FeatureFamilyFeatureItem]


class FeatureFamilyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    suggestion_keywords: list[str] = Field(default_factory=list)
    title_match_pattern: str | None = Field(default=None, max_length=512)

    @field_validator("name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("suggestion_keywords")
    @classmethod
    def _clean_keywords(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]


class FeatureFamilyPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    suggestion_keywords: list[str] | None = None
    title_match_pattern: str | None = Field(default=None, max_length=512)
    active: bool | None = None

    @field_validator("name")
    @classmethod
    def _clean_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("suggestion_keywords")
    @classmethod
    def _clean_keywords(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return [item.strip() for item in value if item.strip()]


class FeatureFamilyMembersPut(BaseModel):
    feature_root_ids: list[int] = Field(default_factory=list)


class FeatureFamilyFeatureListResponse(BaseModel):
    items: list[FeatureFamilyFeatureItem]


class FeatureFamilySuggestionItem(BaseModel):
    suggestion_id: str
    family_id: int
    family_name: str
    feature_root_id: int
    root_key: str
    feature_name: str
    confidence: float = Field(ge=0, le=1)
    reason: str
    matched_tokens: list[str] = Field(default_factory=list)


class FeatureFamilySuggestionsResponse(BaseModel):
    items: list[FeatureFamilySuggestionItem]


class FeatureFamilySuggestionDecisionRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1024)

