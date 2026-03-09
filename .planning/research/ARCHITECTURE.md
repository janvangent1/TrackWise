# Architecture Patterns

**Domain:** GPX waypoint finder web app — FastAPI backend, plain HTML/JS frontend
**Researched:** 2026-03-09
**Overall confidence:** HIGH (FastAPI/SSE patterns verified against official docs and sse-starlette library)

---

## Recommended Architecture

The system has four distinct layers: HTTP transport (Nginx), application server (Uvicorn + FastAPI), a job engine that wraps the existing Python processing logic, and a plain HTML/JS frontend. The tkinter launcher on Windows is a separate process that manages the Pi server via SSH or a local subprocess.

```
Browser
  |
  | HTTP/SSE
  v
Nginx (port 80)                       <- Raspberry Pi, public facing
  |
  | proxy_pass to unix socket
  v
Uvicorn (FastAPI app)                 <- ASGI server, single worker on Pi
  |
  +-- POST /api/search  --------->  JobManager (in-memory dict)
  |                                     |
  +-- GET  /api/search/{job_id}/sse  -- asyncio.Queue per job
  |                                     |
  +-- DELETE /api/search/{job_id}       Worker thread (ThreadPoolExecutor)
  |                                       |
  +-- GET  /api/results/{job_id}          +-- Overpass API calls (parallel, 2 workers)
  |                                       +-- OSRM API calls (sequential per place)
  +-- POST /api/gpx/generate              +-- gpxpy / geopy / shapely logic (unchanged)
  |
  +-- GET  /static/*  (served by Nginx, not FastAPI)
  |
  +-- GET  /  (index.html via FastAPI Jinja2 or static file)
```

---

## Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `backend/main.py` | FastAPI app factory, mounts routers, configures CORS | All routers |
| `backend/routers/search.py` | POST /api/search, DELETE /api/search/{id} | JobManager |
| `backend/routers/sse.py` | GET /api/search/{id}/sse — streams EventSourceResponse | JobManager |
| `backend/routers/results.py` | GET /api/results/{id} — returns JSON results | JobManager |
| `backend/routers/gpx.py` | POST /api/gpx/generate, GET /api/gpx/{id}/download | JobManager, file system |
| `backend/jobs/manager.py` | In-memory job registry, creates/destroys jobs | Worker, SSE router |
| `backend/jobs/worker.py` | Runs search in a thread, posts progress to Queue | Overpass client, OSRM client, gpxpy |
| `backend/services/overpass.py` | Overpass API queries — extracted from monolith | worker.py |
| `backend/services/osrm.py` | OSRM routing queries — extracted from monolith | worker.py |
| `backend/services/gpx_parser.py` | gpxpy parse/write — extracted from monolith | worker.py, gpx router |
| `backend/services/gpx_builder.py` | Creates output GPX from selected waypoints | gpx router |
| `backend/services/route_processor.py` | Chunking, deduplication, distance calculation | worker.py |
| `frontend/static/` | HTML + Alpine.js + Leaflet.js — no build step | Browser only |
| `launcher/launcher_gui.py` | Windows tkinter launcher: SSH/subprocess control | Pi server via network |
| `web/deployment/` | systemd unit + nginx config | Raspberry Pi OS |

---

## Data Flow

### Search Request Flow

