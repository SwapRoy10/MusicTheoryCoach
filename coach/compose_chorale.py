"""Compose a four-part (SATB) chorale phrase in a major or minor key.

The progression is assembled from the contrapuntal expansions in the classroom
reference (page 12: neighbor, passing and incomplete-neighbor bass motions with
their required soprano lines), then a predominant and an authentic cadence.
A beam search voices the chords under the same rules the chorale checker
enforces; every candidate is then reviewed by ``coach.review.run_review`` on its
exported MusicXML, and only phrases with no errors are returned.
"""
from functools import lru_cache
from pathlib import Path
import random
import tempfile
from typing import NamedTuple
import xml.etree.ElementTree as ET

from .harmony import label_for, tonic_pc as key_tonic_pc, tonic_step, vocabulary
from .model import RANGES, STEPS, Pitch, perfect, scale


class Key(NamedTuple):
    fifths: int
    mode: str = "major"


KEYS = {"C": Key(0), "G": Key(1), "D": Key(2), "A": Key(3), "E": Key(4), "F": Key(-1), "Bb": Key(-2), "Eb": Key(-3),
        "Ab": Key(-4), "Am": Key(0, "minor"), "Em": Key(1, "minor"), "Bm": Key(2, "minor"), "F#m": Key(3, "minor"),
        "C#m": Key(4, "minor"), "Dm": Key(-1, "minor"), "Gm": Key(-2, "minor"), "Cm": Key(-3, "minor"), "Fm": Key(-4, "minor")}


def key_name(name):
    key = KEYS[name]
    return f"{name.rstrip('m') if key.mode == 'minor' else name} {key.mode}".replace("b ", "♭ ").replace("#", "♯")


def as_key(key):
    return key if isinstance(key, Key) else Key(key)

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
    ("p64", "Passing 6/4", "I", ["V6/4", "I6"], None),
    ("p64", "Passing 6/4", "I6", ["V6/4", "I"], None),
    ("n64", "Pedal 6/4", "I", ["IV6/4", "I"], None),
]
# Chromatic expansions of the tonic (used when chromatic harmony is requested).
CHROMATIC_UNITS = [
    ("ct", "Common-tone diminished seventh", "I", ["ct°7", "I"], None),
    ("tii", "Tonicized ii", "I", ["V6/5/ii", "ii", "V6/5", "I"], None),
    ("tIV", "Tonicized IV", "I", ["V4/2/IV", "IV6", "V4/3", "I"], None),
    ("tvi", "Tonicized vi", "I", ["V4/3/vi", "vi", "V6/5", "I"], None),
    ("tV", "Tonicized V", "I6", ["V6/5/V", "V", "I"], None),
]
PREDOMINANTS = {"I": ["IV", "ii6", "ii6/5"], "I6": ["IV", "ii6", "ii6/5"]}
# Chromatic approaches to the cadence: (label, needs the cadential 6/4 after it).
CHROMATIC_PD = [("N6", False), ("It+6", False), ("Fr+6", False), ("Ger+6", True), ("V6/5/V", False),
                ("vii°7/V", False), ("V7/V", False)]
MIXTURE_PD = ["iv6", "iiø6/5", "ii°6"]  # borrowed from the parallel minor (major keys)
MINOR = {"I": "i", "I6": "i6", "I6/4": "i6/4", "IV": "iv", "IV6": "iv6", "ii": "ii°", "ii6": "ii°6",
         "ii6/5": "iiø6/5", "ii7": "iiø7", "vi": "VI", "iii": "III"}


class ComposeError(ValueError):
    pass


# ---------------------------------------------------------------- harmony

def localize(label, mode):
    """A major-key numeral as it reads in ``mode`` (minor: I -> i, ii6 -> ii°6, IV6/4 -> iv6/4, V6/5/vi -> V6/5/VI)."""
    if mode != "minor":
        return label
    head, _, target = label.rpartition("/")
    if head and target.isalpha():  # an applied chord: V6/5/vi
        return head + "/" + {"IV": "iv", "vi": "VI", "ii": "ii°", "iii": "III"}.get(target, target)
    if label in MINOR:
        return MINOR[label]
    if label.endswith("6/4") and label[:-3] in MINOR:
        return MINOR[label[:-3]] + "6/4"
    return label


def valid(label, key):
    try:
        chord_info(label, key)
        return True
    except ComposeError:
        return False


