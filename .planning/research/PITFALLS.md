# Domain Pitfalls

**Domain:** FastAPI web app with SSE streaming, long-running API tasks, Raspberry Pi deployment, tkinter launcher, Alpine.js + Leaflet.js frontend
**Project:** TrackWise Web
**Researched:** 2026-03-09
**Confidence:** HIGH (all pitfalls verified via official docs or multiple corroborating sources)

---

## Critical Pitfalls

Mistakes that cause rewrites, data loss, or silently broken behavior.

---

### Pitfall 1: FastAPI BackgroundTasks Is the Wrong Tool for Long-Running Jobs

**What goes wrong:**
`FastAPI.BackgroundTasks` was designed for lightweight post-response work (email, logging). When used for Overpass API queries + OSRM routing across 100+ GPX waypoints — a task that can run for several minutes — it ties up the server worker thread, blocks other incoming requests, and provides no way to report progress to the SSE stream without a separate communication channel.

**Why it happens:**
Developers see `BackgroundTasks` in FastAPI's tutorial and assume it handles all background work. The documentation is clear that it is not for long-running or CPU-heavy tasks, but the distinction is easy to miss.

**Consequences:**
- Other HTTP requests (e.g., SSE `/stream` endpoint) queue behind the running task
- No retry on failure — exceptions silently disappear
- Progress cannot be communicated back to the SSE stream without an in-process queue

**Prevention:**
Use `asyncio.Queue` as the communication channel between task and SSE stream. Run the actual blocking work (requests calls to Overpass/OSRM) via `asyncio.to_thread()` or `loop.run_in_executor(ThreadPoolExecutor)`. The correct pattern:
1. POST `/search` creates a per-session `asyncio.Queue` and launches `asyncio.create_task(run_search(queue))`
2. GET `/stream` is an SSE endpoint that `async for item in queue` yields as events
3. The background coroutine pushes progress strings and the final result into the queue, then pushes a sentinel to signal completion

**Warning signs:**
- SSE endpoint returns no data until the search completes
- `/docs` or health check hangs during a search
- Exceptions from search tasks produce no error output

**Phase:** Phase 1 (core backend architecture). Must be decided before any task code is written.

---

### Pitfall 2: SSE Stream Silently Stops — No End Sentinel, No Client Reconnect Guard

**What goes wrong:**
Without an explicit "done" sentinel message, the browser's `EventSource` keeps the connection open forever after the search finishes, waiting for more data. When the client disconnects and reconnects (network hiccup, page reload), a new SSE connection is opened but the old `asyncio.Queue` is orphaned in memory — the new connection has no reference to the running task. On the next search submission the user gets stale events or no events.

**Why it happens:**
SSE connections are long-lived HTTP responses. FastAPI's generator does not know when the client has gone unless it catches `asyncio.CancelledError` on the `await queue.get()`. Without this the coroutine leaks.

**Consequences:**
- Orphaned queues accumulate memory on the Pi
- Client browser reconnects but receives no progress
- Task appears "stuck" from the user's perspective

**Prevention:**
- Always end the SSE generator with a `data: done\n\n` message so the client calls `eventSource.close()`
- Wrap `await queue.get()` in a `try/except asyncio.CancelledError` block; on cancellation, cancel the background search task too
- Give each search a UUID session token; store `{session_id: (queue, task)}` in a module-level dict; the SSE endpoint looks up by session ID
- On the frontend: call `eventSource.close()` explicitly when the `done` event arrives, and do not auto-reconnect after `done`

**Warning signs:**
- Browser DevTools shows the SSE connection never closes
- Repeated searches accumulate RAM on the Pi (`htop` shows growing RSS)
- After a page reload mid-search, no progress events appear

**Phase:** Phase 1 (SSE infrastructure). Address alongside the queue pattern above.

---

### Pitfall 3: Nginx Buffers SSE Events — Stream Appears to Arrive in Batches

**What goes wrong:**
Nginx's default `proxy_buffering on` accumulates the proxied response body before forwarding it. For SSE this means events are held until the buffer (typically 16 KB) fills or a flush timeout triggers. The user sees no progress for the first minute of a search, then a flood of events arrives at once — defeating the entire purpose of streaming.

