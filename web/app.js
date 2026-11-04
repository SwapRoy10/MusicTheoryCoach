// Score review page: Pyodide runs the project's Python analyzer in the browser,
// Verovio engraves the reviewed MusicXML, and overlay.js draws the analysis.

import { drawOverlay, ringNotes } from "./overlay.js";
import { Player } from "./player.js";
import { PracticeEditor, writeExercise, parsePitch } from "./practice.js";
import { romanHTML, ruleName, withNoteIds, escapeHTML, leadingLocation, VOICE_NAMES, SPECIES_NAMES } from "./notation.js";

const PYODIDE = "https://cdn.jsdelivr.net/npm/pyodide@0.29.5/";
const VEROVIO = "https://cdn.jsdelivr.net/npm/verovio@6.3.0/dist/";

const $ = (selector) => document.querySelector(selector);
const scoreEl = $("#score");
const panel = $("#panel");
const statusEl = $("#status");
const state = {
  analysis: null, report: "", musicxml: "", name: "", filter: "all", pinned: null,
  mode: "review", composeTab: "species",
  form: { species: "1", above: "true", source: "generate", mode: "dorian", cantus: "", key: "C", bars: "4",
          line: "", given: "S", lineKey: "C", chromatic: false, lineChromatic: false },
  practiceForm: { pkind: "species", pspecies: "1", pabove: "true", pmode: "dorian", pkey: "C", pbars: "4", pgiven: "S", pchromatic: false },
  practice: null,
};

// ---------- engines ----------

const pythonReady = (async () => {
  const { loadPyodide } = await import(`${PYODIDE}pyodide.mjs`);
  const pyodide = await loadPyodide({ indexURL: PYODIDE });
  const manifest = await (await fetch("py/manifest.json")).json();
  const base = "/home/pyodide/app";
  for (const path of manifest) {
    const response = await fetch(`py/${path}`);
    if (!response.ok) throw new Error(`Could not load ${path}`);
    const target = `${base}/${path}`;
    pyodide.FS.mkdirTree(target.slice(0, target.lastIndexOf("/")));
    pyodide.FS.writeFile(target, new Uint8Array(await response.arrayBuffer()));
  }
  pyodide.runPython(`import sys; sys.path.insert(0, "${base}")`);
  return pyodide.pyimport("bridge");
})();

const verovioReady = (async () => {
  const [{ default: createVerovioModule }, { VerovioToolkit }] = await Promise.all([
    import(`${VEROVIO}verovio-module.mjs`), import(`${VEROVIO}verovio.mjs`)]);
  return new VerovioToolkit(await createVerovioModule());
})();

Promise.all([pythonReady, verovioReady]).then(
  () => setStatus(""),
  (error) => setStatus(`The analyzer could not load: ${error.message}. Check your connection and reload.`, "error"));
setStatus("Loading the analyzer…");

// ---------- playback ----------

const player = new Player(scoreEl, (playing) => {
  $("#play").textContent = playing ? "■ Stop" : "▶ Play";
  $("#play").setAttribute("aria-pressed", String(playing));
});
$("#play").addEventListener("click", () => (player.playing ? player.stop() : player.playAll()));

// ---------- input ----------

$("#file").addEventListener("change", (event) => {
  const file = event.target.files[0];
  if (file) openFile(file.name, file.arrayBuffer());
  event.target.value = "";
});

for (const target of [scoreEl, document.body]) {
  target.addEventListener("dragover", (event) => { event.preventDefault(); document.body.classList.add("dragging"); });
}
document.body.addEventListener("dragleave", (event) => {
  if (!event.relatedTarget) document.body.classList.remove("dragging");
});
document.body.addEventListener("drop", (event) => {
  event.preventDefault();
  document.body.classList.remove("dragging");
  const file = event.dataTransfer.files[0];
  if (file) openFile(file.name, file.arrayBuffer());
});

fetch("examples/index.json").then((r) => r.json()).then((examples) => {
  const list = $("#examples");
  for (const example of examples) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = example.title;
    button.addEventListener("click", () =>
      openFile(example.file, fetch(`examples/${example.file}`).then((r) => r.arrayBuffer())));
    list.append(button);
  }
});

function save(text, type, filename) {
  const link = Object.assign(document.createElement("a"), {
    href: URL.createObjectURL(new Blob([text], { type })), download: filename });
  link.click();
  URL.revokeObjectURL(link.href);
}
const baseName = () => state.name.replace(/\.[^.]+$/, "");
$("#download").addEventListener("click", () => save(state.report, "text/markdown", `${baseName()}-review.md`));
$("#download-xml").addEventListener("click", () =>
  save(state.musicxml, "application/vnd.recordare.musicxml+xml", `${baseName()}.musicxml`));
$("#mode").addEventListener("click", () => setMode(state.mode === "compose" ? "review" : "compose"));
$("#practice").addEventListener("click", () => setMode(state.mode === "practice" ? "review" : "practice"));
$("#start-compose").addEventListener("click", () => setMode("compose"));
$("#start-practice").addEventListener("click", () => setMode("practice"));

function setMode(mode) {
  const leaving = state.mode;
  state.mode = mode;
  $("#mode").setAttribute("aria-pressed", String(mode === "compose"));
  $("#practice").setAttribute("aria-pressed", String(mode === "practice"));
  document.body.classList.toggle("composing", mode === "compose");
  document.body.classList.toggle("practicing", mode === "practice");
  if (leaving === "practice" && mode !== "practice") {
    // Leaving practice clears its score from the page.
    state.analysis = null;
    player.stop();
    scoreEl.querySelector(".engraving")?.remove();
    scoreEl.querySelector(".overlay")?.remove();
    document.body.classList.remove("has-score");
    $("#play").hidden = $("#download").hidden = $("#download-xml").hidden = true;
  }
  if (mode === "practice") {
    if (state.practice) {
      document.body.classList.add("has-score");
      showPractice();
    } else {
      state.analysis = null;
      scoreEl.querySelector(".engraving")?.remove();
      scoreEl.querySelector(".overlay")?.remove();
      document.body.classList.remove("has-score");
      renderPanel();
    }
    return;
  }
  if (state.analysis || mode === "compose") renderPanel();
  else panel.innerHTML = introHTML;
  if (mode === "compose") panel.querySelector("form")?.scrollIntoView({ block: "nearest" });
}

