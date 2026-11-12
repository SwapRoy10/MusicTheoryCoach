"""Harmony with nonchord tones: which notes belong to the chord, and what the others are.

Every onset (and every place a tied note is held into a new chord) is a slice of
the music. A slice that spells a known chord is a chord. Otherwise the analysis
looks for one or two notes that act as embellishments: replacing each with the
note it comes from or goes to must leave a known chord, and its melodic shape
must match a standard nonchord tone. What remains unexplained is reported.

Types (abbreviation): passing tone (PT), accented passing tone (APT), neighbor
(NT), accented neighbor (ANT), suspension (S, with figures such as 4-3),
retardation (RET), appoggiatura (APP), escape tone (ET), anticipation (ANTIC),
changing tones (CT, a double neighbor) and chromatic passing tone (PT, chromatic).
"""
from fractions import Fraction
from itertools import combinations

from .harmony import identify
from .model import VOICES

NAMES = {
    "PT": "passing tone", "APT": "accented passing tone", "NT": "neighbor tone", "ANT": "accented neighbor tone",
    "S": "suspension", "RET": "retardation", "APP": "appoggiatura", "ET": "escape tone",
    "ANTIC": "anticipation", "CT": "changing tone (double neighbor)", "PED": "pedal",
}


def _lines(score):
    lines = {}
    for v in VOICES:
        lines[v] = sorted((n for n in score.notes if n.voice == v), key=lambda n: n.start)
    return lines


def _neighbors(line, note):
    i = line.index(note)
    prev = line[i - 1] if i and line[i - 1].end == note.start else None
    nxt = line[i + 1] if i + 1 < len(line) and line[i + 1].start == note.end else None
    return prev, nxt


def _step(a, b):
    """Motion by step: a diatonic second, or a chromatic half step on the same letter."""
    letters = b.diatonic - a.diatonic
    semis = b.midi - a.midi
    if abs(letters) == 1 and 1 <= abs(semis) <= 2:
        return 1 if semis > 0 else -1
    if letters == 0 and abs(semis) == 1:
        return 1 if semis > 0 else -1
    return 0


def _leap(a, b):
    return abs(b.diatonic - a.diatonic) >= 2


def strong(time):
    """Beats 1 and 3 of a 4/4 bar are accented."""
    return Fraction(time) % 2 == 0


def interval_figure(note, bass):
    """Generic interval above the bass: 2..9 (compound intervals above a ninth reduced)."""
    n = note.diatonic - bass.diatonic
    if n <= 0:
        return None
    figure = n % 7 + 1
    if figure == 1:
        figure = 8
    if figure == 2 and n >= 7:
        figure = 9
    return figure


def classify(note, line, time, prev_chord, chord, next_chord, held=False):
    """The kind of embellishment ``note`` is at ``time`` (or None). Chords are sets of pitch names."""
    prev, nxt = _neighbors(line, note)
    accented = strong(time)
    if held or note.tied:
        # A note held (or tied) from a chord it belonged to, now dissonant: suspension or retardation.
        if nxt is not None and _step(note.pitch, nxt.pitch):
            return "S" if nxt.pitch.midi < note.pitch.midi else "RET"
        return None
    if prev is None or nxt is None:
        if prev is not None and prev.pitch == note.pitch and nxt is None:
            return None
        return None
    a, d = _step(prev.pitch, note.pitch), _step(note.pitch, nxt.pitch)
    if prev.pitch == note.pitch and prev.pitch.name in (prev_chord or ()):
        if d and nxt.pitch.midi < note.pitch.midi:
            return "S"  # re-struck preparation
        if d:
            return "RET"
    if nxt.pitch == note.pitch and not accented and note.pitch.name in (next_chord or ()):
        return "ANTIC"
    if a and d and a == d:
        return "APT" if accented else "PT"
    if a and d and a != d and nxt.pitch == prev.pitch:
        return "ANT" if accented else "NT"
    if _leap(prev.pitch, note.pitch) and d and (note.pitch.midi - prev.pitch.midi) * d < 0:
        return "APP"
    if a and _leap(note.pitch, nxt.pitch) and (nxt.pitch.midi - note.pitch.midi) * a < 0:
        return "ET"
    # Changing tones: step away, leap a third past the chord tone, step back to it.
    i = line.index(note)
    if i + 2 < len(line) and nxt.end == line[i + 2].start:
        after = line[i + 2]
        if a and abs(nxt.pitch.diatonic - note.pitch.diatonic) == 2 and _step(nxt.pitch, after.pitch) and after.pitch == prev.pitch:
            return "CT"
    if i >= 1 and prev is not None:
        before = line[i - 2] if i >= 2 else None
        if before is not None and abs(note.pitch.diatonic - prev.pitch.diatonic) == 2 and _step(prev.pitch, before.pitch) \
                and d and nxt.pitch == before.pitch:
            return "CT"
    return None


