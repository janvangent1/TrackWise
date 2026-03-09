# TrackWise Web

## What This Is

TrackWise Web is a migration of a desktop Python/tkinter GPX waypoint finder application to a full web-based system hosted on a Raspberry Pi. Users upload a GPX route file, configure which types of points-of-interest to search for (petrol stations, supermarkets, bakeries, cafes, repair shops, accommodation, speed cameras) and at what distances, and the app queries OpenStreetMap (Overpass API) + OSRM road routing to return an interactive map and downloadable enhanced GPX file with waypoints.

## Core Value

Any device on the local network (or internet) can plan a motorcycle/cycling route by uploading a GPX file and getting back an enriched GPX with waypoints — no software installation required.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] User can upload a GPX file via web browser
- [ ] User can configure search types (petrol, supermarkets, bakeries, cafes, repair shops, accommodation, speed cameras) with per-type distance thresholds
- [ ] Backend performs Overpass API queries for each enabled place type along the route
- [ ] Backend performs OSRM road routing for each found place
- [ ] User sees real-time progress updates during search (SSE stream)
- [ ] User sees found places in a sortable/filterable results table
- [ ] User sees an interactive Leaflet.js map with the route and found places
- [ ] User can toggle individual places on/off for GPX inclusion
- [ ] User can download an enhanced GPX file containing selected waypoints
- [ ] Application runs as a web server on Raspberry Pi (FastAPI + Uvicorn + Nginx)
- [ ] Developer/user can launch and manage the web server from a Python tkinter GUI launcher on Windows PC
- [ ] GUI launcher has Start Server, Stop Server, Open Browser buttons and a log console
- [ ] Old desktop app files are preserved in an `/old/` subfolder
- [ ] New web app lives in a `/web/` subfolder

### Out of Scope

- User authentication / multi-user accounts — single-user local tool
- Database persistence of past searches — stateless, temp files only
- Mobile native app — responsive web is sufficient
- Real-time collaboration — single session per search
- Offline mode — requires external Overpass/OSRM APIs

## Context

- **Original app**: `main_gui_enhanced.py` — monolithic tkinter GUI, ~1200 lines
- **External APIs**: Overpass API (OpenStreetMap) for POI search, OSRM for road routing — both free, no auth required
- **Core libraries**: gpxpy, geopy, shapely, requests, folium — all remain in web backend
- **Map rendering**: Currently folium (generates HTML) + matplotlib (embedded in tkinter). Web version uses Leaflet.js natively
- **Concurrency**: Current app uses `ThreadPoolExecutor` for parallel API calls — keep this pattern in FastAPI background tasks
- **Platform**: Deploy target is Raspberry Pi OS (Debian-based Linux); development on Windows 11

## Constraints

- **Tech Stack**: Python backend (FastAPI) — reuse existing gpxpy/geopy/shapely/requests code
- **Frontend**: No build step — plain HTML + Alpine.js CDN + Leaflet.js CDN (must work without npm/webpack on Pi)
- **Raspberry Pi**: Limited RAM (~1-4GB) — keep backend lean, no heavy frameworks
- **No breaking changes to APIs**: Overpass and OSRM API calls must remain functionally identical to original
- **Windows launcher**: Must be runnable on Windows without installing server software locally

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| FastAPI over Flask | Async support, built-in SSE streaming, better type safety | — Pending |
| Alpine.js over Vue/React | No build step, tiny footprint, sufficient reactivity | — Pending |
| Leaflet.js for maps | Best-in-class open source maps, replaces folium dependency on frontend | — Pending |
| SSE over WebSocket | One-directional progress stream — SSE is simpler and sufficient | — Pending |
| Nginx on Pi | Standard reverse proxy, handles static files, low RAM | — Pending |
| `/old/` + `/web/` folder split | Clean separation, preserves original for reference | — Pending |

---
*Last updated: 2026-03-09 after initialization*