/** Run a bridge call after the status line has painted (composing can take a few seconds). */
async function run(label, call, name, keep = {}) {
  setStatus(label);
  document.body.classList.add("busy");
  await new Promise((resolve) => requestAnimationFrame(() => setTimeout(resolve, 30)));
  try {
    const [bridge, toolkit] = await Promise.all([pythonReady, verovioReady]);
    const reply = JSON.parse(await call(bridge));
    if (reply.error) {
      showError(name, reply.error, reply.kind);
      return;
    }
    player.stop();
    Object.assign(state, { analysis: reply.analysis, report: reply.report, musicxml: reply.musicxml,
                           composed: Boolean(reply.composed), plan: reply.plan || null,
                           name, pinned: null, filter: "all", fixes: {}, history: [], edits: [], ...keep });
    toolkit.loadData(withNoteIds(reply.musicxml));
    state.toolkit = toolkit;
    player.load(toolkit, reply.musicxml);
    $("#play").hidden = false;
    render();
    renderPanel();
    setStatus("");
    document.body.classList.add("has-score");
  } catch (error) {
    showError(name, error.message || String(error));
  } finally {
    document.body.classList.remove("busy");
  }
}

async function openFile(name, bytesPromise) {
  if (state.mode !== "review") setMode("review");
  const bytes = await bytesPromise;
  return run(`Reviewing ${name}…`, (bridge) => bridge.review_upload(name, new Uint8Array(bytes)), name);
}

function compose() {
  const f = state.form;
  const seed = Math.floor(Math.random() * 2 ** 31);
  if (state.composeTab === "harmonize") {
    const options = { text: f.line, voice: f.given, key: f.lineKey, seed, chromatic: f.lineChromatic };
    return run(`Harmonizing your ${f.given === "S" ? "melody" : "bass"}…`, (bridge) => bridge.harmonize(JSON.stringify(options)),
      `Harmonization in ${keyLabel(f.lineKey)}`);
  }
  if (state.composeTab === "chorale") {
    const options = { key: f.key, bars: Number(f.bars), seed, chromatic: f.chromatic };
    return run("Composing a chorale…", (bridge) => bridge.compose_chorale(JSON.stringify(options)),
      `Chorale in ${keyLabel(f.key)}`);
  }
  const species = Number(f.species);
  const options = { species, above: f.above === "true", mode: f.mode, seed,
                    cantus: f.source === "mine" ? f.cantus.trim() : null };
  const side = options.above ? "above" : "below";
  return run(`Composing ${SPECIES_NAMES[species].toLowerCase()} counterpoint…`,
    (bridge) => bridge.compose_species(JSON.stringify(options)),
    `${SPECIES_NAMES[species]} species, ${side} the cantus`);
}

function showError(name, message, kind) {
  setStatus("");
  $("#download").hidden = $("#download-xml").hidden = $("#play").hidden = true;
  player.stop();
  document.body.classList.remove("has-score");
  state.analysis = null;
  scoreEl.querySelector(".engraving")?.remove();
  scoreEl.querySelector(".overlay")?.remove();
  const help = state.mode === "compose"
    ? "Change the settings and try again."
    : kind === "species"
      ? `Species exercises need two voices: a cantus firmus in whole notes (one per bar) and a counterpoint,
         in 4/4 or 2/2 with one key and no pickup measure. Ties are fine; tuplets and grace notes are not.`
      : `The reviewer reads four-voice chorale exercises (one major key, 4/4 time, four notes sounding together
         at each chord, no ties, dots, tuplets, grace notes or pickup measure) and two-voice species
         counterpoint exercises. Export in concert pitch with repeats written out.`;
  panel.innerHTML = (state.mode === "compose" ? composeHTML() : "") + `
    <div class="problem">
      <h2>${escapeHTML(name)} ${state.mode === "compose" ? "could not be composed" : "could not be reviewed"}</h2>
      <p>${escapeHTML(message)}</p>
      <p class="quiet">${help}</p>
    </div>`;
}

function setStatus(text, kind) {
  statusEl.textContent = text;
  statusEl.className = kind || "";
}

// ---------- engraving ----------

function render() {
  if (!state.toolkit || (!state.analysis && !(state.mode === "practice" && state.practice))) return;
  const width = scoreEl.clientWidth;
  const scale = width < 640 ? 30 : 40;
  state.toolkit.setOptions({
    scale, pageWidth: Math.max(1200, Math.round(width * 100 / scale)), pageHeight: 60000,
    adjustPageHeight: true, breaks: "auto", header: "none", footer: "none",
    // Room for the overlay (finding numbers and paradigm brackets above each
    // system, reviewed numerals below) stays constant in screen pixels.
    pageMarginTop: Math.round(13200 / scale), pageMarginBottom: Math.round(6400 / scale),
    pageMarginLeft: 40, pageMarginRight: 40, spacingSystem: Math.round(1200 / scale), svgViewBox: true,
  });
  state.toolkit.redoLayout();
  scoreEl.querySelector(".engraving")?.remove();
  const engraving = document.createElement("div");
  engraving.className = "engraving";
  for (let page = 1; page <= state.toolkit.getPageCount(); page++) engraving.innerHTML += state.toolkit.renderToSVG(page);
  scoreEl.prepend(engraving);
  if (state.mode === "practice" && state.practice) decoratePractice(engraving);
  if (!state.analysis) {
    scoreEl.querySelector(".overlay")?.remove();
    return;
  }

  const { findings } = state.analysis;
  const worst = new Map();
  findings.forEach((f) => f.notes.forEach((n) => {
    if (worst.get(n.id) !== "error") worst.set(n.id, f.severity);
  }));
  for (const [id, severity] of worst) engraving.querySelector(`g.note[id="${id}"]`)?.classList.add(`mark-${severity}`);
  drawOverlay(scoreEl, state.analysis, findings.map((_, i) => i + 1));
  if (state.pinned) highlight(state.pinned, false);
}

let resizeTimer;
new ResizeObserver(() => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(render, 150);
}).observe(scoreEl);

// ---------- review panel ----------

const introHTML = panel.innerHTML;