def analyze(score, fallback=None):
    """Chord slices with their nonchord tones.

    ``fallback(frame)`` may return a contextual chord reading (an incomplete seventh,
    say) for a slice that is not a complete chord; it is tried first where all four
    voices attack together, and last elsewhere.

    Returns a list of slices: {time, frame, chord (identify() result), chord_notes
    ({voice: Pitch} with embellishments replaced), ncts ({voice: {...}})}.
    """
    mode = getattr(score, "mode", "major")
    lines = _lines(score)
    times = sorted({n.start for n in score.notes})
    slices = []
    for time in times:
        frame = {n.voice: n for n in score.notes if n.start <= time < n.end}
        slices.append({"time": time, "frame": frame})
    # First pass: complete chords.
    for s in slices:
        s["chord"] = identify(s["frame"], score.fifths, mode)
        s["ncts"] = {}
        s["chord_notes"] = {v: n.pitch for v, n in s["frame"].items()}

    # Weak-beat notes moving over held notes decorate the chord before them, even when they happen to
    # spell another chord (a passing tone that makes a "vii°6/4" or an "I7" is still a passing tone).
    if not score.homophonic:
        for index in range(1, len(slices)):
            s, before = slices[index], slices[index - 1]
            if strong(s["time"]) or before["chord"]["status"] not in ("identified", "interpreted"):
                continue
            moving = [v for v, n in s["frame"].items() if n.start == s["time"] and not n.tied]
            held = [v for v, n in s["frame"].items() if n.start < s["time"] or n.tied]
            if not moving or not held:
                continue
            members = set(before["chord"]["pitches"])
            nxt_chord = slices[index + 1]["chord"] if index + 1 < len(slices) else None
            next_members = set(nxt_chord["pitches"]) if nxt_chord and nxt_chord["status"] == "identified" else members
            kinds = {}
            for v in moving:
                note = s["frame"][v]
                if note.pitch.name in members:
                    continue  # a chord tone (arpeggiation)
                kind = classify(note, lines[v], s["time"], members, members, next_members)
                if kind not in ("PT", "NT", "ET", "ANTIC", "CT"):
                    kinds = None
                    break
                kinds[v] = kind
            sounding = {n.pitch.name for n in s["frame"].values()}
            if kinds == {} and sounding <= members:
                s["chord"] = before["chord"]  # the moving voices only arpeggiate the chord
                continue
            if kinds:
                s["chord"] = before["chord"]
                for v, kind in kinds.items():
                    s["ncts"][v] = {"type": kind, "name": NAMES[kind], "note": s["frame"][v], "voice": v, "chromatic": False}
                    prev = _neighbors(lines[v], s["frame"][v])[0]
                    s["chord_notes"][v] = (prev or s["frame"][v]).pitch

    def names(i):
        if 0 <= i < len(slices) and slices[i]["chord"]["status"] == "identified":
            return set(slices[i]["chord"]["pitches"])
        return None

    # Second pass: explain the other slices with one or two embellishing notes.
    for index, s in enumerate(slices):
        if s["chord"]["status"] == "identified" or len(s["frame"]) != 4:
            continue
        all_attack = all(n.start == s["time"] and not n.tied for n in s["frame"].values())
        if score.homophonic:
            # Block chords in half and whole notes: no embellishments to find, only contextual readings.
            reading = fallback(s["frame"]) if fallback else None
            if reading:
                s["chord"] = reading
            continue
        # A slice whose notes all belong to the chord just before or after it (over the same bass) is that chord,
        # momentarily incomplete while a voice arpeggiates.
        sounding = {n.pitch.name for n in s["frame"].values()}
        bass = min(s["frame"].values(), key=lambda n: n.pitch.midi).pitch.name
        for j in (index + 1, index - 1):
            if 0 <= j < len(slices) and slices[j]["chord"]["status"] == "identified":
                other = slices[j]["chord"]
                if sounding <= set(other["pitches"]) and other.get("bass") == bass and len(sounding) >= 2:
                    s["chord"] = {**other, "incomplete": True}
                    break
        if s["chord"]["status"] == "identified":
            continue
        if all_attack and fallback:
            reading = fallback(s["frame"])
            if reading:
                s["chord"] = reading
                continue
        best = None
        candidates = list(s["frame"])
        for size in (1, 2):
            for voices in combinations(candidates, size):
                for choice in _substitutions(voices, s, lines):
                    trial = {v: n for v, n in s["frame"].items()}
                    for v, sub in choice.items():
                        trial[v] = sub
                    chord = identify(trial, score.fifths, mode)
                    if chord["status"] != "identified":
                        continue
                    members = set(chord["pitches"])
                    if any(s["frame"][v].pitch.name in members for v in voices):
                        continue  # an embellishment is not itself a chord tone
                    prev_names = names(index - 1) or members
                    next_names = members
                    kinds = {}
                    for v in voices:
                        note = s["frame"][v]
                        held = note.start < s["time"]
                        kind = classify(note, lines[v], s["time"], prev_names, members, next_names, held=held)
                        if kind is None:
                            break
                        kinds[v] = kind
                    else:
                        # Prefer fewer embellishments; then readings where accented embellishments resolve to the
                        # next note and unaccented ones come from the previous note; then the previous chord.
                        accented = strong(s["time"])
                        mismatch = 0
                        for v, sub in choice.items():
                            forward = sub.start >= s["frame"][v].end
                            mismatch += int(forward != accented and not s["frame"][v].tied)
                        same = int(chord["pitches"] == (slices[index - 1]["chord"].get("pitches") if index else None))
                        score_ = (size, mismatch, -same)
                        if best is None or score_ < best[0]:
                            best = (score_, chord, kinds, choice)
            if best:
                break
        if not best and fallback:
            reading = fallback(s["frame"])
            if reading:
                s["chord"] = reading
                continue
        if best:
            _, chord, kinds, choice = best
            s["chord"] = chord
            for v, kind in kinds.items():
                note = s["frame"][v]
                info = {"type": kind, "name": NAMES[kind], "note": note, "voice": v,
                        "chromatic": False}
                if kind in ("S", "RET") and "B" in s["frame"] and v != "B":
                    resolution = _neighbors(lines[v], note)[1]
                    bass = s["frame"]["B"]
                    top = interval_figure(note.pitch, bass.pitch)
                    if resolution is not None:
                        low = interval_figure(resolution.pitch, bass.pitch)
                        if top and low:
                            info["figure"] = f"{top}-{low}"
                if kind in ("S",) and v == "B":
                    info["figure"] = "2-3"
                s["ncts"][v] = info
                s["chord_notes"][v] = choice[v].pitch
    # Notes attacked inside a slice that is already a chord still need checking: a note that is not a
    # member of the slice's chord (possible when two embellishments happen to spell a chord) is left alone.
    return slices


