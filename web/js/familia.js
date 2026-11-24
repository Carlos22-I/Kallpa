/* App familiar: ingreso por código, registro de comidas y suplemento, recetas y asistente. */
(async () => {
  const { api, toast, esc } = Kallpa;
  const $ = (id) => document.getElementById(id);
  const cfg = await api("/api/config");
  $("n-sector").innerHTML = cfg.sectores.map((s) => `<option>${esc(s.nombre)}</option>`).join("");
  // Solo menores de 5 años: el rango se calcula con la fecha de hoy, así se actualiza solo cada día.
  const isoLocal = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const hoy = new Date();
  $("n-nac").max = isoLocal(hoy);
  $("n-nac").min = isoLocal(new Date(hoy.getFullYear() - 5, hoy.getMonth(), hoy.getDate() + 1));
  let code = null, file = null, data = null;
  try { code = localStorage.getItem("kallpa_codigo"); } catch (_) { }
  const qs = new URLSearchParams(location.search).get("codigo");
  if (qs) code = qs.toUpperCase();

  /* ---------- ingreso ---------- */
  const tab = (nuevo) => {
    $("f-nuevo").hidden = !nuevo; $("f-codigo").hidden = nuevo;
    $("t-nuevo").className = nuevo ? "btn" : "btn sec"; $("t-codigo").className = nuevo ? "btn sec" : "btn";
  };
  $("t-codigo").onclick = () => tab(false);
  $("t-nuevo").onclick = () => tab(true);
  $("f-codigo").onsubmit = async (e) => { e.preventDefault(); await enter($("codigo").value.trim().toUpperCase()); };
  $("f-nuevo").onsubmit = async (e) => {
    e.preventDefault();
    try {
      const r = await api("/api/familias", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ alias: $("n-alias").value, nacimiento: $("n-nac").value, sector: $("n-sector").value,
          cuidador: $("n-cuid").value, consentimiento: $("n-ok").checked }),
      });
      toast(`Tu código es ${r.codigo}. ¡Anótalo!`);
      await enter(r.codigo);
    } catch (err) { toast(err.message); }
  };
  $("salir").onclick = (e) => { e.preventDefault(); try { localStorage.removeItem("kallpa_codigo"); } catch (_) { } location.href = "/"; };

  async function enter(c) {
    try {
      data = await api(`/api/familias/${encodeURIComponent(c)}`);
      code = c;
      try { localStorage.setItem("kallpa_codigo", c); } catch (_) { }
      $("v-login").hidden = true; $("v-app").hidden = false; $("salir").hidden = false;
      render();
    } catch (err) { toast(err.message); }
  }

  /* ---------- render ---------- */
  function render() {
    const n = data.nino;
    const pct = data.referencia_hierro_mg ? Math.min(100, Math.round((100 * data.hierro_hoy_mg) / data.referencia_hierro_mg)) : 0;
    $("kpis").innerHTML = `
      <div class="card kpi"><div class="l">Niño/a</div><div class="v">${esc(n.alias)}</div><div class="l">${data.edad_meses} meses · ${esc(n.sector)} · código <b>${esc(n.codigo)}</b></div></div>
      <div class="card kpi"><div class="l">Hierro de las comidas hoy</div><div class="v">${data.hierro_hoy_mg} <small style="font-size:14px">/ ${data.referencia_hierro_mg} mg</small></div>
        <div class="gauge"><span style="width:${pct}%"></span></div><div class="l">${pct}% de la referencia diaria</div></div>
      <div class="card kpi"><div class="l">Suplemento (14 días)</div><div class="v">${data.adherencia_14d}%</div><div class="l">${data.suplemento_hoy ? "✅ Hoy ya le diste" : "⏰ Falta registrar hoy"}</div></div>
      <div class="card kpi"><div class="l">Estado (según el establecimiento)</div><div class="v"><span class="pill hb-${n.estado_hb}" style="font-size:15px">${esc(n.estado_hb_texto)}</span></div>
        <div class="l">${n.proximo_control ? `Próximo control: ${esc(n.proximo_control)}` : "Sin control programado"} ${data.control_vencido ? "· <b style='color:#b3261e'>vencido</b>" : ""}</div></div>`;
    $("esquema").innerHTML = n.esquema_suplemento ? `Indicación registrada: <b>${esc(n.esquema_suplemento)}</b>` : "El establecimiento aún no registró un esquema. Si te dieron suplemento, igual puedes marcarlo.";
    const max = Math.max(data.referencia_hierro_mg || 7, ...data.semana.map((d) => d.hierro_mg));
    $("week").innerHTML = data.semana.map((d) => {
      const dia = new Date(d.dia + "T12:00:00").toLocaleDateString("es-PE", { weekday: "short" });
      return `<div class="col"><span>${d.hierro_mg}</span><div class="b" style="height:${(70 * d.hierro_mg) / max}%"></div><span>${dia}</span><span class="pill-s">${d.suplemento ? "💊" : "·"}</span></div>`;
    }).join("");
    $("recetas").innerHTML = data.recetas.map((r) => `
      <div class="recipe"><b>${esc(r.nombre)}</b> <span class="pill">~${r.hierro_mg} mg de hierro</span> <span class="pill sev-1">desde ${r.edad_min_meses} meses</span>
        <div class="muted" style="margin:4px 0">${esc(r.ingredientes_nombres.join(", "))} · acompaña con ${esc(r.acompanar_nombre)}</div>
        <div style="font-size:14px">${esc(r.pasos)}</div></div>`).join("") || '<p class="muted">Sin recetas para esta edad.</p>';
  }

  function mealCard(m) {
    const cls = m.estado === "revisar" ? "warn" : m.estado === "descartada_privacidad" ? "err" : "";
    const status = { registrada: "", revisar: "⚠️ La IA no está muy segura: revisa que los alimentos sean correctos.",
      descartada_privacidad: "🔒 En la foto aparecía una persona: la foto no se guardó. Toma la foto solo del plato." }[m.estado];
    return `<div class="result ${cls}">
      <div class="row"><span class="score-badge" style="color:${m.puntaje >= 70 ? "#2e7d32" : m.puntaje >= 40 ? "#8a6100" : "#b3261e"}">${m.puntaje}/100</span>
        <div><b>Plato con hierro</b><div class="muted">~${m.hierro_total_mg} mg de hierro (${m.hierro_hemo_mg} mg de origen animal)</div></div></div>
      ${status ? `<p><b>${status}</b></p>` : ""}
      <div style="margin-top:8px">${m.alimentos.map((a) => `<div class="food"><span>${a.origen_animal ? "🥩" : "🌿"} ${esc(a.nombre)} · ${a.gramos} g</span><b>${a.hierro_mg} mg</b></div>`).join("") || '<span class="muted">No se reconocieron alimentos.</span>'}</div>
      <ul class="muted" style="padding-left:18px">${m.razones.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>
      ${m.consejos.length ? `<b>Para mejorar:</b><ul style="padding-left:18px;margin:4px 0">${m.consejos.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>` : "<b>¡Excelente plato! 💪</b>"}
      <div class="muted" style="margin-top:6px">Confianza de la IA: ${Math.round(m.confianza * 100)}% · ${esc(m.proveedor)}</div>
      <div class="conf-bar"><span style="width:${Math.round(m.confianza * 100)}%"></span></div>
    </div>`;
  }

  /* ---------- comida ---------- */
  $("drop").onclick = () => $("foto").click();
  $("drop").onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") $("foto").click(); };
  $("foto").onchange = () => {
    file = $("foto").files[0] || null;
    if (file) { $("preview").src = URL.createObjectURL(file); $("preview").hidden = false; $("drop-txt").hidden = true; }
  };
  async function compress(f) {
    try {
      const bmp = await createImageBitmap(f);
      const s = Math.min(1, 1024 / Math.max(bmp.width, bmp.height));
      const cv = document.createElement("canvas"); cv.width = bmp.width * s; cv.height = bmp.height * s;
      cv.getContext("2d").drawImage(bmp, 0, 0, cv.width, cv.height);
      return await new Promise((r) => cv.toBlob((b) => r(new File([b], "plato.jpg", { type: "image/jpeg" })), "image/jpeg", 0.8));
    } catch (_) { return f; }
  }
  $("f-comida").onsubmit = async (e) => {
    e.preventDefault();
    if (!file && !$("desc").value.trim()) return toast("Toma una foto o describe la comida.");
    const fd = new FormData();
    fd.append("descripcion", $("desc").value);
    if (file) fd.append("foto", await compress(file));
    $("b-comida").disabled = true; $("b-comida").textContent = "Analizando con IA…";
    try {
      const m = await api(`/api/familias/${code}/comidas`, { method: "POST", body: fd });
      $("r-comida").innerHTML = mealCard(m);
      $("f-comida").reset(); file = null; $("preview").hidden = true; $("drop-txt").hidden = false;
      data = await api(`/api/familias/${code}`); render();
    } catch (err) { $("r-comida").innerHTML = `<div class="result err">${esc(err.message)}</div>`; }
    $("b-comida").disabled = false; $("b-comida").textContent = "Calcular hierro";
  };

  /* ---------- suplemento ---------- */
  async function sup(dado) {
    try {
      const r = await api(`/api/familias/${code}/suplemento`, { method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ dado, nota: $("sup-nota").value }) });
      toast(r.molestia_reportada ? "Registrado. Avisamos al personal de salud sobre la molestia." : dado ? "¡Bien! Registrado 💪" : "Registrado. Mañana no lo olvides.");
      $("sup-nota").value = "";
      data = await api(`/api/familias/${code}`); render();
    } catch (err) { toast(err.message); }
  }
  $("sup-si").onclick = () => sup(true);
  $("sup-no").onclick = () => sup(false);

  /* ---------- asistente ---------- */
  $("f-chat").onsubmit = async (e) => {
    e.preventDefault();
    const q = $("preg").value.trim(); if (!q) return;
    const send = $("f-chat").querySelector("button");
    $("chat").insertAdjacentHTML("beforeend", `<div class="msg yo">${esc(q)}</div>`); $("preg").value = "";
    // Indicador mientras responde la IA (puede tardar varios segundos con señal débil)
    const typing = document.createElement("div");
    typing.className = "msg bot typing"; typing.setAttribute("role", "status");
    typing.innerHTML = 'Kallpa está pensando<span class="dots"><i></i><i></i><i></i></span>';
    $("chat").appendChild(typing); $("chat").scrollTop = $("chat").scrollHeight;
    $("preg").disabled = true; send.disabled = true; send.textContent = "Esperando…";
    try {
      const r = await api("/api/asistente", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ pregunta: q, codigo: code }) });
      typing.outerHTML = `<div class="msg bot">${esc(r.respuesta)}<span class="prov">${esc(r.proveedor)}</span></div>`;
    } catch (err) { typing.outerHTML = `<div class="msg bot">${esc(err.message)}</div>`; }
    $("preg").disabled = false; send.disabled = false; send.textContent = "Enviar"; $("preg").focus();
    $("chat").scrollTop = $("chat").scrollHeight;
  };

  if (code) await enter(code);
  else $("demo-hint").textContent = "Demo: usa el código K-DEMO1 o regístrate.";
})();