```
1. Browser: POST /api/search
   Body: { gpx_file: <binary>, search_config: { petrol: true, petrol_distance_km: 5, ... } }

2. FastAPI:
   a. Save uploaded GPX to /tmp/trackwise/<job_id>/input.gpx
   b. Create Job record: { id, status: "queued", queue: asyncio.Queue(), cancel_event: threading.Event() }
   c. Submit worker to ThreadPoolExecutor (NOT asyncio.create_task — the work is blocking I/O)
   d. Return: { job_id: "uuid4" }

3. Browser: GET /api/search/<job_id>/sse
   Opens EventSource connection.

4. Worker thread (blocking, in executor):
   a. Parse GPX with gpxpy
   b. Split route into 50km segments
   c. For each place_type:
      - ThreadPoolExecutor(max_workers=2) over segments -> Overpass API
      - On each future completion: put progress event on asyncio.Queue
      - Check cancel_event.is_set() — if true, return early
   d. Deduplicate, calculate distances
   e. For each place: OSRM route calculation, put progress event on Queue
   f. Store final results in Job record
   g. Put "complete" sentinel event on Queue

5. SSE endpoint (async generator):
   a. Loop: await queue.get()
   b. yield SSE event (JSON payload)
   c. Check request.is_disconnected() — if true, set cancel_event and return
   d. On "complete" sentinel: yield final event and close

6. Browser: receives SSE events, updates progress bar + partial results table

7. Browser: GET /api/results/<job_id>
   Returns { status, places: [...], route_stats: {...} }

8. Browser: POST /api/gpx/generate
   Body: { job_id, selected_place_ids: [...], mode: "waypoints_only"|"enhanced_track" }
   Returns: { download_url: "/api/gpx/<job_id>/download" }

9. Browser: GET /api/gpx/<job_id>/download
   FileResponse with Content-Disposition: attachment
```

### Cancellation Flow

```
Browser: DELETE /api/search/<job_id>
  -> FastAPI sets cancel_event (threading.Event)
  -> Worker thread checks cancel_event.is_set() at each loop boundary
  -> Worker exits early, puts "cancelled" event on Queue
  -> SSE endpoint yields "cancelled" event and closes
  -> Job record marked cancelled
```

### Temporary File Lifecycle

```
Upload  -> /tmp/trackwise/<job_id>/input.gpx    (saved at POST /api/search)
Output  -> /tmp/trackwise/<job_id>/output.gpx   (created at POST /api/gpx/generate)
Cleanup -> /tmp/trackwise/<job_id>/             (deleted N minutes after job completes, or on server restart)
```

A background cleanup task runs every 30 minutes and deletes job directories older than 2 hours.

---

## Patterns to Follow

### Pattern 1: Job Registry with asyncio.Queue for SSE

The core pattern for bridging a blocking ThreadPoolExecutor worker to a streaming SSE endpoint.

```python
# backend/jobs/manager.py
import asyncio
import threading
import uuid
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Job:
    id: str
    status: str  # "queued" | "running" | "complete" | "cancelled" | "error"
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    cancel_event: threading.Event = field(default_factory=threading.Event)
    results: Optional[dict] = None
    loop: Optional[asyncio.AbstractEventLoop] = None  # captured at creation time

class JobManager:
    def __init__(self):
        self._jobs: dict[str, Job] = {}

    def create_job(self) -> Job:
        job_id = str(uuid.uuid4())
        loop = asyncio.get_event_loop()
        job = Job(id=job_id, status="queued", loop=loop)
        self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job:
            job.cancel_event.set()
            return True
        return False

    def cleanup_old_jobs(self, max_age_seconds: int = 7200):
        # Called periodically; removes jobs and their temp dirs
        ...

job_manager = JobManager()  # Module-level singleton
```

```python
# backend/jobs/worker.py
# This runs in a thread (not async). Uses thread-safe queue posting.
def run_search(job: Job, gpx_path: str, search_config: dict):
    def post_progress(event_type: str, data: dict):
        """Thread-safe: schedule put on the event loop that owns the queue."""
        asyncio.run_coroutine_threadsafe(
            job.queue.put({"type": event_type, "data": data}),
            job.loop
        )

    job.status = "running"
    try:
        # Parse GPX
        post_progress("status", {"message": "Parsing GPX file..."})
        # ... processing ...

        # Overpass queries (with cancellation checks)
        for place_type in enabled_types:
            if job.cancel_event.is_set():
                post_progress("cancelled", {})
                return
            # ... parallel segment queries with ThreadPoolExecutor ...
            post_progress("progress", {"place_type": place_type, "found": count})

        # OSRM routes
        # ...

        job.results = { "places": all_places, "route_stats": stats }
        job.status = "complete"
        post_progress("complete", {"total_places": len(all_places)})

    except Exception as e:
        job.status = "error"
        post_progress("error", {"message": str(e)})
```

