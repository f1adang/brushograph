/* Brushograph WebUI */
(() => {
"use strict";

const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text != null) node.textContent = text;
  return node;
};
const configSelect = $("machine-config");
const configFile = $("machine-config-file");
const container = $("options-form-container");

let machineConfigName = null;
let machineConfigMode = null;
let sketchUrl = null;
let sketchSeq = 0;

const showCfgError = (msg) => {
  const box = $("cfg-error");
  box.hidden = !msg;
  if (msg) box.textContent = msg;
};

/* ------------------------------------------------------------ config picker */

$("cfg-download").addEventListener("click", () => {
  const name = machineConfigName || configSelect.value;
  if (!name) return showCfgError("Choose a config to download first");
  const mode = machineConfigName ? machineConfigMode : "preset";
  const a = document.createElement("a");
  a.href = `machine_config/get?name=${encodeURIComponent(name)}&mode=${mode}`;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
});

configSelect.addEventListener("change", () => {
  if (!configSelect.value) return;
  configFile.value = "";
  machineConfigName = configSelect.value;
  machineConfigMode = "preset";
  loadOptionsForm();
});

configFile.addEventListener("change", async () => {
  if (!configFile.files.length) return;
  showCfgError(null);
  const fd = new FormData();
  fd.append("config_file", configFile.files[0]);
  try {
    const res = await fetch("machine_config/upload", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Upload failed");
    configSelect.selectedIndex = 0;
    machineConfigName = data.name;
    machineConfigMode = "uploaded";
    loadOptionsForm();
  } catch (err) {
    configSelect.selectedIndex = 0;
    configFile.value = "";
    showCfgError(String(err.message || err));
  }
});

/* -------------------------------------------------------------- options form */

async function loadOptionsForm() {
  showCfgError(null);
  container.innerHTML = '<div class="placeholder"><p>Loading options…</p></div>';
  const params = new URLSearchParams({
    session_id: SESSION_ID,
    machine_config_name: machineConfigName,
    machine_config_mode: machineConfigMode,
  });
  const res = await fetch(`options_form?${params}`);
  const html = await res.text();
  container.innerHTML = html;
  if (!res.ok) return;
  wireForm();
}

function wireForm() {
  const form = $("options-form");
  const gcodeBtn = $("options-form-gcode");
  const configBtn = $("options-form-machine-config");
  const sketch = $("machine-sketch");

  container.querySelectorAll("legend.toggle").forEach((lg) => {
    lg.addEventListener("click", () => lg.closest(".card").classList.toggle("open"));
  });

  /* ---- live machine sketch ---- */
  function updateSketch() {
    const fd = new FormData(form);
    form.querySelectorAll('input[type="file"]').forEach((i) => fd.delete(i.name));
    fd.append("sketch_only", "true");

    if (!form.checkValidity()) {
      sketch.classList.add("greyed");
      sketch.title = "Machine sketch (form has errors)";
      return;
    }
    const seq = ++sketchSeq;
    fetch("options_form", { method: "POST", body: fd })
      .then((r) => (r.ok ? r.blob() : Promise.reject(new Error("sketch failed"))))
      .then((blob) => {
        if (seq !== sketchSeq) return;   // a newer edit already won
        if (sketchUrl) URL.revokeObjectURL(sketchUrl);
        sketchUrl = URL.createObjectURL(blob);
        sketch.src = sketchUrl;
        sketch.classList.remove("greyed");
        sketch.title = "Machine sketch";
      })
      .catch(() => {
        if (seq !== sketchSeq) return;
        sketch.classList.add("greyed");
        sketch.title = "Machine sketch (could not be drawn)";
      });
  }

  let debounce = null;
  form.addEventListener("input", () => {
    clearTimeout(debounce);
    debounce = setTimeout(updateSketch, 180);
  });
  updateSketch();

  /* ---- match height to the uploaded image's aspect ratio ---- */
  /* i2gc maps the pixel grid onto width x height regardless of aspect, so a
     mismatch stretches the painting rather than fitting it. */
  const ratioBtn = $("match-ratio");
  const ratioNote = $("ratio-note");
  const widthInput = form.querySelector('[name="brushograph-width"]');
  const heightInput = form.querySelector('[name="brushograph-height"]');
  const shapes = new Map();   // tray name -> {w, h}

  const note = (text, warn) => {
    if (!ratioNote) return;
    ratioNote.textContent = text || "";
    ratioNote.hidden = !text;
    ratioNote.classList.toggle("warn", !!warn);
  };

  function measure(input) {
    const tray = (input.name.match(/^trays-(.+)-image$/) || [])[1];
    if (!tray) return;
    const file = input.files[0];
    if (!file) { shapes.delete(tray); refreshRatio(); return; }
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      shapes.set(tray, { w: img.naturalWidth, h: img.naturalHeight });
      URL.revokeObjectURL(url);
      refreshRatio();
    };
    img.onerror = () => { URL.revokeObjectURL(url); shapes.delete(tray); refreshRatio(); };
    img.src = url;
  }

  function refreshRatio() {
    if (!ratioBtn) return;
    const entries = [...shapes.entries()];
    ratioBtn.disabled = entries.length === 0;
    if (!entries.length) {
      ratioBtn.title = "Upload a tray image first";
      note(null);
      return;
    }
    const ratios = entries.map(([, s]) => s.h / s.w);
    const mixed = Math.max(...ratios) - Math.min(...ratios) > 0.005;
    const [tray, shape] = entries[0];
    ratioBtn.title = `Set height from the width and ${tray}'s ${shape.w}x${shape.h} px ratio`;
    if (mixed) {
      note(`images differ in aspect ratio — will use ${tray} (${shape.w}x${shape.h})`, true);
    } else {
      note(`${shape.w}x${shape.h} px · ratio ${(shape.w / shape.h).toFixed(3)}`);
    }
  }

  /* ---- woodcut conversion ---- */
  const wcPanel = $("woodcut-panel");
  const wcBtn = $("wc-preview-btn");
  const wcImg = $("wc-image");
  const wcNote = $("wc-note");

  // Which tray is set to "photo" and actually has a file chosen.
  function photoTray() {
    for (const sel of form.querySelectorAll("select.image-kind")) {
      if (sel.value !== "photo") continue;
      const tray = (sel.name.match(/^trays-(.+)-image_kind$/) || [])[1];
      const input = form.querySelector(`input[name="trays-${CSS.escape(tray)}-image"]`);
      if (input && input.files.length) return { tray, file: input.files[0] };
    }
    return null;
  }

  function refreshWoodcut() {
    if (!wcPanel) return;
    const anyPhoto = [...form.querySelectorAll("select.image-kind")].some((s) => s.value === "photo");
    wcPanel.hidden = !anyPhoto;
    const target = photoTray();
    if (wcBtn) {
      wcBtn.disabled = !target;
      wcBtn.title = target ? `Convert ${target.tray}'s photo` : "Choose a photo for a tray first";
    }
  }

  if (wcPanel) {
    for (const [id, out] of [["wc-detail", "wc-detail-out"],
                             ["wc-hatching", "wc-hatching-out"],
                             ["wc-threshold", "wc-threshold-out"],
                             ["wc-roughness", "wc-roughness-out"]]) {
      const el = $(id);
      if (el) el.addEventListener("input", () => { $(out).value = el.value; });
    }
    form.querySelectorAll("select.image-kind").forEach((s) =>
      s.addEventListener("change", () => { refreshWoodcut(); detectSubject(); }));

    wcBtn.addEventListener("click", async () => {
      const target = photoTray();
      if (!target) return;
      const fd = new FormData();
      fd.append("image", target.file);
      for (const n of ["woodcut_detail", "woodcut_hatching", "woodcut_threshold",
                       "woodcut_roughness", "brushograph-width", "slicer-infill_line_distance"]) {
        const el = form.querySelector(`[name="${n}"]`);
        if (el) fd.append(n, el.value);
      }
      fd.append("woodcut_outlines", $("wc-outlines").checked ? "true" : "false");
      fd.append("woodcut_isolate", $("wc-isolate") && $("wc-isolate").checked ? "true" : "false");

      const label = wcBtn.textContent;
      wcBtn.textContent = "Converting…";
      wcBtn.disabled = true;
      wcNote.hidden = true;
      try {
        const res = await fetch("woodcut_preview", { method: "POST", body: fd });
        if (!res.ok) {
          let msg = `Server returned ${res.status}`;
          try { msg = (await res.json()).error || msg; } catch (_) { /* not json */ }
          throw new Error(msg);
        }
        const blob = await res.blob();
        if (wcImg.dataset.url) URL.revokeObjectURL(wcImg.dataset.url);
        const url = URL.createObjectURL(blob);
        wcImg.dataset.url = url;
        wcImg.src = url;
        wcImg.hidden = false;
        wcNote.textContent = `${target.tray}: ${target.file.name}`;
        wcNote.classList.remove("warn");
        wcNote.hidden = false;
      } catch (err) {
        wcNote.textContent = String(err.message || err);
        wcNote.classList.add("warn");
        wcNote.hidden = false;
      } finally {
        wcBtn.textContent = label;
        wcBtn.disabled = false;
      }
    });
    refreshWoodcut();
    detectSubject();
  }

  wireSimulator();

  /* ---- is there a person or prominent object worth isolating? ---- */
  let lastDetected = null;
  async function detectSubject() {
    const row = $("wc-subject-row");
    if (!row) return;
    const target = photoTray();
    if (!target) { row.hidden = true; return; }
    if (lastDetected === target.file) return;      // already asked about this file
    lastDetected = target.file;

    const fd = new FormData();
    fd.append("image", target.file);
    try {
      const res = await fetch("detect_subject", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok || !data.found) {
        row.hidden = true;
        if ($("wc-isolate")) $("wc-isolate").checked = false;
        return;
      }
      const what = data.kind === "person"
        ? (data.count > 1 ? `${data.count} people` : "a person")
        : data.kind === "animal" ? "an animal" : "a prominent object";
      $("wc-subject-label").textContent = `Isolate ${what}`;
      $("wc-subject-note").textContent =
        `found by ${data.how}, covering ${Math.round(data.coverage * 100)}% of the frame` +
        " — the background becomes bare paper";
      row.hidden = false;
    } catch (err) {
      row.hidden = true;
    }
  }

  if (ratioBtn) {
    form.querySelectorAll('input[type="file"]').forEach((i) =>
      i.addEventListener("change", () => { measure(i); refreshWoodcut(); detectSubject(); }));

    ratioBtn.addEventListener("click", () => {
      const entries = [...shapes.entries()];
      if (!entries.length) return;
      const width = parseFloat(widthInput.value);
      if (!isFinite(width) || width <= 0) return note("set a width first", true);

      const [tray, shape] = entries[0];
      // Whole millimetres: the ratio is a guide, not a tolerance.
      const height = Math.max(1, Math.round(width * (shape.h / shape.w)));
      heightInput.value = height;
      // Bubbles to the form listener, so the sketch redraws.
      heightInput.dispatchEvent(new Event("input", { bubbles: true }));

      const maxH = parseFloat((form.querySelector('[name="brushograph-max_height"]') || {}).value);
      if (isFinite(maxH) && height > maxH) {
        note(`height ${height} mm from ${tray} — over the machine's ${maxH} mm limit`, true);
      } else {
        note(`height ${height} mm, matching ${tray}'s ${shape.w}x${shape.h} px`);
      }
    });
  }

  /* ---- the calibration macro, built from the config on screen ---- */
  const calBtn = $("options-form-calibration");
  if (calBtn) {
    calBtn.addEventListener("click", async () => {
      const errBox = $("form-error");
      errBox.hidden = true;
      const fd = new FormData(form);
      form.querySelectorAll('input[type="file"]').forEach((i) => fd.delete(i.name));
      fd.append("calibration_only", "true");
      const label = calBtn.textContent;
      calBtn.textContent = "Building…";
      calBtn.disabled = true;
      try {
        const res = await fetch(form.action, { method: "POST", body: fd });
        if (!res.ok) {
          let msg = `Server returned ${res.status}`;
          try { msg = (await res.json()).error || msg; } catch (_) { /* not json */ }
          throw new Error(msg);
        }
        saveBlob(await res.blob(), "calibration.g");
      } catch (err) {
        errBox.textContent = String(err.message || err);
        errBox.hidden = false;
      } finally {
        calBtn.textContent = label;
        calBtn.disabled = false;
      }
    });
  }

  /* ---- submit ---- */
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const submitter = e.submitter;
    const wantsGcode = submitter === gcodeBtn;
    const errBox = $("form-error");
    const statusBox = $("form-status");
    errBox.hidden = true;
    statusBox.hidden = true;

    const fd = new FormData(form);
    if (!wantsGcode) {
      form.querySelectorAll('input[type="file"]').forEach((i) => fd.delete(i.name));
      fd.append("config_only", "true");
    } else {
      const any = [...form.querySelectorAll('input[type="file"]')].some((i) => i.files.length);
      if (!any) {
        errBox.textContent = "No images selected";
        errBox.hidden = false;
        return;
      }
    }

    const label = submitter.textContent;
    submitter.textContent = wantsGcode ? "Generating…" : "Preparing…";
    gcodeBtn.disabled = configBtn.disabled = true;
    if (wantsGcode) {
      statusBox.textContent = "Tracing, slicing and planning brush strokes. This takes a few seconds per tray.";
      statusBox.hidden = false;
    }

    try {
      const res = await fetch(form.action, { method: form.method, body: fd });
      if (!res.ok) {
        let msg = `Server returned ${res.status}`;
        try { msg = (await res.json()).error || msg; } catch (_) { /* not json */ }
        throw new Error(msg);
      }
      const blob = await res.blob();
      const disposition = res.headers.get("Content-Disposition") || "";
      const match = disposition.match(/filename="?([^";]+)"?/);
      const filename = match ? match[1] : (wantsGcode ? "brushograph.gcode" : "machine.conf");

      if (!wantsGcode) {
        saveBlob(blob, filename);
        statusBox.textContent = `Downloaded ${filename} (${(blob.size / 1024).toFixed(0)} KB).`;
        statusBox.hidden = false;
        return;
      }
      // The G-code is offered rather than saved: look at the preview first, and
      // download when it is what you wanted.
      const text = await blob.text();
      offerDownload(blob, filename);
      statusBox.textContent =
        `Ready: ${filename} (${(blob.size / 1024).toFixed(0)} KB). Preview below.`;
      statusBox.hidden = false;
      try {
        showGcode(text);
      } catch (err) {
        console.error("preview failed", err);
      }
    } catch (err) {
      statusBox.hidden = true;
      errBox.textContent = String(err.message || err);
      errBox.hidden = false;
    } finally {
      submitter.textContent = label;
      gcodeBtn.disabled = configBtn.disabled = false;
    }
  });
}