@lru_cache(maxsize=None)
def chord_info(label, key):
    """The chord a numeral names in a key: names (root, third, fifth[, seventh]), bass, size, inversion, kind."""
    key = as_key(key)
    if label == "ct°7":
        if key.mode != "major":
            raise ComposeError("The common-tone diminished seventh is used here in major keys.")
        from .harmony import degree_pitch, name_of
        names = (name_of(*degree_pitch(2, key.fifths, "major", 1)), name_of(*degree_pitch(4, key.fifths, "major", 1)),
                 name_of(*degree_pitch(6, key.fifths, "major")), name_of(*degree_pitch(1, key.fifths, "major")))
        return {"degree": 1, "symbol": "ct°", "pitches": list(names), "size": 4, "kind": "common-tone",
                "names": names, "bass": names[3], "inversion": 3, "label": label}
    for chord in vocabulary(key.fifths, key.mode):
        if chord["kind"] == "ninth":
            continue
        for inversion in range(len(chord["pitches"]) if chord["kind"] != "aug6" else 1):
            if label_for(chord, inversion) == label:
                return {**chord, "names": tuple(chord["pitches"]), "bass": chord["pitches"][inversion],
                        "inversion": inversion, "label": label}
    raise ComposeError(f"{label} is not a chord this composer knows in that key.")


def chord_members(label, key):
    info = chord_info(label, as_key(key))
    return list(info["names"]), info["bass"]


def parse_roman(label, key=Key(0)):
    info = chord_info(label, as_key(key))
    return info["degree"], info["size"], info["inversion"]


def local_leading_tone(info):
    """The note of an applied chord that leads to its target's root."""
    if info["kind"] != "applied":
        return None
    return info["names"][0] if info["symbol"].startswith("vii") else info["names"][1]


def progression(bars, rng, mode="major", chromatic=False, key=None):
    """Roman numerals for 2*bars-1 half-note chords (the last one a whole note), plus unit spans."""
    events = 2 * bars - 1
    six_four = rng.random() < 0.6
    cadence = ["I6/4", "V"] if six_four else ["V"]
    approach = None
    if chromatic:
        options = [label for label, needs in CHROMATIC_PD if six_four or not needs]
        if mode == "major":
            options += MIXTURE_PD
        approach = rng.choice(options)
    # The cadential 6/4 falls on a downbeat; otherwise the predominant does.
    middle = events - 1 - 1 - len(cadence) - 1  # opening I, predominant, cadence, final I
    key = key or Key(0, mode)
    units = [u for u in UNITS + (CHROMATIC_UNITS if chromatic else [])
             if all(valid(localize(c, mode), key) for c in u[3])]
    for _ in range(200):
        chords, spans, current, left = ["I"], [], "I", middle
        last_unit, fixed = None, None  # fixed: soprano degree already required at the current chord
        while left > 0:
            options = [u for u in units if u[2] == current and len(u[3]) <= left
                       and (last_unit is None or u[3] != last_unit[3])
                       and (fixed is None or u[4] is None or u[4][0] == fixed)]
            if not options:
                break
            if last_unit and last_unit[0] == "arp":
                options = [u for u in options if u[0] != "arp"] or options
            # Favor the expansions the reviewer names (reference p. 12, figures 5, 8, 10, 12a, 12b).
            weights = [0.35 if u[0] == "arp" else 2.0 if u[0] in ("5", "8", "10", "12a", "12b")
                       else 0.6 if u[0] in ("p64", "n64") else 2.5 if u in CHROMATIC_UNITS else 1.0 for u in options]
            # Variety: an expansion already used in this phrase is much less likely to return.
            weights = [w * (0.08 if any(u[3] == used[3] and u[2] == used[2] for _, used in spans) else 1) for w, u in zip(weights, options)]
            unit = rng.choices(options, weights)[0]
            spans.append((len(chords) - 1, unit))
            chords += unit[3]
            current, left, last_unit = unit[3][-1], left - len(unit[3]), unit
            fixed = unit[4][-1] if unit[4] else None
        if left == 0:
            chords.append(approach or rng.choice(PREDOMINANTS[current]))
            chords += cadence + ["I"]
            return [localize(c, mode) for c in chords], spans
    raise ComposeError("Could not build a progression of that length.")


# ---------------------------------------------------------------- voicings

def pitches_named(names, low, high, fifths=None):
    out = []
    for name in set(names):
        p0 = Pitch.parse(name + "4")
        for octave in range(1, 7):
            p = Pitch(p0.step, p0.alter, octave)
            if low <= p.midi <= high:
                out.append(p)
    return sorted(out, key=lambda p: p.midi)


