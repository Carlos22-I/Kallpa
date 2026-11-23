/* Utilidades compartidas + adaptador de mapa (Leaflet con respaldo SVG sin conexión). */
const Kallpa = (() => {
  const HB_COLOR = { sin_anemia: "#2e7d32", sin_dato: "#7a8a84", leve: "#d99a2b", moderada: "#c4552d", severa: "#b3261e" };

  async function api(path, opts = {}) {
    const res = await fetch(path, opts);
    let data = null;
    try { data = await res.json(); } catch (_) { /* sin cuerpo */ }
    if (!res.ok) throw new Error((data && data.error) || `Error ${res.status}`);
    return data;
  }

  function toast(msg) {
    let t = document.querySelector(".toast");
    if (!t) { t = document.createElement("div"); t.className = "toast"; document.body.appendChild(t); }
    t.textContent = msg; t.classList.add("show");
    clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("show"), 2600);
  }

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  /* ---------- Adaptador de mapa ---------- */
  class LeafletMap {
    constructor(el, center, zones = []) {
      this.map = L.map(el, { zoomControl: true }).setView([center.lat, center.lng], 15);
      if (zones.length) this.map.fitBounds(zones.map((z) => [z.lat, z.lng]), { padding: [20, 20] });
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19, attribution: "© OpenStreetMap",
      }).addTo(this.map);
      this.layer = L.layerGroup().addTo(this.map);
      this.kind = "leaflet";
    }
    clear() { this.layer.clearLayers(); }
    circle(lat, lng, { color = "#1d5c48", radius = 10, label = "", onClick } = {}) {
      const m = L.circleMarker([lat, lng], { radius, color: "#fff", weight: 2, fillColor: color, fillOpacity: 0.9 }).addTo(this.layer);
      if (label) m.bindTooltip(label);
      if (onClick) m.on("click", onClick);
      return m;
    }
    icon(lat, lng, emoji, label) {
      L.marker([lat, lng], { icon: L.divIcon({ html: `<span style="font-size:16px">${emoji}</span>`, className: "", iconSize: [18, 18] }) })
        .bindTooltip(label).addTo(this.layer);
    }
    line(coords, color = "#1d5c48") { L.polyline(coords.map((c) => [c.lat, c.lng]), { color, weight: 4, opacity: 0.8, dashArray: "6 6" }).addTo(this.layer); }
    number(lat, lng, n) {
      L.marker([lat, lng], { icon: L.divIcon({ html: `<div style="background:#7a1f2b;color:#fff;border-radius:50%;width:22px;height:22px;display:grid;place-items:center;font-size:12px;font-weight:700;border:2px solid #fff">${n}</div>`, className: "", iconSize: [22, 22] }) }).addTo(this.layer);
    }
    pin(lat, lng) {
      if (this._pin) this._pin.remove();
      this._pin = L.marker([lat, lng]).addTo(this.map);
    }
    onClick(cb) { this.map.on("click", (e) => cb(e.latlng.lat, e.latlng.lng)); }
    focus(lat, lng) { this.map.setView([lat, lng], 17); }
  }

  /* Respaldo: mapa esquemático en SVG cuando no hay acceso a los mosaicos (sin internet). */
  class SvgMap {
    constructor(el, center, zones = []) {
      this.el = el; this.center = center; this.zones = zones; this.items = []; this.handlers = []; this.kind = "svg";
      this.cb = null;
      if (zones.length) { // encuadra todas las zonas
        const la = zones.map((z) => z.lat), lo = zones.map((z) => z.lng);
        this.center = { lat: (Math.min(...la) + Math.max(...la)) / 2, lng: (Math.min(...lo) + Math.max(...lo)) / 2 };
        this.span = Math.max(Math.max(...la) - Math.min(...la), Math.max(...lo) - Math.min(...lo)) * 1.35;
      } else this.span = 0.03;
      this.render();
    }
    proj(lat, lng) {
      const w = this.el.clientWidth || 600, h = this.el.clientHeight || 400;
      const s = Math.min(w, h) / this.span;
      return [w / 2 + (lng - this.center.lng) * s, h / 2 - (lat - this.center.lat) * s];
    }
    unproj(x, y) {
      const w = this.el.clientWidth || 600, h = this.el.clientHeight || 400;
      const s = Math.min(w, h) / this.span;
      return [this.center.lat - (y - h / 2) / s, this.center.lng + (x - w / 2) / s];
    }
    render() {
      const w = this.el.clientWidth || 600, h = this.el.clientHeight || 400;
      let svg = `<svg class="svgmap" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg">`;
      svg += `<rect width="100%" height="100%" fill="#eef3f0"/>`;
      for (let i = 1; i < 8; i++) svg += `<line x1="${(w / 8) * i}" y1="0" x2="${(w / 8) * i}" y2="${h}" stroke="#e1e9e5"/><line x1="0" y1="${(h / 8) * i}" x2="${w}" y2="${(h / 8) * i}" stroke="#e1e9e5"/>`;
      for (const z of this.zones) { const [x, y] = this.proj(z.lat, z.lng); svg += `<text x="${x}" y="${y - 14}" text-anchor="middle">${esc(z.nombre)}</text>`; }
      for (const it of this.items) svg += it;
      svg += `<text x="8" y="${h - 8}">Mapa esquemático (sin conexión a mosaicos)</text></svg>`;
      this.el.innerHTML = svg;
      this.el.onclick = (e) => {
        const r = this.el.getBoundingClientRect();
        const t = e.target.closest("[data-i]");
        if (t && this.handlers[t.dataset.i]) return this.handlers[t.dataset.i]();
        if (this.cb) { const [lat, lng] = this.unproj(e.clientX - r.left, e.clientY - r.top); this.cb(lat, lng); }
      };
    }
    clear() { this.items = []; this.handlers = []; this.render(); }
    circle(lat, lng, { color = "#1d5c48", radius = 10, label = "", onClick } = {}) {
      this.handlers = this.handlers || [];
      const i = this.handlers.push(onClick) - 1;
      const [x, y] = this.proj(lat, lng);
      this.items.push(`<circle data-i="${i}" cx="${x}" cy="${y}" r="${radius}" fill="${color}" fill-opacity=".9" stroke="#fff" stroke-width="2" style="cursor:pointer"><title>${esc(label)}</title></circle>`);
      this.render();
    }
    icon(lat, lng, emoji, label) { const [x, y] = this.proj(lat, lng); this.items.push(`<text x="${x}" y="${y}" font-size="14" text-anchor="middle"><title>${esc(label)}</title>${emoji}</text>`); this.render(); }
    line(coords, color = "#1d5c48") { const pts = coords.map((c) => this.proj(c.lat, c.lng).join(",")).join(" "); this.items.unshift(`<polyline points="${pts}" fill="none" stroke="${color}" stroke-width="3" stroke-dasharray="6 5"/>`); this.render(); }
    number(lat, lng, n) { const [x, y] = this.proj(lat, lng); this.items.push(`<circle cx="${x}" cy="${y - 16}" r="9" fill="#7a1f2b" stroke="#fff" stroke-width="2"/><text x="${x}" y="${y - 12.5}" text-anchor="middle" style="fill:#fff;font-weight:700">${n}</text>`); this.render(); }
    pin(lat, lng) { this.items = this.items.filter((s) => !s.startsWith("<g id=pin")); const [x, y] = this.proj(lat, lng); this.items.push(`<g id=pin><path d="M${x} ${y} l-7 -16 a8 8 0 1 1 14 0 z" fill="#c4552d" stroke="#fff"/></g>`); this.render(); }
    onClick(cb) { this.cb = cb; }
    focus() { }
  }

  function createMap(el, center, zones) {
    if (window.L) { try { return new LeafletMap(el, center, zones); } catch (e) { console.warn(e); } }
    return new SvgMap(el, center, zones);
  }


  return { api, toast, esc, createMap, HB_COLOR };
})();
