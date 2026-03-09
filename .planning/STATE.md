# Project State: TrackWise Web

**Project:** TrackWise Web
**Last updated:** 2026-03-09
**Overall status:** COMPLETE

---

## Phase Status

| Phase | Name | Status | Completed |
|-------|------|--------|-----------|
| 1 | Project Setup | COMPLETE | 2026-03-09 |
| 2 | Core Backend Extraction | COMPLETE | 2026-03-09 |
| 3 | FastAPI Web Server | COMPLETE | 2026-03-09 |
| 4 | Web Frontend | COMPLETE | 2026-03-09 |
| 5 | Windows Launcher | COMPLETE | 2026-03-09 |
| 6 | Raspberry Pi Deployment | COMPLETE | 2026-03-09 |

---

## Phase 1: Project Setup — COMPLETE

**Goal:** Move old files to `/old/`, create `/web/` directory structure, establish requirements.

**Deliverables:**
- [x] Original app files moved to `/old/` — preserved and untouched
- [x] `/web/` skeleton created: `backend/`, `frontend/static/css/`, `frontend/static/js/`, `deployment/`, `launcher/`
- [x] `web/backend/requirements.txt` created with pinned versions

---

## Phase 2: Core Backend Extraction — COMPLETE

**Goal:** Extract processing pipeline from monolith into standalone, testable modules.

**Deliverables:**
- [x] `web/backend/services/gpx_parser.py` — GPX file parsing via gpxpy
- [x] `web/backend/services/overpass.py` — Overpass API queries with concurrency control
- [x] `web/backend/services/osrm.py` — OSRM road routing deviation calculations
- [x] `web/backend/services/place_types.py` — POI type definitions and Overpass QL templates
- [x] `web/backend/services/search.py` — full search orchestration
- [x] `web/backend/services/gpx_writer.py` — output GPX generation

---

## Phase 3: FastAPI Web Server — COMPLETE

**Goal:** Wire extracted services to HTTP endpoints with SSE streaming and job lifecycle management.

**Deliverables:**
- [x] `web/backend/app.py` — FastAPI application with all endpoints:
  - [x] `POST /upload` — GPX file upload
  - [x] `POST /api/search` — start search, returns `job_id`
  - [x] `GET /api/search/{job_id}/sse` — SSE progress stream
  - [x] `GET /api/results/{job_id}` — JSON results
  - [x] `POST /api/gpx/export` — GPX file generation and download
- [x] `asyncio.Queue` bridge pattern implemented
- [x] `ThreadPoolExecutor` (max_workers=2) for blocking search work
- [x] Cancellation via `threading.Event`
- [x] `CORSMiddleware` configured
- [x] Startup cleanup for stale temp files

---

## Phase 4: Web Frontend — COMPLETE

**Goal:** Single-page web application with upload, config, progress, map, table, and download.

**Deliverables:**
- [x] `web/frontend/static/index.html` — single-page application
- [x] `web/frontend/static/css/app.css` — custom styles
- [x] GPX drag-and-drop upload zone
- [x] Search configuration panel (7 POI types, per-type distance thresholds)
- [x] SSE progress console with auto-scroll
- [x] Leaflet.js interactive map (route polyline + typed POI markers)
- [x] Bidirectional map/table sync
- [x] Sortable results table with type filter and per-place checkboxes
- [x] GPX download button with selected-count badge

---

## Phase 5: Windows Launcher — COMPLETE

**Goal:** tkinter GUI for Windows users to manage the web server without a terminal.

**Deliverables:**
- [x] `web/launcher/launcher.py` — tkinter GUI launcher
- [x] Start Server button (subprocess.Popen)
- [x] Stop Server button (process.terminate)
- [x] Open Browser button (webbrowser.open)
- [x] Install button (pip install -r requirements.txt)
- [x] Log console (ScrolledText, auto-scroll, timestamped)
- [x] WM_DELETE_WINDOW handler (prevents orphan processes)
- [x] Port-in-use check before spawn

---

## Phase 6: Raspberry Pi Deployment — COMPLETE

**Goal:** systemd service, Nginx config, and setup script for Pi production deployment.

**Deliverables:**
- [x] `web/deployment/trackwise.service` — systemd unit file
  - [x] Absolute path to virtualenv uvicorn binary
  - [x] `--workers 1`
  - [x] `Restart=on-failure`
  - [x] Logs to systemd journal
- [x] `web/deployment/trackwise.nginx.conf` — Nginx site configuration
  - [x] SSE location: `proxy_buffering off`, `proxy_cache off`, `proxy_read_timeout 300s`
  - [x] Static files served directly from filesystem
  - [x] `client_max_body_size 10M` for GPX uploads
- [x] `web/deployment/setup_pi.sh` — automated installation script
  - [x] apt dependencies (libgeos-dev, nginx, python3.11-venv)
  - [x] Python venv creation
  - [x] pip install with piwheels extra index URL
  - [x] systemd service enable + start
  - [x] Nginx site enable + reload

---

## Planning Documents

| Document | Status |
|----------|--------|
| `.planning/PROJECT.md` | Complete |
| `.planning/research/STACK.md` | Complete |
| `.planning/research/FEATURES.md` | Complete |
| `.planning/research/ARCHITECTURE.md` | Complete |
| `.planning/research/PITFALLS.md` | Complete |
| `.planning/research/SUMMARY.md` | Complete |
| `.planning/REQUIREMENTS.md` | Complete |
| `.planning/ROADMAP.md` | Complete |
| `.planning/STATE.md` | This file |

---

## Known Deferred Items (v2+)

- Enhanced GPX export mode (deviations embedded as route segments)
- Search corridor visualization on map
- SSH-based Pi management in launcher
- Pi system stats in launcher
- Cycling tile overlay

No blocking issues. Project is complete and deployable.
