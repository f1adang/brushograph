/* Brushograph WebUI */
(() => {
"use strict";

const $ = (id) => document.getElementById(id);
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
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = match ? match[1] : (wantsGcode ? "brushograph.gcode" : "machine.conf");
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      statusBox.textContent = `Downloaded ${a.download} (${(blob.size / 1024).toFixed(0)} KB).`;
      statusBox.hidden = false;
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
