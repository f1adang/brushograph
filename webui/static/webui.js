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

/* ---------------------------------------------------------------- German */
/* 𝕭𝖗𝖚𝖘𝖈𝖍𝖔𝖑𝖔𝖌𝖎𝖘𝖈𝖍𝖊𝖗 𝕶𝖔𝖓𝖌𝖗𝖊𝖘𝖘 is a German-language theme, so the interface is
 * translated while it is on and put back into English when it goes off. The
 * words themselves all live in de.js; what is here is only the machinery that
 * applies them, which knows nothing about German beyond the name of the theme.
 *
 * Two halves, because the page's text arrives two ways. Text that came from a
 * template or from the server is already in the DOM, so it is walked and
 * swapped in place, with the English kept beside it so the swap can be undone.
 * Text this file writes itself never sits in the DOM as English at all, so it
 * goes through t() at the point it is written — the English string is the key,
 * so the call site still reads as the sentence it prints.
 */
const DE = window.KONGRESS_DE || { text: {}, html: {}, patterns: [] };
const DE_PATTERNS = (DE.patterns || []).map(([source, out]) => [new RegExp(source), out]);
const isKongress = () => document.documentElement.dataset.theme === "kongress";

/* Templates wrap a sentence over several lines; the dictionary holds it as one.
   Matching on the collapsed form is what lets a single entry cover both. */
const squash = (s) => s.replace(/\s+/g, " ").trim();

/* The German for one English string, or null when there is none for it. */
function german(english) {
  const key = squash(english);
  const hit = DE.text[key];
  if (hit) return hit;
  // Text with a detail in it — a message the server builds, a button named
  // after a file — which no fixed key can match. Matched on the collapsed form
  // like the fixed keys, or a template's indentation would defeat the anchors.
  for (const [pattern, out] of DE_PATTERNS) {
    if (pattern.test(key)) return key.replace(pattern, out);
  }
  return null;
}

/* t("height {height} mm", {height}) — the English, translated if the theme is
   on, with {placeholders} filled in either way. */
function t(english, vars) {
  const out = (isKongress() && german(english)) || english;
  if (!vars) return out;
  return out.replace(/\{(\w+)\}/g, (whole, key) => (key in vars ? vars[key] : whole));
}

// The English of everything that has been translated in place, so a theme
// change can put it back. Keyed by node, so a form that is thrown away and
// fetched again takes its entries with it.
const WAS_TEXT = new WeakMap();      // text node -> its English
const WAS_HTML = new WeakMap();      // [data-i18n] element -> its English markup
const WAS_ATTR = new WeakMap();      // element -> {attribute: English}
const I18N_ATTRS = ["title", "aria-label", "alt", "placeholder"];
const I18N_ATTR_SELECTOR = I18N_ATTRS.map((attr) => `[${attr}]`).join(",");

/* Every text node under root, skipping the blocks that carry their own
   translation and the tags whose contents are not prose. */
function eachTextNode(root, visit) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (node.nodeType === Node.TEXT_NODE) return NodeFilter.FILTER_ACCEPT;
      if (node.dataset && node.dataset.i18n) return NodeFilter.FILTER_REJECT;
      return node.tagName === "SCRIPT" || node.tagName === "STYLE"
        ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_SKIP;
    },
  });
  let node;
  while ((node = walker.nextNode())) visit(node);
}

function toGerman(root) {
  // Prose with tags inside it is replaced whole: German will not keep the
  // English word order around an <i> or a <code>.
  for (const node of root.querySelectorAll("[data-i18n]")) {
    const markup = DE.html[node.dataset.i18n];
    if (!markup || WAS_HTML.has(node)) continue;
    WAS_HTML.set(node, node.innerHTML);
    node.innerHTML = markup;
  }
  eachTextNode(root, (node) => {
    if (WAS_TEXT.has(node)) return;
    const text = german(node.nodeValue);
    if (!text) return;
    WAS_TEXT.set(node, node.nodeValue);
    // The surrounding whitespace is the template's indentation; only the
    // sentence between it is ours to change.
    node.nodeValue = node.nodeValue.match(/^\s*/)[0] + text + node.nodeValue.match(/\s*$/)[0];
  });
  for (const node of root.querySelectorAll(I18N_ATTR_SELECTOR)) {
    if (WAS_ATTR.has(node)) continue;
    let saved = null;
    for (const attr of I18N_ATTRS) {
      if (!node.hasAttribute(attr)) continue;
      const text = german(node.getAttribute(attr));
      if (!text) continue;
      (saved || (saved = {}))[attr] = node.getAttribute(attr);
      node.setAttribute(attr, text);
    }
    if (saved) WAS_ATTR.set(node, saved);
  }
}

function toEnglish(root) {
  for (const node of root.querySelectorAll("[data-i18n]")) {
    if (!WAS_HTML.has(node)) continue;
    node.innerHTML = WAS_HTML.get(node);
    WAS_HTML.delete(node);
  }
  eachTextNode(root, (node) => {
    if (!WAS_TEXT.has(node)) return;
    node.nodeValue = WAS_TEXT.get(node);
    WAS_TEXT.delete(node);
  });
  for (const node of root.querySelectorAll(I18N_ATTR_SELECTOR)) {
    const saved = WAS_ATTR.get(node);
    if (!saved) continue;
    for (const attr of Object.keys(saved)) node.setAttribute(attr, saved[attr]);
    WAS_ATTR.delete(node);
  }
}

const applyLanguage = (root) => { if (root) (isKongress() ? toGerman : toEnglish)(root); };

/* Text this file writes, remembered as the English it was written from, so a
   change of theme can write it again in the other language rather than leaving
   a status line standing in the language it happened in. */
const WRITTEN = new Set();

function say(node, english, vars) {
  if (!node) return;
  node._i18n = [english, vars];
  node.textContent = t(english, vars);
  WRITTEN.add(node);
}

function sayTitle(node, english, vars) {
  if (!node) return;
  node._i18nTitle = [english, vars];
  node.title = t(english, vars);
  WRITTEN.add(node);
}

function rewriteWritten() {
  for (const node of WRITTEN) {
    if (!node.isConnected) { WRITTEN.delete(node); continue; }
    if (node._i18n) node.textContent = t(node._i18n[0], node._i18n[1]);
    if (node._i18nTitle) node.title = t(node._i18nTitle[0], node._i18nTitle[1]);
  }
}

/* A file input is lettered by the browser, not by the page: the word on its
   button and the "No file selected" beside it come from the browser's own
   locale, and nothing the page can say reaches them — not the stylesheet, not
   the document's language. So the theme that speaks German brings its own
   control. The native input is left exactly where it is, listeners and all, and
   only taken out of sight by the stylesheet; the proxy is its sibling inside
   the same <label>, so clicking it opens the picker with no script involved.
   Every other theme shows the browser's control and never this one. */
