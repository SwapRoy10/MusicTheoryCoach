// Small, dependency-free helpers for music labels and MusicXML preparation.

const FIGURES = /^(6\/4|6\/5|4\/3|4\/2|6|7)?$/;

/** Render an ASCII Roman numeral ("viiø6/5") as HTML with stacked figures. */
export function romanHTML(label) {
  const match = /^([ivIV]+)([°ø+]?)(.*)$/.exec(label || "");
  if (!match || !FIGURES.test(match[3])) return escapeHTML(label || "?");
  const [, numeral, quality, figures] = match;
  let html = `<span class="rn-base">${numeral}</span>`;
  if (quality) html += `<span class="rn-quality">${quality}</span>`;
  if (figures.includes("/")) {
    const [upper, lower] = figures.split("/");
    html += `<span class="rn-stack"><span>${upper}</span><span>${lower}</span></span>`;
  } else if (figures) {
    html += `<span class="rn-single">${figures}</span>`;
  }
  return html;
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
  measure_count: "Length",
  measure_duration: "Measure duration",
};

export function ruleName(rule) {
  if (RULES[rule]) return RULES[rule];
  const text = String(rule).replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export const VOICE_NAMES = { S: "Soprano", A: "Alto", T: "Tenor", B: "Bass" };

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