/* ------------------------------------------------------- G-code preview ---- */
/* Draws the path the brush will take: painting strokes coloured per tray,
   travel faint, and dips into the cups marked. Parsing is deliberately literal
   — absolute coordinates, last-seen axis words — because that is what the
   machine itself does with the file. */

const TRAY_COLOURS = {
  cyan: "#00a6d6", magenta: "#d6008a", yellow: "#c8a800", kroma: "#1b1f26",
  water: "#7fb2d9", black: "#1b1f26",
};
const FALLBACK_COLOURS = ["#2f7fd0", "#c85a2b", "#3f9c6d", "#8a5bd6", "#c0392b"];

function parseGcode(text) {
  const moves = [];
  let x = 0, y = 0, z = 10, tray = null, trayIndex = -1;
  const trays = [];
  let paintMM = 0, travelMM = 0, dips = 0, strokes = 0, wasDown = false;

  for (const rawLine of text.split("\n")) {
    const marker = rawLine.match(/^\s*;\s*tray\s+(\S+)/i);
    if (marker) {
      tray = marker[1];
      if (!trays.includes(tray)) { trays.push(tray); }
      trayIndex = trays.indexOf(tray);
      continue;
    }
    const line = rawLine.split(";")[0].trim();
    if (!/^G0*[01](?![0-9])/.test(line)) continue;
    let nx = x, ny = y, nz = z;
    const words = line.matchAll(/([XYZ])\s*(-?\d*\.?\d+)/g);
    for (const [, axis, value] of words) {
      const v = parseFloat(value);
      if (axis === "X") nx = v; else if (axis === "Y") ny = v; else nz = v;
    }
    // Z at or below the canvas is painting; well below it is a trip into a cup.
    const down = nz <= 0.001;
    const inCup = nz <= -1;
    const d = Math.hypot(nx - x, ny - y);
    if (down && wasDown && !inCup) paintMM += d; else travelMM += d;
    if (down && !wasDown) strokes++;
    if (inCup && z > -1) dips++;
    moves.push({ x1: x, y1: y, x2: nx, y2: ny, down: down && wasDown, cup: inCup, tray: trayIndex });
    wasDown = down; x = nx; y = ny; z = nz;
  }
  return { moves, trays, paintMM, travelMM, dips, strokes };
}