**Why it happens:**
Nginx is designed for high-throughput responses and buffers by default. SSE requires the opposite behavior: small chunks flushed immediately.

**Consequences:**
- Real-time progress updates appear delayed or batched
- User cannot tell if the search is running or stuck
- The "done" event arrives at the same time as all progress events

**Prevention:**
In the Nginx `location` block for the SSE endpoint, set:
```nginx
location /stream {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 3600s;
    gzip off;
    add_header X-Accel-Buffering no;
}
```
Alternatively (or additionally), have the FastAPI response set the header `X-Accel-Buffering: no` so Nginx respects it per-response. Also ensure `gzip` is off for the SSE endpoint — gzip requires buffering a complete chunk before compressing.

**Warning signs:**
- Events arrive in bursts rather than steadily
- In `curl -N http://pi/stream`, output appears delayed
- Works fine when testing directly against `uvicorn` (port 8000) but not through Nginx (port 80)

**Phase:** Phase 3 (Nginx deployment configuration). Write the Nginx config with buffering disabled from day one — do not add it as a hotfix after noticing the problem.

---

### Pitfall 4: ThreadPoolExecutor Blocking the asyncio Event Loop

**What goes wrong:**
The existing code uses `ThreadPoolExecutor` to parallelise Overpass + OSRM calls. If `executor.map()` or `executor.submit()` is called directly from an `async def` route or task (not wrapped in `await loop.run_in_executor()`), it does not block the thread but it does return a `Future` that is not an `asyncio.Future`. Awaiting it with `await asyncio.wrap_future()` or calling `result()` synchronously on it from async code will freeze the event loop for the duration of the call.

**Why it happens:**
`concurrent.futures.Future` and `asyncio.Future` are different objects. `concurrent.futures.Future.result()` is a blocking call — it should never be called from an async context.

**Consequences:**
- Event loop freezes during the entire Overpass query batch
- SSE heartbeat stops; browser may drop the connection
- Other API endpoints (health check, file download) become unresponsive

**Prevention:**
- Use `await asyncio.to_thread(blocking_fn, *args)` (Python 3.9+) for each individual blocking call — this is the simplest correct pattern
- Or: `loop = asyncio.get_event_loop(); await loop.run_in_executor(executor, fn, *args)` — never call `.result()` on the returned future synchronously
- To preserve parallelism: `results = await asyncio.gather(*[asyncio.to_thread(query, wp) for wp in waypoints])`
- Never call `requests.get(...)` directly in an `async def` without wrapping it

**Warning signs:**
- `PYTHONASYNCIODEBUG=1` shows "Executing <Task> took X.XXX seconds" warnings (threshold: 0.1s)
- SSE stream stops delivering heartbeats during the search
- `uvicorn` logs show no incoming requests during the search window

**Phase:** Phase 1 (porting the existing ThreadPoolExecutor code). Audit every `requests.` call in the migrated code.

---

### Pitfall 5: Overpass API 429 Errors From Concurrent Requests

**What goes wrong:**
The existing app fires multiple concurrent Overpass queries (one per POI type × waypoint). The Overpass public API (`overpass-api.de`) enforces per-IP slot limits: each running query occupies a slot for its execution time plus a cool-down period proportional to load. Firing 7 POI types × 50+ waypoints simultaneously exhausts available slots immediately, resulting in HTTP 429 responses. The API does not include a reliable `Retry-After` header in all cases; requests that fail to get a slot within 15 seconds are simply discarded.

**Why it happens:**
The `ThreadPoolExecutor` pattern that works fine for OSRM (self-hosted, no rate limits) is applied unchanged to Overpass. OSRM and Overpass have completely different concurrency tolerances.

**Consequences:**
- Large GPX files fail silently — all queries after the first few return empty results
- No waypoints added to the output GPX, user gets a blank map
- The Pi's IP may be temporarily banned from the public Overpass instance

