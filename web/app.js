/* ============================================================
   POLARIS — Procurement-Oriented Listing of Applicable References
   in Indian Standards · Team ATLAS · SIH 2026 · PS SIH26108
   frontend logic (vanilla JS, zero deps)
   ============================================================ */
"use strict";

const $ = (id) => document.getElementById(id);
const LW = 1100, LH = 560;

/* ---------------- tiny helpers ---------------- */
function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function toast(msg) {
  let t = $("toast");
  if (!t) {
    t = document.createElement("div");
    t.id = "toast";
    document.body.appendChild(t);
  }
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.remove("show"), 2600);
}

async function api(path, body) {
  const opts = body !== undefined
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
    : {};
  const res = await fetch(path, opts);
  if (!res.ok) {
    let msg = res.status + " " + res.statusText;
    try { msg = (await res.json()).error || msg; } catch (e) {}
    throw new Error(msg);
  }
  return res.json();
}

/* ---------------- views (tabs) ---------------- */
function go(view) {
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
  $("view-" + view).classList.add("active");
  document.querySelectorAll("#tabs .tab").forEach((t) =>
    t.classList.toggle("active", t.dataset.view === view));
  if (view === "map" && LAST) Graph.render(LAST.graph);
  if (view === "report" && LAST) loadReport();
  window.scrollTo({ top: 0 });
}
document.querySelectorAll("#tabs .tab").forEach((t) =>
  t.addEventListener("click", () => go(t.dataset.view)));

/* ---------------- input mode switching ---------------- */
document.querySelectorAll(".input-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".input-tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    document.querySelectorAll(".input-panel").forEach((p) => p.classList.remove("active"));
    $("panel-" + tab.dataset.input).classList.add("active");
  });
});
function currentInputText() {
  const active = document.querySelector(".input-tab.active").dataset.input;
  if (active === "voice") return $("voiceText").value.trim();
  return $("inputText").value.trim();
}

/* ---------------- health ping ---------------- */
(async function ping() {
  try {
    await api("/api/health");
    $("healthDot").classList.add("ok");
    $("healthText").textContent = "Ready";
  } catch (e) {
    $("healthDot").classList.add("err");
    $("healthText").textContent = "Server offline — run: python server.py";
  }
})();

/* ---------------- demo texts ---------------- */
const DEMOS = [
  "Supply of high tensile deformed steel bars Fe 500D grade (TMT) conforming to IS 1786:2008 for reinforcement of RCC works, together with ordinary portland cement, coarse and fine aggregates, ready mixed concrete M25 and concrete cube compressive strength tests.",
  "सड़क निर्माण कार्य के लिए सीमेंट, सरिया, बालू और ईंट की आपूर्ति करनी है। पानी की लाइन के लिए PVC पाइप भी चाहिए और बिजली के केबल तार।",
  "Structural steel sections as per IS 2062:2006, MS tubes per IS 1239:1991, PVC insulated cables per IS 694:1990 and common burnt clay bricks per IS 1077:1992. Tensile testing and chemical analysis required.",
];
function fillDemo(i) {
  $("inputText").value = DEMOS[i];
  document.querySelector('.input-tab[data-input="type"]').click();
  $("inputText").focus();
}

/* ---------------- analysis ---------------- */
let LAST = null;

async function runAnalysis() {
  const text = currentInputText();
  if (!text) { toast("Add a specification first — type, upload, photo or voice."); return; }
  const btn = $("analyzeBtn");
  btn.disabled = true; btn.textContent = "⏳ Analyzing…";
  try {
    LAST = await api("/api/recommend", { text });
    renderAll(LAST);
    $("results").classList.remove("hidden");
    $("elapsed").textContent = "Analyzed in " + LAST.elapsed_ms + " ms";
    $("results").scrollIntoView({ behavior: "smooth", block: "start" });
    toast("Analysis complete — check the Standards Map or generate a Report.");
  } catch (e) {
    toast("Analysis failed: " + e.message);
  } finally {
    btn.disabled = false; btn.textContent = "⚡ Analyze Specification";
  }
}

function renderAll(a) {
  renderHealth(a);
  renderRecs(a);
  renderVersions(a);
  renderCerts(a);
  renderGaps(a);
  Graph.render(a.graph);
}

