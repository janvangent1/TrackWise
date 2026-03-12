/* ================================================================
   TrackWise Web — Alpine.js + Leaflet application
   ================================================================
   Architecture: ALL Leaflet objects live in closure variables below
   (never inside Alpine.js reactive data). This prevents Alpine.js's
   Proxy from wrapping Leaflet internals, which breaks zoom animation
   for markers added after the initial page load.
   ================================================================ */

function trackwise() {

  // ---- Leaflet objects — NOT reactive, live outside Alpine.js scope ----
  let _map            = null;
  let _routeLayer     = null;
  let _markerLayers   = {};   // {place_id: L.Marker}
  let _roadLayers     = {};   // {place_id: L.Polyline}
  let _gpxTrackLayer  = null;
  let _gpxWptLayers   = [];
  // Custom waypoints: markers stored here, not in reactive customWaypoints array
  let _mapClickHandler       = null;
  let _customWpMarkers       = {};  // {id: L.Marker}

  return {
    // ---- Reactive UI state ----
    gpxFile: null,
    gpxFileName: '',
    dragging: false,

    placeTypes: {},
    searchConfig: {},
    gpxMode: 'track_with_waypoints',

    jobId: null,
    searching: false,
    progress: 0,
    log: [],

    places: [],
    highlightedId: null,
    filterText: '',
    sortKey: 'route_position',
    sortAsc: true,

    road_routes: {},
    route_points: [],
    total_km: 0,

    toasts: [],

    addWaypointMode: false,
    customWaypoints: [],   // [{id, lat, lon, name}] — no marker property

    // ---- Lifecycle ----
    async init() {
      this.initMap();
      await this.loadPlaceTypes();
    },

    initMap() {
      _map = L.map('map', { zoomControl: true }).setView([51.5, 4.5], 7);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(_map);

      // Keep Leaflet's _pixelOrigin correct whenever the map container resizes
      // (results panel appearing/disappearing, window resize). Without this,
      // markers drift on zoom and mouse→latlng conversions during drag are wrong.
      new ResizeObserver(() => _map.invalidateSize()).observe(
        document.getElementById('map')
      );
    },

    async loadPlaceTypes() {
      try {
        const res = await fetch('/api/place-types');
        this.placeTypes = await res.json();
        this.searchConfig = { petrol: this.placeTypes.petrol?.default_distance_km ?? 0.1 };
      } catch (e) {
        this.showToast('Could not load place types', 'error');
      }
    },

    // ---- File handling ----
    onDrop(e) {
      this.dragging = false;
      const file = e.dataTransfer.files[0];
      if (file) this.setFile(file);
    },

    onFileChange(e) {
      const file = e.target.files[0];
      if (file) this.setFile(file);
    },

    setFile(file) {
      if (!file.name.toLowerCase().endsWith('.gpx')) {
        this.showToast('Please select a .gpx file', 'error');
        return;
      }
      this.gpxFile = file;
      this.gpxFileName = file.name;
      this.previewGpxOnMap(file);
    },

    async previewGpxOnMap(file) {
      this.clearGpxPreview();
      try {
        const text = await file.text();
        const doc = new DOMParser().parseFromString(text, 'application/xml');

        let ptEls = doc.querySelectorAll('trkpt');
        if (ptEls.length === 0) ptEls = doc.querySelectorAll('rtept');
        const trackCoords = [];
        ptEls.forEach(el => {
          const lat = parseFloat(el.getAttribute('lat'));
          const lon = parseFloat(el.getAttribute('lon'));
          if (!isNaN(lat) && !isNaN(lon)) trackCoords.push([lat, lon]);
        });

        if (trackCoords.length > 1) {
          this.route_points = trackCoords.map(([lat, lon]) => [lon, lat]);

          _gpxTrackLayer = L.polyline(trackCoords, {
            color: '#4a90e2', weight: 3, opacity: 0.85,
          }).addTo(_map);
          _map.fitBounds(_gpxTrackLayer.getBounds().pad(0.1));

          const startIcon = L.divIcon({
            className: 'tw-route-endpoint',
            html: `<div class="tw-endpoint tw-endpoint-start">▶ Start</div>`,
            iconSize: [62, 24], iconAnchor: [0, 12], popupAnchor: [31, -12],
          });
          _gpxWptLayers.push(
            L.marker(trackCoords[0], { icon: startIcon, zIndexOffset: 1000 })
              .bindTooltip('Start').addTo(_map)
          );

          const finishIcon = L.divIcon({
            className: 'tw-route-endpoint',
            html: `<div class="tw-endpoint tw-endpoint-finish">🏁 Finish</div>`,
            iconSize: [68, 24], iconAnchor: [68, 12], popupAnchor: [-34, -12],
          });
          _gpxWptLayers.push(
            L.marker(trackCoords[trackCoords.length - 1], { icon: finishIcon, zIndexOffset: 1000 })
              .bindTooltip('Finish').addTo(_map)
          );
        }

        const wptEls = doc.querySelectorAll('gpx > wpt');
        wptEls.forEach(el => {
          const lat = parseFloat(el.getAttribute('lat'));
          const lon = parseFloat(el.getAttribute('lon'));
          if (isNaN(lat) || isNaN(lon)) return;
          const name = el.querySelector('name')?.textContent?.trim() || 'Waypoint';
          const icon = L.divIcon({
            className: 'tw-gpx-wpt',
            html: '📍',
            iconSize: [18, 18], iconAnchor: [9, 18], popupAnchor: [0, -18],
          });
          _gpxWptLayers.push(L.marker([lat, lon], { icon }).bindTooltip(name).addTo(_map));
        });

        const wptCount = wptEls.length;
        this.showToast(
          `GPX loaded: ${trackCoords.length} points` + (wptCount ? `, ${wptCount} waypoints` : ''),
          'info'
        );
      } catch (e) {
        this.showToast('Could not preview GPX on map', 'error');
      }
    },

    clearGpxPreview() {
      if (_gpxTrackLayer) { _map.removeLayer(_gpxTrackLayer); _gpxTrackLayer = null; }
      _gpxWptLayers.forEach(m => _map.removeLayer(m));
      _gpxWptLayers = [];
    },

    // ---- Place type config ----
    togglePlaceType(key, enabled) {
      if (enabled) {
        this.searchConfig[key] = this.placeTypes[key]?.default_distance_km ?? 0.1;
      } else {
        const cfg = { ...this.searchConfig };
        delete cfg[key];
        this.searchConfig = cfg;
      }
    },

    updateDistance(key, val) {
      const n = parseFloat(val);
      if (!isNaN(n) && n > 0) {
        this.searchConfig = { ...this.searchConfig, [key]: n };
      }
    },

    // ---- Search ----
    async startSearch() {
      if (!this.gpxFile) { this.showToast('Select a GPX file first', 'error'); return; }
      if (Object.keys(this.searchConfig).length === 0) { this.showToast('Enable at least one place type', 'error'); return; }

      this.searching = true;
      this.progress = 0;
      this.log = [];
      this.places = [];
      this.road_routes = {};
      this.route_points = [];
      this.clearMap();

      const form = new FormData();
      form.append('gpx_file', this.gpxFile);
      form.append('config', JSON.stringify(this.searchConfig));

      try {
        const res = await fetch('/api/search', { method: 'POST', body: form });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Server error');
        }
        const { job_id } = await res.json();
        this.jobId = job_id;
        this.listenToJob(job_id);
      } catch (e) {
        this.searching = false;
        this.showToast(`Search failed: ${e.message}`, 'error');
      }
    },

    listenToJob(jobId) {
      const es = new EventSource(`/api/search/${jobId}/stream`);

      es.onmessage = (e) => {
        const event = JSON.parse(e.data);

        if (event.type === 'progress') {
          this.progress = event.percent ?? this.progress;
          this.log.push(event.message);
          this.$nextTick(() => {
            const box = this.$refs.logBox;
            if (box) box.scrollTop = box.scrollHeight;
          });

        } else if (event.type === 'result') {
          this.places = event.places;
          this.road_routes = event.road_routes;
          this.route_points = event.route_points;
          this.total_km = event.total_km;
          this.searching = false;
          this.progress = 100;
          es.close();
          this.renderMap();
          this.showToast(`Found ${event.places.length} places along ${event.total_km.toFixed(1)} km route`, 'success');

        } else if (event.type === 'error') {
          this.searching = false;
          es.close();
          this.showToast(`Error: ${event.message}`, 'error');
          this.log.push(`ERROR: ${event.message}`);

        } else if (event.type === 'cancelled') {
          this.searching = false;
          es.close();
          this.showToast('Search cancelled', 'info');
        }
      };

      es.onerror = () => {
        if (this.searching) {
          this.searching = false;
          es.close();
          this.showToast('Connection lost', 'error');
        }
      };
    },

    async cancelSearch() {
      if (!this.jobId) return;
      await fetch(`/api/search/${this.jobId}/cancel`, { method: 'POST' });
    },

    // ---- Map rendering ----
    clearMap() {
      if (_routeLayer) { _map.removeLayer(_routeLayer); _routeLayer = null; }
      Object.values(_markerLayers).forEach(m => _map.removeLayer(m));
      Object.values(_roadLayers).forEach(l => _map.removeLayer(l));
      _markerLayers = {};
      _roadLayers = {};
    },

    renderMap() {
      this.clearMap();
      if (!this.route_points.length) return;

      if (!_gpxTrackLayer) {
        const routeCoords = this.route_points.map(([lon, lat]) => [lat, lon]);
        _routeLayer = L.polyline(routeCoords, { color: '#4a90e2', weight: 3, opacity: 0.85 }).addTo(_map);
      }

      this.places.forEach(place => {
        const icon = L.divIcon({
          className: 'tw-place-icon',
          html: place.emoji,
          iconSize: [26, 26], iconAnchor: [13, 13], popupAnchor: [0, -14],
        });
        const marker = L.marker([place.lat, place.lon], { icon })
          .addTo(_map)
          .bindPopup(`<b>${place.emoji} ${place.base_name}</b><br>Type: ${place.type_label}<br>Distance from route: ${place.distance_km} km`)
          .bindTooltip(place.base_name);

        marker.on('click', () => this.highlightPlace(place));
        _markerLayers[place.id] = marker;
      });

      Object.entries(this.road_routes).forEach(([pid, route]) => {
        if (!route || route.length < 2) return;
        const place = this.places.find(p => p.id === pid);
        const color = place ? place.color : 'gray';
        const coords = route.map(([lon, lat]) => [lat, lon]);
        _roadLayers[pid] = L.polyline(coords, { color, weight: 2, opacity: 0.55, dashArray: '4 4' }).addTo(_map);
      });

      const boundsLayer = _routeLayer || _gpxTrackLayer;
      if (boundsLayer) _map.fitBounds(boundsLayer.getBounds().pad(0.1));
    },

    updateMarkerOpacity() {
      this.places.forEach(place => {
        const marker = _markerLayers[place.id];
        if (marker) {
          const el = marker.getElement();
          if (el) el.style.opacity = place.included ? '1' : '0.35';
        }
        const road = _roadLayers[place.id];
        if (road) road.setStyle({ opacity: place.included ? 0.55 : 0.15 });
      });
    },

    // ---- Place interaction ----
    togglePlace(place) {
      place.included = !place.included;
      this.updateMarkerOpacity();
    },

    highlightPlace(place) {
      this.highlightedId = place.id;
      const marker = _markerLayers[place.id];
      if (marker) {
        _map.setView([place.lat, place.lon], Math.max(_map.getZoom(), 14));
        marker.openPopup();
      }
    },

    selectAll()  { this.places.forEach(p => p.included = true);  this.updateMarkerOpacity(); },
    selectNone() { this.places.forEach(p => p.included = false); this.updateMarkerOpacity(); },

    // ---- Sorting / filtering ----
    sortBy(key) {
      if (this.sortKey === key) {
        this.sortAsc = !this.sortAsc;
      } else {
        this.sortKey = key;
        this.sortAsc = true;
      }
    },

    get filteredPlaces() {
      let list = this.places;
      if (this.filterText) {
        const q = this.filterText.toLowerCase();
        list = list.filter(p =>
          p.base_name.toLowerCase().includes(q) ||
          p.type_label.toLowerCase().includes(q) ||
          p.place_type.toLowerCase().includes(q)
        );
      }
      const key = this.sortKey;
      const asc = this.sortAsc ? 1 : -1;
      return [...list].sort((a, b) => {
        if (a[key] < b[key]) return -1 * asc;
        if (a[key] > b[key]) return  1 * asc;
        return 0;
      });
    },

    get selectedPlaces() {
      return this.places.filter(p => p.included);
    },

    // ---- GPX Export ----
    async exportGpx() {
      const selected = this.selectedPlaces;
      if (!selected.length && !this.customWaypoints.length) { this.showToast('No places or waypoints selected', 'error'); return; }

      try {
        const res = await fetch('/api/export/gpx', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            job_id: this.jobId,
            selected_ids: selected.map(p => p.id),
            mode: this.gpxMode,
            custom_waypoints: this.customWaypoints.map(w => ({ lat: w.lat, lon: w.lon, name: w.name })),
          }),
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Export failed');
        }
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const baseName = this.gpxFileName.replace(/\.gpx$/i, '');
        a.download = `${baseName}_trackwise.gpx`;
        a.click();
        URL.revokeObjectURL(url);
        const total = selected.length + this.customWaypoints.length;
        this.showToast(`Exported ${total} waypoint${total !== 1 ? 's' : ''}`, 'success');
      } catch (e) {
        this.showToast(`Export error: ${e.message}`, 'error');
      }
    },

    // ---- Status helpers ----
    get statusClass() {
      if (this.searching) return 'running';
      if (!this.jobId)    return '';
      return this.places.length ? 'done' : 'error';
    },

    get statusText() {
      if (this.searching) return 'Searching…';
      if (this.places.length) return `${this.places.length} places found — ${this.total_km.toFixed(1)} km route`;
      if (this.jobId) return 'Ready';
      return '';
    },

    // ---- Toast ----
    showToast(message, type = 'info') {
      this.toasts.push({ message, type });
      setTimeout(() => this.toasts.shift(), 4000);
    },

    // ---- Custom waypoints ----
    toggleAddWaypointMode() {
      this.addWaypointMode = !this.addWaypointMode;
      const container = _map.getContainer();
      if (this.addWaypointMode) {
        _mapClickHandler = (e) => this._onMapClickAddWaypoint(e);
        _map.on('click', _mapClickHandler);
        container.classList.add('tw-add-wpt-mode');
      } else {
        if (_mapClickHandler) {
          _map.off('click', _mapClickHandler);
          _mapClickHandler = null;
        }
        container.classList.remove('tw-add-wpt-mode');
      }
    },

    _onMapClickAddWaypoint(e) {
      const { lat, lng } = e.latlng;
      const id = `custom_${Date.now()}`;

      const marker = L.marker([lat, lng], {
        icon: L.divIcon({
          className: 'tw-gpx-wpt',
          html: '📍',
          iconSize: [18, 18], iconAnchor: [9, 18], popupAnchor: [0, -18],
        }),
      }).addTo(_map);

      const div = document.createElement('div');
      div.style.cssText = 'display:flex;flex-direction:column;gap:6px;min-width:170px;';
      div.innerHTML = `
        <label style="font-size:12px;font-weight:600;">Waypoint name:</label>
        <input id="wn-${id}" type="text" placeholder="e.g. Campsite"
          style="padding:4px 8px;border:1px solid #ccc;border-radius:4px;font-size:13px;"/>
        <div style="display:flex;gap:6px;justify-content:flex-end;">
          <button id="wc-${id}" style="padding:3px 10px;font-size:12px;border:1px solid #ccc;border-radius:4px;cursor:pointer;background:#fff;">Cancel</button>
          <button id="ws-${id}" style="padding:3px 10px;font-size:12px;border:none;border-radius:4px;cursor:pointer;background:#27ae60;color:#fff;font-weight:600;">Save</button>
        </div>`;

      marker.bindPopup(div, { closeButton: false, minWidth: 180 }).openPopup();

      const save = () => {
        const nameEl = document.getElementById(`wn-${id}`);
        const name = nameEl?.value?.trim() || 'Waypoint';
        marker.closePopup();
        marker.bindTooltip(name, { permanent: false });
        _customWpMarkers[id] = marker;
        this.customWaypoints.push({ id, lat, lon: lng, name });
      };

      const cancel = () => {
        marker.closePopup();
        _map.removeLayer(marker);
      };

      setTimeout(() => {
        const inputEl = document.getElementById(`wn-${id}`);
        document.getElementById(`ws-${id}`)?.addEventListener('click', save);
        document.getElementById(`wc-${id}`)?.addEventListener('click', cancel);
        inputEl?.focus();
        inputEl?.addEventListener('keydown', (ev) => {
          if (ev.key === 'Enter') save();
          if (ev.key === 'Escape') cancel();
        });
      }, 40);
    },

    removeCustomWaypoint(id) {
      const idx = this.customWaypoints.findIndex(w => w.id === id);
      if (idx !== -1) {
        if (_customWpMarkers[id]) {
          _map.removeLayer(_customWpMarkers[id]);
          delete _customWpMarkers[id];
        }
        this.customWaypoints.splice(idx, 1);
      }
    },
  };
}
