/* Panel del establecimiento de salud: priorización, registro clínico, ruta de visitas y alertas. */
(async () => {
  const { api, toast, esc, createMap, HB_COLOR } = Kallpa;
  const $ = (id) => document.getElementById(id);
  const HB = { sin_dato: "Sin dosaje", sin_anemia: "Sin anemia", leve: "Anemia leve", moderada: "Anemia moderada", severa: "Anemia severa" };

  // El token nunca va en la URL (quedaría en el historial y en los logs): se pide y vive en sessionStorage.
  function token() {
    let t = null;
    try { t = sessionStorage.getItem("kallpa_token"); } catch (_) { }
    if (!t) t = (prompt("Token del panel de salud") || "").trim();
    try { sessionStorage.setItem("kallpa_token", t); } catch (_) { }
    return t;
  }
  const TOKEN = token();
  const papi = async (p, o = {}) => {
    try {
      return await api(`/api/panel${p}`, { ...o, headers: { "X-Panel-Token": TOKEN, "content-type": "application/json" } });
    } catch (err) {
      if (err.message === "No autorizado") { try { sessionStorage.removeItem("kallpa_token"); } catch (_) { } }
      throw err;
    }
  };
  $("logout").onclick = (e) => { e.preventDefault(); try { sessionStorage.removeItem("kallpa_token"); } catch (_) { } location.href = "/panel"; };

  const cfg = await api("/api/config");
  $("f-sector").innerHTML = `<option value="">Todos los sectores</option>` + cfg.sectores.map((s) => `<option>${esc(s.nombre)}</option>`).join("");
  const map = createMap($("map"), cfg.centro, cfg.sectores);
  let rows = [], route = null;

  const spark = (arr) => `<span class="spark" title="Tendencia de adherencia (21 días)">${arr.map((v) => `<i style="height:${Math.max(2, v * 22)}px;opacity:${0.35 + v * 0.65}"></i>`).join("")}</span>`;

  function renderKids() {
    $("n-ninos").textContent = rows.length;
    $("ninos").innerHTML = rows.map((r, i) => {
      const n = r.nino;
      return `<div class="item" data-id="${n.id}">
        <div class="head"><b>#${i + 1} ${esc(n.alias)}</b><span class="muted">${r.edad_meses} m · ${esc(n.sector)}</span>
          <span class="pill hb-${n.estado_hb}">${esc(HB[n.estado_hb])}${n.hb_valor ? ` · ${n.hb_valor} g/dL` : ""}</span>
          <span class="score">${r.prioridad}</span></div>
        <ul>${r.razones.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
        <div class="row muted" style="margin-top:6px;font-size:12.5px">
          Adherencia: <b>${r.adherencia_14d ?? "—"}${r.adherencia_14d != null ? "%" : ""}</b> ${r.tendencia_adherencia.length ? spark(r.tendencia_adherencia) : ""}
          · Dieta 7 d: <b>${r.puntaje_dieta_7d ?? "—"}</b> · Código: ${esc(n.codigo)}
        </div>
        <details class="edit"><summary>Registrar resultado del establecimiento</summary>
          <div class="formgrid">
            <div><label>Estado de hemoglobina</label><select data-f="estado_hb">${Object.entries(HB).map(([k, v]) => `<option value="${k}" ${k === n.estado_hb ? "selected" : ""}>${v}</option>`).join("")}</select></div>
            <div><label>Hb (g/dL)</label><input type="number" step="0.1" data-f="hb_valor" value="${n.hb_valor ?? ""}"></div>
            <div><label>Fecha del dosaje</label><input type="date" data-f="hb_fecha" value="${n.hb_fecha ?? ""}"></div>
            <div><label>Próximo control</label><input type="date" data-f="proximo_control" value="${n.proximo_control ?? ""}"></div>
          </div>
          <label>Esquema de suplemento indicado</label><input type="text" data-f="esquema_suplemento" value="${esc(n.esquema_suplemento)}">
          <div class="row" style="margin-top:8px"><button class="btn" data-save="${n.id}">Guardar</button><span class="muted">Kallpa no calcula diagnósticos: registra lo determinado por el establecimiento.</span></div>
        </details>
      </div>`;
    }).join("") || '<p class="muted">Sin niños registrados.</p>';
  }

  $("ninos").onclick = async (e) => {
    const b = e.target.closest("[data-save]"); if (!b) return;
    const box = b.closest(".item"), body = {};
    // Un campo vacío se envía como null: así el personal puede borrar un dato mal registrado.
    box.querySelectorAll("[data-f]").forEach((el) => {
      const v = el.value.trim();
      body[el.dataset.f] = v === "" ? null : el.dataset.f === "hb_valor" ? +v : v;
    });
    try { await papi(`/ninos/${b.dataset.save}`, { method: "PATCH", body: JSON.stringify(body) }); toast("Guardado"); await refresh(); }
    catch (err) { toast(err.message); }
  };

  function drawMap() {
    map.clear();
    map.icon(cfg.establecimiento.lat, cfg.establecimiento.lng, "🏥", cfg.establecimiento.nombre);
    if (route) map.line([route.origen, ...route.paradas, route.origen], "#7a1f2b");
    for (const r of rows) {
      if (r.nino.lat == null) continue;
      map.circle(r.nino.lat, r.nino.lng, { color: HB_COLOR[r.nino.estado_hb], radius: 5 + r.prioridad / 12, label: `${r.nino.alias} · prioridad ${r.prioridad}` });
    }
    if (route) route.paradas.forEach((s) => map.number(s.lat, s.lng, s.orden));
  }

  $("ruta").onclick = async () => {
    try {
      route = await papi("/visitas", { method: "POST", body: JSON.stringify({ max_visitas: +$("max").value, sector: $("f-sector").value }) });
      $("ruta-res").innerHTML = `<div class="result"><b>${route.paradas.length} visitas · ${route.distancia_km} km a pie · ~${Math.round(route.duracion_min / 60 * 10) / 10} h (incluye 25 min por visita)</b>
        <div class="muted">Sin optimizar: ${route.distancia_sin_optimizar_km} km → <b>ahorro ${route.ahorro_pct}%</b> de recorrido. ${esc(route.algoritmo)}</div>
        <ol style="margin:6px 0 0;padding-left:20px;font-size:13.5px">${route.paradas.map((s) => `<li>${esc(s.alias)} (${esc(s.sector)}) · prioridad ${s.prioridad} · llega en ~${s.llegada_min} min</li>`).join("")}</ol></div>`;
      drawMap();
    } catch (err) { toast(err.message); }
  };

  async function refresh() {
    try {
      const sector = $("f-sector").value;
      const [d, r, al, ia] = await Promise.all([papi("/resumen"), papi(`/ninos${sector ? `?sector=${encodeURIComponent(sector)}` : ""}`), papi("/alertas"), papi("/ia")]);
      const cadena = ia.cadena.map((x) => `${esc(x.proveedor)} <span class="pill">${esc(x.circuito)}</span>`).join(" → ");
      const usos = Object.entries(ia.uso).map(([k, v]) => `<div>${esc(k)}: ${v.llamadas} llamadas (${v.errores} errores) · ${v.tokens_entrada + v.tokens_salida} tokens · US$ ${v.costo_usd.toFixed(4)} · ~US$ ${v.costo_promedio_por_llamada_usd.toFixed(5)} por llamada · ${v.latencia_promedio_s} s</div>`).join("");
      $("ia").innerHTML = `<div>Cadena: ${cadena}</div>${usos || "<div>Sin llamadas a IA externa desde el último reinicio.</div>"}<div><b>Costo total estimado: US$ ${ia.costo_total_usd.toFixed(4)}</b></div>`;
      rows = r;
      const k = [[d.ninos, "Niños en seguimiento"], [`${d.adherencia_promedio}%`, "Adherencia promedio al suplemento (14 d)"],
        [d.alta_prioridad, "Prioridad alta (≥ 60)"], [d.controles_vencidos, "Controles vencidos"],
        [`${d.platos_con_hierro_pct}%`, "Platos con hierro esta semana (≥ 60 pts)"], [d.comidas_semana, "Comidas registradas (7 d)"]];
      $("kpis").innerHTML = k.map(([v, l]) => `<div class="card kpi"><div class="v">${esc(v)}</div><div class="l">${esc(l)}</div></div>`).join("");
      const max = Math.max(1, ...d.riesgo_por_sector.map((s) => s.riesgo_promedio));
      $("sectores").innerHTML = d.riesgo_por_sector.map((s) => `<div class="bar"><span>${esc(s.sector)}</span><div class="track"><div class="fill" style="width:${(100 * s.riesgo_promedio) / max}%"></div></div><span>${s.riesgo_promedio}</span></div>`).join("");
      const icon = { severa: "🩸", molestia: "⚠️", sin_suplemento: "💊" };
      $("eventos").innerHTML = al.slice(0, 15).map((a) => `<div>${icon[a.tipo]} <b>${esc(a.alias)}</b> (${esc(a.sector)}) · ${esc(a.detalle)} · ${esc(a.fecha)}</div>`).join("") || "Sin alertas.";
      renderKids(); drawMap();
    } catch (err) { toast(err.message); }
  }
  $("f-sector").onchange = () => { route = null; $("ruta-res").innerHTML = ""; refresh(); };
  await refresh();
})();
