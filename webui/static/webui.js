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

  // Sections that fold are <details> now, which the browser opens and closes
  // itself, keyboard and screen reader included.

  /* ---- live machine sketch ---- */
  function updateSketch() {
    const fd = new FormData(form);
    form.querySelectorAll('input[type="file"]').forEach((i) => fd.delete(i.name));
    fd.append("sketch_only", "true");
    fd.append("theme", document.documentElement.dataset.theme || "default");

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
  document.addEventListener("brushograph:theme", updateSketch);

  /* ---- space the cups the way the printed holder does ---- */
  /* The modern holder is one piece, so its five bays cannot be moved relative
     to each other: only where the whole thing sits is a machine measurement.
     This spaces the other four off the water cup using the holder's own
     centres, and only offers itself when that holder is the one selected. */
  const spaceBtn = $("space-cups");
  const holderNote = $("holder-note");
  const shapeSelect = form.querySelector('[name="brushograph-cup_shape"]');
  if (spaceBtn && shapeSelect) {
    const offsets = JSON.parse(spaceBtn.dataset.offsets || "{}");
    const trayX = (name) => form.querySelector('[name="trays-' + name + '-x"]');
    const showIfModern = () => {
      const on = shapeSelect.value === "modern" && !!trayX("water");
      spaceBtn.hidden = !on;
      if (holderNote) holderNote.hidden = !on;
    };
    shapeSelect.addEventListener("change", showIfModern);
    showIfModern();
    spaceBtn.addEventListener("click", () => {
      const water = trayX("water");
      const base = parseFloat(water && water.value);
      if (!isFinite(base)) return;
      let moved = 0;
      for (const [name, off] of Object.entries(offsets)) {
        const input = trayX(name);
        if (!input) continue;
        input.value = String(Math.round((base + off) * 100) / 100);
        moved += 1;
      }
      // One event for the lot: the sketch redraws off the form, not per field.
      if (moved) form.dispatchEvent(new Event("input", { bubbles: true }));
    });
  }

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

    document.addEventListener("brushograph:theme", () => {
      // The cut is printed on the theme's paper by the server, so a theme
      // change means asking for it again — but only if one is being shown.
      if (wcImg && !wcImg.hidden && photoTray()) wcBtn.click();
    });

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
      fd.append("woodcut_face_filter",
                $("wc-face-filter") && $("wc-face-filter").checked ? "true" : "false");
      fd.append("theme", document.documentElement.dataset.theme || "default");

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
    const faceRow = $("wc-face-row");
    if (!row) return;
    const target = photoTray();
    if (!target) { row.hidden = true; if (faceRow) faceRow.hidden = true; return; }
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
        if (faceRow) faceRow.hidden = true;
        if ($("wc-face-filter")) $("wc-face-filter").checked = false;
        return;
      }
      // Only offered when there is a face to work on; it does nothing without one.
      const hasFace = Array.isArray(data.faces) && data.faces.length > 0;
      if (faceRow) faceRow.hidden = !hasFace;
      if (!hasFace && $("wc-face-filter")) $("wc-face-filter").checked = false;
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
      if (faceRow) faceRow.hidden = true;
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

  /* ---- submit ---- */
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const submitter = e.submitter;
    const wantsGcode = submitter === gcodeBtn;
    // The two buttons live in different sections now, so each reports where it
    // is: a "Downloaded ..." line up in Run would be off screen for someone who
    // is down in machine setup.
    const errBox = (wantsGcode ? null : $("setup-error")) || $("form-error");
    const statusBox = (wantsGcode ? null : $("setup-status")) || $("form-status");
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
        // The file is already downloadable at this point, so a preview that
        // fails used to leave an empty box and no explanation.
        console.error("preview failed", err);
        errBox.textContent = `The file is ready, but the preview could not be drawn: ${err.message || err}`;
        errBox.hidden = false;
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
// The trips down into the paint and water cups, drawn in the colour of paint
// rather than of a warning. Named because it is wanted in two places — the
// strokes and the legend — and they must not drift apart.
const CUP_COLOUR = "#8b3e2f";

