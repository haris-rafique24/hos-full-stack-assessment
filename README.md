# Full Stack HOS Trip Planner (Django + React)

This project implements the assessment requirements:
- Input: current location, pickup, drop-off, current cycle used.
- Output: route map with stops/rest handling and generated daily log sheets for multi-day trips.
- Assumptions: property-carrying, 70/8 cycle, no adverse conditions, fuel every 1,000 miles, 1 hour pickup/drop-off.

## Tech Stack
- Backend: Django + Django REST Framework
- Frontend: React + Vite + React Leaflet
- APIs:
  - Geocoding: Nominatim (OpenStreetMap)
  - Routing: OSRM demo server
  - Map tiles: OpenStreetMap

## Project Structure
- `backend/` Django API
- `frontend/` React UI

## Local Run

### 1) Backend
```bash
cd backend
py -3 -m pip install -r requirements.txt
py -3 manage.py runserver
```

Backend runs on `http://127.0.0.1:8000`.

### 2) Frontend
```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://127.0.0.1:5173`.

## API

`POST /api/plan-trip/`

Example payload:
```json
{
  "current_location": "Dallas, TX",
  "pickup_location": "Chicago, IL",
  "dropoff_location": "New York, NY",
  "current_cycle_used": 15
}
```

Returns route geometry, summary, stop events, duty segments, and per-day logs.

## Notes
- This implementation uses practical deterministic scheduling to satisfy core HOS constraints (11-hour driving, 14-hour window, 30-minute break, 70/8 with restart handling).
- For production, replace public demo APIs with paid/SLA map services and extend compliance edge-cases.