def _substitutions(voices, s, lines):
    """Ways to replace embellishing notes by the chord tones around them (previous or next note)."""
    options = []
    for v in voices:
        note = s["frame"][v]
        prev, nxt = _neighbors(lines[v], note)
        subs = [x for x in (nxt, prev) if x is not None]
        if note.tied:
            subs = [x for x in (nxt,) if x is not None]
        options.append([(v, x) for x in subs])
    out = [{}]
    for opts in options:
        out = [dict(o, **{v: x}) for o in out for v, x in opts]
    return out


def harmony_events(slices):
    """Chord-level events. A slice joins the previous event when it has the same chord over the same
    bass and not every voice is struck again (a repeated block chord stays a new event)."""
    events = []
    for s in slices:
        chord = s["chord"]
        key = (chord.get("roman"), tuple(sorted(chord.get("pitches", []))),
               str(s["chord_notes"].get("B")) if "B" in s["chord_notes"] else None)
        restruck = all(n.start == s["time"] and not n.tied for n in s["frame"].values())
        if events and events[-1]["key"] == key and chord["status"] in ("identified", "interpreted") and not restruck:
            events[-1]["slices"].append(s)
            continue
        events.append({"key": key, "slices": [s], "time": s["time"]})
    return events


def structural(slice_, lines):
    """The chord tones of a slice: embellishments replaced by the notes they resolve to or come from."""
    out = {}
    for v, note in slice_["frame"].items():
        info = slice_["ncts"].get(v)
        if not info:
            out[v] = note
            continue
        prev, nxt = _neighbors(lines[v], note)
        accented = info["type"] in ("S", "RET", "APP", "APT", "ANT")
        out[v] = (nxt if accented else prev) or nxt or prev or note
    return out


def lines_of(score):
    return _lines(score)


def unexplained(slices):
    """Slices that are neither chords nor explained by nonchord tones."""
    return [s for s in slices if s["chord"]["status"] != "identified" and len(s["frame"]) == 4]