function proxyFileInputs(root) {
  for (const input of root.querySelectorAll('input[type="file"]')) {
    // sim-open is hidden already and has a label of its own to say it.
    if (input.hidden || input.dataset.proxy) continue;
    const label = input.closest("label");
    if (!label) continue;
    input.dataset.proxy = "true";
    const proxy = el("span", "file-proxy");
    const button = el("b");
    const chosen = el("i");
    proxy.append(button, chosen);
    input.after(proxy);
    const show = () => {
      say(button, "Choose file");
      // A bare placeholder as the key: a filename is nobody's language, but it
      // is written through say() like everything else so that a change of
      // theme rewrites the line beside it rather than half of it.
      if (input.files.length) say(chosen, "{file}", { file: input.files[0].name });
      else say(chosen, "No file selected");
    };
    input.addEventListener("change", show);
    show();
  }
}

/* A button that says something else while it works has to be put back
   afterwards, and the rendered text will not do it: assigning textContent drops
   the text node the in-place translation was recorded against, and with it the
   English to go back to. So the label is taken as English and put back through
   say(), which lands it in whichever language is on by then. */
function labelOf(button) {
  if (button._i18n) return button._i18n[0];
  for (const node of button.childNodes) {
    if (node.nodeType === Node.TEXT_NODE && WAS_TEXT.has(node)) return squash(WAS_TEXT.get(node));
  }
  return squash(button.textContent);
}

/* The tray keys are the config's own words, and the plan view and the G-code
   both carry them; the legend is the one place they are read rather than
   matched, so that is the one place they are translated. */
const trayName = (name) => (name ? t(name[0].toUpperCase() + name.slice(1)) : name);

/* How the subject was found, in the server's own words — "segmentation and 2
   face(s)", a cascade's name, "saliency". subject.py builds those rather than a
   template, so they are taken apart here rather than matched whole. */
function detectorName(how) {
  const text = String(how || "");
  let m;
  if ((m = text.match(/^segmentation and (\d+) face\(s\)$/))) {
    return t("segmentation and {count} face(s)", { count: m[1] });
  }
  if ((m = text.match(/^segmentation, (\d+)% animal$/))) {
    return t("segmentation, {percent}% animal", { percent: m[1] });
  }
  if ((m = text.match(/^(\d+) face\(s\)$/))) return t("{count} face(s)", { count: m[1] });
  return t(text);
}

let pageTitle = null;

function applyLanguageToPage() {
  document.documentElement.lang = isKongress() ? "de" : "en";
  if (pageTitle === null) pageTitle = document.title;
  document.title = t(pageTitle);
  proxyFileInputs(document.body);
  applyLanguage(document.body);
  rewriteWritten();
}

const showCfgError = (msg) => {
  const box = $("cfg-error");
  if (!box) return;
  box.hidden = !msg;
  if (msg) say(box, msg);
};

/* Whatever the server said went wrong, in the server's own English. It is
   translated where it is shown rather than here, so it follows a change of
   theme like the rest of the page — and a failure deep in the pipeline, which
   carries its own detail and is in no dictionary, simply stays as it came. */
async function serverError(res) {
  try {
    const sent = (await res.json()).error;
    if (sent) return String(sent);
  } catch (e) { /* not json */ }
  return `Server returned ${res.status}`;
}

/* ------------------------------------------------------------ config picker */

const configKeep = $("machine-config-keep");

/* Emptying a file input from script fires nothing, and the Kongress theme's
   own file control only hears `change` — so it would go on naming a file that
   is no longer chosen. Say it changed. The upload handler below ignores an
   empty input, so this never uploads anything. */
function clearFile(input) {
  if (!input || !input.value) return;
  input.value = "";
  input.dispatchEvent(new Event("change"));
}

function showCfgNote(english, vars) {
  const box = $("cfg-note");
  if (!box) return;
  box.hidden = !english;
  if (english) say(box, english, vars);
}

/* A kept config joins the pulldown straight away, where the server would list
   it on the next load. Every entry in the pulldown is a kept config — nothing
   ships with the repository — so the list is empty until the first one is
   kept, and its prompt says so until then. */
function addSavedOption(name) {
  const entries = [...configSelect.options].filter((o) => o.value);
  let option = entries.find((o) => o.value === name);
  if (!option) {
    option = el("option", null, name);
    option.value = name;
    // In name order, as the server lists them.
    const next = entries.find((o) => o.value.toLowerCase() > name.toLowerCase());
    configSelect.insertBefore(option, next || null);
  }
  say($("machine-config-prompt"), "Choose a machine…");
  return option;
}

const cfgDlBtn = $("cfg-download");
if (cfgDlBtn) {
  cfgDlBtn.addEventListener("click", () => {
    const name = machineConfigName || (configSelect ? configSelect.value : null);
    if (!name) return showCfgError("Choose a config to download first");
    const mode = machineConfigName ? machineConfigMode : "saved";
    const a = document.createElement("a");
    a.href = `machine_config/get?name=${encodeURIComponent(name)}&mode=${mode}`;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
  });
}

if (configSelect) {
  configSelect.addEventListener("change", () => {
    if (!configSelect.value) return;
    clearFile(configFile);
    showCfgNote(null);
    machineConfigName = configSelect.value;
    machineConfigMode = "saved";
    loadOptionsForm();
  });
}

