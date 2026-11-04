"""Complete a chorale exercise: harmonize a given soprano or bass in four parts.

The given line is half notes with a final whole note, in a major or minor key.
The search chooses a chord for every note and voices the other three parts at
the same time, following a small grammar of harmonic function (tonic,
predominant, dominant, applied chords to their targets) and the voice-leading
rules in ``compose_chorale``. Chromatic notes in the line are harmonized with
applied chords, mixture, the Neapolitan or augmented sixths. Every result is
reviewed by ``coach.review.run_review`` on its exported MusicXML; only results
with no errors are returned.
"""
from functools import lru_cache
from pathlib import Path
import random
import tempfile

from .compose_chorale import KEYS, ComposeError, chord_info, key_name, to_musicxml, transition, voicings
from .harmony import label_for, vocabulary
from .model import RANGES, Pitch

CHROMATIC = ("applied", "mixture", "neapolitan", "aug6")


@lru_cache(maxsize=None)
def chord_labels(key):
    """Every chord the harmonizer may use in ``key``, as numerals with figures."""
    labels = []
    for chord in vocabulary(key.fifths, key.mode):
        kind, symbol, size = chord["kind"], chord["symbol"], chord["size"]
        if kind == "aug6":
            labels.append(label_for(chord, 0))
            continue
        if kind == "neapolitan":
            labels.append(label_for(chord, 1))
            continue
        if kind == "mixture":
            if key.mode == "minor" or symbol in ("bIII", "bVII", "i"):
                continue  # (the minor-mode Picardy third is added for the final chord only)
        if kind == "diatonic" and symbol in ("v", "VII") and key.mode == "minor":
            continue
        if size == 4 and not (symbol in ("V", "viiø", "vii°", "ii", "iiø") or kind == "applied"):
            continue
        if kind == "applied" and size == 3 and not symbol.startswith("V"):
            continue
        for inversion in range(size):
            if size == 3 and inversion == 2 and chord["degree"] != 1:
                continue  # 6/4 chords: only the cadential 6/4
            if size == 3 and symbol.endswith("°") and inversion != 1:
                continue  # diminished triads in first inversion
            if chord["degree"] == 1 and kind == "diatonic" and size == 4:
                continue
            labels.append(label_for(chord, inversion))
    return tuple(labels)


def function(label, key):
    info = chord_info(label, key)
    kind, degree, symbol = info["kind"], info["degree"], info["symbol"]
    if kind == "applied":
        return "APP"
    if kind in ("neapolitan", "aug6"):
        return "PD"
    if degree == 1:
        return "CAD" if info["inversion"] == 2 else "T"
    if symbol in ("vi", "VI", "iii", "III", "bVI"):
        return "TS"
    if degree in (2, 4):
        return "PD"
    return "D"


# Where each dominant may go (the user's framework: V4/2 resolves to I6).
RESOLVES = {"V": {"I", "I6", "TS", "V7", "V6/5", "V4/3", "V4/2"}, "V6": {"I", "V6/5"}, "V7": {"I", "TS"},
            "V6/5": {"I"}, "V4/3": {"I", "I6"}, "V4/2": {"I6"}, "vii°6": {"I", "I6"}, "vii°7": {"I"},
            "vii°6/5": {"I", "I6"}, "vii°4/3": {"I6"}, "viiø7": {"I"}, "viiø6/5": {"I", "I6"}, "viiø4/3": {"I6"}}


def _tonic_form(label):
    return label.replace("i", "I", 1) if label.startswith("i") and not label.startswith(("ii", "iv")) else label


def allowed(old, new, key):
    if old == new:
        return False
    fo, fn = function(old, key), function(new, key)
    info_old, info_new = chord_info(old, key), chord_info(new, key)
    if fo == "CAD":
        return new in ("V", "V7")
    if fo == "APP":
        target_root = _target_root(info_old, key)
        if fn == "APP":  # V/x may gain its seventh: V/V -> V6/5/V
            return (info_new.get("target") == info_old.get("target") and info_old["symbol"] == "V"
                    and info_new["symbol"] == "V" and info_old["size"] == 3 and info_new["size"] == 4)
        if info_new["names"][0] != target_root or info_new["kind"] not in ("diatonic",):
            return fn == "CAD" and info_old.get("target") == "V"
        return True
    if fo == "D":
        allowed_next = RESOLVES.get(_tonic_form(old), set())
        return _tonic_form(new) in allowed_next or (fn == "TS" and "TS" in allowed_next and info_new["degree"] == 6)
    if fo == "PD":
        if info_old["kind"] == "aug6":
            return new in ("V", "V7") or fn == "CAD"
        if fn in ("D", "CAD"):
            return True
        if fn == "APP":
            return info_new.get("target") == "V"
        if fn == "PD" and info_old["kind"] != "neapolitan" and info_old["degree"] == 4:
            return info_new["degree"] == 2 or info_new["kind"] in ("neapolitan", "aug6")
        return False
    if fo == "TS":
        return fn in ("PD", "APP", "TS") or new in ("I6", "i6")
    return fn != "CAD"  # tonic: anything but the cadential 6/4