function renderHealth(a) {
  const s = a.spec_health;
  const C = 326.7;
  $("scoreRing").style.strokeDashoffset = C * (1 - s.score / 100);
  $("scoreRing").style.stroke = s.score >= 85 ? "#2fd28a" : s.score >= 60 ? "#ffb454" : "#ff6b6b";
  animateNum($("scoreNum"), s.score);
  $("healthVerdict").textContent = s.verdict;
  const d = s.detail;
  $("mPrim").textContent = (d.primary_cited || 0) + "/" + (d.primary_expected || 0);
  $("mAllied").textContent = (d.allied_cited || 0) + "/" + (d.allied_expected || 0);
  $("mGaps").textContent = a.coverage.gap_codes.length;
  $("mMs").textContent = a.elapsed_ms;
  const mand = a.certifications.filter((c) => c.mandatory).length;
  const outdated = a.versions.filter((v) => v.status === "outdated").length;
  $("quickChips").innerHTML =
    `<span class="chip red">${outdated} outdated citation${outdated === 1 ? "" : "s"}</span>` +
    `<span class="chip amber">${mand} mandatory certification${mand === 1 ? "" : "s"}</span>` +
    `<span class="chip blue">${a.graph.nodes.length} standards in graph</span>`;
}

function animateNum(el, target) {
  const t0 = performance.now(), dur = 800, from = 0;
  function step(t) {
    const p = Math.min(1, (t - t0) / dur);
    el.textContent = Math.round(from + (target - from) * (1 - Math.pow(1 - p, 3)));
    if (p < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

function renderRecs(a) {
  const prim = new Set(a.primary_codes || []);
  const sorted = [...a.recommendations].sort((x, y) => y.score - x.score);
  $("recList").innerHTML = sorted.map((r) => `
    <div class="rec-item">
      <div>
        <div class="code">${esc(r.code)}${prim.has(r.code) ? ' <span class="primary-badge">PRIMARY</span>' : ""}</div>
        <div class="title">${esc(r.title)}</div>
        <div class="meta">${esc(r.category)} · ${esc(r.kind)}${r.via ? " · " + esc(r.via) : ""}</div>
      </div>
      <span class="score-pill">${(r.score * 100).toFixed(0)}%</span>
    </div>`).join("") || '<p class="empty">No standards matched — try adding more specific material or product keywords.</p>';
}

function renderVersions(a) {
  $("verList").innerHTML = a.versions.map((v) => `
    <div class="ver-item">
      <span class="code">${esc(v.code)}</span>
      <span class="tag ${esc(v.status)}">${esc(v.status.replace(/-/g, " "))}</span>
      <div class="advice">${esc(v.advice)}</div>
    </div>`).join("");
  $("verEmpty").style.display = a.versions.length ? "none" : "block";
}

function renderCerts(a) {
  $("certList").innerHTML = a.certifications.map((c) => `
    <div class="cert-item">
      <span class="code">${esc(c.code)}</span>
      <span class="scheme">${esc(c.scheme)}</span>
      ${c.mandatory ? '<span class="cert-mand">MANDATORY</span>' : '<span class="cert-vol">voluntary</span>'}
    </div>`).join("") || '<p class="empty">No certification data for these standards.</p>';
}

function renderGaps(a) {
  const gaps = a.coverage.gap_codes;
  const idx = {};
  a.graph.nodes.forEach((n) => (idx[n.code] = n));
  $("gapList").innerHTML = gaps.map((c) => {
    const n = idx[c] || {};
    return `<div class="gap-item">
      <span class="code">${esc(c)}</span>
      <span>${esc(n.title || "")}</span>
      <span class="kind">${esc(n.kind || "")}</span>
    </div>`;
  }).join("");
  $("gapEmpty").style.display = gaps.length ? "none" : "block";
}

/* ============================================================
   FILE UPLOAD (.txt / .pdf)
   ============================================================ */
const dz = $("dropzone");
dz.addEventListener("click", () => $("fileInput").click());
dz.addEventListener("dragover", (e) => { e.preventDefault(); dz.classList.add("drag"); });
dz.addEventListener("dragleave", () => dz.classList.remove("drag"));
dz.addEventListener("drop", (e) => {
  e.preventDefault(); dz.classList.remove("drag");
  if (e.dataTransfer.files[0]) uploadFile(e.dataTransfer.files[0]);
});
$("fileInput").addEventListener("change", (e) => {
  if (e.target.files[0]) uploadFile(e.target.files[0]);
});

async function uploadFile(file) {
  const st = $("uploadStatus");
  st.innerHTML = "⏳ Extracting text from <b>" + esc(file.name) + "</b>… (this may take a moment for large files)";
  try {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch("/api/extract", { method: "POST", body: fd });
    const r = await res.json();
    if (!res.ok) throw new Error(r.error || res.statusText);
    $("inputText").value = r.text;
    let msg = "✅ Extracted <b>" + r.chars + "</b> characters from " + esc(file.name);
    if (r.truncated) {
      msg += " — document is " + r.full_chars.toLocaleString() + " chars; " +
             "<b>auto-focused on the key specification sections for best results.";
    }
    msg += " Review the text below, then hit <b>Analyze</b>.";
    st.innerHTML = msg;
    document.querySelector('.input-tab[data-input="type"]').click();
    toast("File loaded — hit Analyze when ready.");
  } catch (e) {
    st.innerHTML = "❌ " + esc(e.message);
  }
}

/* ============================================================
   IN-BROWSER OCR — image/photo of a document (zero deps, honest)
   1) binarize (Otsu) 2) connected components = glyphs
   3) normalize each glyph to 16x24 4) match vs runtime-generated
   templates of a clean sans font 5) emit text with spaces/newlines
   ============================================================ */
const OCR = (() => {
  const CW = 16, CH = 24;
  const CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,:;-()&/%".split("");
  let TPL = null;

  function binarize(imgData) {
    const d = imgData.data, n = d.length / 4;
    const gray = new Uint8Array(n);
    const hist = new Array(256).fill(0);
    for (let i = 0; i < n; i++) {
      const g = (d[i * 4] * 299 + d[i * 4 + 1] * 587 + d[i * 4 + 2] * 114) / 1000;
      gray[i] = g;
      hist[g | 0]++;
    }
    // Otsu threshold
    let sum = 0; for (let i = 0; i < 256; i++) sum += i * hist[i];
    let sumB = 0, wB = 0, best = 0, thr = 128;
    for (let t = 0; t < 256; t++) {
      wB += hist[t]; if (!wB) continue;
      const wF = n - wB; if (!wF) break;
      sumB += t * hist[t];
      const mB = sumB / wB, mF = (sum - sumB) / wF;
      const between = wB * wF * (mB - mF) * (mB - mF);
      if (between > best) { best = between; thr = t; }
    }
    const bin = new Uint8Array(n); // 1 = ink (dark)
    let dark = 0;
    for (let i = 0; i < n; i++) { bin[i] = gray[i] < thr ? 1 : 0; dark += bin[i]; }
    if (dark > n * 0.5) for (let i = 0; i < n; i++) bin[i] ^= 1; // light text on dark
    return bin;
  }

  function components(bin, w, h) {
    const seen = new Uint8Array(w * h);
    const comps = [];
    const stack = new Int32Array(w * h);
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const p = y * w + x;
        if (!bin[p] || seen[p]) continue;
        let top = 0; stack[top++] = p; seen[p] = 1;
        let minx = x, maxx = x, miny = y, maxy = y, count = 0;
        while (top) {
          const q = stack[--top]; count++;
          const qx = q % w, qy = (q / w) | 0;
          if (qx < minx) minx = qx; if (qx > maxx) maxx = qx;
          if (qy < miny) miny = qy; if (qy > maxy) maxy = qy;
          for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
            const nx = qx + dx, ny = qy + dy;
            if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
            const np = ny * w + nx;
            if (bin[np] && !seen[np]) { seen[np] = 1; stack[top++] = np; }
          }
          if (count > 20000) break;
        }
        const cw = maxx - minx + 1, chh = maxy - miny + 1;
        if (count < 12 || cw > w * 0.8 || chh > h * 0.8) continue;
        if (chh < 4 || cw < 1) continue;
        comps.push({ x: minx, y: miny, w: cw, h: chh, count });
      }
    }
    return comps;
  }

  function normalize(bin, w, comp) {
    const out = new Float32Array(CW * CH);
    for (let ty = 0; ty < CH; ty++) {
      for (let tx = 0; tx < CW; tx++) {
        const sx = comp.x + Math.floor((tx * comp.w) / CW);
        const sy = comp.y + Math.floor((ty * comp.h) / CH);
        out[ty * CW + tx] = bin[sy * w + sx] ? 1 : 0;
      }
    }
    return out;
  }

  function buildTemplates() {
    TPL = {};
    const cv = document.createElement("canvas");
    cv.width = 64; cv.height = 96;
    const cx = cv.getContext("2d", { willReadFrequently: true });
    for (const ch of CHARS) {
      cx.fillStyle = "#fff"; cx.fillRect(0, 0, 64, 96);
      cx.fillStyle = "#000";
      cx.font = "bold 72px Arial, sans-serif";
      cx.textBaseline = "middle";
      cx.fillText(ch, 8, 52);
      const img = cx.getImageData(0, 0, 64, 96);
      const bin = binarize(img);
      const comps = components(bin, 64, 96);
      if (!comps.length) continue;
      // biggest component
      comps.sort((a, b) => b.count - a.count);
      TPL[ch] = normalize(bin, 64, comps[0]);
    }
  }

  function similarity(a, b) {
    let s = 0;
    for (let i = 0; i < a.length; i++) s += a[i] === b[i] ? 1 : 0;
    return s / a.length;
  }

  function recognize(img) {
    if (!TPL) buildTemplates();
    // downscale if huge
    let w = img.width, h = img.height;
    const maxW = 1400;
    const scale = w > maxW ? maxW / w : 1;
    w = Math.round(w * scale); h = Math.round(h * scale);
    const cv = $("ocrCanvas");
    cv.width = w; cv.height = h;
    const cx = cv.getContext("2d", { willReadFrequently: true });
    cx.fillStyle = "#fff"; cx.fillRect(0, 0, w, h);
    cx.drawImage(img, 0, 0, w, h);
    const bin = binarize(cx.getImageData(0, 0, w, h));
    let comps = components(bin, w, h);
    if (!comps.length) return "";
    // group into lines by vertical overlap
    comps.sort((a, b) => a.y - b.y || a.x - b.x);
    const lines = [];
    for (const c of comps) {
      const line = lines.find((L) => {
        const mid = (L.y0 + L.y1) / 2;
        return c.y < L.y1 * 0.75 + mid * 0.25 && c.y + c.h > mid;
      });
      if (line) { line.items.push(c); line.y0 = Math.min(line.y0, c.y); line.y1 = Math.max(line.y1, c.y + c.h); }
      else lines.push({ y0: c.y, y1: c.y + c.h, items: [c] });
    }
    lines.sort((a, b) => a.y0 - b.y0);
    const outLines = [];
    for (const L of lines) {
      L.items.sort((a, b) => a.x - b.x);
      const heights = L.items.map((i) => i.h).sort((a, b) => a - b);
      const medH = heights[Math.floor(heights.length / 2)];
      let text = "", prev = null;
      for (const c of L.items) {
        if (c.h < medH * 0.35 || c.w < 2) continue; // noise/dots
        if (prev) {
          const gap = c.x - (prev.x + prev.w);
          if (gap > Math.max(6, medH * 0.45)) text += " ";
        }
        const v = normalize(bin, w, c);
        let bestCh = "?", bestS = 0;
        for (const ch of CHARS) {
          if (!TPL[ch]) continue; // glyph produced no template at runtime
          const s = similarity(v, TPL[ch]);
          if (s > bestS) { bestS = s; bestCh = ch; }
        }
        text += bestS >= 0.62 ? bestCh : "?";
        prev = c;
      }
      if (text.trim()) outLines.push(text.trim());
    }
    return outLines.join("\n");
  }

  return { recognize, warmup: () => { if (!TPL) buildTemplates(); } };
})();

