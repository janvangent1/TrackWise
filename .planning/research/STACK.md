# Technology Stack

**Project:** TrackWise Web
**Researched:** 2026-03-09
**Overall confidence:** HIGH — all versions confirmed against PyPI and official docs

---

## Recommended Stack

### Backend — Python Web Layer

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| FastAPI | 0.135.1 | ASGI web framework | Native SSE via `fastapi.sse` (added 0.135.0), async-first, Pydantic validation, UploadFile built-in. Superior to Flask for this use-case because async is first-class, not bolted on. |
| Uvicorn | 0.41.0 | ASGI server | The standard ASGI server for FastAPI. Lightweight enough for Raspberry Pi single-process deployment. Pre-compiled piwheels ARM wheels available. |
| python-multipart | 0.0.22 | Form/file upload parsing | Required by FastAPI to handle `multipart/form-data` uploads. Without it, UploadFile silently fails. |
| aiofiles | 25.1.0 | Async temp file I/O | Writing uploaded GPX to a temp file without blocking the event loop. Needed because `UploadFile.read()` is async but `open()` is not. |
| httpx | 0.28.1 | Async HTTP client | Replaces `requests` for Overpass API and OSRM calls in the async backend. `requests` is synchronous — using it in an `async def` endpoint blocks the event loop. httpx provides a requests-compatible API with `asyncio` support. |
| Pydantic | v2 (ships with FastAPI 0.135.x) | Request/response validation | Built into FastAPI. Use for search config models (POI types, distance thresholds). Pydantic v1 support is deprecated in FastAPI 0.135.x. |

### Backend — Existing Domain Libraries (carried over unchanged)

| Technology | Version | Purpose | Notes |
|------------|---------|---------|-------|
| gpxpy | 1.6.2 | GPX file parsing | No changes needed. Available on piwheels for ARM. |
| geopy | 2.4.1 | Geographic distance calculations | No changes needed. Pure Python, no ARM binary dependency. |
| shapely | 2.1.2 | Route buffer geometry (polygon around route) | Binary dependency (libgeos). Pre-compiled 2.x wheels on piwheels for Raspberry Pi Bookworm (armv6l, armv7l). Install `libgeos-dev` via apt before pip on the Pi. |

### Frontend — No-Build CDN Stack

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Leaflet.js | 1.9.4 | Interactive map rendering | Best-in-class open-source mapping library. Replaces folium entirely — folium generated static HTML blobs; Leaflet gives live DOM interaction. Use 1.9.4 stable, NOT 2.0.0-alpha (alpha has no stable release timeline as of March 2026, drops IE but also changes ESM structure incompatibly). |
| Alpine.js | 3.15.8 | Reactive UI without a build step | Handles x-data state for: upload form, search config toggles, progress display, results table, GPX selection checkboxes. Small enough (17KB gzipped) to have no perceptible impact on the Pi's ability to serve static files. No npm, no webpack, no node_modules on the Pi. |
| Vanilla JavaScript | ES2020 (browser native) | EventSource (SSE client), fetch API | `EventSource` is browser-native for SSE consumption. No library needed. `fetch` for file upload POST. Both work without build tools. |
| OpenStreetMap tiles | — | Map tile source | Free, no API key, no rate limit for light personal use. Standard Leaflet tile URL: `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png` |

### Infrastructure

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Nginx | 1.24.x (from Raspberry Pi OS Bookworm repo) | Reverse proxy | Terminates external connections on port 80/443, proxies to uvicorn on 127.0.0.1:8000. Handles static files (HTML/CSS/JS) efficiently without involving Python. Standard Raspberry Pi deployment pattern. |
| systemd | OS-provided | Process management on Pi | Manages uvicorn as a system service — auto-start on boot, restart on crash. Replaces Supervisor (deprecated pattern) and Docker (unnecessary overhead for a single-process Pi app). |
| Python venv | Python 3.11+ | Dependency isolation on Pi | Raspberry Pi OS Bookworm ships Python 3.11. Use a venv in `/opt/trackwise/venv/` to isolate from system Python. |

### Windows Developer Launcher

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| tkinter | Python stdlib | GUI launcher | Already in Python stdlib — zero installation. Provides Start/Stop buttons, a log console (`ScrolledText`), and Open Browser button. |
| subprocess.Popen | Python stdlib | Spawn/kill uvicorn process | `Popen(['python', '-m', 'uvicorn', 'app:app', '--reload'])` starts the server as a child process. `process.terminate()` stops it. Read stdout/stderr via a background thread feeding the log console. |
| webbrowser | Python stdlib | Open browser | `webbrowser.open('http://localhost:8000')` on the Open Browser button click. |

---