def _target_root(info, key):
    target = info.get("target")
    for chord in vocabulary(key.fifths, key.mode):
        if chord["kind"] == "diatonic" and chord["size"] == 3 and chord["symbol"] == target:
            return chord["pitches"][0]
    return None


@lru_cache(maxsize=None)
def _voicings(label, key, final):
    return voicings(label, key, final=final, unison=True)


def harmony_cost(index, label, total, key, chromatic=False):
    """A light preference for idiomatic choices; None rules a chord out at this point."""
    strong = index % 2 == 0
    fn = function(label, key)
    info = chord_info(label, key)
    if fn == "CAD" and (not strong or index != total - 3):
        return None  # the cadential 6/4 is accented, and only at the cadence
    cost = 0.0
    if info["kind"] in CHROMATIC:
        cost += 0.3 if chromatic else 4.5
    if fn == "TS" or label in ("V6",):
        cost += 1.0
    if info["degree"] == 3 or label in ("vi6", "VI6", "ii4/3", "ii4/2", "iiø4/3", "iiø4/2", "ii7"):
        cost += 1.5  # less common choices
    if info["kind"] == "applied":
        cost += -1.0 if info.get("target") == "V" else 1.0 if info.get("target") in ("iii", "III") else 0
    if strong and info["inversion"] != 0 and fn != "CAD":
        cost += 0.6  # root position on downbeats
    if index == total - 3 and fn == "T":
        cost += 1.5  # approach the cadence from a predominant when the line allows it
    return cost


def harmonize(given, voice="S", key="C", seed=None, attempts=12, width=60, chromatic=False):
    """Return (musicxml, review, plan) for a four-part setting of ``given`` (a list of Pitch).

    ``voice`` is "S" (a melody to harmonize) or "B" (a bass to realize). ``key`` is a
    name from KEYS ("C", "Am", ...). With ``chromatic``, applied chords, mixture,
    the Neapolitan and augmented sixths are used freely; otherwise only where the
    line needs them.
    """
    from .review import run_review
    if key not in KEYS:
        raise ComposeError(f"Key must be one of {', '.join(KEYS)}.")
    if voice not in ("S", "B"):
        raise ComposeError("The given line must be the soprano or the bass.")
    k = KEYS[key]
    given = list(given)
    if len(given) < 5 or len(given) % 2 == 0:
        raise ComposeError("Give an odd number of notes (at least five): half notes, two per bar, and a final whole note.")
    if len(given) > 31:
        raise ComposeError("Sixteen bars at most.")
    low, high = RANGES[voice]
    name = {"S": "soprano", "B": "bass"}[voice]
    for i, p in enumerate(given, 1):
        if not low <= p.midi <= high:
            raise ComposeError(f"Note {i} ({p}) is outside the {name} range ({Pitch_name(low)}–{Pitch_name(high)}).")
    tonic = chord_info("i" if k.mode == "minor" else "I", k)
    if given[-1].name != tonic["names"][0]:
        raise ComposeError(f"The last note must be the tonic, {tonic['names'][0]}, for an authentic cadence.")
    slot = 0 if voice == "S" else 3
    total = len(given)
    labels = chord_labels(k)
    finals = ["i", "I"] if k.mode == "minor" else ["I"]  # a Picardy third is possible in minor

    # Candidate chords for each note.
    options = []
    for i, p in enumerate(given):
        found = []
        for label in (finals if i == total - 1 else labels):
            info = chord_info(label, k)
            if (voice == "S" and p.name not in info["names"]) or (voice == "B" and p.name != info["bass"]):
                continue
            if i == 0 and label not in ("I", "I6", "i", "i6"):
                continue
            if i == total - 2 and label not in ("V", "V7"):
                continue
            found.append(label)
        if not found:
            where = "last" if i == total - 1 else "next-to-last" if i == total - 2 else f"note {i + 1}"
            need = {total - 1: "the tonic", total - 2: "a note of V (sol, ti or re; fa for V7)",
                    0: "a note of the tonic chord"}.get(i, f"a note of a chord in {key_name(key)}")
            raise ComposeError(f"The {where} note ({p}) cannot be harmonized: it must be {need}.")
        options.append(found)

    rng = random.Random(seed)
    best = None
    for _ in range(attempts):
        path = _search(given, options, slot, k, rng, width, chromatic=chromatic)
        if not path:
            continue
        chords = [label for label, _ in path]
        xml = to_musicxml([v for _, v in path], chords, k.fifths, f"Harmonization in {key_name(key)}", k.mode)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "harmonized.musicxml"
            source.write_text(xml, encoding="utf-8")
            review = run_review(source, Path(tmp) / "out")
        findings = review["result"]["findings"]
        if any(f["severity"] == "error" for f in findings):
            continue
        if [c["roman"] for c in review["result"]["harmony"]] != chords:
            continue
        plan = {"key": key, "key_name": key_name(key), "mode": k.mode, "bars": (total + 1) // 2,
                "chords": chords, "given": voice}
        if best is None or len(findings) < best[0]:
            best = (len(findings), xml, review, plan)
        if not findings:
            break
    if best is None:
        raise ComposeError("No setting of this line passed every rule. Leaps between chord tones that no chord "
                           "connects, or a line that stays on one note, are the usual causes.")
    return best[1], best[2], best[3]