if (configFile) {
  configFile.addEventListener("change", async () => {
    if (!configFile.files.length) return;
    showCfgError(null);
    showCfgNote(null);
    const file = configFile.files[0];
    const keep = !!(configKeep && configKeep.checked);
    const fd = new FormData();
    fd.append("config_file", file);
    if (keep) fd.append("keep", "true");
    try {
      const res = await fetch("machine_config/upload", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Upload failed");
      machineConfigName = data.name;
      machineConfigMode = data.mode || "uploaded";
      if (machineConfigMode === "saved" && configSelect) {
        // It is a machine in the list now, so the list is what shows it — not
        // a file input still holding what was picked from the disk.
        addSavedOption(data.name).selected = true;
        clearFile(configFile);
        if (data.name === file.name) {
          showCfgNote("Kept on the server, and in the machine list from now on.");
        } else {
          showCfgNote("Kept on the server as {name}: {original} was already taken by another machine.",
                      { name: data.name, original: file.name });
        }
      } else if (configSelect) {
        configSelect.selectedIndex = 0;
      }
      loadOptionsForm();
    } catch (err) {
      if (configSelect) configSelect.selectedIndex = 0;
      clearFile(configFile);
      showCfgError(String(err.message || err));
    }
  });
}

/* -------------------------------------------------------------- options form */

async function loadOptionsForm() {
  if (!container) return;
  showCfgError(null);
  container.innerHTML = '<div class="placeholder"><p></p></div>';
  say(container.querySelector("p"), "Loading options…");
  const params = new URLSearchParams({
    session_id: typeof SESSION_ID !== "undefined" ? SESSION_ID : "",
    machine_config_name: machineConfigName,
    machine_config_mode: machineConfigMode,
  });
  const res = await fetch(`options_form?${params}`);
  const html = await res.text();
  container.innerHTML = html;
  // The form is built from the config, so its labels and help arrive in
  // English however long the theme has been on: translate what just landed.
  proxyFileInputs(container);
  applyLanguage(container);
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
      sayTitle(sketch, "Machine sketch (form has errors)");
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
        sayTitle(sketch, "Machine sketch");
      })
      .catch(() => {
        if (seq !== sketchSeq) return;
        sketch.classList.add("greyed");
        sayTitle(sketch, "Machine sketch (could not be drawn)");
      });
  }

  let debounce = null;
  form.addEventListener("input", () => {
    clearTimeout(debounce);
    debounce = setTimeout(updateSketch, 180);
    capPaintedHeight();
  });
  updateSketch();
  document.addEventListener("brushograph:theme", updateSketch);

  /* ---- space the cups the way the printed holder does ---- */
  /* Both holders are one piece, so their cups cannot be moved relative to each
     other: only where the whole thing sits is a machine measurement. Auto-space
     puts the others off the water cup at the selected holder's own centres,
     in line with it.
     Each holder fixes heights as well — the petri dish its radii and lifts,
     the CMYK crucibles their lift, dip and where the swipe leaves the stairs —
     so picking a holder, or pressing Auto-space, applies the lot for the
     holder and model selected; a config that opens already set up keeps
     its own figures. The petri dish holder has four places and no black, so the black
     cup's position and picture are put away while Classic is selected — and
     disabled, so they are not posted either.

     Which CMYK holder it is depends on the model: the 𝔐𝔦𝔨𝔯𝔬 has its own, a
     fraction of the Mini's, and no petri dish holder at all. */
  const spaceBtn = $("space-cups");
  const spaceNote = $("space-note");
  const shapeSelect = form.querySelector('[name="brushograph-cup_shape"]');
  const modelSelect = form.querySelector('[name="brushograph-model"]');
  const modelNote = $("model-note");
  const models = JSON.parse((spaceBtn && spaceBtn.dataset.models) || "{}");
  const classicOffsets = JSON.parse((spaceBtn && spaceBtn.dataset.classic) || "{}");
  const dishSettings = JSON.parse((spaceBtn && spaceBtn.dataset.dishSettings) || "{}");
  const currentModel = () => models[modelSelect ? modelSelect.value : "mini"] || null;
  const trayX = (name) => form.querySelector('[name="trays-' + name + '-x"]');
  const trayY = (name) => form.querySelector('[name="trays-' + name + '-y"]');
  const machineInput = (key) => form.querySelector('[name="brushograph-' + key + '"]');
  /* What is left of the machine for a painting, after the strip the canvas is
     offset by. Max Width and Max Height are the machine's limits, measured from
     the origin — where the containers sit — and a painting starts at the canvas
     offset, so the offset comes off the limit. On Pinkograph that is 156 less
     25: a 149 mm painting was 18 mm past the end of the bed. Infinity when the
     config carries no limit, which leaves the size alone. */
  const machineLimit = (limitKey, offsetKey) => {
    const limit = parseFloat((machineInput(limitKey) || {}).value);
    if (!isFinite(limit)) return Infinity;
    const offset = parseFloat((machineInput(offsetKey) || {}).value);
    return limit - (isFinite(offset) ? offset : 0);
  };
  // Custom cups are spaced from the form's own figures: spacing is centre to
  // centre between colours, and the water cup is parted from cyan by the same
  // wall — the same sum configspec.custom_offsets does.
  const CUSTOM_KEYS = ["cup_width_water", "cup_width", "cup_depth", "cup_spacing"];
  const customOffsets = () => {
    const [water, width, , spacing] = CUSTOM_KEYS.map((k) => parseFloat((machineInput(k) || {}).value));
    if (![water, width, spacing].every(isFinite)) return null;
    const first = water / 2 + width / 2 + (spacing - width);
    return Object.fromEntries([["water", 0],
      ...["cyan", "magenta", "yellow", "kroma"].map((n, i) => [n, first + i * spacing])]);
  };
  const offsetsFor = (shape) => shape === "classic" ? classicOffsets
    : shape === "custom" ? customOffsets()
    : (currentModel() || {}).offsets;
  const setNumber = (input, value) => {
    input.value = String(Math.round(value * 100) / 100);
  };
  // One event for the lot: the sketch redraws off the form, not per field.
  const redraw = () => form.dispatchEvent(new Event("input", { bubbles: true }));

  const spaceCups = () => {
    if (!shapeSelect) return 0;
    const water = trayX("water");
    const base = parseFloat(water && water.value);
    if (!isFinite(base)) return 0;
    // The holder is one straight row, so every cup shares the water cup's Y.
    const row = parseFloat((trayY("water") || {}).value);
    let moved = 0;
    for (const [name, off] of Object.entries(offsetsFor(shapeSelect.value) || {})) {
      const input = trayX(name);
      if (!input) continue;
      setNumber(input, base + off);
      const y = trayY(name);
      if (y && isFinite(row)) setNumber(y, row);
      moved += 1;
    }
    return moved;
  };

  const showForShape = () => {
    if (!shapeSelect) return;
    const classic = shapeSelect.value === "classic";
    if (spaceBtn) {
      spaceBtn.hidden = !trayX("water") || !offsetsFor(shapeSelect.value);
      if (spaceNote) spaceNote.hidden = spaceBtn.hidden;
    }
    for (const el of form.querySelectorAll('.coord[data-tray="kroma"], article.tray[data-tray="kroma"]')) {
      el.hidden = classic;
      for (const input of el.querySelectorAll("input, select")) input.disabled = classic;
    }
    // The cup sizes only mean something for custom containers. Hidden, not
    // disabled, so a config keeps its figures when another holder is picked.
    for (const key of CUSTOM_KEYS) {
      const field = machineInput(key) && machineInput(key).closest(".field");
      if (field) field.hidden = shapeSelect.value !== "custom";
    }
    // The stir before the swipe belongs to a rectangular bay: a round cup
    // sweeps its chord whatever this says. Hidden the same way.
    const mix = machineInput("cup_mix_sweeps");
    const mixField = mix && mix.closest(".field");
    if (mixField) mixField.hidden = classic;
  };

  // What the selected holder fixes besides positions: the dish's radii and
  // heights, or the CMYK crucibles' lift, dip and swipe exit for this model.
  // Custom cups are nobody's design, so they come with no heights of their own.
  const holderSettings = () => !shapeSelect ? {}
    : shapeSelect.value === "classic" ? dishSettings
    : shapeSelect.value === "custom" ? {}
    : (currentModel() || {}).containers || {};

  // Space the cups and set up everything their size decides, for whichever
  // holder is selected — so going from the CMYK holder to the dishes and back,
  // or from one model's crucibles to the other's, leaves nothing behind.
  const setUpContainers = () => {
    let changed = spaceCups();
    for (const [key, value] of Object.entries(holderSettings())) {
      // A config without the setting has no control for it, and no need.
      const input = machineInput(key);
      if (!input) continue;
      setNumber(input, value);
      changed += 1;
    }
    return changed;
  };

  if (shapeSelect) {
    shapeSelect.addEventListener("change", () => {
      showForShape();
      setUpContainers();
      redraw();
    });
    showForShape();
  }
  if (spaceBtn) {
    spaceBtn.addEventListener("click", () => {
      if (setUpContainers()) redraw();
    });
  }

  /* Each speed group's Acc (M204) and Feedrate 2 (M203) are Marlin commands,
     stripped from the G-code for any other controller, so only Marlin shows
     them. A config with no controller is treated as GRBL, as the pipeline does.
     Hidden, not disabled, so the figures survive a switch to another controller. */
  const controllerSelect = form.querySelector('[name="controller-controller_type"]');
  const showForController = () => {
    const marlin = !!controllerSelect && controllerSelect.value.trim().toLowerCase() === "marlin";
    for (const input of form.querySelectorAll('[name^="brushograph-moves-"][name$="-acc"], [name^="brushograph-moves-"][name$="-feedrate_2"]')) {
      const field = input.closest(".field");
      if (field) field.hidden = !marlin;
    }
  };
  if (controllerSelect) controllerSelect.addEventListener("change", showForController);
  showForController();

  /* ---- the model: Mini or 𝔐𝔦𝔨𝔯𝔬 ---- */
  /* Choosing a model puts its travel limits, canvas offset and tray lift in the
     form and spaces the containers on its holder. Going back to the model the
     config opened as puts back what the config said instead, so trying 𝔐𝔦𝔨𝔯𝔬
     on a tuned Mini config and changing your mind costs nothing. The painted
     width is brought inside the new travel, and the height follows it. */
  if (modelSelect) {
    const touched = () => [
      ...[...new Set([
        ...Object.values(models).flatMap((m) => [
          ...Object.keys(m.settings || {}), ...Object.keys(m.containers || {})]),
        ...Object.keys(dishSettings), ...CUSTOM_KEYS,
      ])].map(machineInput),
      machineInput("width"), machineInput("height"), shapeSelect,
      ...[...form.querySelectorAll('.tray-coords input[name$="-x"], .tray-coords input[name$="-y"]')],
    ].filter(Boolean);
    const opened = { model: modelSelect.value, values: new Map() };
    for (const input of touched()) opened.values.set(input, input.value);

    const fitClassic = () => {
      const m = currentModel();
      const option = shapeSelect && shapeSelect.querySelector('option[value="classic"]');
      if (!m || !option) return;
      option.disabled = !m.classic;
      if (!m.classic && shapeSelect.value === "classic") shapeSelect.value = "modern";
    };

    modelSelect.addEventListener("change", () => {
      const m = currentModel();
      if (!m) return;
      const label = modelSelect.selectedOptions[0].textContent;
      if (modelSelect.value === opened.model) {
        for (const [input, value] of opened.values) input.value = value;
        fitClassic();
      } else {
        for (const [key, value] of Object.entries(m.settings || {})) {
          const input = machineInput(key);
          if (input) setNumber(input, value);
        }
        fitClassic();
        // The holder goes where this model has room for it, and the rest
        // are spaced along from there.
        const [wx, wy] = m.water || [];
        if (trayX("water") && isFinite(wx)) setNumber(trayX("water"), wx);
        if (trayY("water") && isFinite(wy)) setNumber(trayY("water"), wy);
        setUpContainers();
      }
      // The painted size shrinks to fit the new bed, keeping its proportions:
      // a picture loaded later sets the height from the width anyway. Not on
      // the way back, which puts back whatever the config said.
      const width = machineInput("width");
      const height = machineInput("height");
      // Against what is paintable, not the raw limits: the canvas offset is
      // the strip the containers stand in, and no painting reaches into it.
      const maxW = machineLimit("max_width", "offset_x");
      const maxH = machineLimit("max_height", "offset_y");
      const w = parseFloat(width && width.value);
      const h = parseFloat(height && height.value);
      if (modelSelect.value !== opened.model && width && height && w > 0 && h > 0) {
        const fit = Math.min(1, maxW / w, maxH / h);
        if (fit < 1) {
          width.value = String(Math.floor(w * fit));
          height.value = String(Math.floor(h * fit));
        }
      }
      showForShape();
      if (modelNote) {
        say(modelNote, modelSelect.value === opened.model
          ? "Back to the {model} settings this config opened with."
          : "Set up for the {model}: travel limits, canvas offset, container positions and heights. Check them against the machine.",
          { model: label });
        modelNote.hidden = false;
      }
      // Through the width, so the height is matched to the picture again.
      if (width) width.dispatchEvent(new Event("input", { bubbles: true }));
      else redraw();
    });
    fitClassic();
    showForShape();
  }

  /* ---- height follows the width and the uploaded image's aspect ratio ---- */
  /* i2gc maps the pixel grid onto width x height regardless of aspect, so a
     mismatch stretches the painting rather than fitting it. */
  const ratioNote = $("ratio-note");
  const widthInput = form.querySelector('[name="brushograph-width"]');
  const heightInput = form.querySelector('[name="brushograph-height"]');
  const shapes = new Map();   // tray name -> {w, h}

  const note = (english, vars, warn) => {
    if (!ratioNote) return;
    if (english) say(ratioNote, english, vars); else ratioNote.textContent = "";
    ratioNote.hidden = !english;
    ratioNote.classList.toggle("warn", !!warn);
  };

  function measure(input) {
    const tray = input.name === "cmyk_photo"
      ? "photograph"
      : (input.name.match(/^trays-(.+)-image$/) || [])[1];
    if (!tray) return;
    const file = input.files[0];
    if (!file) { shapes.delete(tray); matchRatio(); return; }
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      let w = img.naturalWidth, h = img.naturalHeight;
      // The server lays a portrait photograph on its side (cmyk_sep.landscape).
      if (tray === "photograph" && h > w) [w, h] = [h, w];
      shapes.set(tray, { w, h });
      URL.revokeObjectURL(url);
      matchRatio();
    };
    img.onerror = () => { URL.revokeObjectURL(url); shapes.delete(tray); matchRatio(); };
    img.src = url;
  }

  const paintableHeight = () => machineLimit("max_height", "offset_y");

  /* The browser's own guard on a height typed by hand, kept in step with the
     two fields it comes from: matching the picture's proportions is the only
     thing that sets the height on its own, and it fits it, but nothing stopped
     a figure entered straight into the field. */
  const capPaintedHeight = () => {
    const height = machineInput("height");
    if (!height) return;
    const limit = paintableHeight();
    if (isFinite(limit) && limit >= 1) height.max = String(Math.floor(limit));
    else height.removeAttribute("max");
  };
  capPaintedHeight();

  function matchRatio() {
    if (!widthInput || !heightInput) return;
    const entries = [...shapes.entries()];
    if (!entries.length) return note(null);
    const width = parseFloat(widthInput.value);
    if (!isFinite(width) || width <= 0) return note("set a width first", null, true);

    const [tray, shape] = entries[0];
    const ratio = shape.h / shape.w;
    // Whole millimetres: the ratio is a guide, not a tolerance.
    const limit = paintableHeight();
    let fitted = width;
    let height = Math.max(1, Math.round(fitted * ratio));
    let touched = false;
    // Too tall for the bed: narrow the painting until it fits, rather than
    // squash it. The width is the figure that was set, but a picture that runs
    // off the end of the bed is not a painting.
    if (height > limit) {
      fitted = Math.max(1, Math.floor(limit / ratio));
      height = Math.max(1, Math.min(Math.round(fitted * ratio), Math.floor(limit)));
      // Set quietly: the listener that calls this runs on typing, not on an
      // assignment, so writing the field back does not call it again.
      if (widthInput.value !== String(fitted)) {
        widthInput.value = fitted;
        touched = true;
      }
    }
    if (heightInput.value !== String(height)) {
      heightInput.value = height;
      touched = true;
    }
    // One event for whichever of the two moved — it bubbles to the form
    // listener, which is what redraws the sketch.
    if (touched) heightInput.dispatchEvent(new Event("input", { bubbles: true }));

    const ratios = entries.map(([, s]) => s.h / s.w);
    if (Math.max(...ratios) - Math.min(...ratios) > 0.005) {
      note("images differ in aspect ratio — will use {tray} ({w}x{h})",
           { tray: trayName(tray), w: shape.w, h: shape.h }, true);
    } else if (fitted !== width) {
      note("{w}x{h} mm from {tray} — narrowed from {asked} mm, the bed paints {max} mm tall",
           { w: fitted, h: height, tray: trayName(tray), asked: width, max: limit }, true);
    } else {
      note("height {height} mm, matching {tray}'s {w}x{h} px",
           { height, tray: trayName(tray), w: shape.w, h: shape.h });
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
      if (target) sayTitle(wcBtn, "Convert {tray}'s photo", { tray: trayName(target.tray) });
      else sayTitle(wcBtn, "Choose a photo for a tray first");
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

      const label = labelOf(wcBtn);
      wcBtn.textContent = t("Converting…");
      wcBtn.disabled = true;
      wcNote.hidden = true;
      try {
        const res = await fetch("woodcut_preview", { method: "POST", body: fd });
        if (!res.ok) throw new Error(await serverError(res));
        const blob = await res.blob();
        if (wcImg.dataset.url) URL.revokeObjectURL(wcImg.dataset.url);
        const url = URL.createObjectURL(blob);
        wcImg.dataset.url = url;
        wcImg.src = url;
        wcImg.hidden = false;
        say(wcNote, "{tray}: {file}", { tray: trayName(target.tray), file: target.file.name });
        wcNote.classList.remove("warn");
        wcNote.hidden = false;
      } catch (err) {
        say(wcNote, String(err.message || err));
        wcNote.classList.add("warn");
        wcNote.hidden = false;
      } finally {
        say(wcBtn, label);
        wcBtn.disabled = false;
      }
    });
    refreshWoodcut();
    detectSubject();
  }

  /* ---- colour photograph -> CMYK plates ---- */
  const cmykInput = $("cmyk-photo");
  const cmykControls = $("cmyk-controls");
  const cmykBtn = $("cmyk-preview-btn");
  const cmykImg = $("cmyk-image");
  const cmykNote = $("cmyk-note");
  const cmykCutoff = $("cmyk-cutoff");
  const cmykKnockout = $("cmyk-knockout");
  let cmykPreviewTimer = null;

  function cmykFile() {
    return cmykInput && cmykInput.files.length ? cmykInput.files[0] : null;
  }

  async function previewCmyk() {
    const file = cmykFile();
    if (!file || !cmykBtn) return;
    const fd = new FormData();
    fd.append("image", file);
    if (cmykCutoff) fd.append("cmyk_threshold", cmykCutoff.value);
    if (cmykKnockout) fd.append("cmyk_knockout", cmykKnockout.checked ? "true" : "false");
    fd.append("theme", document.documentElement.dataset.theme || "default");

    const label = labelOf(cmykBtn);
    cmykBtn.textContent = t("Separating…");
    cmykBtn.disabled = true;
    if (cmykNote) cmykNote.hidden = true;
    try {
      const res = await fetch("cmyk_preview", { method: "POST", body: fd });
      if (!res.ok) throw new Error(await serverError(res));
      const blob = await res.blob();
      if (cmykImg.dataset.url) URL.revokeObjectURL(cmykImg.dataset.url);
      const url = URL.createObjectURL(blob);
      cmykImg.dataset.url = url;
      cmykImg.src = url;
      cmykImg.hidden = false;
      if (cmykNote) {
        cmykNote.textContent = file.name;      // a filename is nobody's language
        cmykNote.classList.remove("warn");
        cmykNote.hidden = false;
      }
    } catch (err) {
      if (cmykNote) {
        say(cmykNote, String(err.message || err));
        cmykNote.classList.add("warn");
        cmykNote.hidden = false;
      }
    } finally {
      say(cmykBtn, label);
      cmykBtn.disabled = false;
    }
  }

  if (cmykInput && cmykControls) {
    const cutoffOut = $("cmyk-cutoff-out");
    if (cmykCutoff && cutoffOut) {
      cmykCutoff.addEventListener("input", () => {
        cutoffOut.value = cmykCutoff.value;
        if (!cmykFile()) return;
        clearTimeout(cmykPreviewTimer);
        cmykPreviewTimer = setTimeout(previewCmyk, 180);
      });
    }
    if (cmykKnockout) {
      cmykKnockout.addEventListener("change", () => {
        if (cmykFile()) previewCmyk();
      });
    }
    const sizeNote = $("size-note");
    const sizeNotePhoto = $("size-note-photo");
    cmykInput.addEventListener("change", () => {
      const on = !!cmykFile();
      cmykControls.hidden = !on;
      // A colour photograph is laid on its side by the server when it is
      // portrait, so the painted-size note says that instead.
      if (sizeNote && sizeNotePhoto) {
        sizeNote.hidden = on;
        sizeNotePhoto.hidden = !on;
      }
      if (cmykImg) cmykImg.hidden = true;
      if (cmykNote) cmykNote.hidden = true;
      if (on) previewCmyk();
    });
    if (cmykBtn) cmykBtn.addEventListener("click", previewCmyk);
    document.addEventListener("brushograph:theme", () => {
      if (cmykImg && !cmykImg.hidden && cmykFile()) previewCmyk();
    });
  }

  /* ---- write the settings back over the kept config they came from ---- */
  /* Only offered for a kept config; the server refuses the update if somebody
     else has changed that config since this form was loaded. */
  const updateBtn = $("options-form-update-config");
  const versionInput = form.querySelector('[name="machine_config_version"]');
  if (updateBtn && versionInput) {
    updateBtn.addEventListener("click", async () => {
      const errBox = $("setup-error");
      const statusBox = $("setup-status");
      errBox.hidden = true;
      statusBox.hidden = true;
      // A type=button is not validated the way a submit is, so ask.
      if (!form.reportValidity()) return;
      const fd = new FormData(form);
      form.querySelectorAll('input[type="file"]').forEach((i) => fd.delete(i.name));
      const label = labelOf(updateBtn);
      updateBtn.textContent = t("Updating…");
      updateBtn.disabled = gcodeBtn.disabled = configBtn.disabled = true;
      try {
        const res = await fetch("machine_config/update", { method: "POST", body: fd });
        if (!res.ok) throw new Error(await serverError(res));
        const data = await res.json();
        // The next update from this form is compared against what this one wrote.
        versionInput.value = data.version;
        say(statusBox, "Updated {name} on the server.", { name: data.name });
        statusBox.hidden = false;
      } catch (err) {
        say(errBox, String(err.message || err));
        errBox.hidden = false;
      } finally {
        say(updateBtn, label);
        updateBtn.disabled = gcodeBtn.disabled = configBtn.disabled = false;
      }
    });
  }

  wireSimulator();
  wireMacros();

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
        ? (data.count > 1 ? t("{count} people", { count: data.count }) : t("a person"))
        : data.kind === "animal" ? t("an animal") : t("a prominent object");
      say($("wc-subject-label"), "Isolate {what}", { what });
      say($("wc-subject-note"),
          "found by {how}, covering {percent}% of the frame — the background becomes bare paper",
          { how: detectorName(data.how), percent: Math.round(data.coverage * 100) });
      row.hidden = false;
    } catch (err) {
      row.hidden = true;
      if (faceRow) faceRow.hidden = true;
    }
  }

  form.querySelectorAll('input[type="file"]').forEach((i) =>
    i.addEventListener("change", () => { measure(i); refreshWoodcut(); detectSubject(); }));
  if (widthInput) widthInput.addEventListener("input", matchRatio);

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
        say(errBox, "No images selected");
        errBox.hidden = false;
        return;
      }
    }

    const label = labelOf(submitter);
    submitter.textContent = t(wantsGcode ? "Generating…" : "Preparing…");
    gcodeBtn.disabled = configBtn.disabled = true;
    if (wantsGcode) {
      say(statusBox, "Tracing, slicing and planning brush strokes.");
      statusBox.hidden = false;
    }

    try {
      const res = await fetch(form.action, { method: form.method, body: fd });
      if (!res.ok) throw new Error(await serverError(res));
      const blob = await res.blob();
      const disposition = res.headers.get("Content-Disposition") || "";
      const match = disposition.match(/filename="?([^";]+)"?/);
      const filename = match ? match[1] : (wantsGcode ? "brushograph.gcode" : "machine.conf");

      if (!wantsGcode) {
        saveBlob(blob, filename);
        say(statusBox, "Downloaded {file} ({size} KB).",
            { file: filename, size: (blob.size / 1024).toFixed(0) });
        statusBox.hidden = false;
        return;
      }
      // The G-code is offered rather than saved: look at the preview first, and
      // download when it is what you wanted.
      const text = await blob.text();
      offerDownload(blob, filename);
      say(statusBox, "Ready: {file} ({size} KB). Preview below.",
          { file: filename, size: (blob.size / 1024).toFixed(0) });
      statusBox.hidden = false;
      try {
        showGcode(text);
      } catch (err) {
        // The file is already downloadable at this point, so a preview that
        // fails used to leave an empty box and no explanation.
        console.error("preview failed", err);
        say(errBox, "The file is ready, but the preview could not be drawn: {error}",
            { error: t(String(err.message || err)) });
        errBox.hidden = false;
      }
    } catch (err) {
      statusBox.hidden = true;
      say(errBox, String(err.message || err));
      errBox.hidden = false;
    } finally {
      say(submitter, label);
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

/* The preview is drawn on white paper whatever the theme. It stands for the
 * painting, and paint colours only read true against paper: on a dark theme's
 * sheet yellow glared and black vanished into it. The paint colours are not in
 * here: a stroke is the colour of the paint that draws it. */
const PREVIEW_INK = {
  paper: "#ffffff",
  travel: "#e6e9e8",
  marker: "#a8321f",
  cup: CUP_COLOUR,
  key: TRAY_COLOURS.kroma,
};

// A dip is read from the "; dip" marker copicograf writes before each descent
// into a cup: from there until the brush first rises, the moves are in the
// paint. Heights cannot tell, because a dip depth equal to the canvas height
// puts both at the same Z. A file without markers (from before them) falls back
// to the heights: canvas and dip are the config's canvas_height and dip_depth.
function parseGcode(text, { canvas = 0, dip = null } = {}) {
  const near = (a, b) => Math.abs(a - b) < 0.001;
  const marked = /^\s*;\s*dip\b/im.test(text);
  const moves = [];
  let x = 0, y = 0, z = 10, tray = null, trayIndex = -1;
  const trays = [];
  let paintMM = 0, travelMM = 0, dips = 0, strokes = 0, wasDown = false, dipping = false;

  for (const rawLine of text.split("\n")) {
    if (marked && /^\s*;\s*dip\b/i.test(rawLine)) { dipping = true; dips++; continue; }
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
    // Z at the canvas is painting; in a cup is not, however low it goes. The
    // move that leaves the cup (the swipe up the stairs, or the lift) is in it.
    let inCup;
    if (marked) {
      inCup = dipping;
      if (dipping && nz > z + 0.001) dipping = false;
    } else {
      inCup = dip === null ? nz < canvas - 0.001
        : !near(dip, canvas) && (near(nz, dip) || near(z, dip));
    }
    const down = !inCup && (near(nz, canvas) || nz < canvas);
    const d = Math.hypot(nx - x, ny - y);
    if (down && wasDown) paintMM += d; else travelMM += d;
    if (down && !wasDown) strokes++;
    // Unmarked: one per descent into the paint, not per move made down there.
    if (!marked && (dip === null ? inCup && z >= canvas - 0.001
      : inCup && near(nz, dip) && z > nz + 0.001)) dips++;
    moves.push({ x1: x, y1: y, x2: nx, y2: ny, down: down && wasDown, cup: inCup, tray: trayIndex });
    wasDown = down; x = nx; y = ny; z = nz;
  }
  return { moves, trays, paintMM, travelMM, dips, strokes };
}

function trayColour(name, index) {
  const key = name && name.toLowerCase();
  if (key === "key") return PREVIEW_INK.key;
  if (key && TRAY_COLOURS[key]) return TRAY_COLOURS[key];
  if (key && /^#[0-9a-f]{6}$/i.test(key)) return key;
  return FALLBACK_COLOURS[(index < 0 ? 0 : index) % FALLBACK_COLOURS.length];
}

// view and drawn are the preview's caches (see drawGcode); null means redo.
const sim = { data: null, upto: 1, view: null, drawn: null };

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
  say(button, "Download {file}", { file: filename });
  button.hidden = false;
  if (note) {
    say(note, "{size} KB", { size: (blob.size / 1024).toFixed(0) });
    note.hidden = false;
  }
}

/* What a draw needs that does not change from frame to frame: the scale and
 * each tray's colour. Worked out once per file rather than per frame. */
function simView(canvas) {
  const { moves, trays } = sim.data;
  // Swept in a loop rather than with Math.min(...xs). The spread passes one
  // argument per coordinate, and a real job has hundreds of thousands of them:
  // past roughly a hundred thousand the call stack gives out and the preview
  // dies with "Maximum call stack size exceeded".
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
  const skin = PREVIEW_INK;
  const colours = new Map();
  for (let i = -1; i < trays.length; i++) colours.set(i, trayColour(trays[i], i));
  return {
    skin, colours,
    // Machine Y grows away from the origin; the canvas grows downward.
    px: (x) => pad + (x - minX) * scale,
    py: (y) => canvas.height - pad - (y - minY) * scale,
  };
}

function simLayer(canvas) {
  const layer = document.createElement("canvas");
  layer.width = canvas.width;
  layer.height = canvas.height;
  const ctx = layer.getContext("2d");
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  return { layer, ctx };
}

function drawGcode() {
  const canvas = $("gcode-canvas");
  if (!canvas || !sim.data || !sim.data.moves.length) return;
  const { moves } = sim.data;
  const cut = Math.floor(moves.length * sim.upto);

  // Travel and painting are kept on layers of their own, so painting stays on
  // top of travel however the moves arrive. Playing forward only adds the
  // moves since the last frame to them; going back starts the layers again.
  if (!sim.view) {
    sim.view = simView(canvas);
    sim.drawn = null;
  }
  const { skin, colours, px, py } = sim.view;
  if (!sim.drawn || cut < sim.drawn.upto) {
    sim.drawn = { upto: 0, travel: simLayer(canvas), paint: simLayer(canvas) };
  }
  const { travel, paint } = sim.drawn;

  if (cut > sim.drawn.upto) {
    const from = sim.drawn.upto;
    travel.ctx.strokeStyle = skin.travel;
    travel.ctx.lineWidth = 1;
    travel.ctx.beginPath();
    for (let i = from; i < cut; i++) {
      const m = moves[i];
      if (m.down || m.cup) continue;
      travel.ctx.moveTo(px(m.x1), py(m.y1));
      travel.ctx.lineTo(px(m.x2), py(m.y2));
    }
    travel.ctx.stroke();

    const p = paint.ctx;
    let current = null;
    p.lineWidth = 1.8;
    for (let i = from; i < cut; i++) {
      const m = moves[i];
      if (!m.down) continue;
      const colour = m.cup ? skin.cup : colours.get(m.tray);
      if (colour !== current) {
        if (current !== null) p.stroke();
        p.strokeStyle = colour;
        p.beginPath();
        current = colour;
      }
      p.moveTo(px(m.x1), py(m.y1));
      p.lineTo(px(m.x2), py(m.y2));
    }
    if (current !== null) p.stroke();
    sim.drawn.upto = cut;
  }

  const ctx = canvas.getContext("2d");
  ctx.fillStyle = skin.paper;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(travel.layer, 0, 0);
  ctx.drawImage(paint.layer, 0, 0);

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
  const rough = minutes < 60
    ? t("{n} min", { n: minutes.toFixed(0) })
    : t("{n} h", { n: (minutes / 60).toFixed(1) });
  const stats = [
    [`${(paintMM / 1000).toFixed(1)} m`, "painted"],
    [`${(travelMM / 1000).toFixed(1)} m`, "travel"],
    [strokes.toLocaleString(), "brush downs"],
    [dips.toLocaleString(), "cup dips"],
    [moves.length.toLocaleString(), "moves"],
    [`~${rough}`, "rough time"],
  ];
  box.innerHTML = "";
  for (const [value, label] of stats) {
    const d = el("div", "sim-stat");
    d.appendChild(el("b", null, value));
    d.appendChild(el("span", null, t(label)));
    box.appendChild(d);
  }
  const legend = el("div", "sim-legend");
  const entries = trays.length
    ? trays.map((name, i) => [trayColour(name, i), trayName(name)])
    : [["#2f7fd0", t("painting")]];
  const skin = PREVIEW_INK;
  entries.push([skin.cup, t("in the cups")], [skin.travel, t("travel")]);
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

/* ------------------------------------------------------------ macros ---- */
/* zero.g, home.g, paper.g, clean.g, prime.g — one round trip to /macros, held
 * here as {name: text} so Download and Upload need no second request. Same
 * shape as the config download, minus the tray images that one refuses to
 * run without: /macros only reads the text fields. */
let pendingMacros = null;

function wireMacros() {
  const form = $("options-form");
  const genBtn = $("macros-generate");
  const dlBtn = $("macros-download");
  const upBtn = $("macros-upload");
  const status = $("macros-status");
  const errBox = $("macros-error");
  const list = $("macro-list");
  if (!genBtn || !form) return;

  function report(english, vars, bad) {
    if (bad) {
      say(errBox, english, vars);
      errBox.hidden = false;
      status.hidden = true;
    } else {
      say(status, english, vars);
      status.hidden = false;
      errBox.hidden = true;
    }
  }

  genBtn.addEventListener("click", async () => {
    errBox.hidden = true;
    status.hidden = true;
    const label = labelOf(genBtn);
    genBtn.textContent = t("Generating…");
    genBtn.disabled = true;
    try {
      const fd = new FormData(form);
      // The images are for a paint job; the macros never touch them, and
      // sending them anyway would be the whole tray upload for nothing.
      form.querySelectorAll('input[type="file"]').forEach((i) => fd.delete(i.name));
      const res = await fetch("macros", { method: "POST", body: fd });
      if (!res.ok) throw new Error(await serverError(res));
      const { macros } = await res.json();
      pendingMacros = macros;
      list.innerHTML = "";
      for (const [name, text] of Object.entries(macros)) {
        const li = el("li");
        say(li, "{name} ({bytes} B)", { name, bytes: new Blob([text]).size });
        list.appendChild(li);
      }
      list.hidden = false;
      dlBtn.hidden = false;
      upBtn.hidden = false;
      report("Generated {count} macros from the settings above.",
             { count: Object.keys(macros).length });
    } catch (err) {
      report(String(err.message || err), null, true);
    } finally {
      say(genBtn, label);
      genBtn.disabled = false;
    }
  });

  dlBtn.addEventListener("click", () => {
    if (!pendingMacros) return;
    // One save per file rather than a zip: no new dependency for five small
    // text files, and each already has the name it should land under.
    for (const [name, text] of Object.entries(pendingMacros)) {
      saveBlob(new Blob([text], { type: "text/plain" }), name);
    }
  });

  upBtn.addEventListener("click", () => uploadMacrosToMachine());
}

function showGcode(text) {
  const card = $("preview-card");
  if (!card) return;
  stopSim();
  const height = (key) => parseFloat((document.querySelector('[name="brushograph-' + key + '"]') || {}).value);
  const canvas = height("canvas_height"), dip = height("dip_depth");
  sim.data = parseGcode(text, { canvas: isFinite(canvas) ? canvas : 0, dip: isFinite(dip) ? dip : null });
  sim.view = sim.drawn = null;
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
    say(at, "{percent}% of {n} moves",
        { percent: Math.round(sim.upto * 100), n: sim.data.moves.length.toLocaleString() });
    at.hidden = false;
  }
}

// How long Play takes from start to finish, whatever the size of the job.
const SIM_PLAY_MS = 4000;
let simFrame = null;

function stopSim() {
  if (simFrame === null) return;
  cancelAnimationFrame(simFrame);
  simFrame = null;
  const play = $("sim-play");
  if (play) say(play, "▶ Play");
}

function wireSimulator() {
  document.addEventListener("brushograph:theme", () => {
    // The drawing keeps its white paper; only the words under it follow the
    // theme, which can change their language.
    if (sim.data) renderSimStats();
  });
  const scrub = $("sim-scrub"), play = $("sim-play"), open = $("sim-open");
  if (!scrub) return;
  // A drag fires input faster than the screen refreshes; draw once per frame.
  let scrubFrame = null;
  scrub.addEventListener("input", () => {
    stopSim();
    sim.upto = Number(scrub.value) / 1000;
    if (scrubFrame !== null) return;
    scrubFrame = requestAnimationFrame(() => {
      scrubFrame = null;
      drawGcode();
      updateSimAt();
    });
  });
  play.addEventListener("click", () => {
    if (simFrame !== null) { stopSim(); return; }
    if (!sim.data) return;
    if (sim.upto >= 1) sim.upto = 0;
    say(play, "❚❚ Pause");
    // Paced by the clock, not by a fixed step per tick: a frame that takes
    // longer than it should moves the preview on further instead of letting
    // ticks queue up behind it.
    let last = performance.now();
    const step = (now) => {
      sim.upto = Math.min(1, sim.upto + (now - last) / SIM_PLAY_MS);
      last = now;
      scrub.value = Math.round(sim.upto * 1000);
      drawGcode();
      updateSimAt();
      if (sim.upto >= 1) { simFrame = null; say(play, "▶ Play"); return; }
      simFrame = requestAnimationFrame(step);
    };
    simFrame = requestAnimationFrame(step);
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

/* The about page has no dialog and no tooltips to put in one. */
const dialog = $("info-dialog");
if (dialog) {
  const closeDialog = () => dialog.close();
  dialog.addEventListener("click", closeDialog);
  dialog.addEventListener("close", () => window.removeEventListener("scroll", closeDialog));
  document.addEventListener("click", (e) => {
    const btn = e.target.closest(".info-btn");
    if (!btn) return;
    e.preventDefault();
    if (window.innerWidth > 768) return;   // desktop gets the native tooltip
    e.stopPropagation();
    // Already translated in place, tooltip and label alike, so it is read off
    // the button rather than translated a second time here.
    const text = btn.getAttribute("title") || btn.getAttribute("aria-label");
    if (!text) return;
    dialog.textContent = text;
    dialog.showModal();
    setTimeout(() => window.addEventListener("scroll", closeDialog, { once: true, passive: true }), 100);
  });
}
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

function machineSay(english, vars, bad) {
  const note = $("machine-note");
  const err = $("machine-error");
  if (note) note.hidden = true;
  if (err) err.hidden = true;
  const box = bad ? err : note;
  if (box) {
    say(box, english, vars);
    box.hidden = false;
  }
}

async function sendToMachine(start) {
  if (!pendingFile) return;
  const base = await machineBase();
  if (!base) {
    machineSay("Set a hostname under Machine setup, Connection.", null, true);
    return;
  }
  // A page served over https may not talk to a machine over http, and no
  // amount of no-cors changes that: the browser blocks it as mixed content.
  if (location.protocol === "https:" && base.startsWith("http:")) {
    machineSay("This page is on https and {base} is not, so the browser will block the "
      + "connection. Open the WebUI over http on the same network as the machine, or "
      + "download the file and upload it yourself.", { base }, true);
    return;
  }

  const name = pendingFile.filename.replace(/[^A-Za-z0-9._-]/g, "_");
  const buttons = [$("gcode-send"), $("gcode-run")].filter(Boolean);
  const labels = buttons.map(labelOf);
  buttons.forEach((b) => { b.disabled = true; });
  let ws = null;

  try {
    machineSay("Sending {name} to {base}…", { name, base });
    const fd = new FormData();
    fd.append("path", "/");
    fd.append("myfile", pendingFile.blob, name);
    await fetch(`${base}/upload`, { method: "POST", body: fd, mode: "no-cors" });

    if (!start) {
      machineSay("{name} sent to {base}. The reply is opaque, so check the machine's own "
        + "file list to be sure.", { name, base });
      return;
    }
    // The card needs a moment to commit the file before the controller can be
    // asked to run it.
    machineSay("{name} sent. Waiting {seconds}s for the card to catch up…",
               { name, seconds: SD_SYNC_MS / 1000 });
    buttons[1].textContent = t("Starting…");
    await new Promise((r) => setTimeout(r, SD_SYNC_MS));

    const heard = [];
    ws = await openMachineSocket(base, heard);
    const cmd = encodeURIComponent(`$SD/Run=/${name}`);
    await fetch(`${base}/command?cmd=${cmd}`, { mode: "no-cors" });
    // Listen to the machine's own console rather than assuming.
    await new Promise((r) => setTimeout(r, WS_LISTEN_MS));
    const said = heard.filter((m) => m && !/^PING/i.test(m)).slice(-3).join(" · ");
    if (said) machineSay("{name}: $SD/Run sent. The machine says: {said}", { name, said });
    else machineSay("{name}: $SD/Run sent, but the machine said nothing back. Check it.", { name });
  } catch (e) {
    machineSay("Could not reach {base}: {error}. Check the hostname under Machine setup, "
      + "Connection, and that this page and the machine are on the same network.",
      { base, error: t(String(e.message || e)) }, true);
  } finally {
    if (ws) { try { ws.close(); } catch (e) { /* already gone */ } }
    buttons.forEach((b, i) => { b.disabled = false; say(b, labels[i]); });
  }
}

/* Same shape as sendToMachine(), one request per macro rather than one file,
 * but a different endpoint: /upload writes to the SD card, and macros are not
 * a job the SD card ever runs — FluidNC's own web server registers /files for
 * its local flash filesystem and /upload for the SD card as two distinct
 * routes (WebUIServer.cpp: "/files" -> LocalFSFileupload, "/upload" ->
 * SDFileUpload), sharing the same fileUpload() and so the same path/myfile
 * shape either way. There is no $SD/Run here either: these are routines an
 * operator runs by hand, not a job to start the moment it lands. */
async function uploadMacrosToMachine() {
  if (!pendingMacros) return;
  const note = $("macros-machine-note");
  const err = $("macros-machine-error");
  function report(english, vars, bad) {
    if (note) note.hidden = true;
    if (err) err.hidden = true;
    const box = bad ? err : note;
    if (box) { say(box, english, vars); box.hidden = false; }
  }

  const base = await machineBase();
  if (!base) {
    report("Set a hostname under Machine setup, Connection.", null, true);
    return;
  }
  if (location.protocol === "https:" && base.startsWith("http:")) {
    report("This page is on https and {base} is not, so the browser will block the "
      + "connection. Open the WebUI over http on the same network as the machine, or "
      + "download the macros and upload them yourself.", { base }, true);
    return;
  }

  const upBtn = $("macros-upload");
  const label = labelOf(upBtn);
  upBtn.disabled = true;
  const names = Object.keys(pendingMacros);
  let sent = 0;
  try {
    for (const name of names) {
      report("Sending {name} to {base} (flash)… ({sent}/{total})",
             { name, base, sent, total: names.length });
      const fd = new FormData();
      fd.append("path", "/");
      fd.append("myfile", new Blob([pendingMacros[name]], { type: "text/plain" }), name);
      await fetch(`${base}/files`, { method: "POST", body: fd, mode: "no-cors" });
      sent += 1;
    }
    report("Sent {count} macros to {base}'s flash filesystem. The reply is opaque, so "
      + "check the machine's own file list to be sure.", { count: sent, base });
  } catch (e) {
    report("Could not reach {base}: {error}. Sent {sent}/{total} before that. Check the "
      + "hostname under Machine setup, Connection, and that this page and the machine "
      + "are on the same network.",
      { base, error: t(String(e.message || e)), sent, total: names.length }, true);
  } finally {
    upBtn.disabled = false;
    say(upBtn, label);
  }
}

/* ------------------------------------------------------- language, applied */
/* The head script has already put the remembered theme on <html>, so this runs
 * with the right language known and the page is translated on the way to the
 * first paint rather than flashing English first. The form is not here yet —
 * loadOptionsForm translates that as it arrives. */
applyLanguageToPage();
document.addEventListener("brushograph:theme", applyLanguageToPage);
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
