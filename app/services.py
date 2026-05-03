from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from statistics import mean
from typing import Any

from app.schemas import (
    EventDetail,
    EventListItem,
    EventStats,
    GeoJSONFeature,
    GeoJSONFeatureCollection,
    Geometry,
    PaginatedEventsResponse,
    PredictionDetection,
    PredictionResponse,
)


DATA_FILE = Path(__file__).parent / "data" / "seed_events.geojson"
MODEL_FILE = Path(__file__).parent / "models" / "dartis_yolov8s_768_best.pt"
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


class DataFileError(RuntimeError):
    pass


class EventNotFoundError(LookupError):
    pass


class ModelFileError(RuntimeError):
    pass


class InferenceDependencyError(RuntimeError):
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
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedEventsResponse:
        records = self._filter_records(
            min_confidence=min_confidence,
            max_confidence=max_confidence,
            min_area=min_area,
            max_area=max_area,
            status=status,
            start_date=start_date,
            end_date=end_date,
        )
        paginated_records = records[offset : offset + limit]
        events = [EventListItem(**record.properties) for record in paginated_records]
        return PaginatedEventsResponse(
            total_count=len(records),
            returned_count=len(events),
            limit=limit,
            offset=offset,
            events=events,
        )

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

    def predict_from_image(self, *, filename: str, image_bytes: bytes) -> PredictionResponse:
        image = _open_image(image_bytes)
        image_width, image_height = image.size
        model = _load_yolo_model()
        results = model.predict(image, verbose=False)

        detections: list[PredictionDetection] = []
        for result in results:
            boxes = getattr(result, "boxes", None)
            names = getattr(result, "names", {})
            if boxes is None:
                continue

            xyxy_values = boxes.xyxy.tolist()
            confidence_values = boxes.conf.tolist()
            class_values = boxes.cls.tolist()

            for xyxy, confidence, class_id in zip(xyxy_values, confidence_values, class_values):
                class_name = names.get(int(class_id), str(int(class_id)))
                detections.append(
                    PredictionDetection(
                        class_name=str(class_name),
                        confidence=round(float(confidence), 6),
                        bbox_pixels=[round(float(value), 2) for value in xyxy],
                    )
                )

        detections_count = len(detections)
        return PredictionResponse(
            filename=filename,
            image_width=image_width,
            image_height=image_height,
            detections_count=detections_count,
            detections=detections,
            status="candidate_detected" if detections_count > 0 else "no_candidate_detected",
            note="AI-generated candidate detections; not manually verified.",
            map_ready=False,
            map_ready_reason="Uploaded image does not include geospatial metadata.",
        )


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


@lru_cache(maxsize=1)
def _load_yolo_model():
    if not MODEL_FILE.exists():
        raise ModelFileError(
            f"YOLO model file not found at '{MODEL_FILE}'. Place dartis_yolov8s_768_best.pt in app/models and try again."
        )

    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise InferenceDependencyError(
            "Inference dependencies are not installed. Run 'pip install -r requirements.txt' and try again."
        ) from exc

    try:
        return YOLO(str(MODEL_FILE))
    except Exception as exc:
        raise ModelFileError(f"Unable to load YOLO model file: {exc}") from exc


def _open_image(image_bytes: bytes):
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:
        raise InferenceDependencyError(
            "Inference dependencies are not installed. Run 'pip install -r requirements.txt' and try again."
        ) from exc

    try:
        image = Image.open(BytesIO(image_bytes))
        image.load()
        return image
    except UnidentifiedImageError as exc:
        raise ValueError("Uploaded file is not a valid image.") from exc


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