def Pitch_name(midi):
    names = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
    return f"{names[midi % 12]}{midi // 12 - 1}"


def _search(given, options, slot, key, rng, width, total=None, chromatic=False):
    total = total or len(given)
    n = len(given)
    complete = n == total

    def cadence(i):
        return complete and i == total - 1
    # Label-level lookahead: keep only chords from which the grammar can still reach the cadence.
    def label_ok(i, label):
        if harmony_cost(i, label, total, key, chromatic) is None:
            return False
        return not (i == total - 3 and function(label, key) == "D")
    reach = [set() for _ in range(n)]
    reach[n - 1] = {l for l in options[n - 1] if label_ok(n - 1, l)}
    for i in range(n - 2, -1, -1):
        reach[i] = {l for l in options[i] if label_ok(i, l) and (not complete or any(allowed(l, m, key) for m in reach[i + 1]))}
        if not complete:
            reach[i] = {l for l in options[i] if label_ok(i, l)}
    states = []
    for i in range(n):
        final = complete and i == total - 1
        states.append([(label, v) for label in sorted(reach[i])
                       for v in _voicings(label, key, final) if v[slot] == given[i]])
    # Voicing-level lookahead over the cadence (the last three chords): exact backward feasibility.
    if complete:
        for i in range(n - 2, max(-1, n - 4), -1):
            nxt = states[i + 1]
            states[i] = [(l, v) for l, v in states[i]
                         if any(allowed(l, m, key) and transition(v, w, l, m, key, cadence(i + 1), slot) is not None for m, w in nxt)]
    # Exact dynamic programming over (chord, voicing) states: the best path into every state.
    free = 3 if slot == 0 else 0
    best = {state: (harmony_cost(0, state[0], total, key, chromatic) + rng.random() * 2, [state]) for state in states[0]}
    for i in range(1, n):
        nxt = {}
        for label, v in states[i]:
            hcost = harmony_cost(i, label, total, key, chromatic)
            choice = None
            for (old_label, old), (cost, path) in best.items():
                if not allowed(old_label, label, key):
                    continue
                c = transition(old, v, old_label, label, key, cadence(i), slot)
                if c is None:
                    continue
                # A soprano that is free to move recovers its leaps by step the other way.
                if free == 0 and len(path) >= 2:
                    a, b2 = path[-2][1][0].midi, old[0].midi
                    if abs(b2 - a) > 4 and not (0 < abs(v[0].midi - b2) <= 2 and (v[0].midi - b2) * (b2 - a) < 0):
                        c += 8
                total_cost = cost + c + hcost + rng.random() * 3
                if choice is None or total_cost < choice[0]:
                    choice = (total_cost, path)
            if choice:
                nxt[(label, v)] = (choice[0], choice[1] + [(label, v)])
        if not nxt:
            return None
        best = nxt
    return min(best.values(), key=lambda x: x[0])[1]


def parse_line(text):
    """'E5 D5 C5 | D5 E5' -> list of Pitch (bar lines are optional)."""
    tokens = [t for t in text.replace(",", " ").replace("|", " ").split() if t]
    try:
        return [Pitch.parse(t.replace("♭", "b").replace("♯", "#")) for t in tokens]
    except ValueError as exc:
        raise ComposeError(f"{exc}. Write pitches like E5, F#4 or Bb3.") from None


def read_line(path):
    """A single-voice MusicXML line: (pitches, key name, voice), checking the half-note rhythm."""
    from fractions import Fraction
    from .score_import import root_from_file
    root = root_from_file(path)
    pitches, durations, fifths, divisions = [], [], None, None
    for part in root.findall("part"):
        for measure in part.findall("measure"):
            for el in measure:
                if el.tag == "attributes":
                    if el.findtext("divisions"):
                        divisions = int(el.findtext("divisions"))
                    if el.findtext("key/fifths"):
                        fifths = int(el.findtext("key/fifths"))
                elif el.tag == "note" and el.find("pitch") is not None and el.find("chord") is None:
                    p = el.find("pitch")
                    pitches.append(Pitch(p.findtext("step"), int(p.findtext("alter", "0")), int(p.findtext("octave"))))
                    durations.append(Fraction(int(el.findtext("duration", "0")), divisions or 1))
    if not pitches:
        raise ComposeError("The file has no notes.")
    if fifths is None or not -4 <= fifths <= 4:
        raise ComposeError("Use a key with up to four flats or four sharps.")
    if any(d != 2 for d in durations[:-1]) or durations[-1] not in (2, 4):
        raise ComposeError("Write the line in half notes with a final whole note (one chord per half note).")
    voice = "B" if sum(p.midi for p in pitches) / len(pitches) < 57 else "S"
    # Minor when the line ends on the relative minor's tonic.
    minor = pitches[-1].midi % 12 == (7 * fifths + 9) % 12
    key = next(name for name, k in KEYS.items() if k.fifths == fifths and k.mode == ("minor" if minor else "major"))
    return pitches, key, voice