**Prevention:**
- Check `https://overpass-api.de/api/status` before starting batch queries: parse available slots and wait if 0 are free
- Limit concurrency: use `asyncio.Semaphore(2)` to allow at most 2 parallel Overpass requests
- Implement exponential backoff on 429: start with 10s wait, double up to 60s, max 3 retries
- Consider batching: combine multiple POI-type queries for a waypoint into one Overpass QL query using `union` — reduces total request count by up to 7×
- Use the `[timeout:60]` directive in the query string so the Overpass server enforces a per-query timeout instead of holding a slot indefinitely

**Warning signs:**
- Search returns 0 results for all POI types but GPX parses correctly
- HTTP 429 in the uvicorn log during search
- Increasing failure rate as GPX file size grows

**Phase:** Phase 2 (Overpass query layer). The concurrency control and batching strategy must be designed before porting the query code, not retrofitted.

---

## Moderate Pitfalls

---

### Pitfall 6: Leaflet.js "Map Container Already Initialized" Error

**What goes wrong:**
Calling `L.map('map-container')` a second time on the same `<div>` throws `Error: Map container is already initialized`. This happens when: (a) the user submits a second search without a page reload, (b) Alpine.js re-renders the DOM section containing the map div (x-if toggling), or (c) Leaflet.js is loaded twice.

**Why it happens:**
Leaflet sets `_leaflet_id` on the container DOM element on first initialization and checks for it on subsequent calls. Alpine.js's `x-if` removes and re-adds DOM elements, which resets the element but the JavaScript map instance may still exist in a variable.

**Prevention:**
- Store the map instance in a module-level variable: `let map = null`
- Before initializing: `if (map) { map.remove(); map = null; }`
- `map.remove()` destroys the Leaflet instance and clears `_leaflet_id` from the container
- Do not put the map container inside an Alpine.js `x-if` block — use `x-show` (hides with CSS, does not remove the DOM element)
- Initialize the map only once on page load; update it with `map.setView()` and layer manipulation for subsequent searches

**Warning signs:**
- Console error "Map container is already initialized" on second search
- Blank map on second search with no console error (orphaned instance still holds the container)

**Phase:** Phase 2 (frontend map integration).

---

### Pitfall 7: Alpine.js Reactive State Leaking Into Leaflet-Managed DOM

**What goes wrong:**
Alpine.js tracks DOM mutations within `x-data` scopes. If Alpine's reactive data properties (arrays of found places) are bound with `x-for` to elements inside or adjacent to the Leaflet map container, Alpine may attempt to reconcile the DOM at the same time Leaflet is adding/removing markers or tile layers. This can cause Alpine to remove Leaflet-injected elements or cause Leaflet events to fire on stale DOM nodes.

**Why it happens:**
Both Alpine.js and Leaflet.js mutate the DOM independently. Alpine's `x-for` replaces list items on array mutation. Leaflet adds `<svg>`, `<canvas>`, and `<img>` elements inside its container. If the container boundary is not clear, one library steps on the other.

**Prevention:**
- Strict DOM boundary: Leaflet owns `<div id="map">` and everything inside it. Alpine owns everything outside that div.
- Never put `x-data` or `x-for` directives on the map container or any ancestor that also contains Leaflet-managed children
- Use Alpine's `$store` for results data and bind it to a table/list element that is a sibling of the map div, not a parent or child
- Communicate from Alpine to Leaflet via explicit function calls (e.g., `addMarker(place)`) triggered by Alpine event handlers — not by shared reactive properties that Leaflet observes

**Warning signs:**
- Markers disappear after the results table updates
- Console errors about removed event listeners
- Tile layer re-renders every time the results array changes

**Phase:** Phase 2 (frontend integration). Design the DOM boundary before writing any frontend code.

---

### Pitfall 8: systemd Service Cannot Find uvicorn or Application Modules

**What goes wrong:**
The systemd unit file's `ExecStart` uses a bare `uvicorn` command or a relative path. When systemd starts the service it uses a minimal environment (no `PATH` additions from `.bashrc`, no virtualenv activation). The service fails with `exec: uvicorn: not found` or `ModuleNotFoundError` for the app's own packages.

**Why it happens:**
Systemd services do not inherit the user's shell environment. `ExecStart` does not run through a shell and does not support environment variable expansion in paths (e.g., `$HOME` is not expanded unless `Environment=HOME=/home/pi` is set explicitly).

