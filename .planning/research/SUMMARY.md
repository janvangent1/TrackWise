# Research Summary: TrackWise Web

**Project:** TrackWise Web — migration of desktop tkinter GPX enrichment tool to a web application
**Research completed:** 2026-03-09
**Summary authored:** 2026-03-09
**Status:** COMPLETE — all 4 research files synthesized

---

## Executive Summary

TrackWise Web is a migration of a monolithic Python/tkinter desktop application to a self-hosted web application deployable on a Raspberry Pi. The core problem is exposing the existing GPX route enrichment logic — Overpass API POI queries, OSRM road deviation routing, gpxpy file processing — through a web interface accessible to any device on the local network (or internet), without requiring users to install software. The research confirms that FastAPI with SSE streaming is the correct architecture for surfacing long-running search tasks to a browser in real time, replacing the tkinter progress callbacks the desktop app used.

The recommended stack is deliberate in its constraint-awareness: no build toolchain on the Raspberry Pi (Alpine.js and Leaflet.js are loaded from CDN), a single Uvicorn worker (the in-memory job state cannot be shared across processes), Nginx as a thin reverse proxy that serves static files directly, and systemd for process management. The key architectural decision is the `asyncio.Queue` bridge pattern: blocking Overpass/OSRM calls run in a `ThreadPoolExecutor`, progress events are posted thread-safely to a per-job `asyncio.Queue`, and the SSE endpoint yields from that queue to the browser. This preserves the original app's proven concurrency model while making it compatible with an async HTTP framework.

The two highest-risk areas are SSE buffering through Nginx (requires `proxy_buffering off` and `X-Accel-Buffering: no` from day one) and Overpass API rate limiting (the public API enforces per-IP slot limits that the current ThreadPoolExecutor pattern will exhaust on large routes). Both are solvable with well-documented patterns, but both cause silent failures if not addressed at architecture time rather than as hotfixes. The Windows tkinter launcher adds a modest third risk: orphan server processes on launcher close require a `WM_DELETE_WINDOW` protocol handler from the initial implementation.

---

## Key Findings

### From STACK.md

**Core technologies with rationale:**

| Technology | Version | One-line rationale |
|------------|---------|-------------------|
| FastAPI | 0.135.1 | Native SSE via `fastapi.sse` (added 0.135.0), async-first, UploadFile built-in |
| Uvicorn | 0.41.0 | Standard ASGI server; piwheels ARM wheels confirmed available |
| python-multipart | 0.0.22 | Required for FastAPI file uploads — without it UploadFile silently fails |
| aiofiles | 25.1.0 | Async temp file I/O without blocking the event loop |
| httpx | 0.28.1 | Async HTTP client; `requests` is sync and blocks the event loop inside async handlers |
| gpxpy | 1.6.2 | Carried over unchanged; piwheels ARM wheel available |
| geopy | 2.4.1 | Carried over unchanged; pure Python, no binary dependency |
| shapely | 2.1.2 | Carried over unchanged; requires `sudo apt install libgeos-dev` before pip on Pi |
| Leaflet.js | 1.9.4 | Best-in-class open-source mapping; 2.0.0-alpha dropped as ESM-incompatible with CDN pattern |
| Alpine.js | 3.15.8 | 17KB reactive UI, no build step, sufficient for all required reactivity |
| Nginx | 1.24.x | Standard Raspberry Pi reverse proxy; serves static files without Python overhead |
| systemd | OS-provided | Auto-start on boot, restart on crash; replaces Supervisor (deprecated) and Docker (unnecessary overhead) |
| tkinter | stdlib | Zero-install Windows launcher with Start/Stop/Open Browser and log console |

**Critical version requirement:** Leaflet 1.9.4 stable — do NOT use 2.0.0-alpha (ESM-only, no stable CDN `<script>` tag support).

**Key infrastructure note:** Single Uvicorn worker required. In-memory `JobManager` and `asyncio.Queue` cannot be shared across processes. Multiple workers would route SSE connections to a different process than the one running the job.

---

### From FEATURES.md

**Table stakes (missing = product feels broken):**
- GPX file upload with drag-and-drop + click fallback
- Real-time progress display during 10–60 second searches (SSE stream)
- Interactive Leaflet map showing route polyline + POI markers by type
- Results list with sortable columns and per-place checkboxes
- Per-type on/off toggles and per-type distance thresholds (7 types)
- GPX download of selected waypoints
- Stop/cancel running search
- Inline error messages on API failure