@lru_cache(maxsize=None)
def voicings(label, key, final=False, unison=False, fifth=False):
    """Complete, well-spaced voicings; ``unison`` lets the alto and tenor share a note.

    ``fifth`` also allows a root-position triad with its fifth doubled (around a
    common-tone diminished seventh, whose neighbors return to the fifth)."""
    key = as_key(key)
    info = chord_info(label, key)
    names, bass_name, size, inversion = list(info["names"]), info["bass"], info["size"], info["inversion"]
    leading = (key_tonic_pc(key.fifths, key.mode) - 1) % 12
    signature = scale(key.fifths)
    chromatic = {n for n in names if Pitch.parse(n + "4").alter != signature[n[0]]}
    local_lt = local_leading_tone(info)
    root = names[0]
    out = []
    upper = {v: pitches_named(names, *RANGES[v]) for v in "TAS"}
    for b in pitches_named([bass_name], *RANGES["B"]):
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
                    if sum(p.midi % 12 == leading for p in chord) > 1:
                        continue  # never double the leading tone
                    if size == 3:
                        doubled = next(n for n in names if present.count(n) == 2)
                        if doubled in chromatic or doubled == local_lt:
                            continue  # nor a chromatic note or an applied chord's leading tone
                        if info["kind"] == "aug6":
                            if doubled != names[1]:
                                continue  # the Italian sixth doubles the tonic
                        elif inversion == 0 and doubled != root and not (fifth and doubled == names[2]):
                            continue
                        elif inversion == 2 and doubled != bass_name:
                            continue
                        elif inversion == 1 and (info["symbol"].endswith("°") or info["kind"] == "neapolitan") and doubled != bass_name:
                            continue  # vii°6, ii°6 and N6 double the bass (the chord's third)
                    if final and (s.name != root or info["degree"] != 1 or inversion != 0):
                        continue
                    out.append(chord)
    return tuple(out)


def degree_of(p, key):
    key = as_key(key)
    return (STEPS.index(p.step) - STEPS.index(tonic_step(key.fifths, key.mode))) % 7 + 1


# ---------------------------------------------------------------- voice leading

MAX_LEAP = {0: 9, 1: 7, 2: 7, 3: 12}  # S, A, T, B in semitones
TONICS = ("I", "i")
DOMINANTS = ("V", "V7")


def transition(old, new, old_label, new_label, key, frustrated=False, fixed=None):
    """Cost of moving between two voicings, or None when a rule forbids it.

    ``fixed`` names a voice index whose line is given (harmonization), exempt
    from the melodic checks. ``frustrated`` permits the inner-voice exception at a
    final V-I: the leading tone in the alto or tenor may fall a third to the fifth
    of I, so the tonic is complete.
    """
    key = as_key(key)
    leading = (key_tonic_pc(key.fifths, key.mode) - 1) % 12
    cost = 0.0
    for i in range(4):
        if i == fixed:
            continue  # a given line is the student's: its own melody is not ours to judge here
        o, n = old[i], new[i]
        d = n.midi - o.midi
        if abs(d) == 6 or abs(d) in (10, 11) or abs(d) > MAX_LEAP[i]:
            return None
        if abs(n.diatonic - o.diatonic) == 1 and abs(d) == 3:
            return None  # augmented second
        if o.midi % 12 == leading and d not in (0, 1):
            if not (frustrated and i in (1, 2) and d in (-3, -4) and new_label in TONICS and old_label in DOMINANTS):
                return None  # the leading tone rises to the tonic
            cost += 6
        if i == 0:
            cost += abs(d) * 0.9 + (7 if abs(d) > 4 else 2 if abs(d) > 2 else 0) + (4 if d == 0 else 0)
        elif i == 3:
            cost += abs(d) * 0.15
        else:
            cost += abs(d) * 0.6 + (2 if abs(d) > 4 else 0)
    info = chord_info(old_label, key)
    if old_label != new_label:
        for i, o in enumerate(old):
            n = new[i]
            if i == fixed or n == o:
                continue
            step_down = o.diatonic - n.diatonic == 1 and o.midi - n.midi in (1, 2)
            half_up = n.diatonic - o.diatonic == 1 and n.midi - o.midi == 1
            # Chordal sevenths descend by step, except the rising soprano of the parallel 10ths.
            if info["size"] == 4 and info["kind"] != "aug6" and o.name == info["names"][3]:
                tenths = old_label == "V4/3" and new_label in ("I6", "i6") and i == 0 and n.diatonic - o.diatonic == 1
                if not step_down and not tenths:
                    return None
            # An applied chord's leading tone rises to its target.
            if o.name == local_leading_tone(info) and not half_up:
                return None
            # Augmented sixths expand outward by half step; the Neapolitan's lowered second falls.
            if info["kind"] == "aug6":
                if o.name == info["names"][0] and not (o.midi - n.midi == 1):
                    return None
                if o.name == info["names"][-1] and not half_up:
                    return None
            if info["kind"] == "neapolitan" and o.name == info["names"][0] and n.midi > o.midi:
                return None
            if info["kind"] == "altered" and o.name == info["names"][2] and not half_up:
                return None  # an augmented fifth continues up
    # No cross relation: a letter that changes accidental does so within one voice.
    for i, o in enumerate(old):
        for j, n in enumerate(new):
            if i != j and o.step == n.step and o.alter != n.alter and new[i].step != o.step and old[j].step != n.step:
                if i != fixed and j != fixed:
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
    if old_label in ("I6/4", "i6/4") and new[3] != old[3]:
        return None  # the cadential 6/4 keeps its bass
    if (old_label in ("IV6/4", "iv6/4") or new_label in ("IV6/4", "iv6/4")) and new[3] != old[3]:
        return None  # the pedal 6/4 holds its bass
    if (old_label == "V6/4" or new_label == "V6/4") and not (0 < abs(new[3].midi - old[3].midi) <= 2):
        return None  # the passing 6/4 moves its bass by step
    if info["kind"] == "common-tone" and any(abs(new[i].midi - old[i].midi) > 2 for i in range(4) if i != fixed):
        return None  # the common-tone diminished seventh returns by step
    return cost