function renderPanel() {
  const a = state.analysis;
  if (state.mode === "practice") {
    panel.innerHTML = practiceHTML() + (a ? (a.kind === "species" ? speciesHTML(a) : choraleHTML(a)) : "");
    $("#download").hidden = !a;
    $("#download-xml").hidden = !state.practice;
    return;
  }
  const form = state.mode === "compose" ? composeHTML() : "";
  if (!a) {
    panel.innerHTML = form || introHTML;
    return;
  }
  panel.innerHTML = form + (a.kind === "species" ? speciesHTML(a) : choraleHTML(a));
  $("#download").hidden = false;
  $("#download-xml").hidden = false;
}

// ---------- compose form ----------

const MODES = { dorian: "Dorian (D)", phrygian: "Phrygian (E)", mixolydian: "Mixolydian (G)", aeolian: "Aeolian (A)", ionian: "Ionian (C)" };
const KEYS = ["C", "G", "D", "A", "E", "F", "Bb", "Eb", "Ab", "Am", "Em", "Bm", "F#m", "C#m", "Dm", "Gm", "Cm", "Fm"];
const keyLabel = (k) => (k.endsWith("m") ? `${k.slice(0, -1)} minor` : `${k} major`).replace(/^([A-G])b/, "$1♭").replace("#", "♯");
const keyOptions = (current, option) => `<optgroup label="Major">${KEYS.filter((k) => !k.endsWith("m")).map((k) => option(k, keyLabel(k), current)).join("")}</optgroup>
  <optgroup label="Minor">${KEYS.filter((k) => k.endsWith("m")).map((k) => option(k, keyLabel(k), current)).join("")}</optgroup>`;
const check = (name, on, label) => `<label class="check"><input type="checkbox" name="${name}" ${on ? "checked" : ""}> ${label}</label>`;

function composeHTML() {
  const f = state.form;
  const option = (value, label, current) => `<option value="${value}" ${String(current) === String(value) ? "selected" : ""}>${escapeHTML(label)}</option>`;
  const tab = (id, label) => `<button type="button" role="tab" data-tab="${id}" aria-selected="${state.composeTab === id}">${label}</button>`;
  const species = `
      <label>Species
        <select name="species">${[1, 2, 3, 4, 5].map((n) => option(n, `${SPECIES_NAMES[n]} species`, f.species)).join("")}</select>
      </label>
      <fieldset class="choice"><legend>Counterpoint</legend>
        <label><input type="radio" name="above" value="true" ${f.above === "true" ? "checked" : ""}> Above the cantus</label>
        <label><input type="radio" name="above" value="false" ${f.above === "false" ? "checked" : ""}> Below the cantus</label>
      </fieldset>
      <fieldset class="choice"><legend>Cantus firmus</legend>
        <label><input type="radio" name="source" value="generate" ${f.source === "generate" ? "checked" : ""}> Compose one in
          <select name="mode" aria-label="Mode">${Object.entries(MODES).map(([v, l]) => option(v, l, f.mode)).join("")}</select></label>
        <label><input type="radio" name="source" value="mine" ${f.source === "mine" ? "checked" : ""}> Use mine</label>
        <input type="text" name="cantus" value="${escapeHTML(f.cantus)}" placeholder="D4 F4 E4 D4 G4 F4 A4 G4 F4 E4 D4"
          spellcheck="false" autocomplete="off" aria-label="Your cantus firmus" ${f.source === "mine" ? "" : "hidden"}>
      </fieldset>
      <p class="quiet">Every result is checked by the species reviewer before it is shown. Rules and sources:
        the species counterpoint guide in the reference library.</p>`;
  const chorale = `
      <div class="row">
        <label>Key
          <select name="key">${keyOptions(f.key, option)}</select></label>
        <label>Length
          <select name="bars">${[4, 5, 6, 7, 8].map((n) => option(n, `${n} bars`, f.bars)).join("")}</select></label>
      </div>
      ${check("chromatic", f.chromatic, "Approach the cadence with a chromatic chord (applied V, Neapolitan, augmented sixth or borrowed chord)")}
      <p class="quiet">A new phrase each time: tonic expansions from the reference paradigms, a predominant and an
        authentic cadence, voiced in SATB and then reviewed by the chorale checker.</p>`;
  const example = f.given === "S" ? "E5 F5 G5 F5 | E5 D5 C5" : "C3 D3 E3 F3 | G3 G3 C3";
  const harmonize = `
      <fieldset class="choice"><legend>Your line is the</legend>
        <label><input type="radio" name="given" value="S" ${f.given === "S" ? "checked" : ""}> Soprano (harmonize a melody)</label>
        <label><input type="radio" name="given" value="B" ${f.given === "B" ? "checked" : ""}> Bass (realize a bass line)</label>
      </fieldset>
      <label>Notes
        <textarea name="line" rows="2" spellcheck="false" autocomplete="off" placeholder="${example}">${escapeHTML(f.line)}</textarea></label>
      <label>Key
        <select name="lineKey">${keyOptions(f.lineKey, option)}</select></label>
      ${check("lineChromatic", f.lineChromatic, "Use chromatic chords freely (otherwise only where the line needs them)")}
      <p class="quiet">Half notes, one chord each, ending on a whole-note tonic; bar lines are optional. You can also open a
        MusicXML file with just one line. The other three voices are written and the whole chorale is checked.</p>`;
  const panes = { species, chorale, harmonize };
  return `
    <form class="compose" id="compose-form">
      <h2>Compose</h2>
      <div class="tabs" role="tablist">${tab("species", "Species")}${tab("chorale", "Chorale")}${tab("harmonize", "Harmonize")}</div>
      ${panes[state.composeTab]}
      <button type="submit" class="primary">${state.analysis && state.composed ? "Compose another" : "Compose"}</button>
    </form>`;
}

