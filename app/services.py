from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from statistics import mean
from typing import Any

from app.schemas import EventDetail, EventListItem, EventStats, GeoJSONFeature, GeoJSONFeatureCollection, Geometry


DATA_FILE = Path(__file__).parent / "data" / "seed_events.geojson"


class DataFileError(RuntimeError):
    pass


class EventNotFoundError(LookupError):
    pass


@dataclass
class EventRecord:
    properties: dict[str, Any]
    geometry: dict[str, Any]
    feature: dict[str, Any]


class EventService:
    def _load_feature_collection(self) -> dict[str, Any]:
        return _read_geojson_file()

    def _load_records(self) -> list[EventRecord]:
        feature_collection = self._load_feature_collection()
        features = feature_collection.get("features", [])
        records: list[EventRecord] = []

        for feature in features:
            properties = dict(feature.get("properties", {}))
            geometry = dict(feature.get("geometry", {}))
            records.append(EventRecord(properties=properties, geometry=geometry, feature=feature))

        return records

    def list_events(
        self,
        *,
        min_confidence: float | None = None,
        max_confidence: float | None = None,
        min_area: float | None = None,
        max_area: float | None = None,
        status: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[EventListItem]:
        records = self._filter_records(
            min_confidence=min_confidence,
            max_confidence=max_confidence,
            min_area=min_area,
            max_area=max_area,
            status=status,
            start_date=start_date,
            end_date=end_date,
        )
        return [EventListItem(**record.properties) for record in records]

    def get_event_by_id(self, event_id: str) -> EventDetail:
        for record in self._load_records():
            if str(record.properties.get("event_id")) == event_id:
                return EventDetail(
                    **record.properties,
                    geometry=Geometry(**record.geometry),
                )
        raise EventNotFoundError(f"Event '{event_id}' was not found.")

    def get_stats(
        self,
        *,
        min_confidence: float | None = None,
        max_confidence: float | None = None,
        min_area: float | None = None,
        max_area: float | None = None,
        status: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> EventStats:
        records = self._filter_records(
            min_confidence=min_confidence,
            max_confidence=max_confidence,
            min_area=min_area,
            max_area=max_area,
            status=status,
            start_date=start_date,
            end_date=end_date,
        )

        confidences = [value for value in (_to_float(r.properties.get("confidence")) for r in records) if value is not None]
        areas = [value for value in (_to_float(r.properties.get("estimated_area_km2")) for r in records) if value is not None]

        return EventStats(
            total_candidate_events=len(records),
            mean_confidence=_safe_mean(confidences),
            min_confidence=min(confidences, default=0.0),
            max_confidence=max(confidences, default=0.0),
            mean_estimated_area_km2=_safe_mean(areas),
            min_estimated_area_km2=min(areas, default=0.0),
            max_estimated_area_km2=max(areas, default=0.0),
            total_estimated_area_km2=round(sum(areas), 6),
        )

    def get_geojson(
        self,
        *,
        min_confidence: float | None = None,
        max_area: float | None = None,
        status: str | None = None,
    ) -> GeoJSONFeatureCollection:
        records = self._filter_records(
            min_confidence=min_confidence,
            max_area=max_area,
            status=status,
        )

        return GeoJSONFeatureCollection(
            features=[
                GeoJSONFeature(
                    type="Feature",
                    geometry=Geometry(**record.geometry),
                    properties=record.properties,
                )
                for record in records
            ]
        )

    def _filter_records(
        self,
        *,
        min_confidence: float | None = None,
        max_confidence: float | None = None,
        min_area: float | None = None,
        max_area: float | None = None,
        status: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[EventRecord]:
        records = self._load_records()
        return [
            record
            for record in records
            if _matches_filters(
                record,
                min_confidence=min_confidence,
                max_confidence=max_confidence,
                min_area=min_area,
                max_area=max_area,
                status=status,
                start_date=start_date,
                end_date=end_date,
            )
        ]


@lru_cache(maxsize=1)
def _read_geojson_file() -> dict[str, Any]:
    if not DATA_FILE.exists():
        raise DataFileError(
            f"GeoJSON data file not found at '{DATA_FILE}'. Add app/data/seed_events.geojson and try again."
        )

    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except json.JSONDecodeError as exc:
        raise DataFileError(f"GeoJSON data file is not valid JSON: {exc}") from exc
    except OSError as exc:
        raise DataFileError(f"Unable to read GeoJSON data file: {exc}") from exc

    if payload.get("type") != "FeatureCollection":
        raise DataFileError("GeoJSON data file must contain a FeatureCollection.")

    return payload


def _matches_filters(
    record: EventRecord,
    *,
    min_confidence: float | None = None,
    max_confidence: float | None = None,
    min_area: float | None = None,
    max_area: float | None = None,
    status: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> bool:
    confidence = _to_float(record.properties.get("confidence"))
    area = _to_float(record.properties.get("estimated_area_km2"))
    record_status = str(record.properties.get("status", "")).strip().lower()
    record_start = _parse_date(record.properties.get("start_time"))
    record_end = _parse_date(record.properties.get("end_time"))

    if min_confidence is not None and (confidence is None or confidence < min_confidence):
        return False
    if max_confidence is not None and (confidence is None or confidence > max_confidence):
        return False
    if min_area is not None and (area is None or area < min_area):
        return False
    if max_area is not None and (area is None or area > max_area):
        return False
    if status is not None and record_status != status.strip().lower():
        return False
    if start_date is not None and (record_start is None or record_start < start_date):
        return False
    if end_date is not None and (record_end is None or record_end > end_date):
        return False

    return True


def _parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None

    text = str(value).strip()
    try:
        if text.endswith("Z"):
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        return datetime.fromisoformat(text).date()
    except ValueError:
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(mean(values), 6)
