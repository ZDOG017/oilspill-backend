# Oil Spill Candidate Detection Backend

This project is a simple FastAPI backend for a university capstone prototype that serves candidate oil-spill detections from a GeoJSON file. It is designed to power a future frontend map by exposing detection records, summary statistics, and a filtered GeoJSON feed.

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
- `GET /events` to list detection events with optional filters
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

## Endpoint Examples

### `GET /health`

Response example:

```json
{
  "status": "ok"
}
```

### `GET /events`

Returns a JSON list of event records.

Supported query filters:

- `min_confidence`
- `max_confidence`
- `min_area`
- `max_area`
- `status`
- `start_date`
- `end_date`

Example:

```text
/events?min_confidence=0.70&max_area=15&status=candidate&start_date=2024-01-01&end_date=2024-12-31
```

### `GET /events/{event_id}`

Returns a single event. If the event does not exist, the API returns `404 Not Found`.

Example:

```text
/events/EVT_001
```

### `GET /events/stats`

Returns:

- `total_candidate_events`
- `mean_confidence`
- `min_confidence`
- `max_confidence`
- `mean_estimated_area_km2`
- `min_estimated_area_km2`
- `max_estimated_area_km2`
- `total_estimated_area_km2`

Example:

```text
/events/stats?status=candidate&min_confidence=0.6
```

### `GET /events.geojson`

Returns the GeoJSON `FeatureCollection`.

Supported query filters:

- `min_confidence`
- `max_area`
- `status`

Example:

```text
/events.geojson?min_confidence=0.75&max_area=8&status=candidate
```

## Example curl Commands

```bash
curl http://127.0.0.1:8000/health
```

```bash
curl "http://127.0.0.1:8000/events?min_confidence=0.8&status=candidate"
```

```bash
curl http://127.0.0.1:8000/events/EVT_001
```

```bash
curl "http://127.0.0.1:8000/events/stats?min_area=1.0&max_area=20"
```

```bash
curl "http://127.0.0.1:8000/events.geojson?min_confidence=0.7&status=candidate"
```

## Error Handling Notes

- If `app/data/seed_events.geojson` is missing, data endpoints return a `500` response with a clear message.
- If an `event_id` does not exist, `GET /events/{event_id}` returns `404`.
- If query parameters are invalid, FastAPI returns a validation error response.