## CDN URLs (Pin These Exactly)

```html
<!-- Leaflet 1.9.4 -->
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<!-- Alpine.js 3.15.8 (defer required) -->
<script defer src="https://cdn.jsdelivr.net/npm/[email protected]/dist/cdn.min.js"></script>
```

Use unpkg for Leaflet (official recommendation). Use jsDelivr for Alpine.js (official recommendation from Alpine docs). Pin exact versions — never use `@latest` in production.

---

## Alternatives Considered and Rejected

| Category | Recommended | Rejected | Reason Rejected |
|----------|-------------|----------|-----------------|
| HTTP client | httpx | requests | `requests` is synchronous. Using it inside `async def` blocks the entire uvicorn event loop, serialising all Overpass/OSRM calls instead of running them concurrently. |
| HTTP client | httpx | aiohttp | httpx has a requests-compatible API (easier migration from existing code). aiohttp is also valid but requires more API rewrite. |
| SSE | FastAPI native `fastapi.sse` | sse-starlette | FastAPI 0.135.0 ships native `EventSourceResponse` in `fastapi.sse`. sse-starlette is now redundant and adds an unnecessary dependency. |
| Background tasks | asyncio tasks | Celery | Celery requires Redis/RabbitMQ broker — far too heavy for a Raspberry Pi single-user tool. FastAPI's `BackgroundTasks` or plain `asyncio.create_task()` is sufficient. |
| Frontend framework | Alpine.js | Vue/React/Svelte | All require a build step (npm, webpack, vite). Violates the "no build step on Pi" constraint. Alpine.js is sufficient for this UI complexity. |
| Frontend framework | Alpine.js | HTMX | HTMX handles HTML fragments but SSE progress stream and Leaflet map integration require JavaScript reactivity that HTMX doesn't cover cleanly. Alpine.js is a better fit here. |
| Map library | Leaflet.js | folium | folium generates static HTML blobs from Python — no live interaction. Leaflet.js runs in the browser with live DOM, enabling toggle/filter/zoom without round-trips. |
| Map library | Leaflet.js | MapLibre GL | MapLibre requires WebGL, heavier JavaScript footprint, and is optimised for vector tiles. Overkill for raster OSM tiles + simple markers. |
| Process manager | systemd | Docker | Docker adds ~200MB+ overhead on Raspberry Pi, complex networking, and unnecessary abstraction for a single-process app with no containerisation benefit. |
| Process manager | systemd | Supervisor | Supervisor is the older pattern. systemd is the modern standard on Debian/Raspberry Pi OS and requires no additional install. |
| Leaflet version | 1.9.4 (stable) | 2.0.0-alpha | 2.0 alpha has no stable release timeline and ships as an ESM module — incompatible with `<script>` CDN tag pattern without a bundler. Not suitable for a no-build-step constraint. |

---

## SSE Streaming Implementation Notes

FastAPI 0.135.0+ provides native SSE via `fastapi.sse`:

```python
from collections.abc import AsyncIterable
from fastapi import FastAPI
from fastapi.sse import EventSourceResponse, ServerSentEvent

app = FastAPI()

@app.get("/search/stream", response_class=EventSourceResponse)
async def stream_search(job_id: str) -> AsyncIterable[ServerSentEvent]:
    async for event in job_queue[job_id]:
        yield ServerSentEvent(data=event, event="progress")
```

FastAPI automatically sets:
- `Cache-Control: no-cache`
- `X-Accel-Buffering: no` — tells Nginx to not buffer this response

Nginx still needs `proxy_read_timeout` extended for long-running searches:

```nginx
location /search/stream {
    proxy_pass http://127.0.0.1:8000;
    proxy_read_timeout 300s;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
}
```

The `X-Accel-Buffering: no` header from FastAPI handles buffering suppression automatically. No `proxy_buffering off` directive is needed in the Nginx config.

---

## File Upload Handling Notes

GPX files are 50-500KB. FastAPI's `UploadFile` streams without loading the full file into memory. Recommended pattern:

```python
from fastapi import UploadFile
import aiofiles, tempfile, os

@app.post("/upload")
async def upload_gpx(file: UploadFile):
    suffix = ".gpx"
    async with aiofiles.tempfile.NamedTemporaryFile(
        suffix=suffix, delete=False
    ) as tmp:
        content = await file.read()
        await tmp.write(content)
        return {"path": tmp.name}
```

For GPX files at this size range, reading the full file into memory with `await file.read()` is acceptable (max ~500KB). Chunked streaming is unnecessary here — the complexity tradeoff is not worth it.

---

## Parallel HTTP Request Pattern (Overpass + OSRM)

