"""Compose a four-part (SATB) chorale phrase in a major key.

The progression is assembled from the contrapuntal expansions in the classroom
reference (page 12: neighbor, passing and incomplete-neighbor bass motions with
their required soprano lines), then a predominant and an authentic cadence.
A beam search voices the chords under the same rules the chorale checker
enforces; every candidate is then reviewed by ``coach.review.run_review`` on its
exported MusicXML, and only phrases with no errors are returned.
"""
from fractions import Fraction
from pathlib import Path
import random
import tempfile
import xml.etree.ElementTree as ET

from .harmony import vocabulary
from .model import RANGES, STEPS, Pitch, perfect, scale

KEYS = {"C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "F": -1, "Bb": -2, "Eb": -3, "Ab": -4}

# Contrapuntal expansions of the tonic (reference page 12). Each unit continues from
# the current tonic chord: (figure, name, follows, chords, soprano degrees or None).
# Soprano degrees cover the preceding tonic plus the unit's chords.
UNITS = [
    ("5", "Lower neighbor with V6/5", "I", ["V6/5", "I"], None),
    ("6", "Upper neighbor with V4/3", "I", ["V4/3", "I"], None),
    ("7", "Lower neighbor with V4/3", "I6", ["V4/3", "I6"], None),
    ("8", "Upper neighbor with V4/2", "I6", ["V4/2", "I6"], None),
    ("9a", "Voice exchange (passing vii°6)", "I", ["vii°6", "I6"], [3, 2, 1]),
    ("9b", "Voice exchange (passing vii°6)", "I6", ["vii°6", "I"], [1, 2, 3]),
    ("10", "Parallel 10ths", "I", ["V4/3", "I6"], [3, 4, 5]),
    ("4", "10-long (arpeggiated IV6)", "I", ["IV6", "I6"], [3, 4, 5]),
    ("12a", "Voice exchange with skips ascending bass", "I", ["V4/2", "I6"], [3, 7, 1]),
    ("12b", "Voice exchange with skips descending bass", "I6", ["V6/5", "I"], [1, 4, 3]),
    ("arp", "Bass arpeggiation", "I", ["I6"], None),
    ("arp", "Bass arpeggiation", "I6", ["I"], None),
]
PREDOMINANTS = {"I": ["IV", "ii6", "ii6/5"], "I6": ["IV", "ii6", "ii6/5"]}
FIGURES = {"": 0, "6": 1, "6/4": 2, "7": 0, "6/5": 1, "4/3": 2, "4/2": 3}


class ComposeError(ValueError):
    pass


# ---------------------------------------------------------------- harmony

def parse_roman(label):
    numeral = label.rstrip("0123456789/").rstrip("°ø")
    figures = label[len(label.rstrip("0123456789/")):]
    degree = ["I", "II", "III", "IV", "V", "VI", "VII"].index(numeral.upper()) + 1
    size = 4 if figures in ("7", "6/5", "4/3", "4/2") else 3
    return degree, size, FIGURES[figures]


def chord_members(label, fifths):
    degree, size, inversion = parse_roman(label)
    chord = next(c for c in vocabulary(fifths) if c["degree"] == degree and c["size"] == size)
    names = chord["pitches"]
    return names, names[inversion]


def progression(bars, rng):
    """Roman numerals for 2*bars-1 half-note chords (the last one a whole note), plus unit spans."""
    events = 2 * bars - 1
    six_four = rng.random() < 0.6
    cadence = ["I6/4", "V"] if six_four else ["V"]
    # The cadential 6/4 falls on a downbeat; otherwise the predominant does.
    middle = events - 1 - 1 - len(cadence) - 1  # opening I, predominant, cadence, final I
    for _ in range(200):
        chords, spans, current, left = ["I"], [], "I", middle
        last_unit, fixed = None, None  # fixed: soprano degree already required at the current chord
        while left > 0:
            options = [u for u in UNITS if u[2] == current and len(u[3]) <= left
                       and (last_unit is None or u[3] != last_unit[3])
                       and (fixed is None or u[4] is None or u[4][0] == fixed)]
            if not options:
                break
            if last_unit and last_unit[0] == "arp":
                options = [u for u in options if u[0] != "arp"] or options
            # Favor the expansions the reviewer names (reference p. 12, figures 5, 8, 10, 12a, 12b).
            weights = [0.35 if u[0] == "arp" else 2.0 if u[0] in ("5", "8", "10", "12a", "12b") else 1.0 for u in options]
            # Variety: an expansion already used in this phrase is much less likely to return.
            weights = [w * (0.08 if any(u[3] == used[3] and u[2] == used[2] for _, used in spans) else 1) for w, u in zip(weights, options)]
            unit = rng.choices(options, weights)[0]
            spans.append((len(chords) - 1, unit))
            chords += unit[3]
            current, left, last_unit = unit[3][-1], left - len(unit[3]), unit
            fixed = unit[4][-1] if unit[4] else None
        if left == 0:
            chords.append(rng.choice(PREDOMINANTS[current]))
            chords += cadence + ["I"]
            return chords, spans
    raise ComposeError("Could not build a progression of that length.")


# ---------------------------------------------------------------- voicings

def pitches_named(names, low, high, fifths):
    alter = scale(fifths)
    out = []
    for octave in range(1, 7):
        for step in STEPS:
            p = Pitch(step, alter[step], octave)
            if p.name in names and low <= p.midi <= high:
                out.append(p)
    return out


def voicings(label, fifths, final=False, unison=False):
    """Complete, well-spaced voicings; ``unison`` lets the alto and tenor share a note."""
    names, bass_name = chord_members(label, fifths)
    _, size, inversion = parse_roman(label)
    tonic_pc = (7 * fifths) % 12
    root = names[0]
    out = []
    upper = {v: pitches_named(names, *RANGES[v], fifths) for v in "TAS"}
    for b in pitches_named([bass_name], *RANGES["B"], fifths):
        for t in upper["T"]:
            if t.midi <= b.midi:
                continue
            for a in upper["A"]:
                if a.midi < t.midi or (a.midi == t.midi and not unison) or a.midi - t.midi > 12:
                    continue
                for s in upper["S"]:
                    if s.midi <= a.midi or s.midi - a.midi > 12:
                        continue
                    chord = (s, a, t, b)
                    present = [p.name for p in chord]
                    if set(present) != set(names):
                        continue  # complete chords only
                    if sum(p.midi % 12 == (tonic_pc - 1) % 12 for p in chord) > 1:
                        continue  # never double the leading tone
                    if size == 3:
                        doubled = next(n for n in names if present.count(n) == 2)
                        if inversion == 0 and doubled != root:
                            continue
                        if inversion == 2 and doubled != bass_name:
                            continue
                        if label == "vii°6" and doubled != bass_name:
                            continue
                    if final and (s.name != root or label != "I"):
                        continue
                    out.append(chord)
    return out


def degree_of(p, fifths):
    return (STEPS.index(p.step) - (4 * fifths) % 7) % 7 + 1


# ---------------------------------------------------------------- voice leading

MAX_LEAP = {0: 9, 1: 7, 2: 7, 3: 12}  # S, A, T, B in semitones


def transition(old, new, old_label, new_label, fifths, frustrated=False, fixed=None):
    """Cost of moving between two voicings, or None when a rule forbids it.

    ``fixed`` names a voice index whose line is given (harmonization), exempt
    from the melodic checks. ``frustrated`` permits the inner-voice exception at a final V-I: the leading
    tone in the alto or tenor may fall a third to the fifth of I, so the tonic is
    complete (the reviewer still notes it as a suggestion).
    """
    tonic_pc = (7 * fifths) % 12
    cost = 0.0
    for i in range(4):
        if i == fixed:
            continue  # a given line is the student's: its own melody is not ours to judge here
        o, n = old[i], new[i]
        d = n.midi - o.midi
        if abs(d) == 6 or abs(d) in (10, 11) or abs(d) > MAX_LEAP[i]:
            return None
        if o.midi % 12 == (tonic_pc - 1) % 12 and d not in (0, 1):
            if not (frustrated and i in (1, 2) and d in (-3, -4) and new_label == "I" and old_label in ("V", "V7")):
                return None  # the leading tone rises to the tonic
            cost += 6
        if i == 0:
            cost += abs(d) * 0.9 + (7 if abs(d) > 4 else 2 if abs(d) > 2 else 0) + (4 if d == 0 else 0)
        elif i == 3:
            cost += abs(d) * 0.15
        else:
            cost += abs(d) * 0.6 + (2 if abs(d) > 4 else 0)
    # Chordal sevenths descend by step (or are held), except the rising soprano of the parallel 10ths.
    _, size, _ = parse_roman(old_label)
    if size == 4 and old_label != new_label:
        seventh = chord_members(old_label, fifths)[0][3]
        for i, o in enumerate(old):
            if o.name != seventh:
                continue
            n = new[i]
            falls = o.diatonic - n.diatonic == 1 and o.midi - n.midi in (1, 2)
            tenths = old_label == "V4/3" and new_label == "I6" and i == 0 and n.diatonic - o.diatonic == 1
            if n != o and not falls and not tenths:
                return None
    for i in range(4):
        for j in range(i + 1, 4):
            a, b = perfect(old[i], old[j]), perfect(new[i], new[j])
            moved = old[i] != new[i] and old[j] != new[j]
            if a and a == b and moved:
                return None  # parallel or contrary fifths/octaves
    for i in range(3):  # overlap of adjacent voices
        if new[i].midi < old[i + 1].midi or new[i + 1].midi > old[i].midi:
            return None
    ds, db = new[0].midi - old[0].midi, new[3].midi - old[3].midi
    target = perfect(new[0], new[3])
    if ds * db > 0 and abs(new[0].diatonic - old[0].diatonic) > 1 and target and perfect(old[0], old[3]) != target:
        return None  # direct fifth/octave in the outer voices with a soprano leap
    if old_label == "I6/4" and new[3] != old[3]:
        return None  # the cadential 6/4 keeps its bass
    return cost


def voice(chords, fifths, soprano, rng, width=48, cadence=True):
    """Beam search over voicings. ``soprano`` maps event index to allowed soprano degrees."""
    options = []
    for i, label in enumerate(chords):
        vs = voicings(label, fifths, final=cadence and i == len(chords) - 1)
        if i in soprano:
            vs = [v for v in vs if degree_of(v[0], fifths) in soprano[i]]
        if not vs:
            raise ComposeError(f"No voicing for {label}.")
        options.append(vs)
    beam = [(rng.random() * 2, [v]) for v in options[0]]
    for i in range(1, len(chords)):
        grown = []
        for cost, path in beam:
            prev = path[-1]
            for v in options[i]:
                c = transition(prev, v, chords[i - 1], chords[i], fifths)
                if c is None:
                    continue
                # A soprano leap is recovered by a step the other way.
                if len(path) >= 2:
                    p2 = path[-2][0]
                    leap = prev[0].midi - p2.midi
                    if leap == 0 and v[0] == prev[0]:
                        c += 5  # three soprano notes on one pitch
                    if abs(leap) > 4 and not (0 < abs(v[0].midi - prev[0].midi) <= 2 and (v[0].midi - prev[0].midi) * leap < 0):
                        continue  # a soprano leap must be recovered by a step the other way
                grown.append((cost + c + rng.random() * 3, path + [v]))
        if not grown:
            return None
        grown.sort(key=lambda x: x[0])
        # Keep the beam diverse: at most a few paths per final voicing.
        seen, beam = {}, []
        for item in grown:
            key = item[1][-1]
            if seen.get(key, 0) < 3:
                seen[key] = seen.get(key, 0) + 1
                beam.append(item)
            if len(beam) >= width:
                break
    return min(beam, key=lambda x: x[0])[1]


# ---------------------------------------------------------------- export

def to_musicxml(path_voicings, chords, fifths, title):
    """Grand staff: soprano and alto on the treble staff, tenor and bass on the bass staff."""
    root = ET.Element("score-partwise", version="4.0")
    work = ET.SubElement(root, "work")
    ET.SubElement(work, "work-title").text = title
    part_list = ET.SubElement(root, "part-list")
    sp = ET.SubElement(part_list, "score-part", id="P1")
    ET.SubElement(sp, "part-name").text = "Chorale"
    part = ET.SubElement(root, "part", id="P1")
    events = [(i // 2, (i % 2) * 2, 4 if i == len(chords) - 1 else 2, v) for i, v in enumerate(path_voicings)]
    bars = events[-1][0] + 1
    for b in range(bars):
        m = ET.SubElement(part, "measure", number=str(b + 1))
        if b == 0:
            attr = ET.SubElement(m, "attributes")
            ET.SubElement(attr, "divisions").text = "1"
            key = ET.SubElement(attr, "key")
            ET.SubElement(key, "fifths").text = str(fifths)
            ET.SubElement(key, "mode").text = "major"
            time = ET.SubElement(attr, "time")
            ET.SubElement(time, "beats").text = "4"
            ET.SubElement(time, "beat-type").text = "4"
            ET.SubElement(attr, "staves").text = "2"
            for number, sign, line in ((1, "G", 2), (2, "F", 4)):
                clef = ET.SubElement(attr, "clef", number=str(number))
                ET.SubElement(clef, "sign").text = sign
                ET.SubElement(clef, "line").text = str(line)
        bar_events = [e for e in events if e[0] == b]
        for vi, (voice_no, staff, stem) in enumerate(((1, 1, "up"), (2, 1, "down"), (3, 2, "up"), (4, 2, "down"))):
            if vi:
                backup = ET.SubElement(m, "backup")
                ET.SubElement(backup, "duration").text = "4"
            for _, _, dur, v in bar_events:
                p = v[vi]
                n = ET.SubElement(m, "note")
                pitch = ET.SubElement(n, "pitch")
                ET.SubElement(pitch, "step").text = p.step
                if p.alter:
                    ET.SubElement(pitch, "alter").text = str(p.alter)
                ET.SubElement(pitch, "octave").text = str(p.octave)
                ET.SubElement(n, "duration").text = str(dur)
                ET.SubElement(n, "voice").text = str(voice_no)
                ET.SubElement(n, "type").text = "whole" if dur == 4 else "half"
                if dur != 4:
                    ET.SubElement(n, "stem").text = stem
                ET.SubElement(n, "staff").text = str(staff)
        if b == bars - 1:
            barline = ET.SubElement(m, "barline", location="right")
            ET.SubElement(barline, "bar-style").text = "light-heavy"
    ET.indent(root)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")


# ---------------------------------------------------------------- entry point

def compose_chorale(key="C", bars=4, seed=None, attempts=40):
    """Return (musicxml, review, plan) for an original chorale phrase.

    ``review`` is ``coach.review.run_review``'s result on the exported score, so the
    composition is checked exactly as an uploaded exercise would be.
    """
    from .review import run_review
    if key not in KEYS:
        raise ComposeError(f"Key must be one of {', '.join(KEYS)} major.")
    if not 4 <= bars <= 8:
        raise ComposeError("Choose four to eight bars.")
    fifths = KEYS[key]
    rng = random.Random(seed)
    best = None
    for _ in range(attempts):
        chords, spans = progression(bars, rng)
        soprano = {}
        for start, unit in spans:
            if unit[4]:
                for offset, deg in enumerate(unit[4]):
                    soprano[start + offset] = {deg}
        soprano[len(chords) - 2] = soprano.get(len(chords) - 2, {2, 7}) & {2, 7} or {2, 7}
        if chords[-3] == "I6/4":
            soprano[len(chords) - 3] = {1, 3, 5}
        path = voice(chords, fifths, soprano, rng)
        if not path:
            continue
        title = f"Chorale in {key} major"
        xml = to_musicxml(path, chords, fifths, title)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "chorale.musicxml"
            source.write_text(xml, encoding="utf-8")
            review = run_review(source, Path(tmp) / "out")
        findings = review["result"]["findings"] if "result" in review else review["findings"]
        errors = [f for f in findings if f["severity"] == "error"]
        if errors:
            continue
        score = len(findings)
        plan = {"key": key, "bars": bars, "chords": chords,
                "expansions": [{"figure": u[0], "name": u[1], "chords": [chords[s]] + u[3], "start": s}
                               for s, u in spans if u[0] != "arp"]}
        if best is None or score < best[0]:
            best = (score, xml, review, plan)
        if score == 0:
            break
    if best is None:
        raise ComposeError("No phrase passed every rule this time; try again.")
    return best[1], best[2], best[3]