/* The preview sits on the page, so it takes its paper, its travel lines and its
 * marker from whatever theme is on. The paint colours are not in here: a stroke
 * is the colour of the paint that draws it. Black is the exception, and only
 * because it has to be — on the dark papers it is the paper, so each theme
 * says what its darkest ink looks like. */
function themeInk() {
  const cs = getComputedStyle(document.documentElement);
  const pick = (name, fallback) => (cs.getPropertyValue(name) || "").trim() || fallback;
  return {
    paper: pick("--sheet", "#ffffff"),
    travel: pick("--line-soft", "#e6e9ee"),
    marker: pick("--bad", "#c0392b"),
    cup: pick("--preview-cup", CUP_COLOUR),
    key: pick("--k", TRAY_COLOURS.kroma),
  };
}

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
    // Backlash compensation injects a corrective move before each reversal.
    // Those are for the machine's slack, not part of the path that was asked
    // for, and drawing them buries the artwork in hatching that is not in it.
    if (/;\s*backlash take-up/i.test(rawLine)) continue;
    const line = rawLine.split(";")[0].trim();
    if (!/^G0*[01](?![0-9])/.test(line)) continue;
    let nx = x, ny = y, nz = z;
    const words = line.matchAll(/([XYZ])\s*(-?\d*\.?\d+)/g);
    for (const [, axis, value] of words) {
      const v = parseFloat(value);
      if (axis === "X") nx = v; else if (axis === "Y") ny = v; else nz = v;
    }
    // Z at the canvas is painting; anything below it is a trip into a cup.
    // Not a fixed depth: the dip is configurable, and a shallow one would
    // otherwise be drawn as painting.
    const down = nz <= 0.001;
    const inCup = nz < -0.001;
    const d = Math.hypot(nx - x, ny - y);
    if (down && wasDown && !inCup) paintMM += d; else travelMM += d;
    if (down && !wasDown) strokes++;
    if (inCup && z >= -0.001) dips++;
    moves.push({ x1: x, y1: y, x2: nx, y2: ny, down: down && wasDown, cup: inCup, tray: trayIndex });
    wasDown = down; x = nx; y = ny; z = nz;
  }
  return { moves, trays, paintMM, travelMM, dips, strokes };
}

