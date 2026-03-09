# Roadmap: TrackWise Web

**Project:** TrackWise Web
**Version:** 1.0
**Status:** ALL PHASES COMPLETE
**Last updated:** 2026-03-09

---

## Summary

Six phases, all implemented. The implementation migrated a monolithic Python/tkinter desktop application to a full web stack: FastAPI backend with SSE streaming, Alpine.js + Leaflet.js no-build frontend, Raspberry Pi deployment via systemd + Nginx, and a Windows tkinter launcher for local server management.

| Phase | Name | Status |
|-------|------|--------|
| 1 | Project Setup | COMPLETE |
| 2 | Core Backend Extraction | COMPLETE |
| 3 | FastAPI Web Server | COMPLETE |
| 4 | Web Frontend | COMPLETE |
| 5 | Windows Launcher | COMPLETE |
| 6 | Raspberry Pi Deployment | COMPLETE |

---

## Phase 1: Project Setup

**Status:** COMPLETE
**Goal:** Establish the repository structure that separates the original desktop app from the new web application and creates the skeleton for all subsequent phases.

### What Was Done

- Moved original `main_gui_enhanced.py` and associated desktop app files to `/old/` — preserving them as a reference and fallback without modifying them
- Created the `/web/` directory tree: `web/backend/`, `web/frontend/static/css/`, `web/frontend/static/js/`, `web/deployment/`, `web/launcher/`
- Created `web/backend/requirements.txt` with pinned versions of all Python dependencies
- Verified all dependencies have piwheels ARM wheels for Raspberry Pi Bookworm deployment

### Deliverables

- `/old/` — preserved original desktop application, untouched
- `/web/` — skeleton directory structure for the new web application
- `web/backend/requirements.txt` — pinned dependency manifest

### Key Decisions Made

- `/old/` + `/web/` folder split enforced clean separation between legacy and new code
- No code was modified in the original app — it remains runnable from `/old/`

### Requirements Addressed

F1.7, NF7

---

## Phase 2: Core Backend Extraction

**Status:** COMPLETE
**Goal:** Extract the processing pipeline from the monolithic `main_gui_enhanced.py` into standalone, independently testable Python modules. Validate that extracted logic produces identical results to the original.

### What Was Done

- Extracted `gpx_parser.py` — gpxpy-based GPX file parsing; returns list of track points with lat/lon/elevation
- Extracted `overpass.py` — Overpass QL query builder and HTTP caller; includes `[timeout:60]` header and `asyncio.Semaphore(2)` concurrency control to prevent 429 rate limit errors on the public Overpass API
- Extracted `osrm.py` — OSRM road routing client; returns detour distance and route geometry per POI
- Extracted `place_types.py` — POI type definitions, default distance thresholds, Overpass QL templates for all 7 types (petrol, supermarkets, bakeries, cafes, repair shops, accommodation, speed cameras)
- Extracted `search.py` — orchestrates the full search: parse GPX, segment route into chunks, run per-type Overpass queries, deduplicate results, run OSRM deviation routing per place
- Extracted `gpx_writer.py` — builds output GPX file from a list of selected places using gpxpy

### Deliverables

- `web/backend/services/gpx_parser.py`
- `web/backend/services/overpass.py`
- `web/backend/services/osrm.py`
- `web/backend/services/place_types.py`
- `web/backend/services/search.py`
- `web/backend/services/gpx_writer.py`

### Key Decisions Made

- Overpass concurrency capped at 2 parallel requests (`ThreadPoolExecutor(max_workers=2)`) — the public Overpass API enforces per-IP slot limits; more than 2 concurrent requests causes 429 errors on large routes
- Route segmentation implemented from the start — not added later — because large GPX files exceed Overpass bounding box limits without it
- Temp file cleanup pattern established: per-session directories in `/tmp/trackwise/{session_id}/`

### Requirements Addressed

F1.6, F3.1, F3.2, F3.3, F3.4, F7.2, NF6

---

## Phase 3: FastAPI Web Server

