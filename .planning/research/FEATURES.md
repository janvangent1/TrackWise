# Feature Landscape: TrackWise Web

**Domain:** Web-based GPX route POI finder / waypoint enrichment tool
**Researched:** 2026-03-09
**Confidence:** MEDIUM-HIGH (competitive tools inspected directly, UX patterns from authoritative sources)

---

## Competitive Landscape Context

Tools surveyed: POI Ahead (poi-ahead.fly.dev), gpx.studio, GPX-POI Waypoint Generator, Ride with GPS POI system, GPS Geoplaner. TrackWise is closest to POI Ahead in scope but adds road-deviation routing (OSRM) and GPX enrichment export, which most competitors lack.

---

## Table Stakes

Features users expect. Missing = product feels broken or incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| GPX file upload (click or drag-and-drop) | Every GPX tool starts here; no upload = no tool | Low | Drop zone + click fallback both required; dashed border, hover highlight, file type validation (.gpx only) |
| Visible progress during search | Overpass + OSRM calls take 10-60s; silence = user thinks it crashed | Low-Med | SSE stream is the right pattern (simpler than WebSocket for one-directional); show per-type step messages |
| Interactive Leaflet map showing route | Users need spatial orientation of results | Med | GPX polyline in blue; tile layer (OpenStreetMap default); fit-to-bounds on load |
| POI markers on map with popups | Primary output of the tool | Med | Colored by type; popup shows name, type, distance from route; click to select |
| Results list of found places | Spatial+tabular views are complementary; power users scan the list | Med | Shows name, type, distance-from-route, deviation distance; checkbox per row for include/exclude |
| Per-type on/off toggles | Users want petrol but not cafes on one trip | Low | 7 type checkboxes mirroring original app |
| Per-type distance threshold | Route context varies (motorway vs country lane) | Low | Number input in km per type; sensible defaults (e.g. 0.5 km petrol, 1.0 km accommodation) |
| GPX download of selected waypoints | The entire point of the tool | Low | Browser download via `<a download>` link or Blob URL; no confirmation dialog needed |
| Stop/cancel running search | Slow API calls; users change their mind | Low | Abort SSE + cancel backend task; button visible only while running |
| Error messages on API failure | Overpass rate-limits; OSRM can timeout | Low | Inline message in log, not modal; show which type failed and why |

---

## Differentiators

Features that set TrackWise apart from typical GPX/POI tools. Not expected, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Road-deviation routing per POI (OSRM) | Competitors (POI Ahead, GPX-POI) give crow-fly distance only; TrackWise shows actual road detour distance | High | Already in desktop app; must be preserved; this is the key differentiator for motorbike/cycle trip planning |
| GPX export with "enhanced track + deviations" mode | Embeds the detour routes into the GPX as route segments, not just waypoints | High | Two-mode export: waypoints-only vs enhanced track; rare in competitors |
| Per-place include/exclude toggle (not just type-level) | Users may want the Shell station but not the BP 2km further | Low | Checkbox per row; map marker visual state updates on toggle |
| Bidirectional map/list sync | Clicking a list row highlights its marker and vice versa | Med | Pattern: data-id on row + Leaflet marker ID; openOn for auto-close of previous popup |
| Search radius shown as corridor on map | Visualizes the actual search band around the route; builds trust in results | Med | Leaflet L.Polygon or buffer visualization using Turf.js or shapely-generated GeoJSON from backend |
| Log panel with per-API-call detail | Power users (motorbike planners) want to understand what was queried and how many results came back | Low | Text area or console-style div; shows "Querying petrol stations (0.5km)... 12 found" |
| Windows tkinter launcher for Pi server | No other tool in this class ships a desktop launcher; covers the power-user / self-hoster persona | Med | See launcher section below |

---

## Anti-Features