**Prevention:**
- Use the absolute path to the virtualenv's uvicorn: `ExecStart=/home/pi/trackwise/venv/bin/uvicorn web.main:app --host 127.0.0.1 --port 8000`
- Set `WorkingDirectory=/home/pi/trackwise`
- Set `Environment=PYTHONPATH=/home/pi/trackwise` if needed for module resolution
- Set `User=pi` so the process runs with the correct file permissions
- Test with `systemd-run --unit=test-trackwise /home/pi/trackwise/venv/bin/uvicorn ...` before writing the unit file

**Warning signs:**
- `systemctl status trackwise` shows `code=exited, status=203/EXEC` or `status=1`
- `journalctl -u trackwise` shows "No such file or directory" on the ExecStart line
- Service starts fine when run manually as the pi user but fails under systemd

**Phase:** Phase 3 (Pi deployment).

---

### Pitfall 9: Temporary GPX Files Accumulate on Pi SD Card

**What goes wrong:**
Each search uploads a GPX file and generates an output GPX. If the cleanup path is never reached (exception mid-search, SSE client disconnects before download) the files accumulate. Raspberry Pi SD cards are typically 8–32 GB; a busy day of route planning could fill `/tmp` with large GPX files.

**Why it happens:**
Async cleanup code that runs "after the response is sent" may not execute if the client disconnects. `BackgroundTasks` cleanup after response is unreliable when the response itself is a long-lived SSE stream.

**Prevention:**
- Store temp files in a subdirectory: `/tmp/trackwise/{session_id}/`
- Schedule cleanup via `asyncio.create_task(cleanup_after_delay(session_id, delay=3600))` — runs 1 hour after creation regardless of client connection state
- On the SSE generator's `finally` block: delete the session's temp directory
- Add a startup cleanup task in the FastAPI `lifespan` handler: delete any `/tmp/trackwise/` directories older than 2 hours at server boot
- Monitor disk usage in the Pi health check endpoint

**Warning signs:**
- `df -h` on the Pi shows `/tmp` growing over time
- Old session directories visible in `/tmp/trackwise/`
- After a server restart, old temp files are not cleaned

**Phase:** Phase 2 (file handling). Implement cleanup from the first file-handling code, not as a later maintenance task.

---

### Pitfall 10: Windows tkinter Launcher Leaves Orphan uvicorn/SSH Processes

**What goes wrong:**
The tkinter launcher starts the web server via `subprocess.Popen`. When the launcher window is closed (via the X button, not the "Stop Server" button), the `Popen` object is garbage collected without `terminate()` being called. The child process continues running until Windows is rebooted. On subsequent launcher starts, a new server process is spawned on the same port, causing an "Address already in use" error.

**Why it happens:**
Python's `subprocess.Popen` does not automatically terminate children when the parent process exits. Windows does not have Unix's process group / session leader concept that would kill children automatically.

**Prevention:**
- Register a `tkinter` `protocol("WM_DELETE_WINDOW", on_close)` handler that calls `proc.terminate()` before destroying the window
- Also register `atexit.register(cleanup)` as a fallback for crash exits
- Use `subprocess.CREATE_NEW_PROCESS_GROUP` flag on Windows so a `CTRL_BREAK_EVENT` can be sent to the child's entire process group
- Before spawning a new server, check if the port is already in use with a `socket.connect` test; if so, warn the user
- Store the PID to a file (`~/.trackwise_launcher.pid`); on startup, check if that PID is still running and offer to kill it

**Warning signs:**
- "Address already in use" error on second launcher start without a Pi reboot
- `tasklist` / Task Manager shows multiple `python.exe` processes after repeated open/close cycles
- The "Stop Server" button has no effect after the launcher was force-closed

**Phase:** Phase 4 (Windows launcher). Address in the initial launcher implementation — very hard to retrofit reliably.

---

### Pitfall 11: CORS Blocks Requests During Local Development

**What goes wrong:**
During development the tkinter launcher opens a browser to `http://localhost:PORT` (or `http://RASPBERRY_PI_IP`) while the API runs on a different host or port. If FastAPI's `CORSMiddleware` is not configured, the browser blocks XHR / `EventSource` requests with a CORS error, but direct `curl` calls work fine — leading to confusion about whether the API is broken or the frontend is broken.

