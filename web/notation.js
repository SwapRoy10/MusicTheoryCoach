// Small, dependency-free helpers for music labels and MusicXML preparation.

const FIGURES = /^(6\/4|6\/5|4\/3|4\/2|6|7)?$/;

function figuresHTML(figures) {
  if (!figures) return "";
  if (figures.includes("/")) {
    const [upper, lower] = figures.split("/");
    return `<span class="rn-stack"><span>${upper}</span><span>${lower}</span></span>`;
  }
  return `<span class="rn-single">${figures}</span>`;
}

function numeralHTML(text) {
  const match = /^(b?)([ivIV]+|N)([°ø+]?)(.*)$/.exec(text || "");
  if (!match || !FIGURES.test(match[4])) return null;
  const [, flat, numeral, quality, figures] = match;
  let html = flat ? `<span class="rn-flat">♭</span>` : "";
  html += `<span class="rn-base">${numeral}</span>`;
  if (quality) html += `<span class="rn-quality">${quality}</span>`;
  return html + figuresHTML(figures);
}

/** Render an ASCII Roman numeral ("viiø6/5", "V6/5/V", "N6", "Ger+6", "bVI") as HTML with stacked figures. */
export function romanHTML(label) {
  const six = /^(It|Fr|Ger)\+6$/.exec(label || "");
  if (six) return `<span class="rn-base">${six[1]}</span><span class="rn-single">+6</span>`;
  const [chord, target] = String(label || "").split(/\/(?=b?[ivIV]+[°]?$)/);
  const head = numeralHTML(chord);
  if (!head) return escapeHTML(label || "?");
  if (target === undefined) return head;
  const tail = numeralHTML(target);
  return tail ? `${head}<span class="rn-slash">/</span>${tail}` : escapeHTML(label);
}

const RULES = {
  parallel_fifth: "Parallel fifths",
  parallel_octave: "Parallel octaves",
  parallel_unison: "Parallel unisons",
  direct_outer_interval: "Direct (hidden) interval",
  leading_tone: "Leading tone",
  doubled_leading_tone: "Doubled leading tone",
  seventh_resolution: "Seventh resolution",
  incomplete_seventh: "Incomplete seventh chord",
  incomplete_triad: "Incomplete triad",
  roman_numeral: "Roman numeral",
  harmony_uncertain: "Harmony not identified",
  chord_membership: "Chord membership",
  doubling: "Doubling",
  inversion: "Inversion",
  diatonic: "Outside the key",
  range: "Voice range",
  spacing: "Spacing",
  crossing: "Voice crossing",
  overlap: "Voice overlap",
  rhythm: "Rhythm",
  tonic_ending: "Ending",
  applied_resolution: "Applied chord resolution",
  augmented_sixth: "Augmented sixth resolution",
  neapolitan: "Neapolitan",
  measure_count: "Length",
  measure_duration: "Measure duration",
};

// Species rule IDs read "s4-cadence", "mel-leap-recovery", "comb-no-parallel-perfect", ...
const SPECIES_PREFIX = /^(s[1-5]|comb|mel|cf)-/;
const SPECIES_GROUP = { cf: "Cantus", mel: "Melody", comb: "Two voices" };

export function ruleName(rule) {
  if (RULES[rule]) return RULES[rule];
  const prefix = SPECIES_PREFIX.exec(rule);
  const text = String(rule).replace(SPECIES_PREFIX, "").replace(/[_-]/g, " ");
  const name = text.charAt(0).toUpperCase() + text.slice(1);
  if (!prefix) return name;
  const group = SPECIES_GROUP[prefix[1]] || `${SPECIES_NAMES[prefix[1][1]]} species`;
  return `${name} <span class="group">${group}</span>`;
}

export const VOICE_NAMES = { S: "Soprano", A: "Alto", T: "Tenor", B: "Bass", CP: "Counterpoint", CF: "Cantus firmus" };
export const SPECIES_NAMES = { 1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth" };

/**
 * Give every <note> element the ID the analyzer uses for it.
 * coach.score_import numbers note elements n1, n2, ... in document order
 * (all parts, all measures, rests included). Verovio keeps MusicXML note
 * `id` attributes on the rendered SVG groups, which links the two.
 */
export function withNoteIds(musicxml) {
  const doc = new DOMParser().parseFromString(musicxml, "application/xml");
  if (doc.querySelector("parsererror")) throw new Error("The reviewed MusicXML could not be parsed for display.");
  let index = 0;
  for (const note of doc.getElementsByTagName("note")) note.setAttribute("id", `n${++index}`);
  return new XMLSerializer().serializeToString(doc);
}

export function escapeHTML(text) {
  return String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/** Turn "m. 4, beat 3" style references in analyzer prose into a location. */
export function leadingLocation(text) {
  const match = /^m\.\s*(\S+?),?\s+(?:beat|b\.)\s*(\S+?)[:,\s]/.exec(text);
  return match ? { measure: match[1], beat: match[2] } : null;
}