// pre-build OCR glyph templates in the background so the first
// image recognition is instant when the user needs it
setTimeout(() => { try { OCR.warmup(); } catch (e) {} }, 1200);

$("imgInput").addEventListener("change", (e) => {
  const f = e.target.files[0];
  if (f) ocrFile(f);
});
const iz = $("imgzone");
iz.addEventListener("click", () => $("imgInput").click());
iz.addEventListener("dragover", (e) => { e.preventDefault(); iz.classList.add("drag"); });
iz.addEventListener("dragleave", () => iz.classList.remove("drag"));
iz.addEventListener("drop", (e) => {
  e.preventDefault(); iz.classList.remove("drag");
  if (e.dataTransfer.files[0]) ocrFile(e.dataTransfer.files[0]);
});

function ocrFile(file) {
  const st = $("imgStatus");
  if (!file.type.startsWith("image/")) { st.innerHTML = "❌ Please choose a PNG/JPG image."; return; }
  st.innerHTML = "⏳ Reading image &amp; running in-browser OCR…";
  const img = new Image();
  img.onload = () => {
    setTimeout(() => {
      try {
        const t0 = performance.now();
        const text = OCR.recognize(img);
        const ms = Math.round(performance.now() - t0);
        if (!text.trim()) {
          st.innerHTML = "❌ No text found. Try a clearer, higher-resolution photo of printed text.";
          return;
        }
        $("inputText").value = text;
        st.innerHTML = "✅ OCR done in " + ms + " ms — <b>" + text.length + "</b> characters recognized. " +
          "Check the text below and fix anything that looks off, then hit <b>Analyze</b>.";
        document.querySelector('.input-tab[data-input="type"]').click();
        toast("OCR done — check the text below and hit Analyze.");
      } catch (err) {
        st.innerHTML = "❌ OCR failed: " + esc(err.message);
      }
    }, 30);
  };
  img.onerror = () => { st.innerHTML = "❌ Could not read that image file."; };
  const rd = new FileReader();
  rd.onload = (ev) => { img.src = ev.target.result; };
  rd.readAsDataURL(file);
}

