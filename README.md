# Oil Spill Candidate Detection Backend

This project is a simple FastAPI backend for a university capstone prototype that serves AI-generated oil-spill candidate detections from a GeoJSON file. It is designed to power a future frontend map by exposing event records, summary statistics, and a filtered GeoJSON feed.

The detections in this API are candidate events produced by an AI pipeline. They should not be treated as manually verified oil spills without expert review.

The backend reads detection features from `app/data/seed_events.geojson`. Each feature is expected to be a GeoJSON `Polygon` with properties such as `event_id`, `confidence`, `estimated_area_km2`, `status`, and time metadata.

This version intentionally keeps the stack lightweight and file-based. A database and PostGIS can be added in the next version when the prototype grows beyond a single GeoJSON source.

## Project Structure

```text
oilspill-backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── schemas.py
│   ├── services.py
│   └── data/
│       └── seed_events.geojson
├── requirements.txt
└── README.md
```

## Features

- `GET /health` for a quick API health check
- `GET /events` to list detection events with optional filters and pagination
- `GET /events/{event_id}` to fetch one detection event
- `GET /events/stats` to compute summary statistics
- `GET /events.geojson` to return the filtered GeoJSON `FeatureCollection`
- CORS enabled for frontend integration
- Basic error handling for missing data file, invalid JSON, and unknown event IDs

## Requirements

- Python 3.10+

## How To Run Locally

1. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Make sure your GeoJSON file exists at:

```text
app/data/seed_events.geojson
```

4. Start the development server:

```bash
uvicorn app.main:app --reload
```

5. Open the API docs:

```text
http://127.0.0.1:8000/docs
```

## Available Endpoints

### `GET /health`

Returns a simple health-check response.

Example response:

```json
{
  "status": "ok"
}
```

### `GET /events`

Returns paginated detection event records.

Available query parameters:

- `min_confidence`
- `max_confidence`
- `min_area`
- `max_area`
- `status`
- `start_date`
- `end_date`
- `limit`
- `offset`

Example queries:

```text
/events
/events?min_confidence=0.8
/events?min_confidence=0.7&max_area=100
/events?status=candidate_detection&limit=25&offset=50
/events?start_date=2019-01-01&end_date=2019-12-31
```

Example response structure:

```json
{
  "total_count": 425,
  "returned_count": 50,
  "limit": 50,
  "offset": 0,
  "events": [
    {
      "event_id": "oc-0002_0",
      "image_name": "oc-0002.jpg",
      "patch_name": "S1_20190101_034235_034350_VV_4",
      "start_time": "2019-01-01T03:42:35",
      "end_time": "2019-01-01T03:43:50",
      "sentinel_id": "S1B_IW_GRDH_1SDV_20190101T034325_20190101T034350_014295_01A97E_5586.SAFE",
      "class_name": "oil",
      "confidence": 0.862,
      "bbox_pixels": [256.03, 305.41, 301.73, 408.69],
      "centroid_lon": 34.391957,
      "centroid_lat": 31.494651,
      "estimated_area_km2": 2.8605,
      "status": "candidate_detection",
      "note": "AI-generated suspected oil-spill candidate; not verified."
    }
  ]
}
```

### `GET /events/{event_id}`

Returns one detection event with its polygon geometry. If the event does not exist, the API returns `404 Not Found`.

Example query:

```text
/events/oc-0002_0
```

### `GET /events/stats`

Returns summary statistics for all matching detections.

Available query parameters:

- `min_confidence`
- `max_confidence`
- `min_area`
- `max_area`
- `status`
- `start_date`
- `end_date`

Example query:

```text
/events/stats?min_confidence=0.7&max_area=100
```

### `GET /events.geojson`

Returns all matching detections as a GeoJSON `FeatureCollection`. This endpoint does not use pagination.

Available query parameters:

- `min_confidence`
- `max_area`
- `status`

Example queries:

```text
/events.geojson
/events.geojson?min_confidence=0.7
/events.geojson?min_confidence=0.7&max_area=100&status=candidate_detection
```

## Example curl Commands

```bash
curl http://127.0.0.1:8000/health
```

```bash
curl "http://127.0.0.1:8000/events"
```

```bash
curl "http://127.0.0.1:8000/events?min_confidence=0.8"
```

```bash
curl "http://127.0.0.1:8000/events?min_confidence=0.7&max_area=100"
```

```bash
curl http://127.0.0.1:8000/events/stats
```

```bash
curl http://127.0.0.1:8000/events.geojson
```

```bash
curl "http://127.0.0.1:8000/events.geojson?min_confidence=0.7"
```

```bash
curl http://127.0.0.1:8000/events/oc-0002_0
```

## Testing Notes

The current repository data file at `app/data/seed_events.geojson` contains the real exported detections from your pipeline.

Observed local behavior with the current dataset:

- `GET /health` returns `{"status":"ok"}`
- `GET /events` returns a paginated response with `total_count=425`, `returned_count=50`, `limit=50`, and `offset=0`
- `GET /events?min_confidence=0.8` returns `total_count=121`
- `GET /events?min_confidence=0.7&max_area=100` returns filtered paginated results
- `GET /events/stats` returns aggregate metrics across all 425 detections
- `GET /events.geojson` returns all 425 features without pagination
- `GET /events.geojson?min_confidence=0.7` returns a `FeatureCollection` with 218 filtered features
- `GET /events/oc-0002_0` returns the matching event with polygon geometry

## Current Limitations

- The backend uses a local GeoJSON file instead of a database.
- Detections are AI-generated candidate results and still need expert or manual verification.
- Very large polygons may require additional quality control in later versions.
- PostGIS can be added in the next version for scalable geospatial querying.

## Error Handling Notes

- If `app/data/seed_events.geojson` is missing, data endpoints return a `500` response with a clear message.
- If an `event_id` does not exist, `GET /events/{event_id}` returns `404`.
- If query parameters are invalid, FastAPI returns a validation error response.
