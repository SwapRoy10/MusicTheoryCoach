"""Conservative, spelling-aware identification of complete chords in a key.

Covers the diatonic triads and seventh chords of major and minor keys (minor
uses the raised leading tone for V and vii°, and the natural forms for III, VI
and VII), and the common chromatic chords: applied (secondary) dominants and
leading-tone chords, mode mixture in major, the Neapolitan, and the Italian,
French and German augmented sixths. This describes the sounding sonority, not
its contextual function. It never invents an absent root, third, fifth or seventh.
"""
from functools import lru_cache

from .model import Pitch, STEPS, VOICES, scale

ROMAN = ("I", "II", "III", "IV", "V", "VI", "VII")
TRIADS = {"M": ((2, 4), (4, 7)), "m": ((2, 3), (4, 7)), "d": ((2, 3), (4, 6)), "A": ((2, 4), (4, 8))}
SEVENTHS = {"Mm": ("M", (6, 10)), "MM": ("M", (6, 11)), "mm": ("m", (6, 10)), "dm": ("d", (6, 10)), "dd": ("d", (6, 9))}
TRIAD_FIGURES = ("", "6", "6/4")
SEVENTH_FIGURES = ("7", "6/5", "4/3", "4/2")


def tonic_step(fifths, mode="major"):
    return STEPS[(4 * fifths + (5 if mode == "minor" else 0)) % 7]


def tonic_pc(fifths, mode="major"):
    return (7 * fifths + (9 if mode == "minor" else 0)) % 12


def name_of(step, alter):
    return Pitch(step, alter, 4).name


def degree_pitch(degree, fifths, mode="major", shift=0):
    """Scale degree 1-7 as (step, alter), from the key signature (natural minor), shifted by semitones."""
    step = STEPS[(STEPS.index(tonic_step(fifths, mode)) + degree - 1) % 7]
    return step, scale(fifths)[step] + shift


def spell(root, intervals):
    """Names of a chord from its root (step, alter) and (letters, semitones) intervals above it."""
    step, alter = root
    base = Pitch(step, alter, 4)
    names = [base.name]
    for letters, semitones in intervals:
        s = STEPS[(STEPS.index(step) + letters) % 7]
        octave_shift = (STEPS.index(step) + letters) // 7
        natural = Pitch(s, 0, 4 + octave_shift)
        names.append(name_of(s, base.midi + semitones - natural.midi))
    return names


def build(root, quality):
    if quality in TRIADS:
        return spell(root, TRIADS[quality])
    triad, seventh = SEVENTHS[quality]
    return spell(root, TRIADS[triad] + (seventh,))


def numeral(degree, quality, prefix=""):
    base = ROMAN[degree - 1]
    if quality[0] in "md":
        base = base.lower()
    if quality == "d":
        return prefix + base + "°"
    if quality == "A":
        return prefix + base + "+"
    if quality == "dm":
        return prefix + base + "ø"
    if quality == "dd":
        return prefix + base + "°"
    return prefix + base


@lru_cache(maxsize=None)
def _vocabulary(fifths, mode):
    chords, seen = [], set()

    def add(entry):
        key = frozenset(entry["pitches"])
        if key in seen:
            return
        seen.add(key)
        chords.append(entry)

    # Diatonic chords (minor: harmonic minor for V and vii°, natural minor otherwise).
    for degree in range(1, 8):
        for size in (3, 4):
            variants = [0]
            if mode == "minor" and degree in (5, 7):
                variants = [1, 0]  # raised leading tone first: V, V7, vii°, vii°7; then v, VII
            for raise7 in variants:
                names = []
                for k in range(size):
                    d = (degree - 1 + 2 * k) % 7 + 1
                    shift = 1 if (mode == "minor" and raise7 and d == 7) else 0
                    names.append(name_of(*degree_pitch(d, fifths, mode, shift)))
                quality = _quality(names)
                if quality is None:
                    continue
                symbol = numeral(degree, quality)
                if mode == "major" and degree == 7:
                    symbol = "vii°" if size == 3 else "viiø"
                add({"degree": degree, "symbol": symbol, "pitches": names, "size": size, "kind": "diatonic"})
    if mode == "minor":
        add({"degree": 1, "symbol": "I", "pitches": build(degree_pitch(1, fifths, mode), "M"), "size": 3, "kind": "mixture"})
    else:
        # Mode mixture: chords borrowed from the parallel minor.
        borrowed = [(4, 0, "m", ""), (4, 0, "mm", ""), (2, 0, "d", ""), (2, 0, "dm", ""), (6, -1, "M", "b"),
                    (3, -1, "M", "b"), (7, -1, "M", "b"), (7, 0, "dd", ""), (1, 0, "m", "")]
        for degree, shift, quality, prefix in borrowed:
            names = build(degree_pitch(degree, fifths, mode, shift), quality)
            add({"degree": degree, "symbol": numeral(degree, quality, prefix), "pitches": names,
                 "size": 4 if len(quality) == 2 else 3, "kind": "mixture"})
    diatonic = [c for c in chords if c["kind"] == "diatonic" and c["size"] == 3]
    # Applied dominants and leading-tone chords of every major or minor diatonic triad except the tonic.
    for target in diatonic:
        if target["degree"] == 1 or target["symbol"].endswith(("°", "+")) or target["symbol"] in ("v",):
            continue
        root = _root(target["pitches"][0])
        five = _transpose(root, 4, 7)
        seven = _transpose(root, -1, -1)
        options = [(five, "M", "V"), (five, "Mm", "V"), (seven, "d", "vii°"), (seven, "dd", "vii°")]
        if target["symbol"][0].isupper():
            options.append((seven, "dm", "viiø"))
        for r, quality, name in options:
            names = build(r, quality)
            add({"degree": target["degree"], "symbol": name, "target": target["symbol"], "pitches": names,
                 "size": len(names), "kind": "applied"})
    # Neapolitan: major triad on the lowered second degree.
    flat2 = degree_pitch(2, fifths, mode, -1)
    add({"degree": 2, "symbol": "N", "pitches": build(flat2, "M"), "size": 3, "kind": "neapolitan"})
    # Augmented sixths, built from the lowered sixth degree (written with it in the bass).
    b6 = name_of(*degree_pitch(6, fifths, mode, -1 if mode == "major" else 0))
    one = name_of(*degree_pitch(1, fifths, mode))
    two = name_of(*degree_pitch(2, fifths, mode))
    b3 = name_of(*degree_pitch(3, fifths, mode, -1 if mode == "major" else 0))
    sharp4 = name_of(*degree_pitch(4, fifths, mode, 1))
    sharp2 = name_of(*degree_pitch(2, fifths, mode, 1))
    for symbol, names in (("It+6", [b6, one, sharp4]), ("Fr+6", [b6, one, two, sharp4]),
                          ("Ger+6", [b6, one, b3, sharp4]), ("Ger+6", [b6, one, sharp2, sharp4])):
        add({"degree": 6, "symbol": symbol, "pitches": names, "size": len(names), "kind": "aug6"})
    return tuple(chords)