/* ============================================================
   VOICE INPUT (browser speech recognition)
   ============================================================ */
(function initVoice() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const btn = $("micBtn");
  window.setVoiceLang = function (code) {
    VOICE_LANG = code;
    $("langHi").classList.toggle("active-lang", code === "hi-IN");
    $("langEn").classList.toggle("active-lang", code === "en-IN");
    $("voiceStatus").textContent = (code === "hi-IN" ? "Hindi (हिन्दी)" : "English") +
      " selected — speak after clicking Start.";
  };
  let VOICE_LANG = "hi-IN";
  if (!SR) {
    btn.disabled = true;
    btn.textContent = "🎙️ Not supported in this browser";
    $("voiceStatus").textContent = "Voice needs Chrome or Edge (Web Speech API). Other input modes work everywhere.";
    return;
  }
  let rec = null, listening = false;
  btn.addEventListener("click", () => {
    if (listening) { rec.stop(); return; }
    rec = new SR();
    rec.lang = VOICE_LANG;
    rec.interimResults = false;
    rec.continuous = true;
    rec.onstart = () => { listening = true; btn.textContent = "🔴 Listening… (click to stop)"; };
    rec.onerror = (ev) => {
      $("voiceStatus").textContent = "Mic error: " + ev.error +
        (ev.error === "not-allowed" ? " — allow microphone access and retry." : ".");
      listening = false; btn.textContent = "🎙️ Start listening";
    };
    rec.onend = () => { listening = false; btn.textContent = "🎙️ Start listening"; };
    rec.onresult = (ev) => {
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        if (ev.results[i].isFinal) {
          const t = ev.results[i][0].transcript.trim();
          $("voiceText").value = ($("voiceText").value + " " + t).trim();
        }
      }
    };
    try { rec.start(); $("voiceStatus").textContent = "Listening in हिन्दी — go ahead and speak."; }
    catch (e) { $("voiceStatus").textContent = "Could not start: " + e.message; }
  });
})();