Replace `ThreadPoolExecutor` from the original app with `asyncio.gather()` using `httpx.AsyncClient`:

```python
import httpx
import asyncio

async def fetch_pois(queries: list[str]) -> list[dict]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = [client.post(OVERPASS_URL, data=q) for q in queries]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
    return responses
```

This achieves the same parallelism as `ThreadPoolExecutor` but without thread overhead, and without blocking the event loop. The async client is shared across all concurrent requests in one search session.

---

## Raspberry Pi Deployment Notes

**Hardware target:** Raspberry Pi 4 (or Pi 5) — 2-4GB RAM, ARMv7/ARM64, Raspberry Pi OS Bookworm (Debian 12).

**Python version:** Python 3.11 (ships with Bookworm). All piwheels wheels confirmed available for 3.11.

**libgeos dependency (for Shapely):**
```bash
sudo apt install libgeos-dev
```
Must be installed before `pip install shapely`. piwheels provides binary wheels for Shapely 2.1.2 but they still link against the system libgeos.

**Worker count:** 1 uvicorn worker. This is a single-user local tool — multiple workers would only consume extra RAM. A single async worker handles concurrent SSE streams and background searches efficiently.

**Nginx as static file server:** Serve `/web/static/` directly from Nginx, bypassing Python entirely for HTML/CSS/JS files. This is the main benefit of Nginx over running uvicorn on port 80 directly.

---

## Installation

### Raspberry Pi (production)

```bash
# System dependencies
sudo apt update
sudo apt install python3.11-venv libgeos-dev nginx

# App setup
sudo mkdir -p /opt/trackwise
sudo python3 -m venv /opt/trackwise/venv
sudo /opt/trackwise/venv/bin/pip install --extra-index-url https://www.piwheels.org/simple \
    fastapi==0.135.1 \
    uvicorn==0.41.0 \
    python-multipart==0.0.22 \
    aiofiles==25.1.0 \
    httpx==0.28.1 \
    gpxpy==1.6.2 \
    geopy==2.4.1 \
    shapely==2.1.2
```

The `--extra-index-url https://www.piwheels.org/simple` flag ensures pip prefers ARM-compiled wheels from piwheels over attempting to compile from source.

### Windows (development)

```bash
pip install \
    fastapi==0.135.1 \
    uvicorn==0.41.0 \
    python-multipart==0.0.22 \
    aiofiles==25.1.0 \
    httpx==0.28.1 \
    gpxpy==1.6.2 \
    geopy==2.4.1 \
    shapely==2.1.2
```

Shapely 2.x ships pre-compiled Windows wheels on PyPI — no GEOS install needed on Windows.

---

## Sources

- FastAPI 0.135.1 on PyPI: https://pypi.org/project/fastapi/ (MEDIUM confidence — PyPI confirmed)
- FastAPI native SSE docs: https://fastapi.tiangolo.com/tutorial/server-sent-events/ (HIGH confidence — official docs)
- Uvicorn 0.41.0 on PyPI and piwheels: https://pypi.org/project/uvicorn/ + https://www.piwheels.org/project/uvicorn/ (HIGH confidence)
- python-multipart 0.0.22 on PyPI: https://pypi.org/project/python-multipart/ (HIGH confidence)
- aiofiles 25.1.0 on PyPI: https://pypi.org/project/aiofiles/ (HIGH confidence)
- httpx 0.28.1 on PyPI: https://pypi.org/project/httpx/ (HIGH confidence)
- Shapely 2.1.2 on piwheels: https://www.piwheels.org/project/shapely/ (HIGH confidence)
- gpxpy 1.6.2 on PyPI and piwheels: https://pypi.org/project/gpxpy/ + https://www.piwheels.org/project/gpxpy/ (HIGH confidence)
- Leaflet.js 1.9.4 stable vs 2.0.0-alpha: https://leafletjs.com/download.html (HIGH confidence — official docs)
- Alpine.js 3.15.8 CDN: https://alpinejs.dev/ + https://www.jsdelivr.com/package/npm/alpinejs (HIGH confidence)
- httpx async vs requests: https://www.python-httpx.org/async/ (HIGH confidence — official docs)
- FastAPI background tasks pattern: https://fastapi.tiangolo.com/tutorial/background-tasks/ (HIGH confidence — official docs)
- FastAPI SSE Nginx buffering: https://fastapi.tiangolo.com/tutorial/server-sent-events/ (HIGH confidence — X-Accel-Buffering handled automatically)
- Nginx + systemd + Raspberry Pi service pattern: https://miltschek.de/article_2023-10-21_nginx+++Uvicorn+++FastAPI+++systemd.html (MEDIUM confidence — blog, aligns with official patterns)
