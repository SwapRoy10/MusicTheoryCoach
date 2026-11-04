// Plays the engraved score with a small Web Audio synth and lights up the
// notes as they sound. Timing and pitches come from Verovio's timemap, so the
// sound always matches what is drawn; tied notes sound once.

const TEMPO = 0.75;      // 120 qpm in Verovio's timemap -> 90 qpm
const LEAD = 0.08;       // seconds before the first note

export class Player {
  constructor(container, onChange) {
    this.container = container;
    this.onChange = onChange;
    this.notes = [];
    this.playing = false;
    this.ctx = null;
    this.voices = [];
    this.frame = 0;
  }

  /** Read note times and pitches for the score now loaded in the toolkit. */
  load(toolkit, musicxml) {
    this.stop();
    const doc = new DOMParser().parseFromString(musicxml, "application/xml");
    const tieStops = new Set();
    let index = 0;
    for (const note of doc.getElementsByTagName("note")) {
      index++;
      if ([...note.getElementsByTagName("tie")].some((t) => t.getAttribute("type") === "stop")) tieStops.add(`n${index}`);
    }
    const timemap = toolkit.renderToTimemap({ includeMeasures: false, includeRests: false });
    const open = new Map();
    const notes = [];
    for (const entry of timemap) {
      const t = entry.tstamp / 1000 / TEMPO;
      for (const id of entry.off || []) {
        const note = open.get(id);
        if (note) note.end = t;
        open.delete(id);
      }
      for (const id of entry.on || []) {
        const { pitch } = toolkit.getMIDIValuesForElement(id) || {};
        if (!pitch) continue;
        // A tie continuation extends the note it is tied from instead of sounding again.
        const tiedFrom = tieStops.has(id) && notes.find((n) => n.pitch === pitch && Math.abs(n.end - t) < 1e-6);
        if (tiedFrom) {
          tiedFrom.ids.push(id);
          tiedFrom.end = Infinity;
          open.set(id, tiedFrom);
          continue;
        }
        const note = { ids: [id], pitch, start: t, end: Infinity };
        notes.push(note);
        open.set(id, note);
      }
    }
    this.notes = notes.filter((n) => Number.isFinite(n.end));
  }

  playAll() {
    this.play(this.notes);
  }

  /** Play the chords around the given note IDs (a finding's evidence). */
  playNotes(ids) {
    const wanted = this.notes.filter((n) => n.ids.some((id) => ids.includes(id)));
    if (!wanted.length) return;
    const start = Math.min(...wanted.map((n) => n.start));
    const end = Math.max(...wanted.map((n) => n.end));
    this.play(this.notes.filter((n) => n.start < end && n.end > start), start, end);
  }

  play(notes, from = null, to = null) {
    this.stop();
    if (!notes.length) return;
    this.ctx ||= new (window.AudioContext || window.webkitAudioContext)();
    const ctx = this.ctx;
    ctx.resume();
    const offset = from ?? Math.min(...notes.map((n) => n.start));
    const t0 = ctx.currentTime + LEAD;
    const master = ctx.createGain();
    master.gain.value = 0.9 / Math.max(2, Math.min(4, maxPolyphony(notes)));
    const tone = ctx.createBiquadFilter();
    tone.type = "lowpass";
    tone.frequency.value = 2600;
    master.connect(tone).connect(ctx.destination);
    this.master = master;
    for (const n of notes) {
      const start = t0 + Math.max(0, n.start - offset);
      const end = t0 + (Math.min(n.end, to ?? n.end) - offset);
      this.voices.push(voice(ctx, master, n.pitch, start, end));
    }
    this.schedule = notes.map((n) => ({ ...n, on: t0 + Math.max(0, n.start - offset), off: t0 + (Math.min(n.end, to ?? n.end) - offset) }));
    this.until = Math.max(...this.schedule.map((n) => n.off)) + 0.25;
    this.playing = true;
    this.onChange?.(true);
    const tick = () => {
      const now = ctx.currentTime;
      const lit = new Set();
      for (const n of this.schedule) if (n.on <= now && now < n.off) n.ids.forEach((id) => lit.add(id));
      this.light(lit);
      if (now > this.until) this.stop();
      else this.frame = requestAnimationFrame(tick);
    };
    this.frame = requestAnimationFrame(tick);
  }

  light(ids) {
    for (const el of this.container.querySelectorAll("g.note.playing")) if (!ids.has(el.id)) el.classList.remove("playing");
    for (const id of ids) this.container.querySelector(`g.note[id="${id}"]`)?.classList.add("playing");
  }

  stop() {
    cancelAnimationFrame(this.frame);
    if (this.master && this.ctx) {
      const now = this.ctx.currentTime;
      this.master.gain.cancelScheduledValues(now);
      this.master.gain.setTargetAtTime(0, now, 0.02);
      const old = this.voices;
      setTimeout(() => old.forEach((v) => v.forEach((o) => { try { o.stop(); } catch { /* already stopped */ } })), 120);
    }
    this.voices = [];
    this.master = null;
    this.light(new Set());
    if (this.playing) {
      this.playing = false;
      this.onChange?.(false);
    }
  }
}

function maxPolyphony(notes) {
  return Math.max(...notes.map((n) => notes.filter((m) => m.start <= n.start && n.start < m.end).length));
}

/** A soft, organ-like tone: a sine with a quieter octave and twelfth. */
function voice(ctx, out, midi, start, end) {
  const freq = 440 * 2 ** ((midi - 69) / 12);
  const gain = ctx.createGain();
  const attack = 0.03, release = 0.12;
  gain.gain.setValueAtTime(0, start);
  gain.gain.linearRampToValueAtTime(1, start + attack);
  gain.gain.setTargetAtTime(0.75, start + attack, 0.15);
  gain.gain.setValueAtTime(0.75, Math.max(start + attack, end - 0.01));
  gain.gain.linearRampToValueAtTime(0, end + release);
  gain.connect(out);
  return [[1, 1], [2, 0.28], [3, 0.1]].map(([multiple, level]) => {
    const osc = ctx.createOscillator();
    const g = ctx.createGain();
    osc.type = multiple === 1 ? "triangle" : "sine";
    osc.frequency.value = freq * multiple;
    g.gain.value = level;
    osc.connect(g).connect(gain);
    osc.start(start);
    osc.stop(end + release + 0.05);
    return osc;
  });
}
