# Requirements: TrackWise Web

**Project:** TrackWise Web
**Version:** 1.0
**Status:** COMPLETE — all v1 requirements implemented
**Last updated:** 2026-03-09

---

## Requirement Status Legend

- [x] COMPLETE — implemented and working
- [ ] PENDING — not yet implemented
- [~] PARTIAL — partially implemented
- [DEFERRED] — moved to v2+

---

## Functional Requirements

### F1 — File Ingestion

| ID | Requirement | Status | Notes |
|----|-------------|--------|-------|
| F1.1 | User can upload a GPX file via web browser | [x] COMPLETE | Implemented in frontend upload form |
| F1.2 | Upload supports drag-and-drop onto a drop zone | [x] COMPLETE | Alpine.js `x-on:drop` handler |
| F1.3 | Upload supports click-to-browse file picker | [x] COMPLETE | Hidden `<input type="file">` triggered by click |
| F1.4 | Only `.gpx` files are accepted; invalid types show inline error | [x] COMPLETE | Client-side extension validation |
| F1.5 | Uploaded filename and file size are displayed after selection | [x] COMPLETE | Shown in upload zone after drop/select |
| F1.6 | GPX file is parsed server-side using gpxpy | [x] COMPLETE | `gpx_parser.py` extracted from monolith |
| F1.7 | Old desktop app files are preserved in `/old/` subfolder | [x] COMPLETE | Phase 1 file reorganization |

### F2 — Search Configuration

| ID | Requirement | Status | Notes |
|----|-------------|--------|-------|
| F2.1 | User can enable/disable each of 7 POI types: petrol, supermarkets, bakeries, cafes, repair shops, accommodation, speed cameras | [x] COMPLETE | Per-type checkboxes in config panel |
| F2.2 | User can set a per-type distance threshold in km | [x] COMPLETE | Number inputs with sensible defaults |
| F2.3 | Search config is submitted alongside the GPX file upload | [x] COMPLETE | JSON string in multipart form body |
| F2.4 | Sensible defaults are pre-populated (e.g. 0.5 km petrol, 1.0 km accommodation) | [x] COMPLETE | Hardcoded defaults in Alpine.js `x-data` |

### F3 — Search Execution

| ID | Requirement | Status | Notes |
|----|-------------|--------|-------|
| F3.1 | Backend performs Overpass API queries for each enabled POI type along the route | [x] COMPLETE | `overpass.py` service |
| F3.2 | Route is segmented for large GPX files to avoid Overpass bounding box limits | [x] COMPLETE | Segment chunking in `search.py` |
| F3.3 | Overpass concurrency is limited to 2 parallel requests (Semaphore or ThreadPoolExecutor max_workers=2) | [x] COMPLETE | Prevents Overpass 429 rate limit errors |
| F3.4 | Backend performs OSRM road routing deviation calculation for each found place | [x] COMPLETE | `osrm.py` service |
| F3.5 | Search can be cancelled by the user while running | [x] COMPLETE | Cancel button; `threading.Event` checked at loop boundaries |
| F3.6 | Search state is scoped to a per-session job ID (UUID) to prevent cross-request state pollution | [x] COMPLETE | Job-keyed in-memory state |

### F4 — Real-Time Progress

| ID | Requirement | Status | Notes |
|----|-------------|--------|-------|
| F4.1 | User sees real-time progress updates during search via SSE stream | [x] COMPLETE | `app.py` SSE endpoint |
| F4.2 | Progress includes per-type step messages (e.g. "Querying petrol stations... 12 found") | [x] COMPLETE | Structured SSE event types |
| F4.3 | SSE stream ends with an explicit done/complete sentinel event | [x] COMPLETE | `eventSource.close()` called on done event |
| F4.4 | SSE stream sends heartbeat events to prevent proxy timeouts | [x] COMPLETE | 1-second `wait_for` timeout yields heartbeat |
| F4.5 | Server cancels the backing search task when the SSE client disconnects | [x] COMPLETE | `cancel_event` set on disconnect detection |
| F4.6 | Log panel displays per-API-call detail in a scrolling console | [x] COMPLETE | Fixed-height scrolling div, auto-scrolls |

### F5 — Results Display