panel.addEventListener("input", (event) => {
  const { name } = event.target;
  const value = event.target.type === "checkbox" ? event.target.checked : event.target.value;
  if (!(name in state.form)) return;
  state.form[name] = value;
  if (name === "given") {
    panel.querySelector('textarea[name="line"]').placeholder = value === "S" ? "E5 F5 G5 F5 | E5 D5 C5" : "C3 D3 E3 F3 | G3 G3 C3";
  }
  if (name === "source") {
    const field = panel.querySelector('input[name="cantus"]');
    field.hidden = value !== "mine";
    if (value === "mine") field.focus();
  }
  if (name === "cantus" && value.trim()) {
    state.form.source = "mine";
    panel.querySelector('input[name="source"][value="mine"]').checked = true;
  }
});
panel.addEventListener("submit", (event) => {
  event.preventDefault();
  if (state.composeTab === "harmonize" && !state.form.line.trim()) {
    state.form.line = panel.querySelector('textarea[name="line"]').placeholder;
    panel.querySelector('textarea[name="line"]').value = state.form.line;
  }
  if (state.composeTab === "species" && state.form.source === "mine" && !state.form.cantus.trim()) {
    panel.querySelector('input[name="cantus"]').focus();
    return;
  }
  compose();
});
panel.addEventListener("click", (event) => {
  const tab = event.target.closest("[data-tab]");
  if (!tab) return;
  state.composeTab = tab.dataset.tab;
  renderPanel();
});

// ---------- review panels ----------

const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

function findingsHTML(a, name, where) {
  return `
    <section>
      <div class="findings-head">
        <h3>${name}</h3>
        <div class="filter" role="group" aria-label="Show findings">
          ${["all", "error", "suggestion"].map((f) => `<button type="button" data-filter="${f}" aria-pressed="${state.filter === f}">${{ all: "All", error: "Errors", suggestion: "Suggestions" }[f]}</button>`).join("")}
        </div>
      </div>
      ${a.findings.length ? "" : `<p class="quiet">No problems found under the supported rules.</p>`}
      <ol class="findings">${a.findings.map((f, i) => `
        <li class="${f.severity}" ${state.filter !== "all" && state.filter !== f.severity ? "hidden" : ""}>
          <button type="button" class="item" data-finding="${i}">
            <span class="badge ${f.severity}" aria-hidden="true">${i + 1}</span>
            <span class="item-title">${ruleName(f.rule, a.rules)}</span>
            <span class="where">${where(f)}</span>
            <span class="body">${prose(f.message)}</span>
            ${ruleDetail(a, f)}
            ${f.notes.length ? `<span class="evidence">${f.notes.map((n) => `${n.voice} ${n.pitch} <small>m.${n.measure} b.${n.beat}</small>`).join(", ")}</span>` : ""}
          </button>
          ${f.notes.length ? `<div class="actions">
            <button type="button" class="link" data-hear="${i}">▶ Hear it</button>
            ${f.severity === "error" && state.fixes[i] === undefined ? `<button type="button" class="link" data-fixes="${i}">Suggest a fix</button>` : ""}
          </div>${fixesHTML(i)}` : ""}
        </li>`).join("")}</ol>
    </section>`;
}

const VOICE_WORD = { S: "soprano", A: "alto", T: "tenor", B: "bass", CP: "counterpoint" };

function fixesHTML(i) {
  const options = state.fixes[i];
  if (options === undefined) return "";
  if (options === "busy") return `<p class="fixes quiet">Searching and rechecking…</p>`;
  if (!options.length) return `<p class="fixes quiet">No single-note change removes this error without creating another. It needs a larger rewrite.</p>`;
  return `<ul class="fixes">${options.map((o, k) => `
    <li><button type="button" class="fix" data-apply="${i}:${k}">
      <span>Change ${VOICE_WORD[o.voice] || o.voice} <b>${escapeHTML(o.before)}</b> → <b>${escapeHTML(o.after)}</b>
        <small>m. ${escapeHTML(o.measure)}, beat ${escapeHTML(o.beat)}</small></span>
      <span class="quiet">Rechecked: ${o.fixed_errors > 1 ? `clears ${o.fixed_errors} errors` : "clears this error"}, no new errors${
        o.suggestion_change > 0 ? `, ${plural(o.suggestion_change, "new suggestion")}` : o.suggestion_change < 0 ? `, ${plural(-o.suggestion_change, "fewer suggestion")}` : ""}.</span>
      <span class="apply">Apply</span>
    </button></li>`).join("")}</ul>`;
}

async function findFixes(i) {
  state.fixes[i] = "busy";
  renderPanel();
  await new Promise((resolve) => requestAnimationFrame(() => setTimeout(resolve, 20)));
  const bridge = await pythonReady;
  const reply = JSON.parse(bridge.fixes_for(i));
  state.fixes[i] = reply.fixes || [];
  renderPanel();
  if (state.pinned?.finding !== i) {
    state.pinned = { finding: i };
  }
  highlight(state.pinned, false);
}

function applyFix(i, k) {
  const option = state.fixes[i][k];
  if (state.mode === "practice" && state.practice) {
    const editor = state.practice.editor;
    for (const id of option.note_ids || [option.note_id]) {
      if (editor.selectById(id, state.practice.ids)) editor.set(parsePitch(option.after));
    }
    state.practice.edits = (state.practice.edits || 0) + 1;
    return checkPractice();
  }
  const before = { analysis: state.analysis, report: state.report, musicxml: state.musicxml, composed: state.composed,
                   plan: state.plan, fixes: state.fixes, edits: state.edits };
  const history = [...state.history, before];
  const edits = [...state.edits, `${VOICE_WORD[option.voice] || option.voice} ${option.before} → ${option.after} (m. ${option.measure})`];
  run(`Applying ${option.before} → ${option.after} and reviewing again…`,
    (bridge) => bridge.apply_fix(JSON.stringify(option.note_ids || [option.note_id]), option.after),
    state.name, { history, edits, composed: state.composed, plan: state.plan });
}

async function undo() {
  const previous = state.history[state.history.length - 1];
  if (!previous) return;
  const bridge = await pythonReady;
  // Restore the analyzer's copy too, so later fixes apply to the right version.
  const reply = JSON.parse(bridge.restore(previous.musicxml));
  if (reply.error) return showError(state.name, reply.error);
  player.stop();
  Object.assign(state, previous, { history: state.history.slice(0, -1), pinned: null });
  state.toolkit.loadData(withNoteIds(state.musicxml));
  player.load(state.toolkit, state.musicxml);
  render();
  renderPanel();
}

function editsHTML() {
  if (!state.edits?.length) return "";
  return `<div class="edits"><p><b>${plural(state.edits.length, "fix")} applied:</b> ${state.edits.map(escapeHTML).join("; ")}.
    Download the MusicXML to keep this version.</p><button type="button" class="link" data-undo>Undo last fix</button></div>`;
}