**Differentiators (what makes TrackWise valuable vs. competitors):**
- Road-deviation routing via OSRM — competitors show crow-fly distance only; TrackWise shows actual detour distance. This is the primary value proposition for motorbike/cycling trip planning.
- Per-place include/exclude toggle at individual result level (not just type level)
- Bidirectional map/list sync (click row highlights marker, click marker highlights row)
- Log panel with per-API-call detail showing query counts and results
- Windows tkinter launcher for Pi server management

**Features deferred to v2+:**
- Search corridor visualization on map
- Enhanced track with deviations GPX export mode (GPX embeds detour routes, not just waypoints)
- Cycling tile overlay
- Pi system stats in launcher

**Anti-features confirmed (do not build):** User accounts, search history database, route editing, mobile native app, multiple concurrent searches, offline mode, integration with Garmin Connect/Komoot.

---

### From ARCHITECTURE.md

**Major components and responsibilities:**

| Component | Responsibility |
|-----------|---------------|
| `backend/main.py` | FastAPI app factory, mounts routers, configures CORS, registers startup/shutdown |
| `backend/jobs/manager.py` | In-memory job registry keyed by UUID; creates/destroys `Job` objects with `asyncio.Queue` and `threading.Event` |
| `backend/jobs/worker.py` | Blocking search runner in `ThreadPoolExecutor`; posts progress events thread-safely via `asyncio.run_coroutine_threadsafe` |
| `backend/services/overpass.py` | Overpass QL queries extracted from monolith |
| `backend/services/osrm.py` | OSRM routing calls extracted from monolith |
| `backend/services/gpx_parser.py` | gpxpy parse/write wrapper |
| `backend/services/gpx_builder.py` | Builds output GPX from selected waypoints |
| `backend/routers/sse.py` | SSE endpoint; yields from job queue with heartbeat fallback; cancels job on client disconnect |
| `frontend/static/` | HTML + Alpine.js + Leaflet.js; Leaflet owns its `<div>`, Alpine owns everything outside it |
| `web/deployment/` | systemd unit + Nginx config |
| `launcher/launcher_gui.py` | Windows tkinter launcher; subprocess or SSH management |

**Key patterns to follow:**
- `asyncio.Queue` bridge: worker thread posts events via `asyncio.run_coroutine_threadsafe`; SSE endpoint consumes with `await asyncio.wait_for(queue.get(), timeout=1.0)` (heartbeat on timeout)
- Save uploaded GPX file within the request handler (not in BackgroundTasks) — FastAPI closes `UploadFile` before BackgroundTasks runs since v0.106.0
- Module-level `ThreadPoolExecutor(max_workers=2)` — not per-request; caps total concurrency on Pi to 4 threads
- `if (map) { map.remove(); map = null; }` guard before every Leaflet initialization
- Strict DOM boundary: Leaflet owns `<div id="map">`, Alpine owns sibling elements via `$store`

**Folder structure (implemented):**
```
TrackWise 2.0/
├── old/                      # Original app preserved
├── web/
│   ├── backend/              # FastAPI app, routers, jobs, services
│   ├── frontend/             # HTML + Alpine.js + Leaflet.js
│   ├── deployment/           # systemd + Nginx configs
│   └── launcher/             # Windows tkinter launcher
└── .planning/
```

---

### From PITFALLS.md

**Top 5 critical pitfalls with prevention strategies:**

1. **FastAPI BackgroundTasks for long work** — Use `loop.run_in_executor(executor, run_search, job, gpx_path, config)` instead. BackgroundTasks ties up the event loop and provides no cancellation mechanism. Prevention: design with `asyncio.Queue` + `ThreadPoolExecutor` from day one.

2. **SSE stream has no end sentinel + no reconnect guard** — Always end the SSE generator with a `data: done` event so the browser calls `eventSource.close()`. Wrap `await queue.get()` in `try/except asyncio.CancelledError`; cancel the backing task on client disconnect. Orphaned queues accumulate memory on Pi.

3. **Nginx buffers SSE events** — Both `proxy_buffering off` in the Nginx location block AND `X-Accel-Buffering: no` in the FastAPI response headers are required. Either alone is insufficient. Gzip must also be disabled on the SSE endpoint. Write the Nginx config correctly from day one — do not add as a hotfix.

4. **Overpass API 429 from concurrent requests** — The public Overpass API enforces per-IP slot limits. Firing 7 types × 50+ waypoints simultaneously exhausts slots. Use `asyncio.Semaphore(2)`, exponential backoff on 429, batch multiple POI types per query with `union`, and include `[timeout:60]` in the query string.

