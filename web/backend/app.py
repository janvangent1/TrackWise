"""
TrackWise Web — FastAPI backend.

Endpoints:
  POST /api/search          — upload GPX + config, start background job
  GET  /api/search/{job_id}/stream — SSE progress stream
  GET  /api/search/{job_id}/results — JSON results
  POST /api/export/gpx      — export GPX for selected places
  GET  /health              — health check
  GET  /                    — serve frontend index.html
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles

from core.gpx_parser import parse_gpx
from core.gpx_writer import build_enhanced_track_gpx, build_waypoints_only_gpx
from core.osrm import get_road_route_multi
from core.valhalla import get_valhalla_route
from core.place_types import PLACE_TYPE_CONFIG
from core.search import SearchConfig, run_search

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"

app = FastAPI(title="TrackWise Web", version="2.0.0")

# Mount static files (css, js, images)
if (FRONTEND_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")

# ---------------------------------------------------------------------------
# In-memory job store
# ---------------------------------------------------------------------------

class SearchJob:
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.status: str = "pending"  # pending | running | done | error | cancelled
        self.events: List[dict] = []
        self.result: Optional[dict] = None
        self.cancel_flag: bool = False
        self.created_at: float = time.time()
        self._lock = threading.Lock()

    def add_event(self, event: dict):
        with self._lock:
            self.events.append(event)

    def get_events_from(self, index: int) -> List[dict]:
        with self._lock:
            return self.events[index:]

    def cancel(self):
        self.cancel_flag = True

    def is_cancelled(self) -> bool:
        return self.cancel_flag


JOBS: Dict[str, SearchJob] = {}
JOB_TTL = 3600  # 1 hour


def _cleanup_old_jobs():
    """Remove jobs older than TTL."""
    now = time.time()
    stale = [jid for jid, job in JOBS.items() if now - job.created_at > JOB_TTL]
    for jid in stale:
        del JOBS[jid]
        logger.info(f"Cleaned up job {jid}")


# ---------------------------------------------------------------------------
# Background search worker
# ---------------------------------------------------------------------------

def _run_search_worker(job: SearchJob, route_points, gpx_obj, search_config):
    job.status = "running"
    try:
        for event in run_search(route_points, search_config, cancel_check=job.is_cancelled):
            job.add_event(event)
            if event["type"] == "result":
                job.result = {
                    "places": event["places"],
                    "road_routes": event["road_routes"],
                    "route_points": event["route_points"],
                    "total_km": event["total_km"],
                    "gpx_obj": gpx_obj,  # kept for GPX export
                }
                job.status = "done"
            elif event["type"] == "cancelled":
                job.status = "cancelled"
                return
            elif event["type"] == "error":
                job.status = "error"
                return
    except Exception as e:
        logger.exception(f"Job {job.job_id} crashed")
        job.add_event({"type": "error", "message": str(e)})
        job.status = "error"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index = FRONTEND_DIR / "index.html"
    if not index.exists():
        return HTMLResponse("<h1>TrackWise Web — frontend not found</h1>", status_code=404)
    return HTMLResponse(index.read_text(encoding="utf-8"))


@app.get("/api/place-types")
async def get_place_types():
    """Return available place types with metadata."""
    return {
        pt: {
            "name": cfg["name"],
            "emoji": cfg["emoji"],
            "color": cfg["color"],
            "default_distance_km": cfg["default_distance_km"],
            "on_route_only": cfg.get("on_route_only", False),
        }
        for pt, cfg in PLACE_TYPE_CONFIG.items()
    }


@app.post("/api/search")
async def start_search(
    gpx_file: UploadFile = File(...),
    config: str = Form(...),
):
    """
    Start a new search job.

    config: JSON string like:
      {"petrol": 5.0, "cafe": 0.1, "supermarket": 0.2}

    Returns: {"job_id": "..."}
    """
    _cleanup_old_jobs()

    # Parse config
    try:
        place_types_raw = json.loads(config)
        search_config = SearchConfig(
            {pt: float(dist) for pt, dist in place_types_raw.items() if float(dist) > 0}
        )
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid config: {e}")

    if not search_config.place_types:
        raise HTTPException(status_code=422, detail="At least one place type must be selected.")

    # Parse GPX
    try:
        content = await gpx_file.read()
        if not content:
            raise ValueError("Empty file")
        route_points, gpx_obj = parse_gpx(content)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"GPX parse error: {e}")

    # Create job
    job_id = str(uuid.uuid4())
    job = SearchJob(job_id)
    JOBS[job_id] = job

    # Launch background thread
    thread = threading.Thread(
        target=_run_search_worker,
        args=(job, route_points, gpx_obj, search_config),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id}


@app.get("/api/search/{job_id}/stream")
async def stream_search(job_id: str, request: Request):
    """
    SSE endpoint — streams progress events for a search job.
    Client receives data: {...} lines until type=result, error, or cancelled.
    """
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        index = 0
        last_ping = time.time()

        while True:
            if await request.is_disconnected():
                job.cancel()
                break

            events = job.get_events_from(index)
            for event in events:
                yield f"data: {json.dumps(event)}\n\n"
                index += 1

                if event["type"] in ("result", "error", "cancelled"):
                    return

            # Send keepalive ping every 15 seconds
            now = time.time()
            if now - last_ping > 15:
                yield ": ping\n\n"
                last_ping = now

            await asyncio.sleep(0.3)

            # Safety exit: job ended but terminal event not yet seen.
            # Poll up to 3 more seconds to avoid breaking before last events arrive.
            if job.status in ("done", "error", "cancelled") and not events:
                for _ in range(10):
                    await asyncio.sleep(0.3)
                    events = job.get_events_from(index)
                    if events:
                        break
                if not events:
                    break  # genuinely nothing left — exit
                continue

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )


@app.get("/api/search/{job_id}/results")
async def get_results(job_id: str):
    """Return full results for a completed job."""
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status == "running":
        raise HTTPException(status_code=202, detail="Job still running")
    if job.status in ("error", "cancelled"):
        raise HTTPException(status_code=400, detail=f"Job {job.status}")
    if not job.result:
        raise HTTPException(status_code=404, detail="No results")

    result = job.result.copy()
    result.pop("gpx_obj", None)  # not JSON-serialisable
    return JSONResponse(result)


@app.post("/api/search/{job_id}/cancel")
async def cancel_search(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.cancel()
    return {"status": "cancellation requested"}


@app.post("/api/route")
async def route_through_waypoints(request: Request):
    """
    Route through N waypoints via OSRM.
    Body: {"waypoints": [[lat, lon], ...]}
    Returns: {"route_points": [[lon, lat], ...]}
    """
    body = await request.json()
    waypoints = body.get("waypoints", [])
    profile = body.get("profile", "cycling")
    if len(waypoints) < 2:
        raise HTTPException(status_code=422, detail="At least 2 waypoints required")

    loop = asyncio.get_event_loop()
    if profile == "motorcycle_offroad":
        result = await loop.run_in_executor(None, get_valhalla_route, waypoints, profile)
    else:
        result = await loop.run_in_executor(None, get_road_route_multi, waypoints, profile)

    if result is None:
        raise HTTPException(status_code=502, detail="Routing service unavailable")

    return {"route_points": [[lon, lat] for lon, lat in result]}


@app.post("/api/export/gpx")
async def export_gpx(request: Request):
    """
    Export GPX for selected places.

    Body JSON:
    {
      "job_id": "...",
      "selected_ids": ["petrol_0", "cafe_2", ...],
      "mode": "waypoints_only" | "enhanced_track"
    }
    """
    body = await request.json()
    job_id = body.get("job_id")
    selected_ids = body.get("selected_ids", [])
    mode = body.get("mode", "waypoints_only")
    custom_waypoints = body.get("custom_waypoints", [])  # [{lat, lon, name}, ...]

    # Allow export with only custom waypoints (no completed search job required)
    selected_places = []
    road_routes = {}
    route_points = []
    gpx_obj = None

    if job_id:
        job = JOBS.get(job_id)
        if job and job.result:
            result = job.result
            all_places = result["places"]
            selected_places = [p for p in all_places if p["id"] in selected_ids]
            road_routes = result["road_routes"]
            route_points = result["route_points"]
            gpx_obj = result.get("gpx_obj")

    if not selected_places and not custom_waypoints:
        raise HTTPException(status_code=422, detail="No places or custom waypoints selected")

    try:
        if mode == "enhanced_track":
            gpx_xml = build_enhanced_track_gpx(
                gpx_obj, route_points, selected_places, road_routes,
                custom_waypoints=custom_waypoints,
            )
        else:
            gpx_xml = build_waypoints_only_gpx(selected_places, custom_waypoints=custom_waypoints)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GPX generation error: {e}")

    return StreamingResponse(
        iter([gpx_xml.encode("utf-8")]),
        media_type="application/gpx+xml",
        headers={"Content-Disposition": "attachment; filename=trackwise_export.gpx"},
    )


# ---------------------------------------------------------------------------
# Entry point for direct run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