```python
# backend/routers/sse.py
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import asyncio, json

router = APIRouter()

@router.get("/api/search/{job_id}/sse")
async def stream_progress(job_id: str, request: Request):
    job = job_manager.get_job(job_id)
    if not job:
        return {"error": "job not found"}

    async def event_generator():
        while True:
            # Check for client disconnect
            if await request.is_disconnected():
                job_manager.cancel_job(job_id)
                break
            try:
                event = await asyncio.wait_for(job.queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                yield "data: {\"type\": \"heartbeat\"}\n\n"
                continue

            yield f"data: {json.dumps(event)}\n\n"

            if event["type"] in ("complete", "cancelled", "error"):
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Critical for nginx: disables proxy buffering
        }
    )
```

### Pattern 2: File Upload Handling (BackgroundTask Pitfall Avoided)

Since FastAPI closes UploadFile before BackgroundTasks runs (since v0.106.0), save the file synchronously during the request handler, before returning the job ID.

```python
@router.post("/api/search")
async def start_search(
    gpx_file: UploadFile,
    search_config: str = Form(...)   # JSON string from form
):
    job = job_manager.create_job()
    job_dir = Path(f"/tmp/trackwise/{job.id}")
    job_dir.mkdir(parents=True, exist_ok=True)

    # Save file NOW (synchronously in handler, before any background work)
    gpx_path = job_dir / "input.gpx"
    async with aiofiles.open(gpx_path, "wb") as f:
        content = await gpx_file.read()  # File is still open here
        await f.write(content)

    config = json.loads(search_config)

    # Submit blocking work to thread pool
    asyncio.get_event_loop().run_in_executor(
        executor,  # module-level ThreadPoolExecutor(max_workers=2)
        run_search, job, str(gpx_path), config
    )

    return {"job_id": job.id}
```

### Pattern 3: ThreadPoolExecutor Sizing for Raspberry Pi

The existing app uses `ThreadPoolExecutor(max_workers=2)` for Overpass queries — keep this. The Pi cannot sustain more than 2 concurrent outbound HTTP connections without memory pressure or rate limiting on Overpass.

Use a **module-level** executor (not per-request) to cap total concurrent threads:

```python
# backend/main.py
from concurrent.futures import ThreadPoolExecutor

# Global executor: max 2 concurrent search jobs on Pi
executor = ThreadPoolExecutor(max_workers=2)
```

Inside the worker, the nested Overpass executor also caps at 2:
```python
with ThreadPoolExecutor(max_workers=2) as overpass_executor:
    futures = {overpass_executor.submit(query_segment, seg): seg for seg in segments}
```

Total max threads on Pi: 2 (outer, one per job) × 2 (inner, Overpass) = 4 threads max.

### Pattern 4: Nginx SSE Configuration

SSE requires disabling proxy buffering. Without this, Nginx buffers the entire response and the browser receives nothing until the connection closes.