Features to explicitly NOT build. Each one is a distraction from the core value or creates maintenance burden.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| User accounts / login | Single-user local tool; auth adds weeks of work and a permanent attack surface | Rely on network access control (LAN-only or VPN) |
| Persistent search history / database | Stateless is simpler; Pi has limited storage; sessions are short | Use temp files cleaned on session end |
| Route creation / editing in-browser | gpx.studio already does this better; TrackWise is an enrichment tool, not a route builder | Accept GPX from any tool (Komoot, Garmin Connect, etc.) |
| Mobile-native app (iOS/Android) | Responsive web is sufficient for the use case; upload+view works fine on mobile browser | Ensure responsive layout with Tailwind or CSS media queries |
| Real-time collaboration / sharing | Out of scope; adds WebSocket complexity and state management | Single session per search |
| Multiple concurrent searches | Pi RAM is limited; one active search at a time is the design | Clear/reset UI before starting a new search; disable start button while running |
| Offline mode / local Overpass instance | Full planet Overpass requires 64GB+ RAM; not viable on Pi | Document the external API dependency clearly |
| In-app route export to Garmin Connect / Komoot | Integration maintenance is high; GPX is the universal format | Ship GPX, let users import it wherever they want |
| Elevation profile chart | Nice-to-have but unrelated to POI finding; adds a charting library dependency | Defer; gpx.studio already shows elevation |
| Place details / photos (Google Maps-style) | Requires paid API (Google Places) or scraping; overpass gives names only | Show OSM name, type, coordinates — sufficient for waypoint planning |
| Drag-to-reorder waypoints | GPX devices handle ordering; users won't reorder 30 waypoints in a browser | Order by distance along route (already the natural order) |

---

## Feature Dependencies

```
GPX upload
  → Route parsed to lat/lon track points
    → Per-type Overpass queries (requires: type toggles + distance config)
      → OSRM deviation routing per found place
        → Results list rendered (requires: places data)
          → Map markers rendered (requires: places data + route polyline)
            → Per-place include/exclude toggle (requires: results list)
              → GPX download (requires: include/exclude state + export mode selection)

SSE progress stream runs parallel to all backend steps above.
Stop button cancels at any step.
```

---

## UX Patterns: Specific Implementation Guidance

### File Upload

**Pattern:** Combined drop zone + click-to-browse. Drop zone is the dominant element (large, centered on empty state). Once a file is loaded, the drop zone collapses or moves to a secondary "replace file" link.

- Dashed border, icon (map/route), label "Drop your GPX file here or click to browse"
- On hover/dragover: change border to solid, lighten background (100ms CSS transition)
- On drop: validate extension (.gpx), show filename + file size badge, enable config panel
- On invalid file type: inline error "Only .gpx files are supported" — no modal
- Alpine.js `x-on:drop` + `x-on:dragover.prevent` handles this with ~20 lines of JS

### Real-Time Progress Display

**Pattern:** SSE stream from `/api/search/stream/{session_id}`. Log console div + progress bar.

- Log console: fixed-height scrolling div, monospace font, auto-scrolls to bottom
- Each SSE event has `type` (step_start | step_done | place_found | error | complete) and `message`
- Progress bar: determinate (percent complete) if step count is known; indeterminate spinner while waiting for first event
- "Cancel" button replaces "Start Search" during run; re-enables after complete or cancel
- On complete: scroll log to bottom, show "Search complete — N places found" banner
- Do NOT use a modal for progress — inline display keeps context visible

### Results Table

**Pattern:** Inline table below the map, not a sidebar (sidebars compete with map real estate on small screens).

- Columns: checkbox | name | type (icon + label) | dist from route (km) | deviation (km) | actions
- Default sort: distance along route (position on the route, not distance from start)
- Column sort: click header toggles asc/desc; show sort arrow
- Type filter: button group above table (one button per POI type, active = highlighted); "All" button
- "Select All" / "Deselect All" row above table
- Row click: opens popup on corresponding map marker (bidirectional sync via shared ID)
- Row hover: map marker briefly pulses or increases zIndex (CSS class swap)
- Checkbox change: immediately updates GPX download to include/exclude that place
- Keep table simple — no pagination (typical result set is 20-100 places, not thousands)

### Leaflet Map

**Pattern:** Full-width map, fixed height (60vh on desktop, 40vh on mobile), tiles from OpenStreetMap.