function trayColour(name, index) {
  const key = name && name.toLowerCase();
  // Black is the one paint whose own colour will not do in every theme: on the
  // dark papers it *is* the paper. So it comes off --k, the same swatch the
  // tray dot and the card's edge use, and each theme says what black looks
  // like on its paper rather than the preview deciding that on its own.
  if (key === "kroma" || key === "black" || key === "key") return themeInk().key;
  if (key && TRAY_COLOURS[key]) return TRAY_COLOURS[key];
  if (key && /^#[0-9a-f]{6}$/i.test(key)) return key;
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
  for (const id of ["gcode-send", "gcode-run"]) {
    const b = $(id);
    if (b) b.hidden = false;
  }
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

  // Swept in a loop rather than with Math.min(...xs). The spread passes one
  // argument per coordinate, and a real job has hundreds of thousands of them:
  // past roughly a hundred thousand the call stack gives out and the preview
  // dies with "Maximum call stack size exceeded".
  if (!moves.length) return;
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (const m of moves) {
    if (m.x1 < minX) minX = m.x1;
    if (m.x1 > maxX) maxX = m.x1;
    if (m.x2 < minX) minX = m.x2;
    if (m.x2 > maxX) maxX = m.x2;
    if (m.y1 < minY) minY = m.y1;
    if (m.y1 > maxY) maxY = m.y1;
    if (m.y2 < minY) minY = m.y2;
    if (m.y2 > maxY) maxY = m.y2;
  }
  const pad = 16;
  const scale = Math.min((canvas.width - 2 * pad) / Math.max(maxX - minX, 1),
                         (canvas.height - 2 * pad) / Math.max(maxY - minY, 1));
  // Machine Y grows away from the origin; the canvas grows downward.
  const px = (x) => pad + (x - minX) * scale;
  const py = (y) => canvas.height - pad - (y - minY) * scale;

  const skin = themeInk();
  ctx.fillStyle = skin.paper;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.lineCap = "round";
  ctx.lineJoin = "round";

  const cut = Math.floor(moves.length * sim.upto);
  // Travel first, so painting is never hidden under it.
  ctx.strokeStyle = skin.travel;
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
    const colour = m.cup ? skin.cup : trayColour(trays[m.tray], m.tray);
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
    ctx.fillStyle = skin.marker;
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
  const skin = themeInk();
  entries.push([skin.cup, "in the cups"], [skin.travel, "travel"]);
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
  // With no moves the bounds come out infinite, the scale NaN, and every draw
  // call is quietly ignored — an empty box and no complaint. Say so instead.
  if (!sim.data.moves.length) {
    throw new Error("no G0/G1 movement was found in that file");
  }
  sim.upto = 1;
  const wasHidden = card.hidden;
  card.hidden = false;
  // The path is the answer to pressing Generate, so bring it into view once.
  if (wasHidden) card.scrollIntoView({ block: "nearest", behavior: "smooth" });
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
  document.addEventListener("brushograph:theme", () => {
    if (sim.data) { drawGcode(); renderSimStats(); }
  });
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
  const send = $("gcode-send");
  if (send) send.addEventListener("click", () => sendToMachine(false));
  const run = $("gcode-run");
  if (run) run.addEventListener("click", () => sendToMachine(true));
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
/* ----------------------------------------------------------- to the machine */
/* Following openBatak-Assembler, which does this from the page rather than
 * through a server. FluidNC answers a cross-origin preflight without an
 * allow-origin header, so a normal fetch cannot read its reply — but a
 * `no-cors` request is still delivered, and multipart/form-data is a
 * CORS-safelisted content type, so it needs no preflight at all. The cost is
 * that the reply is opaque: the page can say a file was sent, never that it
 * arrived. Doing it from the browser is also what makes it work at all, since
 * the machine sits on the same network as whoever is looking at this page and
 * not necessarily on the same one as the server.
 */
const SD_SYNC_MS = 2000;
const WS_OPEN_MS = 6000;
const WS_LISTEN_MS = 2500;

/* FluidNC will not take a command unless a websocket session is live: ask it
 * to run a file with none open and /command answers 500 "WebSocket dead",
 * which is exactly what an upload that lands but never starts looks like. So
 * one is opened first and held while the command goes out. It is not a
 * transport for the file — that is still a plain POST — it is the thing that
 * makes the controller listen at all.
 *
 * A websocket is not subject to CORS, so the page may open it directly. What
 * comes back over it is the machine's own console, which is the only way this
 * page can report what the machine did rather than what it was told. */
function openMachineSocket(base, heard) {
  return new Promise((resolve, reject) => {
    let ws;
    try {
      ws = new WebSocket(base.replace(/^http/, "ws") + "/", "webui-v3");
    } catch (e) {
      reject(e);
      return;
    }
    const giveUp = setTimeout(() => {
      try { ws.close(); } catch (e) { /* already gone */ }
      reject(new Error("the machine did not accept a websocket connection"));
    }, WS_OPEN_MS);
    ws.onopen = () => { clearTimeout(giveUp); resolve(ws); };
    ws.onerror = () => { clearTimeout(giveUp); reject(new Error("websocket refused")); };
    ws.onmessage = (ev) => {
      if (typeof ev.data === "string") heard.push(ev.data.trim());
    };
  });
}

function machineHost() {
  const field = document.querySelector('[name="connection-hostname"]');
  return field ? field.value.trim().replace(/^https?:\/\//, "").replace(/\/+$/, "") : "";
}

/* Not every browser looks a `.local` name up. Chromium resolves them through
 * mDNS; Firefox returns a bare NetworkError. This server sits on the same
 * network and its resolver does know the name, so ask it and use the address
 * it gives back. If it cannot answer — it is somewhere else, or the name is
 * already an address — carry on with what was typed. */
async function machineBase() {
  const host = machineHost();
  if (!host) return null;
  const bare = host.split(":")[0];
  if (/^[0-9.]+$/.test(bare)) return "http://" + host;
  try {
    const res = await fetch(`machine/resolve?host=${encodeURIComponent(bare)}`);
    if (res.ok) {
      const { ip } = await res.json();
      if (ip) return "http://" + host.replace(bare, ip);
    }
  } catch (e) { /* fall back to the name as typed */ }
  return "http://" + host;
}

function machineSay(text, bad) {
  const note = $("machine-note");
  const err = $("machine-error");
  if (note) note.hidden = true;
  if (err) err.hidden = true;
  const box = bad ? err : note;
  if (box) {
    box.textContent = text;
    box.hidden = false;
  }
}

async function sendToMachine(start) {
  if (!pendingFile) return;
  const base = await machineBase();
  if (!base) {
    machineSay("Set a hostname under Machine setup, Connection.", true);
    return;
  }
  // A page served over https may not talk to a machine over http, and no
  // amount of no-cors changes that: the browser blocks it as mixed content.
  if (location.protocol === "https:" && base.startsWith("http:")) {
    machineSay(`This page is on https and ${base} is not, so the browser will `
      + "block the connection. Open the WebUI over http on the same network as "
      + "the machine, or download the file and upload it yourself.", true);
    return;
  }

  const name = pendingFile.filename.replace(/[^A-Za-z0-9._-]/g, "_");
  const buttons = [$("gcode-send"), $("gcode-run")].filter(Boolean);
  const labels = buttons.map((b) => b.textContent);
  buttons.forEach((b) => { b.disabled = true; });
  let ws = null;

  try {
    machineSay(`Sending ${name} to ${base}…`);
    const fd = new FormData();
    fd.append("path", "/");
    fd.append("myfile", pendingFile.blob, name);
    await fetch(`${base}/upload`, { method: "POST", body: fd, mode: "no-cors" });

    if (!start) {
      machineSay(`${name} sent to ${base}. The reply is opaque, so check the `
        + "machine's own file list to be sure.");
      return;
    }
    // The card needs a moment to commit the file before the controller can be
    // asked to run it.
    machineSay(`${name} sent. Waiting ${SD_SYNC_MS / 1000}s for the card to catch up…`);
    buttons[1].textContent = "Starting…";
    await new Promise((r) => setTimeout(r, SD_SYNC_MS));

    const heard = [];
    ws = await openMachineSocket(base, heard);
    const cmd = encodeURIComponent(`$SD/Run=/${name}`);
    await fetch(`${base}/command?cmd=${cmd}`, { mode: "no-cors" });
    // Listen to the machine's own console rather than assuming.
    await new Promise((r) => setTimeout(r, WS_LISTEN_MS));
    const said = heard.filter((m) => m && !/^PING/i.test(m)).slice(-3).join(" · ");
    machineSay(said
      ? `${name}: $SD/Run sent. The machine says: ${said}`
      : `${name}: $SD/Run sent, but the machine said nothing back. Check it.`);
  } catch (e) {
    machineSay(`Could not reach ${base}: ${e.message || e}. `
      + "Check the hostname under Machine setup, Connection, and that this page "
      + "and the machine are on the same network.", true);
  } finally {
    if (ws) { try { ws.close(); } catch (e) { /* already gone */ } }
    buttons.forEach((b, i) => { b.disabled = false; b.textContent = labels[i]; });
  }
}
})();

/* ------------------------------------------------------------------ themes */
/* The chosen theme is already on <html> — an inline script in the head puts it
 * there before the first paint. This only keeps the select in step with it. */
(function themes() {
  const sel = document.getElementById("theme-select");
  if (!sel) return;
  const KEY = "brushograph-theme";
  let saved = "default";
  try { saved = localStorage.getItem(KEY) || "default"; } catch (e) {}
  sel.value = saved;
  document.documentElement.dataset.theme = saved;
  sel.addEventListener("change", () => {
    document.documentElement.dataset.theme = sel.value;
    try { localStorage.setItem(KEY, sel.value); } catch (e) {}
    // Both drawings carry theme colours, so both are redrawn on the spot.
    document.dispatchEvent(new CustomEvent("brushograph:theme"));
  });
})();
