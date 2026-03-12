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

This guide is for deploying TrackWise **alongside an existing application** (e.g. regenboog) using **Cloudflare Tunnel** (no port forwarding required).

> **Do NOT use `setup_pi.sh` if you already have nginx and Cloudflare Tunnel running** — it removes the default nginx site and uses a catch-all config that will break other hosted apps. Follow the manual steps below instead.

---

### Step 1 — Get the code onto the Pi

SSH into your Pi, then clone the repo:

```bash
cd ~
git clone https://github.com/janvangent1/trackwise.git trackwise
```

---

### Step 2 — Install Python dependencies

```bash
cd ~/trackwise/web
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate
```

---

### Step 3 — Install the systemd service

```bash
sudo sed "s|/home/pi/trackwise|$HOME/trackwise|g; s|User=pi|User=$(whoami)|g" \
    ~/trackwise/web/deployment/trackwise.service \
    | sudo tee /etc/systemd/system/trackwise.service > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable trackwise
sudo systemctl start trackwise

# Verify:
sudo systemctl status trackwise
```

Logs: `sudo journalctl -u trackwise -f`

---

### Step 4 — Configure nginx (optional)

> You can skip this step if Cloudflare Tunnel points directly to `localhost:8000`. nginx adds static file caching and is useful if you want to route multiple apps through port 80, but it's not required.

Create a new nginx site config (this does **not** affect your other apps):

```bash
sudo nano /etc/nginx/sites-available/trackwise
```

Paste:

```nginx
server {
    listen 80;
    server_name trackwise.jbouquet.be;

    client_max_body_size 10M;
    proxy_buffering off;

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_set_header   X-Accel-Buffering no;
        proxy_set_header   Connection        '';
        proxy_read_timeout 300s;
    }

    location /static/ {
        alias /home/pi/trackwise/web/frontend/static/;
        expires 1h;
        add_header Cache-Control "public, immutable";
    }

    gzip on;
    gzip_types text/plain text/css application/json application/javascript;
    gzip_min_length 1000;
}
```

> If your Pi username is not `pi`, replace `/home/pi` with your actual home directory (check with `echo $HOME`).

Enable the config and reload nginx:

```bash
sudo ln -s /etc/nginx/sites-available/trackwise /etc/nginx/sites-enabled/trackwise
sudo nginx -t          # must print "syntax ok"
sudo systemctl reload nginx
```

---

### Step 5 — Add the hostname in Cloudflare

One tunnel can serve multiple subdomains — each subdomain is a separate "Public Hostname" entry pointing to a different local port. You don't need a second tunnel.

1. Go to [https://one.dash.cloudflare.com](https://one.dash.cloudflare.com)
2. Left sidebar: **Networks** → **Tunnels**
3. Find your tunnel `jbouquet` → click the **three dots (...)** on the right → **Configure**
4. Click the **Public Hostname** tab — you'll see the existing `regenboog.jbouquet.be` entry here
5. Click **Add a public hostname**
6. Fill in:
   - **Subdomain:** `trackwise`
   - **Domain:** `jbouquet.be` *(select from dropdown)*
   - **Path:** leave empty
   - **Service Type:** `HTTP`
   - **URL:** `localhost:8000`
7. Click **Save hostname**

Cloudflare automatically creates the DNS record — nothing to do in the DNS tab.

#### Verify on the Pi (optional)

```bash
sudo systemctl status cloudflared
# or check logs:
sudo journalctl -u cloudflared -f
```

---

### Step 6 — Test

```bash
# From the Pi itself:
curl -s http://localhost:8000/health
# Expected: {"status":"ok"}
```

Then open `https://trackwise.jbouquet.be` in your browser.

---

### Troubleshooting

| Symptom | Fix |
|---|---|
| TrackWise not starting | `sudo journalctl -u trackwise -f` |
| 502 Bad Gateway in browser | TrackWise service is down — check above |
| Regenboog broke after nginx reload | `sudo nginx -t` — look for config conflicts |
| Progress bar doesn't update live | Cloudflare may buffer SSE — the search still completes, progress appears in batches. This is cosmetic only. |

---

### Architecture overview

```
Browser
  └── Cloudflare Tunnel (jbouquet)
        ├── regenboog.jbouquet.be  →  localhost:3000  (Node.js/Express)
        └── trackwise.jbouquet.be  →  localhost:8000  (FastAPI/uvicorn)
```

---

### One-command setup (fresh Pi, no other apps)

If this is the only app on the Pi:

```bash
git clone https://github.com/janvangent1/trackwise.git /home/pi/trackwise
cd /home/pi/trackwise/web/deployment
chmod +x setup_pi.sh
./setup_pi.sh
```

Access on your local network: `http://<raspberry-pi-ip>/`

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