- Route polyline: blue (#3B82F6), weight 3, opacity 0.8
- POI markers: colored circle markers by type (use a consistent color map matching the type buttons)
- Active/selected marker: enlarged, different color halo (CSS class + `setIcon`)
- Marker click: opens popup with name + type + distances; highlights corresponding table row (scroll into view)
- Map fit to route bounds on GPX load; "Reset view" button for when user has panned away
- Tile provider: OpenStreetMap default (free, no API key); cycling tiles (OpenCycleMap) as optional overlay — toggle in map controls
- Do NOT use Mapbox or Google Maps tiles — they require API keys and billing

### GPX Download

**Pattern:** Single "Download GPX" button, always visible once results exist. No confirmation dialog.

- Two radio options above the button: "Waypoints only" | "Enhanced track with deviations" (default: waypoints only)
- Filename: `trackwise-[original-filename-without-ext]-[timestamp].gpx`
- Implementation: backend `/api/export` endpoint returns GPX bytes; `Content-Disposition: attachment`; browser handles the download natively
- Show count badge on button: "Download GPX (14 places)" to reflect current include/exclude state
- Button disabled while search is in progress

---

## Windows Tkinter Launcher: Feature Specification

The launcher is a developer/power-user tool for managing the Pi server from a Windows PC. It bridges the gap for non-technical users who don't want to SSH manually.

### Must Have

| Feature | Why | Implementation |
|---------|-----|----------------|
| SSH connection config panel | Pi IP/hostname, port, username, SSH key or password | Paramiko SSHClient; store config in `~/.trackwise/config.json` |
| Start Server button | Sends `systemctl start trackwise` over SSH | `ssh.exec_command("sudo systemctl start trackwise")` |
| Stop Server button | Sends `systemctl stop trackwise` over SSH | Same pattern |
| Server status indicator | Green/grey dot; reads `systemctl is-active trackwise` | Poll every 10s via background thread; `after()` to update UI |
| Open in Browser button | Opens `http://{pi_host}/` in default Windows browser | `webbrowser.open(url)` |
| Log console | Shows stdout/stderr of SSH commands + launcher events | Text widget, auto-scroll, timestamped lines |
| Connection test button | Verify SSH credentials before attempting server operations | Executes `echo ping` over SSH; green/red indicator |

### Should Have

| Feature | Why | Implementation |
|---------|-----|----------------|
| Auto-reconnect on connection loss | Pi may reboot | Catch Paramiko exceptions; retry with backoff |
| Restart Server button | Convenience; faster than stop+start | `systemctl restart trackwise` |
| Show Pi system stats | CPU%, RAM%, disk — useful for Pi 1-2GB models | `top -bn1` or `free -m` over SSH; parse and display |
| Remember last config | Users don't want to re-enter Pi IP every time | `config.json` on first run; auto-load on startup |
| Copy Pi URL to clipboard | Share the URL with other LAN devices | `pyperclip.copy(url)` or `root.clipboard_append(url)` |

### Explicitly Avoid in Launcher

| Anti-Feature | Why |
|--------------|-----|
| File manager / SFTP browser | Out of scope; use FileZilla or WinSCP |
| Log viewer for Pi application logs | SSH to tail logs is error-prone; the web app's own log panel is the right place |
| Auto-deploy / update mechanism | Git pull over SSH is fragile; separate deployment concern |
| CustomTkinter or third-party themes | Adds a non-stdlib dependency; plain ttk is sufficient for a utility tool |
| System tray / minimize-to-tray | Adds complexity; this is a launch-and-monitor tool, not always-on daemon |

---

## MVP Recommendation

For the initial web conversion milestone, prioritize strictly what the desktop app already does:

**Phase 1 MVP (feature parity with desktop):**
1. GPX upload (drag-drop + click)
2. Type toggles + distance config (7 types, matching original)
3. SSE progress log
4. Overpass search + OSRM deviation routing (backend port)
5. Results table with per-place checkboxes
6. Leaflet map with route + POI markers
7. GPX download (waypoints-only mode)
8. Stop/cancel

**Phase 2 (web-native improvements):**
1. Bidirectional map/list sync (click row = highlight marker)
2. Type filter buttons on results table
3. Enhanced track with deviations export mode
4. Windows tkinter launcher (separate sub-project)

**Defer indefinitely:**
- Search corridor visualization on map (nice-to-have, add complexity)
- Cycling tile overlay (low demand for motorbike primary use case)
- Pi system stats in launcher

---

## Sources

- POI Ahead (direct inspection): https://poi-ahead.fly.dev/
- gpx.studio POI documentation: https://gpx.studio/help/toolbar/poi
- Ride with GPS POI system: https://support.ridewithgps.com/hc/en-us/articles/4419004424219-Points-of-Interest-POI
- Leaflet.js documentation: https://leafletjs.com/reference.html
- Leaflet sidebar sync pattern (community): https://groups.google.com/g/leaflet-js/c/4cRQTLPjqvo
- SSE for long-running tasks: https://medium.com/@jyotsna.a.choudhary/dealing-with-long-running-tasks-in-web-apps-the-sse-approach-ba8607638335
- Drag-and-drop UX best practices: https://uploadcare.com/blog/file-uploader-ux-best-practices/
- Data table UX best practices: https://uxplanet.org/best-practices-for-usable-and-efficient-data-table-in-applications-4a1d1fb29550
- Checkbox vs toggle guidance: https://www.eleken.co/blog-posts/checkbox-ux
- Paramiko + tkinter server monitoring: https://github.com/Soulaimaneelhourre/Server-Monitoring
- Paramiko SSH guide: https://www.linode.com/docs/guides/use-paramiko-python-to-ssh-into-a-server/
