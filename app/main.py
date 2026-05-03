from datetime import date

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.schemas import EventDetail, EventListItem, EventStats, GeoJSONFeatureCollection, HealthResponse
from app.services import DataFileError, EventNotFoundError, EventService


app = FastAPI(
    title="Oil Spill Candidate Detection API",
    description="FastAPI backend for serving candidate oil-spill detections from a GeoJSON file.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

event_service = EventService()


@app.exception_handler(DataFileError)
async def data_file_error_handler(_, exc: DataFileError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/events", response_model=list[EventListItem])
def list_events(
    min_confidence: float | None = Query(default=None, ge=0.0, le=1.0),
    max_confidence: float | None = Query(default=None, ge=0.0, le=1.0),
    min_area: float | None = Query(default=None, ge=0.0),
    max_area: float | None = Query(default=None, ge=0.0),
    status: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[EventListItem]:
    return event_service.list_events(
        min_confidence=min_confidence,
        max_confidence=max_confidence,
        min_area=min_area,
        max_area=max_area,
        status=status,
        start_date=start_date,
        end_date=end_date,
    )


@app.get("/events/stats", response_model=EventStats)
def get_event_stats(
    min_confidence: float | None = Query(default=None, ge=0.0, le=1.0),
    max_confidence: float | None = Query(default=None, ge=0.0, le=1.0),
    min_area: float | None = Query(default=None, ge=0.0),
    max_area: float | None = Query(default=None, ge=0.0),
    status: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> EventStats:
    return event_service.get_stats(
        min_confidence=min_confidence,
        max_confidence=max_confidence,
        min_area=min_area,
        max_area=max_area,
        status=status,
        start_date=start_date,
        end_date=end_date,
    )


@app.get("/events/{event_id}", response_model=EventDetail)
def get_event(event_id: str) -> EventDetail:
    try:
        return event_service.get_event_by_id(event_id)
    except EventNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/events.geojson", response_model=GeoJSONFeatureCollection)
def get_events_geojson(
    min_confidence: float | None = Query(default=None, ge=0.0, le=1.0),
    max_area: float | None = Query(default=None, ge=0.0),
    status: str | None = None,
) -> GeoJSONFeatureCollection:
    return event_service.get_geojson(
        min_confidence=min_confidence,
        max_area=max_area,
        status=status,
    )