**Status:** COMPLETE
**Goal:** Wire the extracted backend services to HTTP endpoints with SSE streaming, file upload handling, and job lifecycle management. This is the architectural core of the web application.

### What Was Done

- Implemented `app.py` as the FastAPI application factory with `lifespan` handler for startup/shutdown events
- Implemented file upload endpoint `POST /upload` — saves GPX to `/tmp/trackwise/{job_id}/input.gpx` within the request handler (not in BackgroundTasks, which closes UploadFile before the task runs)
- Implemented search start endpoint `POST /api/search` — creates a `Job` with `asyncio.Queue` and `threading.Event`; submits blocking search to `ThreadPoolExecutor` via `loop.run_in_executor()`
- Implemented SSE streaming endpoint `GET /api/search/{job_id}/sse` — async generator that yields from the job's `asyncio.Queue`; sends heartbeat events on 1-second timeout; sets `cancel_event` on client disconnect; terminates on `complete`/`cancelled`/`error` sentinel events
- Implemented results endpoint `GET /api/results/{job_id}` — returns JSON with places list and route stats
- Implemented GPX export endpoint `POST /api/gpx/export` — accepts selected place IDs and generates downloadable GPX via `gpx_writer.py`; returns `FileResponse` with `Content-Disposition: attachment`
- Added `CORSMiddleware` for development (browsers block cross-origin SSE without it)
- Startup cleanup task deletes `/tmp/trackwise/` directories older than 2 hours on each server start
- Response headers include `X-Accel-Buffering: no` on SSE endpoint to suppress Nginx proxy buffering

### Deliverables

- `web/backend/app.py` — FastAPI application with all endpoints

### Key Decisions Made

- `asyncio.Queue` bridge pattern: blocking worker thread posts events via `asyncio.run_coroutine_threadsafe(queue.put(...), loop)` — this is the only correct way to post to an async queue from a non-async thread
- `ThreadPoolExecutor` is module-level (not per-request) with `max_workers=2` — caps total concurrency on Pi to avoid RAM pressure
- File saved synchronously inside the request handler before returning `job_id` — FastAPI closes `UploadFile` before any background task runs (breaking change in FastAPI v0.106.0)
- SSE response sets `X-Accel-Buffering: no` — tells Nginx to pass events through without buffering (also requires `proxy_buffering off` in Nginx config)

### Requirements Addressed

F3.5, F3.6, F4.1, F4.2, F4.3, F4.4, F4.5, F7.1, F7.3, F7.4, F8.1, F8.8, F8.9, NF3, NF4

---

## Phase 4: Web Frontend

**Status:** COMPLETE
**Goal:** Build the browser UI as a single-page application using Alpine.js and Leaflet.js loaded from CDN. No build step required — the HTML file works when opened from the filesystem or served by Nginx.

### What Was Done