| ID | Requirement | Status | Notes |
|----|-------------|--------|-------|
| F5.1 | User sees found places in a results table | [x] COMPLETE | HTML table with Alpine.js binding |
| F5.2 | Results table shows: name, type, distance from route, road deviation distance | [x] COMPLETE | Matches desktop app output columns |
| F5.3 | Results table supports sorting by clicking column headers | [x] COMPLETE | Alpine.js sort state |
| F5.4 | Results table supports filtering by POI type | [x] COMPLETE | Type filter button group above table |
| F5.5 | Each result row has a checkbox for include/exclude in GPX export | [x] COMPLETE | Per-row checkbox with Alpine.js binding |
| F5.6 | Select All / Deselect All controls are provided above the table | [x] COMPLETE | Bulk selection buttons |
| F5.7 | Results are ordered by position along the route (not by distance from start) | [x] COMPLETE | Natural route order from `search.py` |

### F6 — Interactive Map

| ID | Requirement | Status | Notes |
|----|-------------|--------|-------|
| F6.1 | User sees an interactive Leaflet.js map with the uploaded route as a polyline | [x] COMPLETE | Blue polyline, weight 3 |
| F6.2 | Map shows POI markers colored by type | [x] COMPLETE | Consistent color map matching type buttons |
| F6.3 | Clicking a POI marker opens a popup with name, type, and distances | [x] COMPLETE | Leaflet popup |
| F6.4 | Map auto-fits to route bounds on GPX load | [x] COMPLETE | `map.fitBounds()` on route parse |
| F6.5 | Map uses OpenStreetMap tiles (no API key required) | [x] COMPLETE | Standard OSM tile URL |
| F6.6 | Clicking a result table row highlights the corresponding map marker | [x] COMPLETE | Bidirectional sync via shared place ID |
| F6.7 | Clicking a map marker highlights the corresponding table row and scrolls it into view | [x] COMPLETE | Bidirectional sync |
| F6.8 | Toggling a place's checkbox updates marker visual state on the map | [x] COMPLETE | CSS class swap on marker icon |
| F6.9 | "Reset view" button restores map bounds to the route extent | [x] COMPLETE | `map.fitBounds()` on button click |

### F7 — GPX Export

| ID | Requirement | Status | Notes |
|----|-------------|--------|-------|
| F7.1 | User can download a GPX file containing the selected (checked) waypoints | [x] COMPLETE | `/api/gpx/export` endpoint |
| F7.2 | GPX is generated server-side by `gpx_writer.py` using gpxpy | [x] COMPLETE | Extracted from monolith |
| F7.3 | Export respects per-place include/exclude checkbox state | [x] COMPLETE | Selected IDs sent in export request |
| F7.4 | Downloaded filename includes original GPX name and timestamp | [x] COMPLETE | `trackwise-[name]-[timestamp].gpx` pattern |
| F7.5 | Download button shows count of currently selected places | [x] COMPLETE | Badge: "Download GPX (N places)" |
| F7.6 | Download button is disabled while a search is in progress | [x] COMPLETE | Alpine.js `x-bind:disabled` |

### F8 — Web Server (Raspberry Pi)

| ID | Requirement | Status | Notes |
|----|-------------|--------|-------|
| F8.1 | Application runs as a FastAPI web server managed by Uvicorn | [x] COMPLETE | `app.py` |
| F8.2 | Nginx is configured as a reverse proxy in front of Uvicorn | [x] COMPLETE | `trackwise.nginx.conf` |
| F8.3 | Nginx serves static files (HTML/CSS/JS) directly without Python overhead | [x] COMPLETE | `/static/` location with `alias` directive |
| F8.4 | Nginx SSE location has `proxy_buffering off` and `X-Accel-Buffering: no` | [x] COMPLETE | Required for real-time SSE through proxy |
| F8.5 | Application runs as a systemd service with auto-start on boot | [x] COMPLETE | `trackwise.service` |
| F8.6 | Systemd service restarts automatically on crash | [x] COMPLETE | `Restart=on-failure` |
| F8.7 | Installation script `setup_pi.sh` automates dependency install and service setup | [x] COMPLETE | Raspberry Pi deployment phase |
| F8.8 | Temporary GPX files are cleaned up automatically (per-session and on startup) | [x] COMPLETE | Background cleanup task in `lifespan` handler |
| F8.9 | Single Uvicorn worker (in-memory job state cannot be shared across workers) | [x] COMPLETE | `--workers 1` in systemd unit |

