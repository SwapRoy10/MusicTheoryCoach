// Draws the analysis on top of the Verovio-rendered score.
// Everything is positioned from the rendered note groups (g.note#nX), so the
// marks follow Verovio's layout at any width.

import { romanHTML, escapeHTML } from "./notation.js";

const SVG_NS = "http://www.w3.org/2000/svg";

export function drawOverlay(container, analysis, findingNumbers) {
  container.querySelector(".overlay")?.remove();
  const layer = document.createElement("div");
  layer.className = "overlay";
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.classList.add("overlay-lines");
  layer.append(svg);
  container.append(layer);

  const origin = container.getBoundingClientRect();
  const box = (el) => {
    const r = el.getBoundingClientRect();
    return { left: r.left - origin.left, right: r.right - origin.left, top: r.top - origin.top,
             bottom: r.bottom - origin.top, cx: (r.left + r.right) / 2 - origin.left,
             cy: (r.top + r.bottom) / 2 - origin.top };
  };
  const noteEl = (id) => container.querySelector(`g.note[id="${id}"]`);
  const headBox = (id) => {
    const el = noteEl(id);
    return el ? box(el.querySelector(".notehead") || el) : null;
  };
  const systemOf = (id) => noteEl(id)?.closest("g.system");
  const systemBox = (system) => {
    const staves = [...system.querySelectorAll("g.staff")].map(box);
    return { top: Math.min(...staves.map((s) => s.top)), bottom: Math.max(...staves.map((s) => s.bottom)),
             full: box(system) };
  };
  svg.setAttribute("width", origin.width);
  svg.setAttribute("height", container.scrollHeight);

  // Reviewed Roman numerals, below each system (and below any lyrics/labels).
  for (const chord of analysis.harmony) {
    const head = headBox(chord.anchor);
    const system = systemOf(chord.anchor);
    if (!head || !system) continue;
    const { full } = systemBox(system);
    const el = document.createElement("button");
    el.type = "button";
    el.className = "numeral";
    if (chord.original_label && chord.label_matches === false) el.classList.add("corrected");
    if (chord.status !== "identified") el.classList.add(chord.status === "interpreted" ? "interpreted" : "uncertain");
    el.innerHTML = romanHTML(chord.roman);
    el.style.left = `${head.cx}px`;
    el.style.top = `${full.bottom + 8}px`;
    el.dataset.notes = Object.values(chord.notes).map((n) => n.id).join(" ");
    el.dataset.chord = `${chord.measure}:${chord.beat}`;
    const sounding = Object.entries(chord.notes).map(([v, n]) => `${v} ${n.pitch}`).join(", ");
    el.setAttribute("aria-label", `Measure ${chord.measure}, beat ${chord.beat}: ${chord.roman}`);
    el.title = `${chord.roman} (m. ${chord.measure}, beat ${chord.beat})\n${chord.reason}\n${sounding}` +
      (chord.original_label && chord.label_matches === false ? `\nYou wrote ${chord.original_label}.` : "");
    layer.append(el);
  }

  // Finding numbers, in a row just above each system. Badges for the same spot
  // sit side by side; runs that would collide are nudged right.
  const placed = [];
  analysis.findings.forEach((finding, i) => {
    const last = finding.notes[finding.notes.length - 1];
    const head = last && headBox(last.id);
    const system = last && systemOf(last.id);
    if (head && system) placed.push({ i, x: head.cx, top: systemBox(system).top, severity: finding.severity });
  });
  const BADGE = 20;
  const groups = [];
  for (const p of placed.sort((a, b) => a.top - b.top || a.x - b.x || a.i - b.i)) {
    const group = groups[groups.length - 1];
    if (group && group.top === p.top && Math.abs(group.x - p.x) < 1) group.items.push(p);
    else groups.push({ x: p.x, top: p.top, items: [p] });
  }
  let previous = null;
  for (const group of groups) {
    let left = group.x - (group.items.length * BADGE) / 2;
    if (previous && previous.top === group.top) left = Math.max(left, previous.right + 3);
    group.items.forEach((p, k) => {
      const badge = document.createElement("button");
      badge.type = "button";
      badge.className = `badge ${p.severity}`;
      badge.textContent = findingNumbers[p.i];
      badge.dataset.finding = p.i;
      badge.style.left = `${left + k * BADGE + BADGE / 2}px`;
      badge.style.top = `${group.top - 22}px`;
      badge.setAttribute("aria-label", `Finding ${findingNumbers[p.i]}: ${analysis.findings[p.i].message}`);
      layer.append(badge);
    });
    previous = { top: group.top, right: left + group.items.length * BADGE };
  }

  // Paradigm brackets above the finding row; alternate rows when labels would collide.
  const rows = [];
  for (const [index, mark] of (analysis.review?.marks || []).entries()) {
    const start = headBox(mark.anchor), end = headBox(mark.end_anchor);
    const startSystem = systemOf(mark.anchor), endSystem = systemOf(mark.end_anchor);
    if (!start || !end || !startSystem) continue;
    const segments = [];
    if (startSystem === endSystem) {
      segments.push({ system: startSystem, x1: start.left - 4, x2: end.right + 4, first: true, last: true });
    } else {
      segments.push({ system: startSystem, x1: start.left - 4, x2: systemBox(startSystem).full.right, first: true, last: false });
      segments.push({ system: endSystem, x1: systemBox(endSystem).full.left + 40, x2: end.right + 4, first: false, last: true });
    }
    for (const seg of segments) {
      const top = systemBox(seg.system).top;
      const labelWidth = Math.max(seg.x2 - seg.x1, mark.name.length * 6.4);
      let row = 0;
      while ((rows[row] ||= []).some((r) => r.top === top && r.x1 < seg.x1 + labelWidth && seg.x1 < r.x2)) row++;
      rows[row].push({ top, x1: seg.x1, x2: seg.x1 + labelWidth });
      const y = top - 34 - row * 30;
      const path = document.createElementNS(SVG_NS, "path");
      const tickL = seg.first ? 6 : 0, tickR = seg.last ? 6 : 0;
      path.setAttribute("d", `M${seg.x1},${y + tickL} V${y} H${seg.x2} V${y + tickR}`);
      path.classList.add("bracket");
      path.dataset.paradigm = index;
      svg.append(path);
      if (seg.first) {
        const label = document.createElement("button");
        label.type = "button";
        label.className = "bracket-label";
        label.dataset.paradigm = index;
        label.innerHTML = escapeHTML(mark.name);
        label.style.top = `${y - 17}px`;
        layer.append(label);
        // Keep labels near the right edge inside the page.
        label.style.left = `${Math.max(0, Math.min(seg.x1, origin.width - label.offsetWidth - 6))}px`;
      }
    }
  }
  return { headBox };
}

/** Draw selection rings around the given note IDs. */
export function ringNotes(container, ids, kind) {
  const layer = container.querySelector(".overlay");
  layer?.querySelectorAll(".ring").forEach((r) => r.remove());
  if (!layer || !ids.length) return null;
  const origin = container.getBoundingClientRect();
  let first = null;
  for (const id of ids) {
    const el = container.querySelector(`g.note[id="${id}"]`);
    if (!el) continue;
    const r = (el.querySelector(".notehead") || el).getBoundingClientRect();
    const ring = document.createElement("span");
    ring.className = `ring ${kind || ""}`;
    ring.style.left = `${(r.left + r.right) / 2 - origin.left}px`;
    ring.style.top = `${(r.top + r.bottom) / 2 - origin.top}px`;
    layer.append(ring);
    first ||= ring;
  }
  return first;
}