function trayColour(name, index) {
  if (name && TRAY_COLOURS[name.toLowerCase()]) return TRAY_COLOURS[name.toLowerCase()];
  if (name && /^#[0-9a-f]{6}$/i.test(name)) return name;
  return FALLBACK_COLOURS[(index < 0 ? 0 : index) % FALLBACK_COLOURS.length];
}

const sim = { data: null, upto: 1 };

function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

let pendingFile = null;
function offerDownload(blob, filename) {
  pendingFile = { blob, filename };
  const button = $("gcode-download");
  const note = $("gcode-note");
  if (!button) return;
  button.textContent = `Download ${filename}`;
  button.hidden = false;
  if (note) {
    note.textContent = `${(blob.size / 1024).toFixed(0)} KB`;
    note.hidden = false;
  }
}

function drawGcode() {
  const canvas = $("gcode-canvas");
  if (!canvas || !sim.data) return;
  const { moves, trays } = sim.data;
  const ctx = canvas.getContext("2d");

  const xs = [], ys = [];
  for (const m of moves) { xs.push(m.x1, m.x2); ys.push(m.y1, m.y2); }
  if (!xs.length) return;
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const pad = 16;
  const scale = Math.min((canvas.width - 2 * pad) / Math.max(maxX - minX, 1),
                         (canvas.height - 2 * pad) / Math.max(maxY - minY, 1));
  // Machine Y grows away from the origin; the canvas grows downward.
  const px = (x) => pad + (x - minX) * scale;
  const py = (y) => canvas.height - pad - (y - minY) * scale;

  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.lineCap = "round";
  ctx.lineJoin = "round";

  const cut = Math.floor(moves.length * sim.upto);
  // Travel first, so painting is never hidden under it.
  ctx.strokeStyle = "#e6e9ee";
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let i = 0; i < cut; i++) {
    const m = moves[i];
    if (m.down || m.cup) continue;
    ctx.moveTo(px(m.x1), py(m.y1));
    ctx.lineTo(px(m.x2), py(m.y2));
  }
  ctx.stroke();

  let current = null;
  ctx.lineWidth = 1.8;
  for (let i = 0; i < cut; i++) {
    const m = moves[i];
    if (!m.down) continue;
    const colour = m.cup ? "#e0a03c" : trayColour(trays[m.tray], m.tray);
    if (colour !== current) {
      if (current !== null) ctx.stroke();
      ctx.strokeStyle = colour;
      ctx.beginPath();
      current = colour;
    }
    ctx.moveTo(px(m.x1), py(m.y1));
    ctx.lineTo(px(m.x2), py(m.y2));
  }
  if (current !== null) ctx.stroke();

  // Where the brush is right now.
  if (cut > 0 && cut < moves.length) {
    const m = moves[cut - 1];
    ctx.fillStyle = "#c0392b";
    ctx.beginPath();
    ctx.arc(px(m.x2), py(m.y2), 4, 0, Math.PI * 2);
    ctx.fill();
  }
}