- Implemented `web/frontend/static/index.html` — single HTML file with all layout; includes pinned CDN tags for Leaflet 1.9.4 and Alpine.js 3.15.8
- Implemented upload drop zone — large centered zone; Alpine.js `x-on:drop` + `x-on:dragover.prevent` handles drag-and-drop; hidden `<input type="file">` for click-to-browse; inline validation for `.gpx` extension only
- Implemented search configuration panel — per-type checkboxes and distance threshold inputs for all 7 POI types; pre-populated with sensible defaults; collapses until a file is loaded
- Implemented SSE progress console — fixed-height scrolling `<div>` with monospace font; auto-scrolls to bottom; each SSE event type (`step_start`, `step_done`, `place_found`, `error`, `complete`) appends a formatted log line; `EventSource` opened on search start, closed explicitly on `complete`/`cancelled` event
- Implemented results table — columns: checkbox, name, type icon, distance from route, road deviation; Alpine.js `x-for` binding to results array; sortable by column header click; type filter buttons above table; Select All / Deselect All bulk controls
- Implemented Leaflet.js map — full-width, 60vh height; route polyline in blue (#3B82F6); POI markers colored by type; marker popups with name + type + distances; `map.fitBounds()` on route load; Reset View button; guarded with `if (map) { map.remove(); map = null; }` before every initialization to prevent "Map container already initialized" error
- Implemented bidirectional map/list sync — clicking a table row calls `marker.openPopup()` and scrolls map to marker; clicking a marker adds `row-highlighted` class to corresponding table row and scrolls it into view; communication via shared place ID (no Alpine/Leaflet DOM overlap)
- Strict DOM boundary enforced — Leaflet owns `<div id="map">` exclusively; Alpine `x-data` is never placed on any ancestor of the map container; map is inside `x-show` (not `x-if`) to preserve DOM element across re-renders
- Leaflet initialized in `DOMContentLoaded` listener; dispatches `leaflet-ready` custom event; Alpine components listen with `@leaflet-ready.window` before calling map methods
- Implemented GPX download — "Download GPX (N places)" button; count badge reflects current checkbox state; sends `POST /api/gpx/export` with selected IDs; triggers browser download via Blob URL; disabled while search is running

### Deliverables

- `web/frontend/static/index.html` — complete single-page application
- `web/frontend/static/css/app.css` — minimal custom styles (map height, marker colors, log console)

### Key Decisions Made

- `x-show` used for map container visibility (not `x-if`) — `x-if` removes the DOM element, destroying the Leaflet instance and requiring re-initialization with its associated edge cases
- Alpine `$store` used for results data rather than component-level state — allows the table and the map to share place data without either owning the other's DOM
- Leaflet map initialization deferred to `DOMContentLoaded` and guarded with `leaflet-ready` event — prevents Alpine's `x-init` from calling map methods before Leaflet is ready

### Requirements Addressed

F1.1, F1.2, F1.3, F1.4, F1.5, F2.1, F2.2, F2.3, F2.4, F4.6, F5.1, F5.2, F5.3, F5.4, F5.5, F5.6, F5.7, F6.1, F6.2, F6.3, F6.4, F6.5, F6.6, F6.7, F6.8, F6.9, F7.5, F7.6, NF1, NF5, NF8

---

## Phase 5: Windows Launcher

**Status:** COMPLETE
**Goal:** Provide a Python tkinter GUI that allows a Windows user to start, stop, and monitor the web server without using a terminal.

### What Was Done

- Implemented `web/launcher/launcher.py` — tkinter window with standard ttk widgets (no third-party theme libraries)
- Start Server button — spawns `python -m uvicorn web.backend.app:app --host 0.0.0.0 --port 8000` as a `subprocess.Popen` child process with `stdout=PIPE, stderr=STDOUT`; background daemon thread reads stdout line by line and feeds the log console via `root.after()` for thread-safe UI updates
- Stop Server button — calls `process.terminate()`; clears the stored process reference; updates button states
- Open Browser button — calls `webbrowser.open('http://localhost:8000')`; enabled only when server is running
- Install button — runs `pip install -r requirements.txt` in a subprocess; streams install output to the log console; useful for first-time setup without opening a terminal
- Log console — `ScrolledText` widget in monospace font; timestamped lines; auto-scrolls to bottom; shows all server stdout/stderr and launcher events
- Window close handler — `root.protocol("WM_DELETE_WINDOW", on_close)` calls `process.terminate()` before `root.destroy()`; also registered with `atexit.register(cleanup)` as a fallback for abnormal exits — prevents orphan uvicorn processes on port 8000
- Port-in-use check before spawn — tests `socket.connect(('localhost', 8000))` before starting; warns user with inline message if port is already occupied

### Deliverables

- `web/launcher/launcher.py` — Windows tkinter launcher application

### Key Decisions Made

- `WM_DELETE_WINDOW` protocol handler is non-negotiable — without it, closing the launcher leaves an orphan uvicorn process that blocks port 8000 on subsequent launcher starts (Windows does not kill child processes when parent exits)
- `root.after()` used for all UI updates from background threads — direct `widget.insert()` calls from non-main threads are not thread-safe in tkinter
- Plain `ttk` widgets only — no CustomTkinter or third-party themes; keeps launcher zero-dependency beyond the Python stdlib

### Requirements Addressed

F9.1, F9.2, F9.3, F9.4, F9.5, F9.6, F9.7

---

## Phase 6: Raspberry Pi Deployment

**Status:** COMPLETE
**Goal:** Provide the configuration files and installation script needed to deploy the web application as a production service on a Raspberry Pi running Raspberry Pi OS Bookworm.

### What Was Done

- Implemented `web/deployment/trackwise.service` — systemd unit file; `ExecStart` uses the absolute path to the virtualenv uvicorn binary (`/home/pi/trackwise/venv/bin/uvicorn`); sets `WorkingDirectory=/home/pi/trackwise/web/backend`; `User=pi`; `Restart=on-failure`; `RestartSec=5`; `--workers 1` (in-memory job state cannot be shared across processes); logs to systemd journal via `StandardOutput=journal`
- Implemented `web/deployment/trackwise.nginx.conf` — Nginx site config; dedicated SSE location block (`location ~ ^/api/search/[^/]+/sse$`) with `proxy_buffering off`, `proxy_cache off`, `proxy_read_timeout 300s`, `proxy_http_version 1.1`, `Connection ''` header (required for SSE keep-alive through proxy), `chunked_transfer_encoding on`; `/static/` location served directly from filesystem with 7-day cache headers; general `/api/` location with `client_max_body_size 10M` for GPX uploads; all other requests proxied to `http://127.0.0.1:8000`
- Implemented `web/deployment/setup_pi.sh` — bash installation script; installs system dependencies (`libgeos-dev`, `nginx`, `python3.11-venv`) via apt; creates `/opt/trackwise/` or `/home/pi/trackwise/`; creates virtualenv; installs Python packages from `requirements.txt` using `--extra-index-url https://www.piwheels.org/simple` for ARM-compiled wheels; copies systemd unit file to `/etc/systemd/system/`; enables and starts the service; copies Nginx config to `/etc/nginx/sites-available/` and symlinks to `sites-enabled/`; reloads Nginx; prints final status

### Deliverables

- `web/deployment/trackwise.service` — systemd unit file
- `web/deployment/trackwise.nginx.conf` — Nginx site configuration
- `web/deployment/setup_pi.sh` — automated installation script

### Key Decisions Made

- Absolute uvicorn path in systemd unit is mandatory — systemd services run without the user's shell environment; bare `uvicorn` fails with `exec: uvicorn: not found` because PATH does not include the virtualenv bin directory
- Both `proxy_buffering off` in Nginx AND `X-Accel-Buffering: no` in FastAPI response headers are required for SSE to stream through Nginx in real time — either alone is insufficient in some Nginx configurations
- Gzip disabled on the SSE location — gzip requires buffering a complete chunk before compressing, which defeats SSE streaming
- `--workers 1` in the systemd unit — multiple Uvicorn workers would route SSE connections to a different worker than the one holding the job's `asyncio.Queue`, breaking the streaming entirely
- `piwheels.org` added as extra index URL in setup script — ensures ARM-compiled binary wheels are used for shapely and other packages with C extensions; without this, pip attempts to compile from source and fails (or takes hours on older Pi models)

### Requirements Addressed

F8.2, F8.3, F8.4, F8.5, F8.6, F8.7, F8.9, NF2

---

## Deferred to v2+

These items were identified during research but explicitly deferred from the v1 implementation.

| Feature | Rationale for Deferral |
|---------|----------------------|
| Enhanced GPX export mode (deviations as route segments) | Requires research into GPX schema for embedded route segments; core value (waypoints-only) is already delivered |
| Search corridor visualization on map | Nice-to-have visualization; adds Shapely GeoJSON generation complexity; core results are already clear |
| Bidirectional SSH Pi management in launcher | Current subprocess-based launcher covers local development; SSH adds Paramiko dependency |
| Pi system stats in launcher (CPU/RAM/disk) | Useful for Pi models with ≤2GB RAM; deferred because the core use case (start/stop/open browser) is covered |
| Cycling tile overlay (OpenCycleMap) | Low demand for primary motorbike use case |
| Column sort arrows and advanced table UX | Table is functional; visual refinements deferred |