/** Species findings cite the catalog rule, its strength and its sources. */
function ruleDetail(a, f) {
  const rule = a.rules?.[f.rule];
  if (!rule) return "";
  const sources = rule.sources.map((s) => a.sources[s]).filter(Boolean)
    .map((s) => `<a href="${escapeHTML(s.url)}" target="_blank" rel="noopener">${escapeHTML(s.work)}</a>`);
  return `<span class="rule"><span class="strength ${rule.strength}">${rule.strength}</span> ${escapeHTML(rule.rule)}
    ${sources.length ? `<span class="cite">${[...new Set(sources)].join(" · ")}</span>` : ""}</span>`;
}

function speciesHTML(a) {
  const errors = a.findings.filter((f) => f.severity === "error").length;
  const side = a.above ? "above" : "below";
  const marks = a.review.marks;
  return `
    <header class="panel-head">
      <h2>${escapeHTML(state.name)}</h2>
      <p class="tally">
        <span class="count error">${plural(errors, "error")}</span>
        <span class="count suggestion">${plural(a.findings.length - errors, "suggestion")}</span>
        <span class="count paradigm">${plural(marks.length, "figure")}</span>
      </p>
      <p class="quiet">${SPECIES_NAMES[a.species]} species, counterpoint ${side} the cantus firmus, ${escapeHTML(a.mode)},
        ${a.scope.reviewed_measures} bars. The numbers under the score are the intervals between the voices;
        grey italic ones are dissonances.${a.scope.cantus_assumption ? " " + escapeHTML(a.scope.cantus_assumption) : ""}</p>
      ${state.composed ? `<p class="composed">Composed here and checked by the same reviewer used for uploads.</p>` : ""}
      ${editsHTML()}
    </header>
    ${findingsHTML(a, "Counterpoint", (f) => f.notes.length ? `m. ${f.measure}, beat ${f.beat}` : "Whole exercise")}
    <section>
      <h3>Figures</h3>
      ${marks.length ? "" : `<p class="quiet">No suspensions or idiomatic figures (cambiata, double neighbor) to point out.</p>`}
      <ul class="paradigms">${marks.map((m, i) => `
        <li><button type="button" class="item" data-paradigm="${i}">
          <span class="item-title">${escapeHTML(m.name)}</span>
        </button></li>`).join("")}</ul>
    </section>`;
}

function choraleHTML(a) {
  const errors = a.findings.filter((f) => f.severity === "error").length;
  const suggestions = a.findings.length - errors;
  const corrected = a.harmony.filter((c) => c.original_label && c.label_matches === false);
  const extraParadigmNotes = a.review.paradigm_notes.slice(a.paradigms.length);
  const plan = state.composed && state.plan;

  return `
    <header class="panel-head">
      <h2>${escapeHTML(state.name)}</h2>
      <p class="tally">
        <span class="count error">${plural(errors, "error")}</span>
        <span class="count suggestion">${plural(suggestions, "suggestion")}</span>
        <span class="count paradigm">${plural(a.paradigms.length, "paradigm")}</span>
      </p>
      <p class="quiet">${a.scope.reviewed_measures} measures, ${a.harmony.length} chords reviewed.
        Blue numerals under each system are the reviewed analysis; red ones differ from what you wrote.
        Voices are assigned from the lowest note up, so crossings can’t be detected.</p>
      ${plan ? `<p class="composed">${plan.given ? `Your ${plan.given === "S" ? "melody" : "bass"} is kept as written; the other three voices were written here.`
        : "Composed here."} Checked by the same reviewer used for uploads.
        Chords: ${plan.chords.map((c) => `<span class="rn">${romanHTML(c)}</span>`).join(" ")}</p>` : ""}
      ${editsHTML()}
    </header>

    <section>
      <h3>Roman numerals</h3>
      ${corrected.length ? "" : `<p class="quiet">${a.supplied_labels.length ? "Your numerals match the notes." : "No numerals were written in the score; the reviewed numerals appear under each system."}</p>`}
      <ul class="notes">${a.review.label_notes
        .filter((text) => a.supplied_labels.length || !text.startsWith("Other supplied chord labels"))
        .map(noteItem).join("")}</ul>
      ${a.local_proposals.length ? `<h4>Suggested correction</h4><ul class="notes">${a.local_proposals.map(noteItem).join("")}</ul>` : ""}
    </section>

    <section>
      <h3>Paradigms</h3>
      ${a.paradigms.length ? "" : `<p class="quiet">No paradigm from the reference library was recognized.</p>`}
      <ul class="paradigms">${a.paradigms.map((p, i) => `
        <li><button type="button" class="item" data-paradigm="${i}">
          <span class="item-title">${escapeHTML(p.name)}
            <span class="chip ${p.status}">${p.status === "variant" ? "Variant" : "Match"}</span></span>
          <span class="where">m. ${p.start.measure}, beat ${p.start.beat} to m. ${p.end.measure}, beat ${p.end.beat}</span>
          <span class="body">${prose(p.description)} Reference p. ${p.source_printed_page}, fig. ${escapeHTML(p.source_figure)}.</span>
        </button></li>`).join("")}</ul>
      ${extraParadigmNotes.length ? `<ul class="notes">${extraParadigmNotes.map(noteItem).join("")}</ul>` : ""}
    </section>

    ${findingsHTML(a, "Voice leading", (f) => `m. ${f.measure}, beat ${f.beat}${f.voices.length < 4 ? ", " + f.voices.map((v) => VOICE_NAMES[v] || v).join(" and ") : ""}`)}`;
}

/** Escape analyzer prose and typeset the Roman numerals in it with proper figures. */
function prose(text) {
  const T = "(?:vii|vi|iv|iii|ii|VII|VI|IV|V|III|II)°?";
  const pattern = new RegExp(`\\b(?:It|Fr|Ger)\\+6\\b|\\b(?:b(?=[IViv]))?(?:vii|vi|iv|iii|ii|i|VII|VI|IV|V|III|II|I|N)[°ø+]?(?:(?:6/4|6/5|4/3|4/2|6|7)(?:/b?${T})?|/b?${T})(?=[\\s.,:;)]|$)`, "g");
  return escapeHTML(text).replace(pattern,
    (label) => `<span class="rn">${romanHTML(label)}</span>`);
}