5. **systemd cannot find uvicorn** — Use absolute path to virtualenv binary: `/home/pi/trackwise/venv/bin/uvicorn`. Set `WorkingDirectory` and `User=pi`. Do not rely on PATH.

**Additional pitfalls addressed:**
- Leaflet "Map container already initialized" — guard with `if (map) map.remove()` before every init; use `x-show` not `x-if` for the map container
- Alpine.js + Leaflet DOM conflict — strict boundary; never put `x-data` on any ancestor of the Leaflet container
- Temporary GPX files accumulate on Pi SD card — per-session cleanup task; startup cleanup in `lifespan` handler
- tkinter orphan processes on launcher close — `WM_DELETE_WINDOW` protocol handler calling `proc.terminate()` before window destroy
- CORS blocks SSE during development — add `CORSMiddleware` in initial scaffold; production via Nginx same-origin requires no CORS

---

## Implications for Roadmap

### Suggested Phase Structure

The research strongly implies a 6-phase build order based on two constraints: (1) each phase must be independently verifiable before the next begins, and (2) pitfalls are phase-specific — they must be addressed in the phase where the risk originates.

**Phase 1: Project Structure Setup**
Rationale: The `/old/` + `/web/` folder split is a prerequisite for all subsequent work. Nothing else can be validated until the folder structure and dependency baseline exist.
- Delivers: Preserved original app in `/old/`; skeleton `/web/` structure; `requirements.txt`; git-tracked baseline
- Pitfall to avoid: None specific; establishes clean separation
- Research flag: Standard — no phase research needed

**Phase 2: Core Backend Extraction**
Rationale: Extract and test the processing pipeline as standalone Python modules before wiring to HTTP. This validates that the domain logic is correctly separated from the monolith and that the existing API call patterns still work.
- Delivers: `gpx_parser.py`, `overpass.py`, `osrm.py`, `place_types.py`, `search.py`, `gpx_writer.py` as independent, testable modules
- Pitfalls to address: Overpass 429 rate limiting and concurrency control (Semaphore + backoff); temp file cleanup pattern; `[timeout:60]` in query strings
- Research flag: Standard — all patterns documented

**Phase 3: FastAPI Web Server**
Rationale: Wire the extracted services to HTTP endpoints with SSE streaming. This is the highest-complexity phase — the `asyncio.Queue` bridge pattern, job lifecycle management, SSE endpoint, and cancellation all come together here.
- Delivers: `app.py` with `/api/search` (POST), `/api/search/{id}/sse` (GET), `/api/results/{id}` (GET), `/api/gpx/export` (POST), `/upload` (POST)
- Pitfalls to address: BackgroundTasks misuse (use `run_in_executor`); SSE sentinel and reconnect guard; CORS middleware; file saved in handler not background task; `asyncio.run_coroutine_threadsafe` for thread-safe queue posting
- Research flag: Standard — architecture is fully specified

**Phase 4: Web Frontend**
Rationale: Build the browser UI against the now-stable API. Frontend work is unblocked only after the API contracts are solid.
- Delivers: Single-page HTML + Alpine.js + Leaflet.js app with upload form, SSE progress console, Leaflet map, results table, per-place toggles, GPX download
- Pitfalls to address: Leaflet "container already initialized" guard; Alpine/Leaflet DOM boundary; `x-show` not `x-if` for map container; `DOMContentLoaded` for Leaflet init; bidirectional sync via explicit function calls not shared reactive state
- Research flag: Standard — patterns from FEATURES.md are prescriptive

**Phase 5: Windows Launcher**
Rationale: The tkinter launcher is a separate sub-project with no dependency on frontend completion. It can be built in parallel after Phase 3, but is ordered after Phase 4 because the full-stack system should be smoke-tested before building management tooling around it.
- Delivers: `launcher.py` tkinter GUI with Start/Stop/Open Browser/Install buttons and log console
- Pitfalls to address: Orphan process on window close (`WM_DELETE_WINDOW` + `atexit`); port-in-use check before spawn; subprocess `PIPE` for log streaming via background thread; `root.after()` for thread-safe UI updates
- Research flag: Standard — well-documented tkinter subprocess pattern

**Phase 6: Raspberry Pi Deployment**
Rationale: Pi deployment is last because it requires a working application. The systemd service and Nginx config must be tested on actual Pi hardware — configuration bugs (wrong uvicorn path, missing `proxy_buffering off`) only manifest on the real target.
- Delivers: `trackwise.service` (systemd unit), `trackwise.nginx.conf` (Nginx site config), `setup_pi.sh` (installation script)
- Pitfalls to address: Absolute uvicorn path in systemd unit; `proxy_buffering off` + `X-Accel-Buffering: no` for SSE endpoint; gzip off on SSE location; `client_max_body_size 10M` for GPX uploads; `proxy_read_timeout 300s`; `Restart=on-failure` in service unit
- Research flag: Standard — Nginx + systemd patterns are fully documented

