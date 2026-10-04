from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import FootfallCategory, PoleStatus


class RoadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    latitude: float
    longitude: float
    importance_score: int
    path: list[list[float]]
    pole_count: int = 0


class PoleOut(BaseModel):
    id: int
    code: str
    name: str
    road_id: int | None
    road_name: str | None
    latitude: float
    longitude: float
    footfall: int
    footfall_score: int
    visibility_score: int
    footfall_source: str
    footfall_updated_at: datetime | None
    category: FootfallCategory
    status: PoleStatus
    # Computed per request from the current footfall distribution.
    rank: int | None = None
    category_rank: int | None = None
    percentile: float | None = None
    distance_km: float | None = None


class PoleCreate(BaseModel):
    code: str = Field(pattern=r"^P\d{3,}$", examples=["P101"])
    name: str = Field(min_length=2, max_length=160)
    road_id: int | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    # Optional manual footfall (source "manual"); otherwise the configured
    # provider is asked for a reading.
    footfall: int | None = Field(default=None, ge=0)
    footfall_score: int | None = Field(default=None, ge=0, le=100)
    visibility_score: int | None = Field(default=None, ge=0, le=100)


class PoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    road_id: int | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    status: PoleStatus | None = None
    footfall: int | None = Field(default=None, ge=0)
    footfall_score: int | None = Field(default=None, ge=0, le=100)
    visibility_score: int | None = Field(default=None, ge=0, le=100)


class TopPoles(BaseModel):
    HIGH: list[PoleOut]
    MEDIUM: list[PoleOut]
    LOW: list[PoleOut]


class MapCenter(BaseModel):
    latitude: float
    longitude: float


class DataNotice(BaseModel):
    footfall: str
    geography: str


class MapResponse(BaseModel):
    center: MapCenter
    radius_km: float
    roads: list[RoadOut]
    poles: list[PoleOut]
    top: TopPoles
    counts: dict[str, int]
    notice: DataNotice


class FootfallSourceOut(BaseModel):
    source: str
    synthetic: bool
    model_version: str | None = None
    generated_at: str | None = None
    notice: str | None = None
    high_share: float
    medium_share: float


class RefreshOut(BaseModel):
    source: str
    updated: int
    missing: list[str]