function noteItem(text) {
  const where = leadingLocation(text);
  const chord = where && state.analysis.harmony.find((c) => c.measure === where.measure && c.beat === where.beat);
  const html = prose(text);
  return chord
    ? `<li><button type="button" class="item" data-chord="${chord.measure}:${chord.beat}"><span class="body">${html}</span></button></li>`
    : `<li><span class="body">${html}</span></li>`;
}

// ---------- linking score and panel ----------

function notesFor(target) {
  const a = state.analysis;
  if (target.finding !== undefined) return a.findings[target.finding].notes.map((n) => n.id);
  if (target.paradigm !== undefined && a.kind === "species") {
    const m = a.review.marks[target.paradigm];
    const ids = a.harmony.map((c) => c.notes.CP.id);
    return ids.slice(ids.indexOf(m.anchor), ids.indexOf(m.end_anchor) + 1);
  }
  if (target.paradigm !== undefined) {
    const p = a.paradigms[target.paradigm];
    const order = (c) => Number(c.offset);
    const start = a.harmony.find((c) => c.measure === p.start.measure && c.beat === p.start.beat);
    const end = a.harmony.find((c) => c.measure === p.end.measure && c.beat === p.end.beat);
    return a.harmony.filter((c) => order(c) >= order(start) && order(c) <= order(end))
      .flatMap((c) => [c.notes.S.id, c.notes.B.id]);
  }
  if (target.chord) {
    const [measure, beat] = target.chord.split(":");
    const chord = a.harmony.find((c) => c.measure === measure && c.beat === beat);
    return chord ? Object.values(chord.notes).map((n) => n.id) : [];
  }
  return [];
}

