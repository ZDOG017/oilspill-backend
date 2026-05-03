from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str = "ok"


class EventBase(BaseModel):
    event_id: str
    image_name: str | None = None
    patch_name: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    sentinel_id: str | None = None
    class_name: str | None = None
    confidence: float | None = None
    bbox_pixels: list[float] | dict[str, Any] | str | None = None
    centroid_lon: float | None = None
    centroid_lat: float | None = None
    estimated_area_km2: float | None = None
    status: str | None = None
    note: str | None = None

    model_config = ConfigDict(extra="allow")


class EventListItem(EventBase):
    pass


class Geometry(BaseModel):
    type: str
    coordinates: list[Any]


class EventDetail(EventBase):
    geometry: Geometry


class GeoJSONFeature(BaseModel):
    type: str = "Feature"
    geometry: Geometry
    properties: dict[str, Any]


class GeoJSONFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: list[GeoJSONFeature] = Field(default_factory=list)


class EventStats(BaseModel):
    total_candidate_events: int
    mean_confidence: float
    min_confidence: float
    max_confidence: float
    mean_estimated_area_km2: float
    min_estimated_area_km2: float
    max_estimated_area_km2: float
    total_estimated_area_km2: float
