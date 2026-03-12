"""
TrackWise Web — FastAPI backend.

Endpoints:
  POST /api/search          — upload GPX + config, start background job
  GET  /api/search/{job_id}/stream — SSE progress stream
  GET  /api/search/{job_id}/results — JSON results
  POST /api/export/gpx      — export GPX for selected places
  GET  /health              — health check
  GET  /                    — serve frontend index.html
  GET  /admin               — admin dashboard (password protected)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    StreamingResponse,
)
from fastapi.security import HTTPBasic, HTTPBasicCredentials
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

# ---------------------------------------------------------------------------
# Admin auth
# ---------------------------------------------------------------------------
_http_basic = HTTPBasic()
ADMIN_PASSWORD = "jeroom"


def require_admin(credentials: HTTPBasicCredentials = Depends(_http_basic)):
    ok = secrets.compare_digest(
        credentials.password.encode("utf-8"),
        ADMIN_PASSWORD.encode("utf-8"),
    )
    if not ok:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": 'Basic realm="TrackWise Admin"'},
        )


# ---------------------------------------------------------------------------
# Stats tracker
# ---------------------------------------------------------------------------

class StatsTracker:
    """Tracks usage statistics, persisted to stats.json across restarts."""

    def __init__(self):
        self._lock = threading.Lock()
        self._file = BASE_DIR / "stats.json"
        self._started_at = time.time()
        self._data: dict = {
            "total_searches": 0,
            "completed_searches": 0,
            "cancelled_searches": 0,
            "failed_searches": 0,
            "total_waypoints_found": 0,
            "gpx_exports": 0,
            "recent_searches": [],
        }
        self._load()

    def _load(self):
        if self._file.exists():
            try:
                saved = json.loads(self._file.read_text(encoding="utf-8"))
                self._data.update(saved)
            except Exception:
                pass

    def _save(self):
        try:
            self._file.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _new_entry(self, job_id, filename, status, error=""):
        return {
            "job_id": job_id,
            "at": time.strftime("%Y-%m-%d %H:%M"),
            "filename": filename or "unknown.gpx",
            "status": status,
            "waypoints": 0,
            "route_km": 0,
            "error": error[:300] if error else "",
        }

    def _push_entry(self, entry):
        self._data["recent_searches"].insert(0, entry)
        self._data["recent_searches"] = self._data["recent_searches"][:20]

    def record_search_started(self, job_id: str, filename: str):
        with self._lock:
            self._data["total_searches"] += 1
            self._push_entry(self._new_entry(job_id, filename, "running"))
            self._save()

    def record_upload_failed(self, filename: str, error: str):
        """Record a failure that happened before a job was created (e.g. GPX parse error)."""
        with self._lock:
            self._data["total_searches"] += 1
            self._data["failed_searches"] += 1
            self._push_entry(self._new_entry(None, filename, "failed", error))
            self._save()

    def record_search_done(self, job_id: str, waypoints: int, route_km: float):
        with self._lock:
            self._data["completed_searches"] += 1
            self._data["total_waypoints_found"] += waypoints
            for e in self._data["recent_searches"]:
                if e.get("job_id") == job_id:
                    e["status"] = "done"
                    e["waypoints"] = waypoints
                    e["route_km"] = round(route_km, 1)
                    break
            self._save()

    def record_search_cancelled(self, job_id: str):
        with self._lock:
            self._data["cancelled_searches"] += 1
            for e in self._data["recent_searches"]:
                if e.get("job_id") == job_id:
                    e["status"] = "cancelled"
                    break
            self._save()

    def record_search_failed(self, job_id: str, error: str = ""):
        with self._lock:
            self._data["failed_searches"] += 1
            for e in self._data["recent_searches"]:
                if e.get("job_id") == job_id:
                    e["status"] = "failed"
                    e["error"] = error[:300] if error else ""
                    break
            self._save()

    def record_gpx_export(self):
        with self._lock:
            self._data["gpx_exports"] += 1
            self._save()

    def record_export_error(self, error: str):
        with self._lock:
            errors = self._data.setdefault("recent_export_errors", [])
            errors.insert(0, {"at": time.strftime("%Y-%m-%d %H:%M"), "error": error[:300]})
            self._data["recent_export_errors"] = errors[:10]
            self._save()

    def snapshot(self) -> dict:
        with self._lock:
            uptime_s = int(time.time() - self._started_at)
            h, r = divmod(uptime_s, 3600)
            m, s = divmod(r, 60)
            return {
                **self._data,
                "uptime": f"{h}h {m}m {s}s",
                "started_at": time.strftime("%Y-%m-%d %H:%M", time.localtime(self._started_at)),
                "active_jobs": sum(1 for j in JOBS.values() if j.status == "running"),
            }


STATS = StatsTracker()

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
                STATS.record_search_done(job.job_id, len(event["places"]), event["total_km"])
            elif event["type"] == "cancelled":
                job.status = "cancelled"
                STATS.record_search_cancelled(job.job_id)
                return
            elif event["type"] == "error":
                job.status = "error"
                STATS.record_search_failed(job.job_id, event.get("message", "Unknown error"))
                return
    except Exception as e:
        logger.exception(f"Job {job.job_id} crashed")
        job.add_event({"type": "error", "message": str(e)})
        job.status = "error"
        STATS.record_search_failed(job.job_id, str(e))


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
        STATS.record_upload_failed(gpx_file.filename, f"Invalid config: {e}")
        raise HTTPException(status_code=422, detail=f"Invalid config: {e}")

    if not search_config.place_types:
        STATS.record_upload_failed(gpx_file.filename, "No place types selected")
        raise HTTPException(status_code=422, detail="At least one place type must be selected.")

    # Parse GPX
    try:
        content = await gpx_file.read()
        if not content:
            raise ValueError("Empty file")
        route_points, gpx_obj = parse_gpx(content)
    except Exception as e:
        STATS.record_upload_failed(gpx_file.filename, f"GPX parse error: {e}")
        raise HTTPException(status_code=422, detail=f"GPX parse error: {e}")

    # Create job
    job_id = str(uuid.uuid4())
    job = SearchJob(job_id)
    JOBS[job_id] = job
    STATS.record_search_started(job_id, gpx_file.filename)

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
        STATS.record_export_error(f"GPX generation error: {e}")
        raise HTTPException(status_code=500, detail=f"GPX generation error: {e}")

    STATS.record_gpx_export()
    return StreamingResponse(
        iter([gpx_xml.encode("utf-8")]),
        media_type="application/gpx+xml",
        headers={"Content-Disposition": "attachment; filename=trackwise_export.gpx"},
    )


# ---------------------------------------------------------------------------
# Admin dashboard
# ---------------------------------------------------------------------------

def _admin_html(stats: dict) -> str:
    status_colors = {
        "done": "#4ade80",
        "running": "#60a5fa",
        "cancelled": "#fbbf24",
        "failed": "#f87171",
    }

    def search_row(s):
        err = s.get("error", "")
        err_cell = f"<td style='color:#f87171;font-size:.8rem' title='{err}'>{err[:80] + ('…' if len(err) > 80 else '')}</td>" if err else "<td style='color:#475569'>—</td>"
        return (
            f"<tr>"
            f"<td>{s['at']}</td>"
            f"<td>{s['filename']}</td>"
            f"<td>{s['route_km']} km</td>"
            f"<td><span style='color:{status_colors.get(s['status'], '#94a3b8')};font-weight:600'>{s['status']}</span></td>"
            f"<td>{s['waypoints']}</td>"
            f"{err_cell}"
            f"</tr>"
        )

    rows = "".join(search_row(s) for s in stats["recent_searches"]) \
        or "<tr><td colspan='6' style='color:#475569;text-align:center;padding:2rem'>No searches yet</td></tr>"

    export_errors = stats.get("recent_export_errors", [])
    export_error_section = ""
    if export_errors:
        export_rows = "".join(
            f"<tr><td>{e['at']}</td><td style='color:#f87171'>{e['error']}</td></tr>"
            for e in export_errors
        )
        export_error_section = f"""
  <h2 style="margin-top:2rem">Recent Export Errors</h2>
  <table>
    <thead><tr><th>Time</th><th>Error</th></tr></thead>
    <tbody>{export_rows}</tbody>
  </table>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="30">
  <title>TrackWise Admin</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;padding:2rem}}
    .topbar{{display:flex;align-items:center;justify-content:space-between;margin-bottom:.25rem}}
    h1{{font-size:1.5rem;font-weight:700}}
    .home-btn{{font-size:.8rem;color:#94a3b8;text-decoration:none;padding:5px 12px;border:1px solid #334155;border-radius:6px}}
    .home-btn:hover{{color:#60a5fa;border-color:#60a5fa}}
    .meta{{color:#94a3b8;font-size:.875rem;margin-bottom:2rem}}
    .cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1rem;margin-bottom:2rem}}
    .card{{background:#1e293b;border-radius:.75rem;padding:1.25rem}}
    .card .label{{font-size:.7rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em;margin-bottom:.5rem}}
    .card .value{{font-size:2rem;font-weight:700}}
    h2{{font-size:.75rem;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em;margin-bottom:1rem}}
    table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:.75rem;overflow:hidden}}
    th{{text-align:left;padding:.75rem 1rem;font-size:.7rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid #334155}}
    td{{padding:.75rem 1rem;font-size:.875rem;border-bottom:1px solid #0f172a}}
    tr:last-child td{{border-bottom:none}}
    .footer{{color:#334155;font-size:.75rem;margin-top:1.5rem;text-align:right}}
  </style>
</head>
<body>
  <div class="topbar">
    <h1>TrackWise Admin</h1>
    <a href="/" class="home-btn">← Home</a>
  </div>
  <p class="meta">
    Started {stats['started_at']} &nbsp;&middot;&nbsp;
    Uptime {stats['uptime']} &nbsp;&middot;&nbsp;
    {stats['active_jobs']} active job(s)
  </p>

  <div class="cards">
    <div class="card"><div class="label">Total Searches</div><div class="value" style="color:#60a5fa">{stats['total_searches']}</div></div>
    <div class="card"><div class="label">Completed</div><div class="value" style="color:#4ade80">{stats['completed_searches']}</div></div>
    <div class="card"><div class="label">Cancelled</div><div class="value" style="color:#fbbf24">{stats['cancelled_searches']}</div></div>
    <div class="card"><div class="label">Failed</div><div class="value" style="color:#f87171">{stats['failed_searches']}</div></div>
    <div class="card"><div class="label">Waypoints Found</div><div class="value" style="color:#e2e8f0">{stats['total_waypoints_found']}</div></div>
    <div class="card"><div class="label">GPX Exports</div><div class="value" style="color:#e2e8f0">{stats['gpx_exports']}</div></div>
  </div>

  <h2>Recent Searches (last 20)</h2>
  <table>
    <thead>
      <tr><th>Time</th><th>File</th><th>Route</th><th>Status</th><th>Waypoints</th><th>Error</th></tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
  {export_error_section}

  <p class="footer">Auto-refreshes every 30 seconds</p>
</body>
</html>"""


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(_: None = Depends(require_admin)):
    return HTMLResponse(_admin_html(STATS.snapshot()))


# ---------------------------------------------------------------------------
# Entry point for direct run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