/* ============================================================
   ASSISTANT (chat)
   ============================================================ */
async function sendChat() {
  const inp = $("chatInput");
  const q = inp.value.trim();
  if (!q) return;
  inp.value = "";
  await askStream(q);
}
function askChip(q) { go("assistant"); $("chatInput").value = q; sendChat(); }

async function askStream(q) {
  const log = $("chatLog");
  log.insertAdjacentHTML("beforeend", `<div class="msg user">${esc(q)}</div>`);
  log.insertAdjacentHTML("beforeend", '<div class="msg bot" id="chatWait">On it…</div>');
  log.scrollTop = log.scrollHeight;
  try {
    const r = await api("/api/chat", { question: q });
    $("chatWait").remove();
    const cites = (r.cited || [])
      .map((c) => `<span class="cites">🔗 ${esc(c.code)} — ${esc(c.why)}</span>`).join("<br>");
    log.insertAdjacentHTML("beforeend",
      `<div class="msg bot">${esc(r.answer).replace(/\n/g, "<br>")}${cites ? "<br>" + cites : ""}</div>`);
  } catch (e) {
    $("chatWait").remove();
    log.insertAdjacentHTML("beforeend", `<div class="msg bot">Error: ${esc(e.message)}</div>`);
  }
  log.scrollTop = log.scrollHeight;
}

/* ============================================================
   STANDARDS LIBRARY
   ============================================================ */
let CORPUS_CACHE = null;
(async function loadCorpus() {
  try {
    const r = await api("/api/corpus");
    CORPUS_CACHE = r.records;
    $("libCount").textContent = r.size + " standards";
    const cats = [...new Set(r.records.map((x) => x.category))].sort();
    $("libCat").innerHTML = '<option value="">All categories</option>' +
      cats.map((c) => `<option>${esc(c)}</option>`).join("");
    renderLibrary();
  } catch (e) { /* server offline */ }
})();

