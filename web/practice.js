// Practice mode: the student writes notes straight onto the engraved score.
// The exercise model (voices with fixed rhythms, some given) is turned into
// MusicXML here, engraved by Verovio and checked by the same Python reviewer
// as an upload. Note IDs n1, n2, ... follow document order, as everywhere else.

const STEPS = ["C", "D", "E", "F", "G", "A", "B"];
const SEMITONES = [0, 2, 4, 5, 7, 9, 11];
const SHARPS = "FCGDAEB";
const DIVISIONS = 2; // an eighth note is one division

export function parsePitch(text) {
  const m = /^([A-G])(#{1,2}|b{1,2})?(-?\d)$/.exec(text || "");
  if (!m) return null;
  const alter = (m[2] || "").split("").reduce((a, c) => a + (c === "#" ? 1 : -1), 0);
  return { step: m[1], alter, octave: Number(m[3]) };
}

export function pitchText(p) {
  return p.step + (p.alter > 0 ? "#".repeat(p.alter) : "b".repeat(-p.alter)) + p.octave;
}

const midi = (p) => 12 * (p.octave + 1) + SEMITONES[STEPS.indexOf(p.step)] + p.alter;
const diatonic = (p) => 7 * p.octave + STEPS.indexOf(p.step);

function signature(fifths) {
  const alters = Object.fromEntries(STEPS.map((s) => [s, 0]));
  const order = fifths >= 0 ? SHARPS : [...SHARPS].reverse().join("");
  for (const step of order.slice(0, Math.abs(fifths))) alters[step] = fifths >= 0 ? 1 : -1;
  return alters;
}

function noteType(quarters) {
  return { 4: ["whole", 0], 3: ["half", 1], 2: ["half", 0], 1.5: ["quarter", 1], 1: ["quarter", 0], 0.5: ["eighth", 0] }[quarters] || ["quarter", 0];
}

/** MusicXML for the exercise, and the note ID of every event. */
export function writeExercise(ex) {
  const ids = {};
  let counter = 0;
  const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;");
  const head = `<?xml version="1.0" encoding="UTF-8"?>\n<score-partwise version="4.0"><work><work-title>${esc(ex.title)}</work-title></work>`;
  const attrs = (clefs) => `<attributes><divisions>${DIVISIONS}</divisions><key><fifths>${ex.fifths}</fifths><mode>${ex.mode}</mode></key>`
    + `<time><beats>4</beats><beat-type>4</beat-type></time>${clefs.length > 1 ? `<staves>${clefs.length}</staves>` : ""}`
    + clefs.map((c, i) => `<clef${clefs.length > 1 ? ` number="${i + 1}"` : ""}><sign>${c}</sign><line>${c === "G" ? 2 : 4}</line></clef>`).join("")
    + `</attributes>`;
  const bars = (voice) => {
    const out = [];
    let t = 0;
    voice.events.forEach((e, i) => {
      const bar = Math.floor(t / 4 + 1e-9);
      (out[bar] ||= []).push([e, i]);
      t += e.dur;
    });
    return out;
  };
  const note = (voice, e, i, extra) => {
    const id = `n${++counter}`;
    (ids[voice.id] ||= [])[i] = id;
    const [type, dots] = noteType(e.dur);
    const p = parsePitch(e.pitch);
    const body = p
      ? `<pitch><step>${p.step}</step>${p.alter ? `<alter>${p.alter}</alter>` : ""}<octave>${p.octave}</octave></pitch>`
      : "<rest/>";
    const ties = p ? (e.tieFrom ? `<tie type="stop"/>` : "") + (e.tieTo ? `<tie type="start"/>` : "") : "";
    const notations = p && (e.tieFrom || e.tieTo)
      ? `<notations>${e.tieFrom ? `<tied type="stop"/>` : ""}${e.tieTo ? `<tied type="start"/>` : ""}</notations>` : "";
    return `<note id="${id}">${body}<duration>${e.dur * DIVISIONS}</duration>${ties}${extra.voice}<type>${type}</type>`
      + `${"<dot/>".repeat(dots)}${extra.stem && p && type !== "whole" ? `<stem>${extra.stem}</stem>` : ""}${extra.staff}${notations}</note>`;
  };
  let parts = "";
  let list = "";
  if (ex.layout === "grand") {
    list = `<score-part id="P1"><part-name>Chorale</part-name></score-part>`;
    const perVoice = ex.voices.map(bars);
    const count = Math.max(...perVoice.map((b) => b.length));
    let measures = "";
    for (let b = 0; b < count; b++) {
      let m = `<measure number="${b + 1}">${b === 0 ? attrs(["G", "F"]) : ""}`;
      ex.voices.forEach((voice, vi) => {
        if (vi) m += `<backup><duration>${4 * DIVISIONS}</duration></backup>`;
        const extra = { voice: `<voice>${vi + 1}</voice>`, stem: vi % 2 ? "down" : "up", staff: `<staff>${vi < 2 ? 1 : 2}</staff>` };
        for (const [e, i] of perVoice[vi][b] || []) m += note(voice, e, i, extra);
      });
      if (b === count - 1) m += `<barline location="right"><bar-style>light-heavy</bar-style></barline>`;
      measures += m + "</measure>";
    }
    parts = `<part id="P1">${measures}</part>`;
  } else {
    ex.voices.forEach((voice, vi) => {
      list += `<score-part id="P${vi + 1}"><part-name>${esc(voice.name)}</part-name></score-part>`;
      const voiceBars = bars(voice);
      let measures = "";
      voiceBars.forEach((events, b) => {
        let m = `<measure number="${b + 1}">${b === 0 ? attrs([voice.clef]) : ""}`;
        for (const [e, i] of events) m += note(voice, e, i, { voice: "<voice>1</voice>", staff: "" });
        if (b === voiceBars.length - 1) m += `<barline location="right"><bar-style>light-heavy</bar-style></barline>`;
        measures += m + "</measure>";
      });
      parts += `<part id="P${vi + 1}">${measures}</part>`;
    });
  }
  return { xml: `${head}<part-list>${list}</part-list>${parts}</score-partwise>`, ids };
}

/** Editing state and commands for one exercise. */
export class PracticeEditor {
  constructor(exercise) {
    this.ex = exercise;
    this.sig = signature(exercise.fifths);
    this.selected = this.firstEmpty() || this.editable()[0] || null;
  }

  editable() {
    const out = [];
    this.ex.voices.forEach((v) => {
      if (v.given) return;
      v.events.forEach((e, i) => { if (!e.rest && !e.tieFrom) out.push({ voice: v.id, index: i }); });
    });
    return out;
  }

  voice(id) { return this.ex.voices.find((v) => v.id === id); }
  event(sel = this.selected) { return sel && this.voice(sel.voice).events[sel.index]; }

  firstEmpty() {
    return this.editable().find((s) => !this.event(s).pitch) || null;
  }

  empties() {
    return this.editable().filter((s) => !this.event(s).pitch).length;
  }

  /** Select the event a rendered note or rest belongs to (ties select their first note). */
  selectById(id, ids) {
    for (const [voice, list] of Object.entries(ids)) {
      let index = list.indexOf(id);
      if (index < 0) continue;
      const v = this.voice(voice);
      if (v.given || v.events[index].rest) return false;
      while (v.events[index].tieFrom && index > 0) index--;
      this.selected = { voice, index };
      return true;
    }
    return false;
  }

  move(delta) {
    const list = this.editable();
    const at = list.findIndex((s) => s.voice === this.selected?.voice && s.index === this.selected?.index);
    const sameVoice = list.filter((s) => s.voice === this.selected?.voice);
    const k = sameVoice.findIndex((s) => s.index === this.selected?.index);
    const next = sameVoice[k + delta] || list[(at + delta + list.length) % list.length];
    if (next) this.selected = next;
  }

  nextVoice(delta = 1) {
    const voices = this.ex.voices.filter((v) => !v.given).map((v) => v.id);
    if (!this.selected || voices.length < 2) return;
    const time = this.timeOf(this.selected);
    const id = voices[(voices.indexOf(this.selected.voice) + delta + voices.length) % voices.length];
    const v = this.voice(id);
    let t = 0, best = null;
    v.events.forEach((e, i) => {
      if (!e.rest && !e.tieFrom && t <= time + 1e-9) best = i;
      t += e.dur;
    });
    if (best !== null) this.selected = { voice: id, index: best };
  }

  timeOf(sel) {
    return this.voice(sel.voice).events.slice(0, sel.index).reduce((t, e) => t + e.dur, 0);
  }

  /** A nearby pitch to place a typed letter: the previous note in the voice, or the voice's middle. */
  reference() {
    const v = this.voice(this.selected.voice);
    for (let i = this.selected.index - 1; i >= 0; i--) if (v.events[i].pitch) return parsePitch(v.events[i].pitch);
    for (let i = this.selected.index + 1; i < v.events.length; i++) if (v.events[i].pitch) return parsePitch(v.events[i].pitch);
    const m = v.center || 64;
    return { step: "C", alter: 0, octave: Math.floor(m / 12) - 1, target: m };
  }

  set(p) {
    const v = this.voice(this.selected.voice);
    let i = this.selected.index;
    v.events[i].pitch = p ? pitchText(p) : null;
    while (v.events[i].tieTo && i + 1 < v.events.length) v.events[++i].pitch = v.events[this.selected.index].pitch;
  }

  letter(step) {
    if (!this.selected) return;
    const ref = this.reference();
    const target = ref.target ?? midi(ref);
    let best = null;
    for (let octave = 1; octave <= 6; octave++) {
      const p = { step, alter: this.sig[step], octave };
      if (!best || Math.abs(midi(p) - target) < Math.abs(midi(best) - target)) best = p;
    }
    this.set(best);
  }

  step(delta) {
    const current = parsePitch(this.event()?.pitch);
    if (!current) return this.letter(this.reference().step || "C");
    const d = diatonic(current) + delta;
    const step = STEPS[((d % 7) + 7) % 7];
    this.set({ step, alter: this.sig[step], octave: Math.floor(d / 7) });
  }

  octave(delta) {
    const current = parsePitch(this.event()?.pitch);
    if (current) this.set({ ...current, octave: current.octave + delta });
  }

  accidental(alter) {
    const current = parsePitch(this.event()?.pitch);
    if (!current) return;
    const next = alter === 0 ? 0 : Math.max(-2, Math.min(2, current.alter + alter));
    this.set({ ...current, alter: next });
  }

  clear() { if (this.selected) this.set(null); }

  answers() {
    const out = {};
    for (const v of this.ex.voices) {
      if (v.given) continue;
      out[v.id] = this.ex.rhythmEditable ? structuredClone(v.events) : v.events.map((e) => e.pitch);
    }
    return out;
  }

  fill(answers) {
    for (const [id, values] of Object.entries(answers)) {
      const v = this.voice(id);
      if (values.length && typeof values[0] === "object" && values[0] !== null) {
        v.events = structuredClone(values);
      } else {
        values.forEach((p, i) => { if (v.events[i] && !v.events[i].rest) v.events[i].pitch = p; });
      }
    }
    this.selected = this.firstEmpty() || this.editable()[0] || null;
  }

  solution() {
    return this.ex.rhythmEditable && this.ex.solutionEvents ? this.ex.solutionEvents : this.ex.solution;
  }

  // ----- rhythm (fifth species) -----

  barSpan(voice, index) {
    let t = 0;
    for (let i = 0; i < index; i++) t += voice.events[i].dur;
    const bar = Math.floor(t / 4 + 1e-9);
    return { start: t, barStart: bar * 4, barEnd: bar * 4 + 4 };
  }

  /** Set the selected note's duration in quarters; the rest of its bar is refilled with empty notes. */
  duration(quarters) {
    if (!this.ex.rhythmEditable || !this.selected) return;
    const v = this.voice(this.selected.voice);
    const i = this.selected.index;
    const e = v.events[i];
    const { start, barEnd } = this.barSpan(v, i);
    if (e.rest || (i === v.events.length - 1)) return; // the opening rest and the final whole note stay
    const length = Math.min(quarters, barEnd - start);
    // Remove the events this note now covers in its bar, then fill the remaining time.
    let j = i + 1, t = start + e.dur;
    while (j < v.events.length && t < start + length - 1e-9 && t < barEnd - 1e-9) {
      t += v.events[j].dur;
      j++;
    }
    const tail = Math.max(0, Math.min(t, barEnd) - (start + length));
    const removed = v.events.splice(i + 1, j - i - 1);
    const tiedOut = e.tieTo || removed.some((r) => r.tieTo);
    e.dur = length;
    e.tieTo = tiedOut && start + length >= barEnd - 1e-9; // ties only cross bar lines here
    const fill = [];
    let left = tail;
    for (const d of [4, 3, 2, 1.5, 1, 0.5]) while (left >= d - 1e-9) { fill.push({ dur: d, pitch: null }); left -= d; }
    v.events.splice(i + 1, 0, ...fill);
    this.fixTies(v);
  }

  dot() {
    const e = this.event();
    if (!e || !this.ex.rhythmEditable) return;
    const base = { 3: 2, 1.5: 1 }[e.dur];
    this.duration(base ? base : e.dur * 1.5);
  }

  /** Tie the selected note into the next one (across the bar line), or remove the tie. */
  tie() {
    if (!this.ex.rhythmEditable || !this.selected) return;
    const v = this.voice(this.selected.voice);
    let i = this.selected.index;
    while (v.events[i].tieTo && i + 1 < v.events.length) i++;
    const e = v.events[i], next = v.events[i + 1];
    if (!next || next.rest) return;
    if (this.barSpan(v, i).start + e.dur < this.barSpan(v, i).barEnd - 1e-9) return; // ties cross the bar line
    if (e.tieTo) {
      e.tieTo = false;
      next.tieFrom = false;
    } else {
      e.tieTo = true;
      next.tieFrom = true;
      next.pitch = e.pitch;
    }
    this.fixTies(v);
  }

  fixTies(v) {
    v.events.forEach((e, k) => {
      const next = v.events[k + 1];
      if (e.tieTo && (!next || next.rest)) e.tieTo = false;
      if (next) next.tieFrom = Boolean(e.tieTo);
      if (e.tieFrom && k > 0) e.pitch = v.events[k - 1].pitch;
    });
    if (v.events[0]) v.events[0].tieFrom = false;
  }
}