### F9 — Windows Launcher

| ID | Requirement | Status | Notes |
|----|-------------|--------|-------|
| F9.1 | Developer/user can launch and manage the web server from a tkinter GUI on Windows | [x] COMPLETE | `launcher.py` |
| F9.2 | Launcher has a Start Server button | [x] COMPLETE | Spawns Uvicorn subprocess |
| F9.3 | Launcher has a Stop Server button | [x] COMPLETE | Terminates Uvicorn subprocess |
| F9.4 | Launcher has an Open Browser button | [x] COMPLETE | `webbrowser.open('http://localhost:8000')` |
| F9.5 | Launcher has an Install (dependencies) button | [x] COMPLETE | Runs `pip install -r requirements.txt` |
| F9.6 | Launcher shows a log console with server stdout/stderr | [x] COMPLETE | `ScrolledText` widget fed by background thread |
| F9.7 | Launcher cleans up the server process when the window is closed | [x] COMPLETE | `WM_DELETE_WINDOW` protocol handler |

---

## Non-Functional Requirements

| ID | Requirement | Status | Notes |
|----|-------------|--------|-------|
| NF1 | Frontend requires no build step — plain HTML, CDN JS/CSS only | [x] COMPLETE | No npm, no webpack, no node_modules |
| NF2 | Backend runs on Raspberry Pi 4 (ARMv7/ARM64, 2-4GB RAM) | [x] COMPLETE | All dependencies have piwheels ARM wheels |
| NF3 | No user authentication — single-user local tool | [x] COMPLETE | Network access control via LAN/VPN |
| NF4 | No persistent database — stateless, temp files only | [x] COMPLETE | In-memory job state; files in `/tmp/trackwise/` |
| NF5 | Responsive layout works on mobile browser | [x] COMPLETE | CSS media queries |
| NF6 | All Overpass and OSRM API calls remain functionally identical to original app | [x] COMPLETE | Extracted unchanged from monolith |
| NF7 | Original desktop app is preserved and runnable from `/old/` | [x] COMPLETE | Phase 1 file reorganization |
| NF8 | CDN URLs pinned to exact versions (no `@latest`) | [x] COMPLETE | Leaflet 1.9.4, Alpine.js 3.15.8 |

---

## Out of Scope (v2+ or never)

| Feature | Decision |
|---------|---------|
| User authentication / multi-user accounts | Never — single-user local tool; auth adds attack surface |
| Persistent search history / database | Never — stateless is simpler; Pi has limited storage |
| Route creation / editing in-browser | Never — TrackWise is an enrichment tool, not a route builder |
| Mobile native app (iOS/Android) | Never — responsive web is sufficient |
| Real-time collaboration | Never — out of scope for personal tool |
| Multiple concurrent searches | Never — Pi RAM constraint; one search at a time |
| Offline mode / local Overpass instance | Never — requires 64GB+ RAM for full planet data |
| Enhanced track with deviations GPX export | v2 — deviations embedded as route segments, not just waypoints |
| Search corridor visualization on map | v2 — nice-to-have; adds Shapely GeoJSON backend work |
| Cycling tile overlay (OpenCycleMap) | v2 — low demand for primary motorbike use case |
| SSH-based Pi management in launcher | v2 — current launcher uses local subprocess only |
| Pi system stats in launcher (CPU, RAM, disk) | v2 — useful on Pi 1/2 models with limited RAM |
| Elevation profile chart | v2 — gpx.studio already covers this |

---

## Dependency Summary

### Python (backend)

```
fastapi==0.135.1
uvicorn==0.41.0
python-multipart==0.0.22
aiofiles==25.1.0
httpx==0.28.1
gpxpy==1.6.2
geopy==2.4.1
shapely==2.1.2
```

### Frontend (CDN, no install)

```
Leaflet.js 1.9.4   — https://unpkg.com/leaflet@1.9.4/dist/leaflet.js
Alpine.js 3.15.8   — https://cdn.jsdelivr.net/npm/alpinejs@3.15.8/dist/cdn.min.js
```

### System (Raspberry Pi)

```
nginx       — apt (Bookworm repo, 1.24.x)
libgeos-dev — apt (required before pip install shapely)
python3.11-venv — apt
```