```nginx
location /api/search/ {
    proxy_pass http://unix:/run/trackwise/trackwise.sock;
    proxy_buffering off;           # Critical for SSE
    proxy_cache off;               # No caching for SSE
    proxy_read_timeout 300s;       # Long-running tasks need this
    proxy_send_timeout 300s;
    proxy_set_header Connection '';
    proxy_http_version 1.1;        # Keep-alive for SSE
    chunked_transfer_encoding on;
}

location /api/ {
    proxy_pass http://unix:/run/trackwise/trackwise.sock;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}

location /static/ {
    alias /home/pi/trackwise/web/frontend/static/;
    expires 7d;
}
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Using FastAPI BackgroundTasks for Long Work

**What:** Using `background_tasks.add_task(run_search, gpx_file, ...)` in a route handler.
**Why bad:** (1) BackgroundTasks runs in the same event loop after the response — a 2-minute blocking search will freeze the entire server. (2) Since FastAPI v0.106.0, `UploadFile` is closed before the background task runs. (3) No cancellation support.
**Instead:** Use `asyncio.get_event_loop().run_in_executor(executor, run_search, job, gpx_path, config)` — this puts blocking work on a real OS thread and leaves the event loop free.

### Anti-Pattern 2: Making the Worker Async

**What:** Converting `run_search` and `query_overpass_for_segment` to `async def` functions.
**Why bad:** The Overpass and OSRM calls use the `requests` library (sync). Calling `requests.get()` inside `async def` blocks the entire event loop — every SSE heartbeat, every other request stops. The existing `ThreadPoolExecutor` pattern in the monolith is already correct.
**Instead:** Keep `requests`-based functions synchronous in threads. Use `asyncio.run_coroutine_threadsafe` to post events back to the async queue. Do not switch to `httpx` async unless there is a specific reason — it adds complexity without benefit for this use case.

### Anti-Pattern 3: In-Process State Without Job IDs

**What:** Storing processing state as module-level variables (like `self.stations_data` in the monolith).
**Why bad:** A second request will overwrite the first user's results. Even with single-user intent, browser refreshes create second requests.
**Instead:** Scope all state to a `Job` object keyed by `job_id`. The browser always passes `job_id` when fetching results or generating GPX.

### Anti-Pattern 4: Serving Static Files Through FastAPI on the Pi

**What:** Using `app.mount("/static", StaticFiles(directory="frontend/static"))`.
**Why bad:** FastAPI/Uvicorn handles static file serving synchronously on Raspberry Pi, consuming worker threads and memory for files that Nginx can serve from disk with zero Python overhead.
**Instead:** Let Nginx serve `/static/` directly from the filesystem (see Nginx config above). FastAPI only handles `/api/` routes.

### Anti-Pattern 5: Forgetting `X-Accel-Buffering: no` in SSE Response

**What:** Returning `StreamingResponse` without the `X-Accel-Buffering: no` header.
**Why bad:** Nginx will buffer the entire SSE stream and deliver it all at once when the connection closes, making real-time progress invisible.
**Instead:** Set `X-Accel-Buffering: no` in the response headers AND `proxy_buffering off` in the Nginx location block for SSE routes. Both are required.

### Anti-Pattern 6: Generating the Map Server-Side with Folium

**What:** Using folium to generate an HTML map on the backend and serving that as a response.
**Why bad:** Folium generates large HTML files (100KB+), adds a heavy dependency, and produces a static snapshot. Every toggle of a place requires server round-trip.
**Instead:** Send the route coordinates and POI data as JSON from `/api/results/{job_id}`. The frontend renders the Leaflet.js map natively — this is already in the project's key decisions. The `folium` import can be removed from the backend entirely.

---

## Folder Structure

This is the target structure. The skeleton (`/web/backend/core/`, `/web/frontend/static/css/`, `/web/frontend/static/js/`) already exists.

```
TrackWise 2.0/
├── old/                            # Preserved original app (do not modify)
│   └── main_gui_enhanced.py
│
├── web/
│   ├── backend/
│   │   ├── main.py                 # FastAPI app factory, startup/shutdown events
│   │   ├── config.py               # Settings (temp dir path, executor config)
│   │   ├── routers/
│   │   │   ├── search.py           # POST /api/search, DELETE /api/search/{id}
│   │   │   ├── sse.py              # GET /api/search/{id}/sse
│   │   │   ├── results.py          # GET /api/results/{id}
│   │   │   └── gpx.py              # POST /api/gpx/generate, GET /api/gpx/{id}/download
│   │   ├── jobs/
│   │   │   ├── manager.py          # JobManager class, module-level singleton
│   │   │   └── worker.py           # run_search() — blocking, runs in executor
│   │   ├── services/
│   │   │   ├── overpass.py         # query_overpass_for_segment() — extracted from monolith
│   │   │   ├── osrm.py             # get_road_route() — extracted from monolith
│   │   │   ├── gpx_parser.py       # parse_gpx_file() — gpxpy wrapper
│   │   │   ├── gpx_builder.py      # build_output_gpx() — waypoints_only + enhanced_track modes
│   │   │   └── route_processor.py  # split_route(), deduplicate_places(), calc_distances()
│   │   ├── core/                   # (existing empty dir — put shared models/schemas here)
│   │   │   └── schemas.py          # Pydantic models: SearchConfig, PlaceResult, JobStatus
│   │   └── requirements.txt        # fastapi, uvicorn[standard], gpxpy, geopy, shapely, requests, aiofiles
│   │
│   ├── frontend/
│   │   ├── templates/
│   │   │   └── index.html          # Single page — Alpine.js + Leaflet.js from CDN
│   │   └── static/
│   │       ├── css/
│   │       │   └── app.css         # Minimal custom styles
│   │       └── js/
│   │           ├── app.js          # Alpine.js component: state, SSE client, table
│   │           └── map.js          # Leaflet.js map initialization and layer management
│   │
│   ├── deployment/
│   │   ├── trackwise.service       # systemd unit file
│   │   └── trackwise.nginx.conf    # nginx site config
│   │
│   └── launcher/                   # Windows-only, not deployed to Pi
│       └── launcher_gui.py         # tkinter: Start/Stop/Open Browser + log console
│
└── .planning/
    └── research/
        └── ARCHITECTURE.md         # This file