function renderSimStats() {
  const box = $("sim-stats");
  if (!box || !sim.data) return;
  const { paintMM, travelMM, dips, strokes, trays, moves } = sim.data;
  // copicograf's feed rates: painting is the slow one, travel the fast one.
  const minutes = paintMM / 1000 + travelMM / 1500 + dips * 0.06;
  const stats = [
    [`${(paintMM / 1000).toFixed(1)} m`, "painted"],
    [`${(travelMM / 1000).toFixed(1)} m`, "travel"],
    [strokes.toLocaleString(), "brush downs"],
    [dips.toLocaleString(), "cup dips"],
    [moves.length.toLocaleString(), "moves"],
    [`~${minutes < 60 ? minutes.toFixed(0) + " min" : (minutes / 60).toFixed(1) + " h"}`, "rough time"],
  ];
  box.innerHTML = "";
  for (const [value, label] of stats) {
    const d = el("div", "sim-stat");
    d.appendChild(el("b", null, value));
    d.appendChild(el("span", null, label));
    box.appendChild(d);
  }
  const legend = el("div", "sim-legend");
  const entries = trays.length
    ? trays.map((t, i) => [trayColour(t, i), t])
    : [["#2f7fd0", "painting"]];
  entries.push(["#e0a03c", "in the cups"], ["#e6e9ee", "travel"]);
  for (const [colour, label] of entries) {
    const item = el("span");
    const swatch = el("i");
    swatch.style.background = colour;
    item.appendChild(swatch);
    item.appendChild(document.createTextNode(label));
    legend.appendChild(item);
  }
  box.appendChild(legend);
}

