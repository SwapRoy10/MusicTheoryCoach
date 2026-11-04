"""Complete a chorale exercise: harmonize a given soprano or bass in four parts.

The given line is half notes with a final whole note, in a major key. A beam
search chooses a Roman numeral for every note and voices the other three parts
at the same time, following a small grammar of harmonic function (tonic,
predominant, dominant) and the voice-leading rules in ``compose_chorale``.
Every result is then reviewed by ``coach.review.run_review`` on its exported
MusicXML; only results with no errors are returned.
"""
from functools import lru_cache
from pathlib import Path
import random
import tempfile

from .compose_chorale import KEYS, ComposeError, chord_members, parse_roman, to_musicxml, transition, voicings
from .model import RANGES, Pitch, scale

TONIC = {"I", "I6", "vi"}
PREDOMINANT = {"ii", "ii6", "ii6/5", "IV", "IV6"}
DOMINANT = {"V", "V6", "V7", "V6/5", "V4/3", "V4/2", "vii°6"}
CADENTIAL = "I6/4"
CHORDS = sorted(TONIC | PREDOMINANT | DOMINANT | {CADENTIAL})

# Where each dominant-function chord may go (the user's framework: V4/2 resolves to I6).
RESOLVES = {"V": {"I", "I6", "vi", "V7", "V6/5", "V4/3", "V4/2"}, "V6": {"I", "V6/5"}, "V7": {"I", "vi"},
            "V6/5": {"I"}, "V4/3": {"I", "I6"}, "V4/2": {"I6"}, "vii°6": {"I", "I6"}}


def allowed(old, new):
    if old == new:
        return False
    if old == CADENTIAL:
        return new in ("V", "V7")
    if old in DOMINANT:
        return new in RESOLVES[old]
    if old in PREDOMINANT:
        if new in DOMINANT or new == CADENTIAL:
            return True
        # IV may move to ii (IV - ii6), never ii back to IV.
        return old in ("IV", "IV6") and new in ("ii", "ii6", "ii6/5")
    if old == "vi":
        return new in PREDOMINANT or new == "I6"
    return new != CADENTIAL or old == "I6"  # tonic -> anything; a cadential 6/4 usually follows a predominant


@lru_cache(maxsize=None)
def _voicings(label, fifths, final):
    return voicings(label, fifths, final=final, unison=True)


def harmony_cost(index, label, total):
    """A light preference for idiomatic choices; noise adds variety."""
    strong = index % 2 == 0
    cost = 0.0
    if label == CADENTIAL and not strong:
        return None  # the cadential 6/4 is accented
    if label == CADENTIAL and index != total - 3:
        return None  # only at the cadence
    if label in ("V6", "vi") or label.startswith("ii") and label != "ii6":
        cost += 1.0
    if strong and parse_roman(label)[2] != 0 and label not in (CADENTIAL,):
        cost += 0.6  # root position on downbeats
    if index == total - 3 and label in TONIC:
        cost += 1.5  # approach the cadence from a predominant when the line allows it
    return cost