```

---

## Raspberry Pi Deployment Structure

### systemd Service (`web/deployment/trackwise.service`)

```ini
[Unit]
Description=TrackWise Web Server
After=network.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi/trackwise/web/backend
ExecStart=/home/pi/trackwise/venv/bin/uvicorn main:app \
    --host 127.0.0.1 \
    --port 8000 \
    --workers 1 \
    --timeout-keep-alive 120
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Note:** Use `--workers 1`. The in-memory `JobManager` and `asyncio.Queue` are not shared across processes. Multiple workers would route SSE connections to a different worker than the one running the job. Uvicorn single-worker is sufficient for a single-user LAN tool.

### Nginx Config (`web/deployment/trackwise.nginx.conf`)

```nginx
server {
    listen 80;
    server_name _;  # Match any hostname (LAN access)

    # Static files served by Nginx directly (no Python overhead)
    location /static/ {
        alias /home/pi/trackwise/web/frontend/static/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    # SSE endpoint: disable all buffering
    location ~ ^/api/search/[^/]+/sse$ {
        proxy_pass http://127.0.0.1:8000;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding on;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # All other API calls
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_read_timeout 60s;
        client_max_body_size 10M;  # Allow GPX files up to 10MB
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # Frontend HTML (served via FastAPI template or as a static file)
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Windows Launcher Subprocess Pattern

The tkinter launcher on Windows manages the Pi server. Two options:

**Option A (Pi deployment — recommended):** Launcher connects to the Pi via SSH and issues `systemctl start/stop trackwise`. The Pi server is always on-network.

**Option B (local development):** Launcher spawns `uvicorn main:app` as a local subprocess for testing on Windows before deploying. Use `subprocess.Popen` and communicate via `process.stdout`.

```python
# launcher/launcher_gui.py — subprocess management pattern
import subprocess, threading, tkinter as tk

class LauncherGUI:
    def __init__(self):
        self.server_process = None

    def start_server(self):
        self.server_process = subprocess.Popen(
            ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
            cwd="path/to/web/backend",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True
        )
        threading.Thread(target=self._stream_log, daemon=True).start()

    def _stream_log(self):
        for line in self.server_process.stdout:
            self.log_text.insert(tk.END, line)  # thread-safe via after() in production
            self.log_text.see(tk.END)

    def stop_server(self):
        if self.server_process:
            self.server_process.terminate()
            self.server_process = None
