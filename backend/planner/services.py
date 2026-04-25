from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OSRM_URL = "https://router.project-osrm.org/route/v1/driving"
MPH_ASSUMPTION = 50
FUEL_STOP_MILES = 1000
FUEL_STOP_DURATION_HOURS = 0.5


class TripPlanningError(Exception):
    pass


@dataclass
class Location:
    name: str
    lat: float
    lon: float


def geocode_location(query: str) -> Location:
    response = requests.get(
        NOMINATIM_URL,
        params={"q": query, "format": "json", "limit": 1},
        headers={"User-Agent": "hos-planner-assessment/1.0"},
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    if not data:
        raise TripPlanningError(f"Unable to geocode location: {query}")
    hit = data[0]
    return Location(name=hit.get("display_name", query), lat=float(hit["lat"]), lon=float(hit["lon"]))


def get_route_points(stops: list[Location]) -> dict[str, Any]:
    if len(stops) < 2:
        raise TripPlanningError("At least two route points are required.")

    coord_string = ";".join([f"{p.lon},{p.lat}" for p in stops])
    response = requests.get(
        f"{OSRM_URL}/{coord_string}",
        params={"overview": "full", "geometries": "geojson"},
        timeout=25,
    )
    response.raise_for_status()
    payload = response.json()
    routes = payload.get("routes", [])
    if not routes:
        raise TripPlanningError("Unable to build route for the provided locations.")
    return routes[0]


def _append_segment(segments: list[dict[str, Any]], cursor: datetime, duration_h: float, status: str, label: str) -> datetime:
    if duration_h <= 0:
        return cursor
    end = cursor + timedelta(hours=duration_h)
    segments.append(
        {
            "status": status,
            "label": label,
            "start": cursor.isoformat(),
            "end": end.isoformat(),
            "hours": round(duration_h, 2),
        }
    )
    return end


def _push_driving_blocks(
    segments: list[dict[str, Any]],
    stops: list[dict[str, Any]],
    cursor: datetime,
    driving_hours_needed: float,
    on_duty_cycle_used: float,
    fuel_miles_cursor: float,
) -> tuple[datetime, float, float]:
    drive_left = driving_hours_needed
    since_break = 0.0
    driving_window_used = 0.0
    driving_today = 0.0
    on_duty_today = 0.0

    while drive_left > 0:
        weekly_left = max(0.0, 70 - on_duty_cycle_used)
        if weekly_left <= 0:
            cursor = _append_segment(segments, cursor, 34, "off_duty", "34-hour restart")
            on_duty_cycle_used = 0.0
            driving_window_used = 0.0
            driving_today = 0.0
            on_duty_today = 0.0
            since_break = 0.0
            continue

        legal_drive_chunk = min(
            drive_left,
            11 - driving_today,
            14 - driving_window_used,
            8 - since_break,
            weekly_left,
        )

        if legal_drive_chunk <= 0:
            # Required non-driving break or end-of-window reset.
            if since_break >= 8 and driving_today < 11 and driving_window_used < 14:
                cursor = _append_segment(segments, cursor, 0.5, "on_duty_not_driving", "30-minute break")
                on_duty_cycle_used += 0.5
                on_duty_today += 0.5
                driving_window_used += 0.5
                since_break = 0.0
                continue

            cursor = _append_segment(segments, cursor, 10, "off_duty", "10-hour off-duty reset")
            driving_window_used = 0.0
            driving_today = 0.0
            on_duty_today = 0.0
            since_break = 0.0
            continue

        cursor = _append_segment(segments, cursor, legal_drive_chunk, "driving", "Driving")
        drive_left -= legal_drive_chunk
        driving_today += legal_drive_chunk
        on_duty_today += legal_drive_chunk
        driving_window_used += legal_drive_chunk
        since_break += legal_drive_chunk
        on_duty_cycle_used += legal_drive_chunk
        fuel_miles_cursor += legal_drive_chunk * MPH_ASSUMPTION

        while fuel_miles_cursor >= FUEL_STOP_MILES:
            fuel_miles_cursor -= FUEL_STOP_MILES
            cursor = _append_segment(segments, cursor, FUEL_STOP_DURATION_HOURS, "on_duty_not_driving", "Fuel stop")
            on_duty_cycle_used += FUEL_STOP_DURATION_HOURS
            on_duty_today += FUEL_STOP_DURATION_HOURS
            driving_window_used += FUEL_STOP_DURATION_HOURS
            stops.append({"type": "Fuel", "at": cursor.isoformat(), "duration_hours": FUEL_STOP_DURATION_HOURS})

    return cursor, on_duty_cycle_used, fuel_miles_cursor


def build_trip_plan(
    current_location: str,
    pickup_location: str,
    dropoff_location: str,
    current_cycle_used: float,
) -> dict[str, Any]:
    if current_cycle_used < 0 or current_cycle_used > 70:
        raise TripPlanningError("Current cycle used must be between 0 and 70 hours.")

    current = geocode_location(current_location)
    pickup = geocode_location(pickup_location)
    dropoff = geocode_location(dropoff_location)

    full_route = get_route_points([current, pickup, dropoff])
    distance_miles = (full_route["distance"] / 1000) * 0.621371
    driving_hours = full_route["duration"] / 3600

    start_time = datetime.combine(datetime.now().date(), time(hour=6))
    segments: list[dict[str, Any]] = []
    stops: list[dict[str, Any]] = [
        {"type": "Start", "name": current.name, "at": start_time.isoformat()},
    ]

    cursor = start_time
    fuel_miles_cursor = 0.0
    on_duty_cycle_used = current_cycle_used

    # Drive to pickup and handle loading.
    route_to_pickup = get_route_points([current, pickup])
    pickup_drive_hours = route_to_pickup["duration"] / 3600
    cursor, on_duty_cycle_used, fuel_miles_cursor = _push_driving_blocks(
        segments, stops, cursor, pickup_drive_hours, on_duty_cycle_used, fuel_miles_cursor
    )
    cursor = _append_segment(segments, cursor, 1.0, "on_duty_not_driving", "Pickup (loading)")
    on_duty_cycle_used += 1.0
    stops.append({"type": "Pickup", "name": pickup.name, "at": cursor.isoformat(), "duration_hours": 1.0})

    # Drive to dropoff and handle unload.
    route_to_dropoff = get_route_points([pickup, dropoff])
    dropoff_drive_hours = route_to_dropoff["duration"] / 3600
    cursor, on_duty_cycle_used, fuel_miles_cursor = _push_driving_blocks(
        segments, stops, cursor, dropoff_drive_hours, on_duty_cycle_used, fuel_miles_cursor
    )
    cursor = _append_segment(segments, cursor, 1.0, "on_duty_not_driving", "Drop-off (unloading)")
    on_duty_cycle_used += 1.0
    stops.append({"type": "Dropoff", "name": dropoff.name, "at": cursor.isoformat(), "duration_hours": 1.0})

    logs = generate_daily_logs(segments)

    return {
        "inputs": {
            "current_location": current_location,
            "pickup_location": pickup_location,
            "dropoff_location": dropoff_location,
            "current_cycle_used": current_cycle_used,
        },
        "locations": [
            {"name": current.name, "lat": current.lat, "lon": current.lon, "type": "current"},
            {"name": pickup.name, "lat": pickup.lat, "lon": pickup.lon, "type": "pickup"},
            {"name": dropoff.name, "lat": dropoff.lat, "lon": dropoff.lon, "type": "dropoff"},
        ],
        "summary": {
            "distance_miles": round(distance_miles, 2),
            "estimated_driving_hours": round(driving_hours, 2),
            "projected_total_hours_with_stops": round(sum(x["hours"] for x in segments), 2),
            "days_required": len(logs),
            "cycle_used_after_trip": round(on_duty_cycle_used, 2),
        },
        "route_geojson": full_route["geometry"],
        "stops": stops,
        "segments": segments,
        "daily_logs": logs,
    }


def generate_daily_logs(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not segments:
        return []

    start = datetime.fromisoformat(segments[0]["start"])
    end = datetime.fromisoformat(segments[-1]["end"])
    day_count = (end.date() - start.date()).days + 1
    days: list[dict[str, Any]] = []

    for offset in range(day_count):
        day_start = datetime.combine(start.date() + timedelta(days=offset), time.min)
        day_end = day_start + timedelta(days=1)
        day_segments = []
        totals = {
            "off_duty": 0.0,
            "sleeper_berth": 0.0,
            "driving": 0.0,
            "on_duty_not_driving": 0.0,
        }

        for segment in segments:
            seg_start = datetime.fromisoformat(segment["start"])
            seg_end = datetime.fromisoformat(segment["end"])
            clip_start = max(seg_start, day_start)
            clip_end = min(seg_end, day_end)
            if clip_start >= clip_end:
                continue
            hours = (clip_end - clip_start).total_seconds() / 3600
            status = segment["status"]
            if status not in totals:
                status = "on_duty_not_driving"
            totals[status] += hours
            day_segments.append(
                {
                    "status": status,
                    "label": segment["label"],
                    "start_hour": round((clip_start - day_start).total_seconds() / 3600, 2),
                    "end_hour": round((clip_end - day_start).total_seconds() / 3600, 2),
                    "hours": round(hours, 2),
                }
            )

        if day_segments:
            days.append(
                {
                    "date": day_start.date().isoformat(),
                    "totals": {k: round(v, 2) for k, v in totals.items()},
                    "segments": day_segments,
                }
            )

    return days