def _root(name):
    step = name[0]
    return step, name.count("#") - name.count("b")


def _transpose(root, letters, semitones):
    names = spell(root, ((letters % 7, semitones % 12),))
    return _root(names[1])


def names_root(names):
    return _root(names[0])


def _quality(names):
    root = _root(names[0])
    for q in ("M", "m", "d", "A") if len(names) == 3 else SEVENTHS:
        if build(root, q) == names:
            return q
    return None


def vocabulary(fifths, mode="major"):
    """Chords of the key: dicts with degree, symbol, pitches (root, third, fifth[, seventh]), size, kind."""
    return [dict(c) for c in _vocabulary(fifths, mode)]


def label_for(chord, inversion):
    """Roman numeral with figures: V6/5, V6/5/V, N6, Ger+6."""
    if chord["kind"] == "aug6":
        return chord["symbol"]
    figures = (TRIAD_FIGURES if chord["size"] == 3 else SEVENTH_FIGURES)[inversion]
    if chord["kind"] == "applied":
        return chord["symbol"] + figures + "/" + chord["target"]
    return chord["symbol"] + figures


def identify(frame, fifths, mode="major"):
    names = {n.pitch.name for n in frame.values()}
    result = {"roman": "?", "status": "uncertain", "pitches": sorted(names),
              "reason": "Not a complete chord of the key or a supported chromatic chord; contextual review is needed."}
    if set(frame) != set(VOICES):
        return {**result, "reason": "Four sounding voices are required for this analysis."}
    bass = min(frame.values(), key=lambda n: n.pitch.midi).pitch.name
    for chord in _vocabulary(fifths, mode):
        if set(chord["pitches"]) == names:
            inversion = chord["pitches"].index(bass)
            reason = {"diatonic": "Exact match to the complete spelled pitch set.",
                      "mixture": "A chord borrowed from the parallel " + ("major" if mode == "minor" else "minor") + " (mode mixture).",
                      "applied": f"An applied (secondary) chord: it tonicizes {chord.get('target')}.",
                      "neapolitan": "The Neapolitan: a major triad on the lowered second degree.",
                      "aug6": "An augmented-sixth chord: the lowered sixth and raised fourth expand outward to the dominant."}[chord["kind"]]
            if chord["kind"] == "aug6" and bass != chord["pitches"][0]:
                reason += " Usually the lowered sixth is in the bass."
            return {**chord, "roman": label_for(chord, inversion), "status": "identified",
                    "bass": bass, "inversion": inversion, "reason": reason}
    return result


def analyze(score):
    events = []
    mode = getattr(score, "mode", "major")
    for time, frame in score.frames():
        mi = int(time // 4)
        if mi >= len(score.measures):
            continue
        chord = identify(frame, score.fifths, mode)
        # Repeat at every measure, but only label changes inside a measure.
        if events and time % 4 and chord["roman"] == events[-1]["roman"] and chord["pitches"] == events[-1]["pitches"]:
            continue
        events.append({**chord, "measure": score.measures[mi], "beat": str(time % 4 + 1),
                       "offset": str(time), "anchor": frame["B"].id if "B" in frame else None})
    return events