```

---

## Suggested Build Order

Based on component dependencies, the correct sequence is:

### Phase 1: Backend Core (No Frontend)
Build and test the Python processing pipeline as a standalone module before wiring it to FastAPI.

1. Extract `services/overpass.py` from monolith — test with `pytest`
2. Extract `services/osrm.py` — test independently
3. Extract `services/gpx_parser.py` and `services/route_processor.py`
4. Write `jobs/worker.py` — test with a direct function call, no HTTP
5. Write `services/gpx_builder.py` — test GPX output format

**Validation gate:** `python -c "from jobs.worker import run_search; ..."` produces correct results matching the original app.

### Phase 2: FastAPI Scaffolding
Wire the worker to HTTP endpoints without SSE first.

1. `backend/main.py` with health check endpoint
2. `backend/core/schemas.py` — Pydantic models
3. `routers/search.py` — POST /api/search (synchronous mode, blocking)
4. `routers/results.py` — GET /api/results/{id}
5. `routers/gpx.py` — POST /api/gpx/generate + GET /api/gpx/{id}/download

**Validation gate:** `curl` commands produce correct JSON and downloadable GPX.

### Phase 3: Async + SSE
Replace blocking handler with async job pattern.

1. `jobs/manager.py` — JobManager with asyncio.Queue
2. Refactor `routers/search.py` to use executor + job ID
3. `routers/sse.py` — EventSourceResponse streaming
4. Cancellation via DELETE endpoint and `cancel_event`
5. Periodic cleanup task for temp files

**Validation gate:** `EventSource` in browser DevTools shows streaming events; cancel button stops the worker.

### Phase 4: Frontend
Build UI against the now-stable API.

1. `frontend/templates/index.html` — layout skeleton
2. `frontend/static/js/app.js` — Alpine.js: form, SSE client, results table
3. `frontend/static/js/map.js` — Leaflet.js: route line + POI markers
4. Place toggle: update map markers without re-fetching
5. Download button: trigger file download via anchor href

### Phase 5: Pi Deployment
1. systemd service file
2. Nginx config (including SSE buffering fix)
3. Deploy and smoke-test on actual Pi hardware
4. Windows launcher (subprocess or SSH mode)

---

## Scalability Considerations

This is a single-user LAN tool. Scalability is not a goal. The constraints below are relevant only if the scope changes.

| Concern | Current (single-user Pi) | If Multi-User |
|---------|--------------------------|---------------|
| Job state | In-memory dict | Redis or SQLite |
| SSE routing | Trivial (1 worker) | Need sticky sessions or pub/sub |
| File storage | /tmp on Pi | Object storage or shared filesystem |
| Concurrency | 2 outer + 2 inner threads | Celery + worker queue |

For the current scope: none of these apply. Keep it simple.

---

## Sources

- [FastAPI Server-Sent Events (official docs)](https://fastapi.tiangolo.com/tutorial/server-sent-events/) — HIGH confidence
- [FastAPI Background Tasks (official docs)](https://fastapi.tiangolo.com/tutorial/background-tasks/) — HIGH confidence
- [FastAPI Request Files (official docs)](https://fastapi.tiangolo.com/tutorial/request-files/) — HIGH confidence
- [sse-starlette PyPI — SSE library for FastAPI/Starlette](https://pypi.org/project/sse-starlette/) — HIGH confidence
- [FastAPI: UploadFile closed before BackgroundTask issue #10936](https://github.com/fastapi/fastapi/discussions/10936) — HIGH confidence
- [FastAPI: Stop streaming when client disconnects #7572](https://github.com/fastapi/fastapi/discussions/7572) — HIGH confidence
- [FastAPI: ThreadPoolExecutor sizing discussion #6728](https://github.com/fastapi/fastapi/discussions/6728) — MEDIUM confidence
- [Deploy FastAPI on Debian with Nginx + Uvicorn + Systemd](https://ashfaque.medium.com/deploy-fastapi-app-on-debian-with-nginx-uvicorn-and-systemd-2d4b9b12d724) — MEDIUM confidence
- [Stop Burning CPU on Dead FastAPI Streams — cancel on disconnect pattern](https://jasoncameron.dev/posts/fastapi-cancel-on-disconnect) — MEDIUM confidence
- [Patching UploadFile for FastAPI background tasks workaround](https://dida.do/blog/patching-uploaded-files-for-usage-in-fastapi-background-tasks) — MEDIUM confidence
