// Score review page: Pyodide runs the project's Python analyzer in the browser,
// Verovio engraves the reviewed MusicXML, and overlay.js draws the analysis.

import { drawOverlay, ringNotes } from "./overlay.js";
import { romanHTML, ruleName, withNoteIds, escapeHTML, leadingLocation, VOICE_NAMES } from "./notation.js";

const PYODIDE = "https://cdn.jsdelivr.net/npm/pyodide@0.29.5/";
const VEROVIO = "https://cdn.jsdelivr.net/npm/verovio@6.3.0/dist/";

const $ = (selector) => document.querySelector(selector);
const scoreEl = $("#score");
const panel = $("#panel");
const statusEl = $("#status");
const state = { analysis: null, report: "", name: "", filter: "all", pinned: null };

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

$("#download").addEventListener("click", () => {
  const blob = new Blob([state.report], { type: "text/markdown" });
  const link = Object.assign(document.createElement("a"), {
    href: URL.createObjectURL(blob), download: state.name.replace(/\.[^.]+$/, "") + "-review.md" });
  link.click();
  URL.revokeObjectURL(link.href);
});

async function openFile(name, bytesPromise) {
  setStatus(`Reviewing ${name}…`);
  document.body.classList.add("busy");
  try {
    const [bridge, toolkit, bytes] = await Promise.all([pythonReady, verovioReady, bytesPromise]);
    const reply = JSON.parse(bridge.review_upload(name, new Uint8Array(bytes)));
    if (reply.error) {
      showError(name, reply.error);
      return;
    }
    Object.assign(state, { analysis: reply.analysis, report: reply.report, name, pinned: null, filter: "all" });
    toolkit.loadData(withNoteIds(reply.musicxml));
    state.toolkit = toolkit;
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

function showError(name, message) {
  setStatus("");
  $("#download").hidden = true;
  document.body.classList.remove("has-score");
  state.analysis = null;
  scoreEl.querySelector(".engraving")?.remove();
  scoreEl.querySelector(".overlay")?.remove();
  panel.innerHTML = `
    <div class="problem">
      <h2>${escapeHTML(name)} could not be reviewed</h2>
      <p>${escapeHTML(message)}</p>
      <p class="quiet">The reviewer currently reads four-voice chorale exercises: one major key, 4/4 time,
      four notes sounding together at each chord, no ties, dots, tuplets, grace notes or pickup measure.
      Export in concert pitch with repeats written out.</p>
    </div>`;
}

function setStatus(text, kind) {
  statusEl.textContent = text;
  statusEl.className = kind || "";
}

// ---------- engraving ----------

function render() {
  if (!state.toolkit || !state.analysis) return;
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

function renderPanel() {
  const a = state.analysis;
  const errors = a.findings.filter((f) => f.severity === "error").length;
  const suggestions = a.findings.length - errors;
  const corrected = a.harmony.filter((c) => c.original_label && c.label_matches === false);
  const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
  const extraParadigmNotes = a.review.paradigm_notes.slice(a.paradigms.length);

  panel.innerHTML = `
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

    <section>
      <div class="findings-head">
        <h3>Voice leading</h3>
        <div class="filter" role="group" aria-label="Show findings">
          ${["all", "error", "suggestion"].map((f) => `<button type="button" data-filter="${f}" aria-pressed="${state.filter === f}">${{ all: "All", error: "Errors", suggestion: "Suggestions" }[f]}</button>`).join("")}
        </div>
      </div>
      ${a.findings.length ? "" : `<p class="quiet">No voice-leading problems found under the supported rules.</p>`}
      <ol class="findings">${a.findings.map((f, i) => `
        <li class="${f.severity}" ${state.filter !== "all" && state.filter !== f.severity ? "hidden" : ""}>
          <button type="button" class="item" data-finding="${i}">
            <span class="badge ${f.severity}" aria-hidden="true">${i + 1}</span>
            <span class="item-title">${ruleName(f.rule)}</span>
            <span class="where">m. ${f.measure}, beat ${f.beat}${f.voices.length < 4 ? ", " + f.voices.map((v) => VOICE_NAMES[v] || v).join(" and ") : ""}</span>
            <span class="body">${prose(f.message)}</span>
            <span class="evidence">${f.notes.map((n) => `${n.voice} ${n.pitch} <small>m.${n.measure} b.${n.beat}</small>`).join(", ")}</span>
          </button>
        </li>`).join("")}</ol>
    </section>`;
  $("#download").hidden = false;
}

/** Escape analyzer prose and typeset the Roman numerals in it with proper figures. */
function prose(text) {
  return escapeHTML(text).replace(/\b(?:vii|vi|iv|iii|ii|i|VII|VI|IV|V|III|II|I)[°ø]?(?:6\/4|6\/5|4\/3|4\/2|6|7)(?=[\s.,:;)]|$)/g,
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
  if (!state.analysis) return;
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