**Why it happens:**
`EventSource` and `fetch` requests from a browser page at origin `http://localhost:8080` to an API at `http://192.168.1.X:8000` are cross-origin. FastAPI has no CORS middleware by default.

**Prevention:**
- Add `CORSMiddleware` with explicit origins in development; do not use `allow_origins=["*"]` in production because SSE with credentials requires explicit origins
- Configure origins via environment variable so the same code works in dev and prod
- For the Nginx-proxied deployment, CORS is not needed if the frontend is served by the same Nginx instance (same origin); remove or restrict CORS middleware in production

**Warning signs:**
- Browser console shows "Access to fetch at X from origin Y has been blocked by CORS policy"
- API works in Postman / curl but not from the browser
- SSE `EventSource` never connects (no error shown unless DevTools Network tab is open)

**Phase:** Phase 1 (FastAPI setup). Add CORS middleware in the initial scaffold.

---

## Minor Pitfalls

---

### Pitfall 12: Raspberry Pi Cold Start / SD Card Corruption Risk

**What goes wrong:**
The Pi is powered off without a clean shutdown (power cut, user just unplugs it). The ext4 filesystem is not cleanly unmounted. On reboot, `fsck` runs and may fail or take minutes, delaying the web service start. In worst cases, the SD card is corrupted.

**Prevention:**
- Add a "Shutdown Pi" button to the tkinter launcher that SSH's to the Pi and runs `sudo shutdown -h now`
- Configure `systemd` service with `Restart=on-failure` and `RestartSec=5s` so it auto-recovers from transient boot issues
- Consider a read-only root filesystem for the Pi with a writable overlay for `/tmp` and `/var` — eliminates SD corruption risk at the cost of some setup complexity (defer to post-MVP)

**Phase:** Phase 3 (Pi deployment) and Phase 4 (launcher).

---

### Pitfall 13: Overpass Query Timeout for Routes Spanning Many Waypoints

**What goes wrong:**
A GPX file with 100+ waypoints generates Overpass queries covering a very large geographic bounding box. Overpass may timeout (HTTP 504 or query result truncated at `maxsize`) for queries that touch a large area with many POIs.

**Prevention:**
- Always include `[timeout:60][maxsize:536870912]` in the Overpass QL header
- Segment very long routes: break into chunks of 20–30 waypoints, query each chunk separately, merge results
- Use `(around:RADIUS;)` filters on a set of lat/lon points rather than a bounding box — more efficient for sparse routes
- Cache Overpass results in memory (dict keyed by query hash) for the duration of a session to avoid duplicate queries for overlapping route segments

**Phase:** Phase 2 (Overpass query layer).

---

### Pitfall 14: Alpine.js `x-init` Runs Before Leaflet Map Is Ready

**What goes wrong:**
If `x-init` code on an Alpine component calls a function that expects the Leaflet map instance to exist (`map.addLayer()`), but the map is initialized in a separate `<script>` tag that runs after Alpine's initialization, the call fails silently or throws "Cannot read property of null."

**Prevention:**
- Initialize Leaflet map in a `DOMContentLoaded` listener, not inline
- Use a custom event: dispatch `leaflet-ready` from the map initialization script; Alpine components listen with `@leaflet-ready.window="setupMap()"`
- Or use a simple global flag: `window.mapReady = false`; Alpine polls or checks before calling map methods

**Phase:** Phase 2 (frontend). Simple to fix, annoying to debug.

---

## Phase-Specific Warnings

