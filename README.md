# TrackWise Web 2.0

A web-based GPX waypoint finder — find petrol stations, supermarkets, bakeries, cafes, repair shops, accommodation, and speed cameras along any GPX route.

Upload a GPX file from any browser on your local network. The Raspberry Pi does all the work.

## Quick Start (Windows — Local Testing)

```
python launcher.py
```

The launcher GUI will:
- Start the web server (FastAPI + Uvicorn)
- Let you open the browser with one click
- Show live server logs

**First run — install dependencies:**

Click **📦 Install Dependencies** in the launcher, or run manually:

```bash
cd web
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Project Structure

```
TrackWise 2.0/
├── launcher.py              # Windows GUI launcher (tkinter)
├── README.md
├── web/
│   ├── requirements.txt     # Python dependencies
│   ├── backend/
│   │   ├── app.py           # FastAPI application
│   │   └── core/
│   │       ├── gpx_parser.py    # GPX file parsing
│   │       ├── overpass.py      # Overpass API (OpenStreetMap)
│   │       ├── osrm.py          # OSRM road routing
│   │       ├── search.py        # Main search orchestrator
│   │       ├── gpx_writer.py    # GPX export
│   │       └── place_types.py   # Place type config
│   ├── frontend/
│   │   ├── index.html           # Single-page app
│   │   └── static/
│   │       ├── css/style.css
│   │       └── js/app.js        # Alpine.js + Leaflet.js app
│   └── deployment/
│       ├── trackwise.service    # systemd service
│       ├── nginx.conf           # Nginx reverse proxy
│       └── setup_pi.sh          # One-command Pi setup script
└── old/                     # Original desktop app (archived)
    └── main_gui_enhanced.py
```

## Raspberry Pi Deployment

### One-command setup

```bash
git clone https://github.com/janvangent1/TrackWise /home/pi/trackwise
cd /home/pi/trackwise/web/deployment
chmod +x setup_pi.sh
./setup_pi.sh
```

Access TrackWise from any device on your network:
```
http://<raspberry-pi-ip>/
```

### Manual setup

See [web/deployment/setup_pi.sh](web/deployment/setup_pi.sh) for step-by-step instructions.

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/` | Serve the web UI |
| `GET`  | `/api/place-types` | Available place types + defaults |
| `POST` | `/api/search` | Start search (form: `gpx_file`, `config` JSON) |
| `GET`  | `/api/search/{job_id}/stream` | SSE progress stream |
| `GET`  | `/api/search/{job_id}/results` | JSON results |
| `POST` | `/api/search/{job_id}/cancel` | Cancel running search |
| `POST` | `/api/export/gpx` | Download GPX for selected places |
| `GET`  | `/health` | Health check |

## Place Types

| Type | Default Distance | OSM Query |
|------|-----------------|-----------|
| ⛽ Petrol | 5.0 km | `amenity=fuel` |
| 🛒 Supermarket | 0.1 km | `shop=supermarket` |
| 🥖 Bakery | 0.1 km | `shop=bakery` |
| ☕ Café/Restaurant | 0.1 km | `amenity=cafe\|restaurant\|fast_food` |
| 🔧 Repair Shop | 0.1 km | `shop=car_repair\|motorcycle` |
| 🏨 Accommodation | 0.1 km | `tourism=hotel\|motel\|hostel\|...` |
| 📷 Speed Camera | on-route only | `highway=speed_camera` |

## External Services

- **Overpass API** (overpass-api.de) — OpenStreetMap POI data — free, no key required
- **OSRM** (router.project-osrm.org) — road routing — free, no key required