### Phase Summary Table

| Phase | Name | Key Deliverable | Pitfalls Phase Addresses |
|-------|------|----------------|--------------------------|
| 1 | Project Setup | Folder structure, `/old/`, `/web/` skeleton | None critical |
| 2 | Core Backend Extraction | Extracted services, testable modules | Overpass 429, temp file cleanup |
| 3 | FastAPI Web Server | API endpoints, SSE streaming, job lifecycle | BackgroundTasks, event loop blocking, CORS |
| 4 | Web Frontend | Single-page app, map, table, download | Leaflet init, Alpine/Leaflet DOM, bidirectional sync |
| 5 | Windows Launcher | tkinter GUI with server management | Orphan processes, port conflict |
| 6 | Raspberry Pi Deployment | systemd + Nginx, setup script | SSE buffering, systemd path, SD card cleanup |

---

## Research Flags

**Needs `/gsd:research-phase`:** None. All phases have well-documented patterns with high-confidence sources.

**Standard patterns (skip phase research):**
- All 6 phases use documented, verified patterns from FastAPI official docs, Leaflet docs, Alpine.js docs, and confirmed piwheels availability
- The Overpass rate-limiting mitigation (Semaphore + backoff) is established practice documented in the Overpass API commons

**What to validate during implementation (not research):**
- Confirm piwheels wheels for all packages install correctly on the specific Pi hardware model and Bookworm version in use
- Smoke-test SSE buffering through actual Nginx on Pi — this is the most environment-dependent behavior
- Verify `libgeos-dev` apt package name on Bookworm (name has been stable but worth confirming)

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions confirmed on PyPI and piwheels. FastAPI 0.135.0 native SSE confirmed in official docs. CDN URLs pinned to exact versions. |
| Features | MEDIUM-HIGH | Competitive analysis based on direct inspection of live tools. UX patterns from established sources. OSRM differentiator is clear. |
| Architecture | HIGH | Patterns verified against FastAPI official docs and issue tracker. `UploadFile` BackgroundTasks bug verified via GitHub discussion #10936. ThreadPoolExecutor sizing conservative and well-reasoned. |
| Pitfalls | HIGH | All 5 critical pitfalls verified via official docs or multiple corroborating community sources. Nginx buffering behavior confirmed in official Nginx proxy module docs. |

**Overall confidence: HIGH**

**Gaps to address during implementation (not blockers):**
- The exact `app.py` structure (flat file vs. router modules) was researched as a structured layout but the actual implementation may simplify to a single file — both are valid
- The enhanced GPX export mode (deviations embedded as route segments) is deferred to v2; the GPX schema for that mode was not researched and would need investigation when prioritized
- Paramiko SSH in the launcher (for remote Pi management) was specified in FEATURES.md but the implementation confirmed in scope uses local subprocess only; SSH integration is a v2 consideration

---

## Sources (Aggregated)

**Official documentation:**
- FastAPI: https://fastapi.tiangolo.com/tutorial/server-sent-events/
- FastAPI BackgroundTasks: https://fastapi.tiangolo.com/tutorial/background-tasks/
- FastAPI Request Files: https://fastapi.tiangolo.com/tutorial/request-files/
- Uvicorn: https://www.uvicorn.org/
- Leaflet.js: https://leafletjs.com/reference.html
- Alpine.js: https://alpinejs.dev/
- Nginx proxy module: https://nginx.org/en/docs/http/ngx_http_proxy_module.html
- Python subprocess: https://docs.python.org/3/library/subprocess.html

**Package availability:**
- PyPI (all packages): https://pypi.org/
- piwheels (ARM wheels): https://www.piwheels.org/

**Community / corroborating sources:**
- FastAPI UploadFile BackgroundTasks bug: https://github.com/fastapi/fastapi/discussions/10936
- Leaflet "container already initialized": https://github.com/Leaflet/Leaflet/issues/3962
- Overpass API commons: https://dev.overpass-api.de/overpass-doc/en/preface/commons.html
- Nginx + Uvicorn + FastAPI + systemd: https://miltschek.de/article_2023-10-21_nginx+++Uvicorn+++FastAPI+++systemd.html
- FastAPI SSE Nginx buffering: https://oneuptime.com/blog/post/2025-12-16-server-sent-events-nginx/view