| Phase | Topic | Likely Pitfall | Mitigation |
|-------|-------|---------------|------------|
| Phase 1 | FastAPI scaffold + SSE | BackgroundTasks misuse; event loop blocking | Use asyncio.Queue + asyncio.to_thread from day one |
| Phase 1 | CORS configuration | Browser blocks SSE before any progress | Add CORSMiddleware in initial scaffold |
| Phase 2 | Overpass query migration | 429 rate limiting; large-route timeouts | Semaphore + exponential backoff + [timeout:60] header |
| Phase 2 | Leaflet.js map init | "Container already initialized" on second search | Guard with `if (map) map.remove()` before init |
| Phase 2 | Alpine + Leaflet DOM | Reactive updates corrupt Leaflet DOM | Strict DOM boundary: Leaflet owns its div exclusively |
| Phase 2 | Temp file handling | Accumulation on Pi SD card | Per-session cleanup task from first file operation |
| Phase 3 | Nginx reverse proxy | SSE events buffered — progress appears batched | `proxy_buffering off` + `X-Accel-Buffering: no` |
| Phase 3 | systemd unit file | Service won't start — wrong uvicorn path | Absolute path to virtualenv binary |
| Phase 4 | tkinter launcher | Orphan processes on launcher close | WM_DELETE_WINDOW handler + atexit cleanup |
| Phase 4 | Launcher shutdown | Pi left running after work session | "Shutdown Pi" button via SSH in launcher |

---

## Sources

**FastAPI background tasks and SSE:**
- [FastAPI BackgroundTasks official docs](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [Understanding Pitfalls of Async Task Management in FastAPI — Leapcell](https://leapcell.io/blog/understanding-pitfalls-of-async-task-management-in-fastapi-requests)
- [Managing Background Tasks and Long-Running Operations in FastAPI — Leapcell](https://leapcell.io/blog/managing-background-tasks-and-long-running-operations-in-fastapi)
- [Using Asyncio queues for SSE — Medium](https://medium.com/@Rachita_B/lookout-for-these-cryptids-while-working-with-server-sent-events-43afabb3a868)
- [FastAPI difference between run_in_executor and run_in_threadpool — Sentry](https://sentry.io/answers/fastapi-difference-between-run-in-executor-and-run-in-threadpool/)
- [sse-starlette PyPI](https://pypi.org/project/sse-starlette/)

**Nginx SSE buffering:**
- [How to Configure Server-Sent Events Through Nginx — OneUptime](https://oneuptime.com/blog/post/2025-12-16-server-sent-events-nginx/view)
- [Nginx Module ngx_http_proxy_module — official docs](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)
- [Server-sent events buffered by nginx — gin-gonic issue](https://github.com/gin-gonic/gin/issues/1589)

**Overpass API rate limiting:**
- [Overpass API Commons — dev.overpass-api.de](https://dev.overpass-api.de/overpass-doc/en/preface/commons.html)
- [Overpass API — OpenStreetMap Wiki](https://wiki.openstreetmap.org/wiki/Overpass_API)
- [OverpassTooManyRequests python-overpy issue](https://github.com/DinoTools/python-overpy/issues/56)
- [Overpass 429 polygon queries — drolbr/Overpass-API](https://github.com/drolbr/Overpass-API/issues/391)

**systemd + Raspberry Pi deployment:**
- [Running uvicorn as systemd service — uvicorn issue tracker](https://github.com/Kludex/uvicorn/issues/678)
- [nginx + Uvicorn + FastAPI + systemd — miltschek.de](https://miltschek.de/article_2023-10-21_nginx+++Uvicorn+++FastAPI+++systemd.html)
- [Create a simple systemd service unit file for uvicorn — devopslogs.net](https://devopslogs.net/posts/uvicorn-systemd/)

**Leaflet.js initialization:**
- [Error: Map Container Is Already Initialized — Leaflet GitHub issue #3962](https://github.com/Leaflet/Leaflet/issues/3962)
- [Map container already initialized — OpenStreetMap Help](https://help.openstreetmap.org/questions/12935/error-map-container-is-already-initialized/)

**Alpine.js DOM conflicts:**
- [Troubleshooting Alpine.js: Fixing Reactivity Issues, DOM Conflicts — Mindful Chase](https://www.mindfulchase.com/explore/troubleshooting-tips/front-end-frameworks/troubleshooting-alpine-js-fixing-reactivity-issues,-dom-conflicts,-transition-bugs,-scope-problems,-and-integration-pitfalls.html)

**tkinter subprocess management:**
- [The dangers of the subprocess module — O'Reilly Python GUI Programming](https://www.oreilly.com/library/view/python-gui-programming/9781788835886/9c4b5306-560e-42f2-9a28-aa72bddf3def.xhtml)
- [subprocess.Popen — Python official docs](https://docs.python.org/3/library/subprocess.html)