function highlight(target, scroll = true) {
  document.querySelectorAll(".is-selected").forEach((el) => el.classList.remove("is-selected"));
  if (!target) {
    ringNotes(scoreEl, []);
    return;
  }
  const key = Object.keys(target)[0];
  const attr = { finding: "finding", paradigm: "paradigm", chord: "chord" }[key];
  document.querySelectorAll(`[data-${attr}="${CSS.escape(String(target[key]))}"]`).forEach((el) => el.classList.add("is-selected"));
  const severity = target.finding !== undefined ? state.analysis.findings[target.finding].severity : key;
  const ring = ringNotes(scoreEl, notesFor(target), severity);
  if (scroll) {
    ring?.scrollIntoView({ block: "center", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    panel.querySelector(`.item.is-selected`)?.scrollIntoView({ block: "nearest" });
  }
}

/** The rendered note whose notehead is at (or within a few pixels of) a point.
 *  Hit-testing by geometry is more forgiving than SVG glyph hit areas. */
function noteAt(x, y, slop = 5) {
  for (const head of scoreEl.querySelectorAll("g.note .notehead")) {
    const r = head.getBoundingClientRect();
    if (x >= r.left - slop && x <= r.right + slop && y >= r.top - slop && y <= r.bottom + slop) return head.closest("g.note");
  }
  return null;
}

function targetFrom(el) {
  if (el.dataset.finding !== undefined) return { finding: Number(el.dataset.finding) };
  if (el.dataset.paradigm !== undefined) return { paradigm: Number(el.dataset.paradigm) };
  if (el.dataset.chord) return { chord: el.dataset.chord };
  return null;
}

document.addEventListener("click", (event) => {
  if (state.mode === "practice" && !state.analysis) {
    practiceClick(event);
    return;
  }
  if (!state.analysis) return;
  if (event.target.closest("a[href]")) return;
  if (state.mode === "practice" && practiceClick(event)) return;
  const hear = event.target.closest("[data-hear]");
  if (hear) {
    const f = state.analysis.findings[Number(hear.dataset.hear)];
    player.playNotes(f.notes.map((n) => n.id));
    return;
  }
  const fixes = event.target.closest("[data-fixes]");
  if (fixes) return findFixes(Number(fixes.dataset.fixes));
  const apply = event.target.closest("[data-apply]");
  if (apply) {
    const [i, k] = apply.dataset.apply.split(":").map(Number);
    return applyFix(i, k);
  }
  if (event.target.closest("[data-undo]")) return undo();
  const filter = event.target.closest("[data-filter]");
  if (filter) {
    state.filter = filter.dataset.filter;
    renderPanel();
    if (state.pinned) highlight(state.pinned, false);
    return;
  }
  const item = event.target.closest("[data-finding], [data-paradigm], [data-chord]");
  if (item) {
    const target = targetFrom(item);
    const same = JSON.stringify(target) === JSON.stringify(state.pinned);
    state.pinned = same ? null : target;
    highlight(state.pinned, !same);
    return;
  }
  // Clicking a note on the score selects the first finding that cites it.
  const note = event.target.closest("#score") && noteAt(event.clientX, event.clientY);
  if (note) {
    const index = state.analysis.findings.findIndex((f) => f.notes.some((n) => n.id === note.id));
    if (index >= 0) {
      if (state.filter !== "all" && state.analysis.findings[index].severity !== state.filter) {
        state.filter = "all";
        renderPanel();
      }
      state.pinned = { finding: index };
      highlight(state.pinned, false);
      panel.querySelector(`.item[data-finding="${index}"]`)?.scrollIntoView({ block: "center", behavior: "smooth" });
    }
    return;
  }
  if (event.target.closest("#score")) {
    state.pinned = null;
    highlight(null);
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && state.pinned) {
    state.pinned = null;
    highlight(null);
  }
});


// ---------- practice ----------

const PRACTICE_STORE = "mtc-practice-v1";

function savePractice() {
  try {
    if (state.practice) localStorage.setItem(PRACTICE_STORE, JSON.stringify(state.practice.editor.ex));
  } catch { /* storage is a convenience only */ }
}

function restorePractice() {
  try {
    const saved = JSON.parse(localStorage.getItem(PRACTICE_STORE) || "null");
    if (saved?.voices) {
      state.practice = { editor: new PracticeEditor(saved), ids: {} };
      state.practiceForm.pkind = saved.kind;
    }
  } catch { /* ignore */ }
}
restorePractice();

async function newPractice() {
  const f = state.practiceForm;
  const options = f.pkind === "species"
    ? { kind: "species", species: Number(f.pspecies), above: f.pabove === "true", mode: f.pmode }
    : { kind: "chorale", key: f.pkey, bars: Number(f.pbars), given: f.pgiven, chromatic: f.pchromatic };
  options.seed = Math.floor(Math.random() * 2 ** 31);
  setStatus("Writing a new exercise…");
  document.body.classList.add("busy");
  await new Promise((resolve) => requestAnimationFrame(() => setTimeout(resolve, 30)));
  try {
    const bridge = await pythonReady;
    const reply = JSON.parse(bridge.practice_new(JSON.stringify(options)));
    if (reply.error) {
      setStatus(reply.error, "error");
      return;
    }
    state.practice = { editor: new PracticeEditor(reply.exercise), ids: {} };
    state.analysis = null;
    savePractice();
    document.body.classList.add("has-score");
    await showPractice();
    setStatus("");
  } finally {
    document.body.classList.remove("busy");
  }
}

/** Engrave the exercise as it stands and refresh the panel. */
async function showPractice() {
  const toolkit = await verovioReady;
  const { editor } = state.practice;
  const { xml, ids } = writeExercise(editor.ex);
  state.practice.ids = ids;
  state.musicxml = xml;
  state.name = editor.ex.title;
  toolkit.loadData(withNoteIds(xml));
  state.toolkit = toolkit;
  render();
  player.load(toolkit, xml);
  $("#play").hidden = false;
  renderPanel();
}

function decoratePractice(engraving) {
  const { editor, ids } = state.practice;
  for (const voice of editor.ex.voices) {
    (ids[voice.id] || []).forEach((id, i) => {
      const el = engraving.querySelector(`g[id="${id}"]`);
      if (!el) return;
      el.classList.add(voice.given ? "given" : "answer");
      if (!voice.given && !voice.events[i].rest && !voice.events[i].pitch) el.classList.add("blank");
    });
  }
  const sel = editor.selected;
  if (sel) {
    let i = sel.index;
    const v = editor.voice(sel.voice);
    do {
      engraving.querySelector(`g[id="${ids[sel.voice]?.[i]}"]`)?.classList.add("selected");
    } while (v.events[i].tieTo && ++i < v.events.length);
  }
}

function edited() {
  state.analysis = null;
  state.practice.notice = "";
  state.fixes = {};
  state.pinned = null;
  savePractice();
  showPractice();
}

function practiceClick(event) {
  const button = event.target.closest("[data-practice]");
  if (button) {
    const action = button.dataset.practice;
    const editor = state.practice?.editor;
    if (action === "new") newPractice();
    else if (action === "check") checkPractice();
    else if (action === "solution") toggleSolution();
    else if (action === "reset" && editor) {
      for (const v of editor.ex.voices) if (!v.given) v.events.forEach((e) => { if (!e.rest) e.pitch = null; });
      editor.selected = editor.firstEmpty();
      edited();
    } else if (editor) {
      keyCommand(action);
    }
    return true;
  }
  if (!state.practice || !event.target.closest("#score")) return false;
  const el = noteOrRestAt(event.clientX, event.clientY);
  if (el && state.practice.editor.selectById(el.id, state.practice.ids)) {
    if (state.analysis) {
      // A click on a marked note still opens its finding; editing starts with a key press.
      const index = state.analysis.findings.findIndex((f) => f.notes.some((n) => n.id === el.id));
      if (index >= 0) {
        state.pinned = { finding: index };
        highlight(state.pinned, false);
        panel.querySelector(`.item[data-finding="${index}"]`)?.scrollIntoView({ block: "center", behavior: "smooth" });
      }
      render();
      return true;
    }
    render();
    return true;
  }
  return false;
}

function noteOrRestAt(x, y, slop = 6) {
  for (const el of scoreEl.querySelectorAll("g.note, g.rest")) {
    const head = el.querySelector(".notehead") || el;
    const r = head.getBoundingClientRect();
    if (x >= r.left - slop && x <= r.right + slop && y >= r.top - slop && y <= r.bottom + slop) return el;
  }
  return null;
}

function keyCommand(action) {
  const editor = state.practice.editor;
  if (!editor.selected && !["next", "prev"].includes(action)) return;
  if (/^[A-G]$/.test(action)) {
    editor.letter(action);
    editor.move(1); // like most notation programs, typing a note moves on to the next one
  } else {
    ({ up: () => editor.step(1), down: () => editor.step(-1), octUp: () => editor.octave(1), octDown: () => editor.octave(-1),
       sharp: () => editor.accidental(1), flat: () => editor.accidental(-1), natural: () => editor.accidental(0),
       clear: () => editor.clear(), next: () => editor.move(1), prev: () => editor.move(-1),
       voiceUp: () => editor.nextVoice(-1), voiceDown: () => editor.nextVoice(1) }[action] || (() => {}))();
  }
  if (["next", "prev", "voiceUp", "voiceDown"].includes(action)) render();
  else edited();
}

document.addEventListener("keydown", (event) => {
  if (state.mode !== "practice" || !state.practice) return;
  if (event.target.closest("input, textarea, select") || event.metaKey || event.ctrlKey || event.altKey) return;
  const key = event.key;
  let action = null;
  if (/^[a-gA-G]$/.test(key)) action = key.toUpperCase();
  else if (key === "ArrowUp") action = event.shiftKey ? "octUp" : "up";
  else if (key === "ArrowDown") action = event.shiftKey ? "octDown" : "down";
  else if (key === "ArrowRight" || (key === "Tab" && !event.shiftKey)) action = "next";
  else if (key === "ArrowLeft" || (key === "Tab" && event.shiftKey)) action = "prev";
  else if (key === "#" || key === "+") action = "sharp";
  else if (key === "-" || key === "_") action = "flat";
  else if (key === "n" || key === "=") action = "natural";
  else if (key === "Backspace" || key === "Delete") action = "clear";
  else if (key === "PageUp") action = "voiceUp";
  else if (key === "PageDown") action = "voiceDown";
  else if (key === "Enter") return checkPractice();
  if (!action) return;
  event.preventDefault();
  keyCommand(action);
});

async function checkPractice() {
  const { editor } = state.practice;
  const empty = editor.empties();
  if (empty) {
    state.practice.notice = `${empty} note${empty === 1 ? " is" : "s are"} still empty (shown as rests). Fill every note, then check.`;
    renderPanel();
    return;
  }
  state.practice.notice = "";
  const ex = editor.ex;
  const { xml } = writeExercise(ex);
  const options = ex.kind === "species"
    ? { kind: "species", species: ex.species, cantus: ex.above ? "lower" : "upper" }
    : { kind: "chorale" };
  const bytes = new TextEncoder().encode(xml);
  await run("Checking your work…", (bridge) => bridge.review_upload(`${ex.title}.musicxml`, bytes, JSON.stringify(options)),
    ex.title, { composed: false, plan: null });
  if (state.analysis) {
    state.practice.checked = true;
    render();
    renderPanel();
  }
}

function toggleSolution() {
  const p = state.practice;
  if (p.mine) {
    p.editor.fill(p.mine);
    p.mine = null;
  } else {
    p.mine = p.editor.answers();
    p.editor.fill(p.editor.ex.solution);
  }
  state.analysis = null;
  showPractice().then(() => { if (!p.mine) return; checkPractice(); });
}

function practiceHTML() {
  const f = state.practiceForm;
  const option = (value, label, current) => `<option value="${value}" ${String(current) === String(value) ? "selected" : ""}>${escapeHTML(label)}</option>`;
  const species = `
      <div class="row">
        <label>Species <select name="pspecies">${[1, 2, 3, 4, 5].map((n) => option(n, `${SPECIES_NAMES[n]}`, f.pspecies)).join("")}</select></label>
        <label>Counterpoint <select name="pabove">${option("true", "Above", f.pabove)}${option("false", "Below", f.pabove)}</select></label>
      </div>
      <label>Mode <select name="pmode">${Object.entries(MODES).map(([v, l]) => option(v, l, f.pmode)).join("")}</select></label>`;
  const chorale = `
      <div class="row">
        <label>Key <select name="pkey">${keyOptions(f.pkey, option)}</select></label>
        <label>Given <select name="pgiven">${option("S", "Melody (soprano)", f.pgiven)}${option("B", "Bass line", f.pgiven)}</select></label>
      </div>
      <div class="row">
        <label>Length <select name="pbars">${[4, 5, 6, 7, 8].map((n) => option(n, `${n} bars`, f.pbars)).join("")}</select></label>
      </div>
      ${check("pchromatic", f.pchromatic, "Include a chromatic chord before the cadence")}`;
  const p = state.practice;
  const ex = p?.editor.ex;
  const sel = p?.editor.selected;
  const selected = sel && p.editor.event(sel);
  const pad = p ? `
    <div class="pad" role="group" aria-label="Note entry">
      <div class="pad-row">${["C", "D", "E", "F", "G", "A", "B"].map((l) => `<button type="button" data-practice="${l}">${l}</button>`).join("")}</div>
      <div class="pad-row">
        <button type="button" data-practice="up" title="Step up (↑)">↑</button>
        <button type="button" data-practice="down" title="Step down (↓)">↓</button>
        <button type="button" data-practice="octUp" title="Octave up (Shift+↑)">8va</button>
        <button type="button" data-practice="octDown" title="Octave down (Shift+↓)">8vb</button>
        <button type="button" data-practice="sharp" title="Sharp (#)">♯</button>
        <button type="button" data-practice="flat" title="Flat (-)">♭</button>
        <button type="button" data-practice="natural" title="Natural (n)">♮</button>
      </div>
      <div class="pad-row">
        <button type="button" data-practice="prev" title="Previous note (←)">◀</button>
        <button type="button" data-practice="next" title="Next note (→)">▶</button>
        ${ex.voices.filter((v) => !v.given).length > 1 ? `<button type="button" data-practice="voiceUp" title="Voice above (Page Up)">Voice ↑</button>
        <button type="button" data-practice="voiceDown" title="Voice below (Page Down)">Voice ↓</button>` : ""}
        <button type="button" data-practice="clear" title="Clear (Backspace)">Clear</button>
      </div>
      <p class="quiet">Click a rest or note to select it, then type a letter (A–G) or use the buttons. Arrows move by step;
        Shift+arrows by octave; # and - add accidentals; → and ← move along the voice.
        ${selected ? `<b>Selected:</b> ${escapeHTML(p.editor.voice(sel.voice).name)}, ${selected.pitch ? escapeHTML(selected.pitch) : "empty"}.` : ""}</p>
    </div>
    <div class="practice-actions">
      <button type="button" class="primary" data-practice="check">Check my work</button>
      <button type="button" class="link" data-practice="solution">${p.mine ? "Back to my answer" : "Show a solution"}</button>
      <button type="button" class="link" data-practice="reset">Start over</button>
    </div>
    ${p.notice ? `<p class="notice">${escapeHTML(p.notice)}</p>` : ""}
    ${p.mine ? `<p class="composed">Showing a solution written by the composer and checked by the reviewer. Your answer is kept.</p>` : ""}` : "";
  return `
    <form class="compose practice" id="practice-form">
      <h2>Practice</h2>
      <div class="tabs two" role="tablist">
        <button type="button" role="tab" data-ptab="species" aria-selected="${f.pkind === "species"}">Species</button>
        <button type="button" role="tab" data-ptab="chorale" aria-selected="${f.pkind === "chorale"}">Chorale</button>
      </div>
      ${f.pkind === "species" ? species : chorale}
      <button type="button" class="${p ? "link" : "primary"}" data-practice="new">${p ? "New exercise" : "Start an exercise"}</button>
      ${ex ? `<div class="prompt"><h3>${escapeHTML(ex.title)}</h3><p>${escapeHTML(ex.prompt)}</p></div>` : `<p class="quiet">Write the answer right here on the score: no notation program or upload needed. Your work stays in this browser.</p>`}
      ${pad}
    </form>`;
}

panel.addEventListener("input", (event) => {
  const { name } = event.target;
  if (!(name in state.practiceForm)) return;
  state.practiceForm[name] = event.target.type === "checkbox" ? event.target.checked : event.target.value;
});
panel.addEventListener("click", (event) => {
  const tab = event.target.closest("[data-ptab]");
  if (!tab) return;
  state.practiceForm.pkind = tab.dataset.ptab;
  renderPanel();
});