def voice(chords, key, soprano, rng, width=48, cadence=True):
    """Beam search over voicings. ``soprano`` maps event index to allowed soprano degrees."""
    options = []
    for i, label in enumerate(chords):
        near_ct = "ct°7" in chords[max(0, i - 1):i + 2]
        vs = voicings(label, key, final=cadence and i == len(chords) - 1, fifth=near_ct and label in TONICS)
        if i in soprano:
            vs = [v for v in vs if degree_of(v[0], key) in soprano[i]]
        if not vs:
            raise ComposeError(f"No voicing for {label}.")
        options.append(vs)
    beam = [(rng.random() * 2, [v]) for v in options[0]]
    for i in range(1, len(chords)):
        grown = []
        for cost, path in beam:
            prev = path[-1]
            for v in options[i]:
                c = transition(prev, v, chords[i - 1], chords[i], key)
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
            k = item[1][-1]
            if seen.get(k, 0) < 3:
                seen[k] = seen.get(k, 0) + 1
                beam.append(item)
            if len(beam) >= width:
                break
    return min(beam, key=lambda x: x[0])[1]


# ---------------------------------------------------------------- export

def to_musicxml(path_voicings, chords, fifths, title, mode="major"):
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
            ET.SubElement(key, "mode").text = mode
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

def compose_chorale(key="C", bars=4, seed=None, attempts=40, chromatic=False, picardy=False):
    """Return (musicxml, review, plan) for an original chorale phrase.

    ``key`` is a name from KEYS ("C", "Bb", "Am", "F#m", ...). With ``chromatic``,
    the cadence is approached by a chromatic chord (an applied dominant of V, the
    Neapolitan, an augmented sixth, or in major a chord borrowed from minor), and
    the tonic may be expanded with tonicizations or a common-tone diminished
    seventh. ``picardy`` ends a minor-key phrase on a major tonic.
    ``review`` is ``coach.review.run_review``'s result on the exported score, so the
    composition is checked exactly as an uploaded exercise would be.
    """
    from .review import run_review
    if key not in KEYS:
        raise ComposeError(f"Key must be one of {', '.join(KEYS)}.")
    if not 4 <= bars <= 8:
        raise ComposeError("Choose four to eight bars.")
    k = KEYS[key]
    rng = random.Random(seed)
    best = None
    for _ in range(attempts):
        chords, spans = progression(bars, rng, k.mode, chromatic, k)
        if picardy and k.mode == "minor":
            chords[-1] = "I"  # the Picardy third: a major tonic to end a minor-key phrase
        soprano = {}
        for start, unit in spans:
            if unit[4]:
                for offset, deg in enumerate(unit[4]):
                    soprano[start + offset] = {deg}
        soprano[len(chords) - 2] = soprano.get(len(chords) - 2, {2, 7}) & {2, 7} or {2, 7}
        if chords[-3] in ("I6/4", "i6/4"):
            soprano[len(chords) - 3] = {1, 3, 5}
        try:
            path = voice(chords, k, soprano, rng)
        except ComposeError:
            continue
        if not path:
            continue
        title = f"Chorale in {key_name(key)}"
        xml = to_musicxml(path, chords, k.fifths, title, k.mode)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "chorale.musicxml"
            source.write_text(xml, encoding="utf-8")
            review = run_review(source, Path(tmp) / "out")
        findings = review["result"]["findings"]
        if any(f["severity"] == "error" for f in findings):
            continue
        if [c["roman"] for c in review["result"]["harmony"]] != chords:
            continue  # the reviewer must read exactly the chords that were composed
        score = len(findings)
        plan = {"key": key, "key_name": key_name(key), "mode": k.mode, "bars": bars, "chords": chords,
                "expansions": [{"figure": u[0], "name": u[1], "chords": [chords[s]] + [localize(c, k.mode) for c in u[3]], "start": s}
                               for s, u in spans if u[0] != "arp"]}
        if best is None or score < best[0]:
            best = (score, xml, review, plan)
        if score == 0:
            break
    if best is None:
        raise ComposeError("No phrase passed every rule this time; try again.")
    return best[1], best[2], best[3]
