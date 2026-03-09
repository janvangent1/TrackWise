/* ================================================================
   TrackWise Web — Alpine.js + Leaflet application
   ================================================================ */

function trackwise() {
  return {
    // ---- State ----
    gpxFile: null,
    gpxFileName: '',
    dragging: false,

    placeTypes: {},          // loaded from /api/place-types
    searchConfig: {},        // {place_type: distance_km}
    gpxMode: 'waypoints_only',

    jobId: null,
    searching: false,
    progress: 0,
    log: [],

    places: [],              // all found places
    highlightedId: null,
    filterText: '',
    sortKey: 'route_position',
    sortAsc: true,

    road_routes: {},         // {place_id: [[lon, lat], ...]}
    route_points: [],        // [[lon, lat], ...]
    total_km: 0,

    toasts: [],

    // ---- Leaflet map ----
    map: null,
    routeLayer: null,
    markerLayers: {},        // {place_id: marker}
    roadLayers: {},          // {place_id: polyline}

    // ---- Lifecycle ----
    async init() {
      this.initMap();
      await this.loadPlaceTypes();
    },

    initMap() {
      this.map = L.map('map', { zoomControl: true }).setView([51.5, 4.5], 7);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(this.map);
    },

    async loadPlaceTypes() {
      try {
        const res = await fetch('/api/place-types');
        this.placeTypes = await res.json();
        // Default: enable petrol only
        this.searchConfig = { petrol: this.placeTypes.petrol?.default_distance_km ?? 5.0 };
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
      if (this.routeLayer) { this.map.removeLayer(this.routeLayer); this.routeLayer = null; }
      Object.values(this.markerLayers).forEach(m => this.map.removeLayer(m));
      Object.values(this.roadLayers).forEach(l => this.map.removeLayer(l));
      this.markerLayers = {};
      this.roadLayers = {};
    },

    renderMap() {
      this.clearMap();

      if (!this.route_points.length) return;

      // Route line [lon, lat] → Leaflet [lat, lon]
      const routeCoords = this.route_points.map(([lon, lat]) => [lat, lon]);
      this.routeLayer = L.polyline(routeCoords, { color: '#4a90e2', weight: 3, opacity: 0.85 }).addTo(this.map);

      // Place markers
      this.places.forEach(place => {
        const color = place.color || 'gray';
        const icon = L.divIcon({
          className: '',
          html: `<div style="background:${color};width:14px;height:14px;border-radius:50%;border:2px solid white;box-shadow:0 1px 3px rgba(0,0,0,.5)"></div>`,
          iconSize: [14, 14],
          iconAnchor: [7, 7],
        });
        const marker = L.marker([place.lat, place.lon], { icon })
          .addTo(this.map)
          .bindPopup(`<b>${place.name}</b><br>${place.base_name}<br>Type: ${place.type_label}<br>Distance: ${place.distance_km} km`)
          .bindTooltip(place.base_name);

        marker.on('click', () => this.highlightPlace(place));
        this.markerLayers[place.id] = marker;
      });

      // Road routes
      Object.entries(this.road_routes).forEach(([pid, route]) => {
        if (!route || route.length < 2) return;
        const place = this.places.find(p => p.id === pid);
        const color = place ? place.color : 'gray';
        const coords = route.map(([lon, lat]) => [lat, lon]);
        this.roadLayers[pid] = L.polyline(coords, { color, weight: 2, opacity: 0.55, dashArray: '4 4' }).addTo(this.map);
      });

      // Fit map
      this.map.fitBounds(this.routeLayer.getBounds().pad(0.1));
    },

    updateMarkerOpacity() {
      this.places.forEach(place => {
        const marker = this.markerLayers[place.id];
        if (marker) {
          const el = marker.getElement();
          if (el) el.style.opacity = place.included ? '1' : '0.35';
        }
        const road = this.roadLayers[place.id];
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
      const marker = this.markerLayers[place.id];
      if (marker) {
        this.map.setView([place.lat, place.lon], Math.max(this.map.getZoom(), 14));
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
      if (!selected.length) { this.showToast('No places selected', 'error'); return; }

      try {
        const res = await fetch('/api/export/gpx', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            job_id: this.jobId,
            selected_ids: selected.map(p => p.id),
            mode: this.gpxMode,
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
        a.download = 'trackwise_export.gpx';
        a.click();
        URL.revokeObjectURL(url);
        this.showToast(`Exported ${selected.length} places`, 'success');
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
  };
}