def harmonize(given, voice="S", key="C", seed=None, attempts=12, width=60):
    """Return (musicxml, review, plan) for a four-part setting of ``given`` (a list of Pitch).

    ``voice`` is "S" (a melody to harmonize) or "B" (a bass to realize).
    """
    from .review import run_review
    if key not in KEYS:
        raise ComposeError(f"Key must be one of {', '.join(KEYS)} major.")
    if voice not in ("S", "B"):
        raise ComposeError("The given line must be the soprano or the bass.")
    fifths = KEYS[key]
    alter = scale(fifths)
    given = list(given)
    if len(given) < 5 or len(given) % 2 == 0:
        raise ComposeError("Give an odd number of notes (at least five): half notes, two per bar, and a final whole note.")
    if len(given) > 31:
        raise ComposeError("Sixteen bars at most.")
    low, high = RANGES[voice]
    for i, p in enumerate(given, 1):
        if p.alter != alter[p.step]:
            raise ComposeError(f"Note {i} ({p}) is not in {key} major. Chromatic notes are not supported yet.")
        if not low <= p.midi <= high:
            name = {"S": "soprano", "B": "bass"}[voice]
            raise ComposeError(f"Note {i} ({p}) is outside the {name} range ({Pitch_name(low)}–{Pitch_name(high)}).")
    tonic_name = chord_members("I", fifths)[0][0]
    if given[-1].name != tonic_name:
        raise ComposeError(f"The last note must be the tonic, {tonic_name}, for an authentic cadence.")
    slot = 0 if voice == "S" else 3
    total = len(given)

    # Candidate chords for each note.
    options = []
    for i, p in enumerate(given):
        labels = []
        for label in CHORDS:
            names, bass = chord_members(label, fifths)
            if (voice == "S" and p.name not in names) or (voice == "B" and p.name != bass):
                continue
            if i == 0 and label not in ("I", "I6"):
                continue
            if i == total - 1 and label != "I":
                continue
            if i == total - 2 and label not in ("V", "V7"):
                continue
            labels.append(label)
        if not labels:
            where = "last" if i == total - 1 else "next-to-last" if i == total - 2 else f"note {i + 1}"
            need = {total - 1: "the tonic", total - 2: "a note of V (sol, ti or re; fa for V7)"}.get(i, "a chord tone")
            raise ComposeError(f"The {where} note ({p}) cannot be harmonized: it must be {need}.")
        options.append(labels)

    rng = random.Random(seed)
    best = None
    for _ in range(attempts):
        path = _search(given, options, slot, fifths, rng, width)
        if not path:
            continue
        chords = [label for label, _ in path]
        xml = to_musicxml([v for _, v in path], chords, fifths, f"Harmonization in {key} major")
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "harmonized.musicxml"
            source.write_text(xml, encoding="utf-8")
            review = run_review(source, Path(tmp) / "out")
        findings = review["result"]["findings"]
        if any(f["severity"] == "error" for f in findings):
            continue
        plan = {"key": key, "bars": (total + 1) // 2, "chords": chords, "given": voice}
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


def _search(given, options, slot, fifths, rng, width, total=None):
    total = total or len(given)
    n = len(given)
    complete = n == total

    def cadence(i):
        return complete and i == total - 1
    # Label-level lookahead: keep only chords from which the grammar can still reach the cadence.
    def label_ok(i, label):
        if harmony_cost(i, label, total) is None:
            return False
        return not (i == total - 3 and label not in PREDOMINANT and label != CADENTIAL and label not in TONIC)
    reach = [set() for _ in range(n)]
    reach[n - 1] = {l for l in options[n - 1] if label_ok(n - 1, l)}
    for i in range(n - 2, -1, -1):
        reach[i] = {l for l in options[i] if label_ok(i, l) and (not complete or any(allowed(l, m) for m in reach[i + 1]))}
        if not complete:
            reach[i] = {l for l in options[i] if label_ok(i, l)}
    states = []
    for i in range(n):
        final = complete and i == total - 1
        states.append([(label, v) for label in sorted(reach[i])
                       for v in _voicings(label, fifths, final) if v[slot] == given[i]])
    # Voicing-level lookahead over the cadence (the last three chords): exact backward feasibility.
    if complete:
        for i in range(n - 2, max(-1, n - 4), -1):
            nxt = states[i + 1]
            states[i] = [(l, v) for l, v in states[i]
                         if any(allowed(l, m) and transition(v, w, l, m, fifths, cadence(i + 1), slot) is not None for m, w in nxt)]
    # Exact dynamic programming over (chord, voicing) states: the best path into every state.
    free = 3 if slot == 0 else 0
    best = {state: (harmony_cost(0, state[0], total) + rng.random() * 2, [state]) for state in states[0]}
    for i in range(1, n):
        nxt = {}
        for label, v in states[i]:
            hcost = harmony_cost(i, label, total)
            choice = None
            for (old_label, old), (cost, path) in best.items():
                if not allowed(old_label, label):
                    continue
                c = transition(old, v, old_label, label, fifths, cadence(i), slot)
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
    names = {v: k for k, v in KEYS.items()}
    if fifths not in names:
        raise ComposeError("Use a major key with up to four flats or four sharps.")
    if any(d != 2 for d in durations[:-1]) or durations[-1] not in (2, 4):
        raise ComposeError("Write the line in half notes with a final whole note (one chord per half note).")
    voice = "B" if sum(p.midi for p in pitches) / len(pitches) < 57 else "S"
    return pitches, names[fifths], voice