function showGcode(text) {
  const card = $("preview-card");
  if (!card) return;
  sim.data = parseGcode(text);
  sim.upto = 1;
  card.hidden = false;
  const scrub = $("sim-scrub");
  if (scrub) scrub.value = 1000;
  drawGcode();
  renderSimStats();
  updateSimAt();
}

function updateSimAt() {
  const at = $("sim-at");
  if (at && sim.data) {
    at.textContent = `${Math.round(sim.upto * 100)}% of ${sim.data.moves.length.toLocaleString()} moves`;
    at.hidden = false;
  }
}

let simTimer = null;
function wireSimulator() {
  const scrub = $("sim-scrub"), play = $("sim-play"), open = $("sim-open");
  if (!scrub) return;
  scrub.addEventListener("input", () => {
    sim.upto = Number(scrub.value) / 1000;
    drawGcode();
    updateSimAt();
  });
  play.addEventListener("click", () => {
    if (simTimer) {
      clearInterval(simTimer); simTimer = null; play.textContent = "▶ Play"; return;
    }
    if (sim.upto >= 1) sim.upto = 0;
    play.textContent = "❚❚ Pause";
    simTimer = setInterval(() => {
      sim.upto = Math.min(1, sim.upto + 0.01);
      scrub.value = Math.round(sim.upto * 1000);
      drawGcode();
      updateSimAt();
      if (sim.upto >= 1) { clearInterval(simTimer); simTimer = null; play.textContent = "▶ Play"; }
    }, 40);
  });
  const download = $("gcode-download");
  if (download) {
    download.addEventListener("click", () => {
      if (pendingFile) saveBlob(pendingFile.blob, pendingFile.filename);
    });
  }
  if (open) {
    open.addEventListener("change", async () => {
      const file = open.files[0];
      if (!file) return;
      showGcode(await file.text());
      offerDownload(file, file.name);
      open.value = "";
    });
  }
}

/* ------------------------------------------- tooltips as a dialog on mobile */

const dialog = $("info-dialog");
const closeDialog = () => dialog.close();
dialog.addEventListener("click", closeDialog);
dialog.addEventListener("close", () => window.removeEventListener("scroll", closeDialog));
document.addEventListener("click", (e) => {
  const btn = e.target.closest(".info-btn");
  if (!btn) return;
  e.preventDefault();
  if (window.innerWidth > 768) return;   // desktop gets the native tooltip
  e.stopPropagation();
  const text = btn.getAttribute("title") || btn.getAttribute("aria-label");
  if (!text) return;
  dialog.textContent = text;
  dialog.showModal();
  setTimeout(() => window.addEventListener("scroll", closeDialog, { once: true, passive: true }), 100);
});
})();