function renderLibrary() {
  if (!CORPUS_CACHE) return;
  const q = $("libSearch").value.trim().toLowerCase();
  const cat = $("libCat").value;
  const kind = $("libKind").value;
  const items = CORPUS_CACHE.filter((r) => {
    if (cat && r.category !== cat) return false;
    if (kind && r.kind !== kind) return false;
    if (!q) return true;
    const hay = (r.code + " " + r.num + " " + r.title + " " + r.scope + " " + r.category).toLowerCase();
    return q.split(/\s+/).every((w) => hay.includes(w));
  });
  const prim = LAST ? new Set(LAST.primary_codes) : new Set();
  $("libList").innerHTML = items.map((r) => `
    <details class="lib-item">
      <summary>
        <span class="code">${esc(r.code)}</span>
        <span class="title">${esc(r.title)}</span>
        ${prim.has(r.code) ? '<span class="primary-badge">PRIMARY</span>' : ""}
        ${r.cert.mandatory ? '<span class="tag outdated">MANDATORY CERT</span>' : ""}
        <span class="kind">${esc(r.kind)} · Ed ${r.edition}</span>
      </summary>
      <div class="lib-detail">
        <p><b>Category:</b> ${esc(r.category)}</p>
        <p><b>Scope (summary):</b> ${esc(r.scope)}</p>
        <p><b>Edition:</b> ${r.edition} · <b>Amendments:</b> ${r.amendments.length ? esc(r.amendments.join(", ")) : "none"}</p>
        <p><b>Certification:</b> ${esc(r.cert.scheme)} — ${esc(r.cert.basis)}</p>
        <p><b>Normative references:</b> ${r.refs.length
          ? r.refs.map((x) => `<button class="chip blue" onclick="libFind('${esc(x).split("(")[0]}')">${esc(x)}</button>`).join(" ")
          : "<i>none</i>"}</p>
      </div>
    </details>`).join("") || '<p class="empty">No standards match those filters.</p>';
}
function libFind(code) {
  $("libSearch").value = code;
  $("libCat").value = ""; $("libKind").value = "";
  renderLibrary();
}

/* ============================================================
   REPORT VIEW
   ============================================================ */
async function loadReport() {
  if (!LAST) { toast("Run an analysis first, then come back here."); return; }
  const prev = $("reportPreview");
  prev.innerHTML = "<p class='empty'>Generating your report…</p>";
  try {
    const [repRaw, exp] = await Promise.all([
      fetch("/api/report").then((r) => r.text()),
      api("/api/export", { analysis: LAST }),
    ]);
    // The report endpoint returns a full standalone document with its own
    // <style> block (dark text on light background). Injecting that style
    // via innerHTML would restyle the WHOLE app — the "everything goes dark"
    // bug. Strip it; .report-preview CSS already styles the content.
    const rep = repRaw
      .replace(/<style>[\s\S]*?<\/style>/gi, "")
      .replace(/<p class="noprint">[\s\S]*?<\/p>/gi, "");
    prev.innerHTML =
      rep +
      "<h3 style='margin-top:26px'>Tender-ready specification block</h3>" +
      "<pre id='exportPre' style='background:#f5f7fb;border:1px solid #d7dfeb;border-radius:10px;padding:14px;font-size:12.5px;white-space:pre-wrap;color:#1c2740'>" +
      esc(exp.spec) + "</pre>" +
      "<div class='action-row'><button class='btn primary' onclick='copyExport()'>Copy block to clipboard</button></div>";
  } catch (e) {
    prev.innerHTML = "<p class='empty'>Report failed: " + esc(e.message) + "</p>";
  }
}
async function copyExport() {
  const txt = $("exportPre") ? $("exportPre").textContent : "";
  if (!txt) { toast("Nothing to copy — generate a report first."); return; }
  try { await navigator.clipboard.writeText(txt); toast("Copied to clipboard ✓"); }
  catch (e) {
    const ta = document.createElement("textarea");
    ta.value = txt; document.body.appendChild(ta); ta.select();
    document.execCommand("copy"); ta.remove();
    toast("Copied to clipboard ✓");
  }
}

/* ============================================================
   GRAPH EXPLORER — canvas radial layout, pan + zoom + tooltips
   ============================================================ */
const Graph = (() => {
  const canvas = $("graphCanvas");
  const ctx = canvas.getContext("2d");
  const tip = $("graphTip");
  let nodes = [], edges = [], view = { x: 0, y: 0, k: 1 };
  let drag = null, hovered = null;

  const COLORS = {
    "Product / Specification": "#6c8dbd",
    "Test Method": "#16a34a",
    "Terminology": "#7c3aed",
    "Safety": "#dc2626",
    "Code of Practice / Installation": "#d97706",
  };

  function resize() {
    const dpr = window.devicePixelRatio || 1;
    canvas.width = LW * dpr;
    canvas.height = LH * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function layout(graph) {
    nodes = graph.nodes.map((n) => ({ ...n, x: 0, y: 0 }));
    edges = graph.edges;
    const prim = nodes.filter((n) => n.depth === 0);
    prim.forEach((p, i) => {
      p.x = (LW * (i + 1)) / (prim.length + 1);
      p.y = LH / 2 + (i % 2 ? -30 : 30);
    });
    const byCode = {}; nodes.forEach((n) => (byCode[n.code] = n));
    const kids = {};
    edges.forEach((e) => {
      (kids[e.from] = kids[e.from] || []);
      if (!kids[e.from].includes(e.to)) kids[e.from].push(e.to);
    });
    const placed = new Set(prim.map((p) => p.code));
    prim.forEach((p, pi) => {
      const list = (kids[p.code] || []).filter((c) => !placed.has(c) && byCode[c]);
      const n = list.length || 1;
      const base = -Math.PI / 2 + (pi % 2 ? 0.55 : -0.55);
      list.forEach((c, j) => {
        const node = byCode[c];
        const ang = base + (j - (n - 1) / 2) * (2 * Math.PI / Math.max(n, 3));
        node.x = p.x + 200 * Math.cos(ang);
        node.y = p.y + 175 * Math.sin(ang);
        placed.add(c);
      });
    });
    nodes.filter((n) => n.depth === 2).forEach((n) => {
      const pe = edges.find((e) => e.to === n.code && byCode[e.from] && byCode[e.from].depth === 1);
      if (!pe) { n.x = LW / 2; n.y = 60; return; }
      const par = byCode[pe.from];
      const sibs = (kids[par.code] || []).filter((c) => byCode[c] && byCode[c].depth === 2);
      const idx = Math.max(0, sibs.indexOf(n.code));
      const up = par.y < LH / 2;
      const ang = (up ? -Math.PI / 2 : Math.PI / 2) + (idx - (sibs.length - 1) / 2) * 0.7;
      n.x = par.x + 150 * Math.cos(ang);
      n.y = par.y + 115 * Math.sin(ang);
    });
    for (let it = 0; it < 90; it++) {
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i], b = nodes[j];
          if (a.depth === 0 && b.depth === 0) continue;
          let dx = b.x - a.x, dy = b.y - a.y;
          let d2 = dx * dx + dy * dy;
          if (d2 < 1) { dx = Math.random() - 0.5; dy = Math.random() - 0.5; d2 = 1; }
          const minD = 64, d = Math.sqrt(d2);
          if (d < minD) {
            const push = (minD - d) / 2, ux = dx / d, uy = dy / d;
            const aFix = a.depth === 0, bFix = b.depth === 0;
            if (!aFix && !bFix) { a.x -= ux * push; a.y -= uy * push; b.x += ux * push; b.y += uy * push; }
            else if (!aFix) { a.x -= ux * push * 2; a.y -= uy * push * 2; }
            else if (!bFix) { b.x += ux * push * 2; b.y += uy * push * 2; }
          }
        }
      }
      nodes.forEach((n) => {
        if (n.depth === 0) return;
        n.x = Math.max(64, Math.min(LW - 64, n.x));
        n.y = Math.max(50, Math.min(LH - 50, n.y));
      });
    }
  }

  function nodeRadius(n) { return n.depth === 0 ? 28 : 17; }

  function draw() {
    ctx.clearRect(0, 0, LW, LH);
    ctx.save();
    ctx.translate(view.x, view.y);
    ctx.scale(view.k, view.k);
    edges.forEach((e) => {
      const a = nodes.find((n) => n.code === e.from), b = nodes.find((n) => n.code === e.to);
      if (!a || !b) return;
      const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
      const dx = b.x - a.x, dy = b.y - a.y;
      const cx = mx - dy * 0.12, cy = my + dx * 0.12;
      const hot = hovered && (hovered.code === e.from || hovered.code === e.to);
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.quadraticCurveTo(cx, cy, b.x, b.y);
      ctx.strokeStyle = hot ? "rgba(37,99,235,.85)" : "rgba(100,120,180,.2)";
      ctx.lineWidth = hot ? 2.2 : 1.2;
      ctx.stroke();
      const ang = Math.atan2(b.y - cy, b.x - cx);
      const r = nodeRadius(b);
      const ax = b.x - (r + 3) * Math.cos(ang), ay = b.y - (r + 3) * Math.sin(ang);
      ctx.beginPath();
      ctx.moveTo(ax, ay);
      ctx.lineTo(ax - 8 * Math.cos(ang - 0.4), ay - 8 * Math.sin(ang - 0.4));
      ctx.lineTo(ax - 8 * Math.cos(ang + 0.4), ay - 8 * Math.sin(ang + 0.4));
      ctx.closePath();
      ctx.fillStyle = "rgba(100,120,180,.55)";
      ctx.fill();
    });
    nodes.forEach((n) => {
      const r = nodeRadius(n);
      const color = COLORS[n.kind] || "#6c8dbd";
      ctx.beginPath();
      ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
      ctx.fillStyle = n.depth === 0 ? "#2563eb" : color;
      ctx.globalAlpha = hovered && hovered !== n ? 0.35 : 1;
      ctx.fill();
      if (n.cert_mandatory) {
        ctx.beginPath();
        ctx.arc(n.x, n.y, r + 4, 0, Math.PI * 2);
        ctx.strokeStyle = "#dc2626"; ctx.lineWidth = 2.2; ctx.setLineDash([4, 3]);
        ctx.stroke(); ctx.setLineDash([]);
      }
      if (hovered === n) {
        ctx.beginPath();
        ctx.arc(n.x, n.y, r + 6, 0, Math.PI * 2);
        ctx.strokeStyle = "#1a2340"; ctx.lineWidth = 1.5; ctx.stroke();
      }
      ctx.globalAlpha = 1;
      ctx.font = "600 11px IBM Plex Mono, monospace";
      ctx.textAlign = "center";
      ctx.fillStyle = n.depth === 0 ? "#fff" : "#1e293b";
      ctx.fillText(n.code, n.x, n.y + r + 14);
    });
    ctx.restore();
  }

  function toLogical(ev) {
    const rect = canvas.getBoundingClientRect();
    return {
      x: (ev.clientX - rect.left) * (LW / rect.width),
      y: (ev.clientY - rect.top) * (LH / rect.height),
    };
  }

  function pick(p) {
    for (const n of nodes) {
      const r = nodeRadius(n) + 4;
      const sx = n.x * view.k + view.x, sy = n.y * view.k + view.y;
      if ((p.x - sx) ** 2 + (p.y - sy) ** 2 <= r * r) return n;
    }
    return null;
  }

  function showTip(n, ev) {
    const wrapRect = $("graphWrap").getBoundingClientRect();
    tip.innerHTML = `<b>${esc(n.code)}</b><br>${esc(n.title)}<br>
      <span style="color:#8fa3c4">${esc(n.kind)} · Ed ${n.edition} · ${n.amendments.length} amendments</span><br>
      <span style="color:${n.cert_mandatory ? "#ff6b6b" : "#8fa3c4"}">${esc(n.cert_scheme)}</span>
      <br><i style="color:#4da3ff;font-size:.7rem">click node → ask the assistant why</i>`;
    tip.classList.remove("hidden");
    const x = ev.clientX - wrapRect.left + 14, y = ev.clientY - wrapRect.top + 14;
    tip.style.left = Math.min(x, wrapRect.width - 330) + "px";
    tip.style.top = Math.min(y, wrapRect.height - 130) + "px";
  }

  canvas.addEventListener("mousemove", (ev) => {
    const p = toLogical(ev);
    if (drag) {
      view.x += p.x - drag.x; view.y += p.y - drag.y;
      drag = { x: p.x, y: p.y };
      canvas.style.cursor = "grabbing";
      draw(); return;
    }
    const n = pick(p);
    if (n !== hovered) { hovered = n; draw(); }
    if (n) { showTip(n, ev); canvas.style.cursor = "pointer"; }
    else { tip.classList.add("hidden"); canvas.style.cursor = "grab"; }
  });
  canvas.addEventListener("mousedown", (ev) => {
    drag = { x: toLogical(ev).x, y: toLogical(ev).y };
  });
  window.addEventListener("mouseup", () => { drag = null; canvas.style.cursor = "grab"; });
  canvas.addEventListener("wheel", (ev) => {
    ev.preventDefault();
    const p = toLogical(ev);
    const wx = (p.x - view.x) / view.k, wy = (p.y - view.y) / view.k;
    const factor = ev.deltaY < 0 ? 1.12 : 1 / 1.12;
    view.k = Math.max(0.5, Math.min(2.6, view.k * factor));
    view.x = p.x - wx * view.k;
    view.y = p.y - wy * view.k;
    draw();
  }, { passive: false });
  canvas.addEventListener("mouseleave", () => { tip.classList.add("hidden"); hovered = null; draw(); });
  canvas.addEventListener("click", (ev) => {
    const n = pick(toLogical(ev));
    if (n) {
      go("assistant");
      $("chatInput").value = "Why is " + n.code + " recommended?";
      sendChat();
    }
  });

  return {
    render(graph) {
      resize();
      view = { x: 0, y: 0, k: 1 };
      layout(graph);
      draw();
    },
  };
})();
