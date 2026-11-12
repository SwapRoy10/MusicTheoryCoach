"""Practice exercises the page lets students complete in the browser.

Each exercise is a small model the page edits directly: voices with fixed
rhythms, some given (the cantus firmus, or the soprano or bass of a chorale) and
some for the student to fill. Every exercise is generated from a composed
solution, so it is always solvable; the solution is included for "Show a solution".
"""
import random

from .compose_chorale import KEYS, compose_chorale, key_name
from .compose_species import MODES, compose_species

ORDINAL = {1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth"}
CENTER = {"S": 72, "A": 65, "T": 57, "B": 48}


def _clef(pitches):
    mean = sum(p.midi for p in pitches) / len(pitches)
    return "G" if mean >= 60 else "F"


def species_exercise(species=1, mode="dorian", above=True, seed=None):
    rng = random.Random(seed)
    _, exercise, analysis = compose_species(species, mode, above, seed=rng.random())
    cantus = [{"dur": float(e.dur), "pitch": str(e.pitch), "given": True} for e in exercise.cantus]
    counterpoint = []
    for e in exercise.counterpoint:
        event = {"dur": float(e.dur), "pitch": None, "tieFrom": bool(e.tie_from), "tieTo": bool(e.tie_to)}
        if e.pitch is None:
            event["rest"] = True
        counterpoint.append(event)
    solution = [str(e.pitch) if e.pitch else None for e in exercise.counterpoint]
    solution_events = [{"dur": float(e.dur), "pitch": str(e.pitch) if e.pitch else None, "tieFrom": bool(e.tie_from),
                        "tieTo": bool(e.tie_to), **({"rest": True} if e.pitch is None else {})} for e in exercise.counterpoint]
    rhythm = species == 5
    if rhythm:
        # Fifth species: the student writes the rhythm too. Start from half notes after the opening rest.
        bars = exercise.bars
        counterpoint = [{"dur": 2.0, "pitch": None, "rest": True}, {"dur": 2.0, "pitch": None}]
        for _ in range(1, bars - 1):
            counterpoint += [{"dur": 2.0, "pitch": None}, {"dur": 2.0, "pitch": None}]
        counterpoint.append({"dur": 4.0, "pitch": None})
    cp_pitches = [e.pitch for e in exercise.counterpoint if e.pitch]
    cf_pitches = [e.pitch for e in exercise.cantus]
    cp = {"id": "CP", "name": "Counterpoint", "given": False, "clef": _clef(cp_pitches), "events": counterpoint,
          "center": round(sum(p.midi for p in cp_pitches) / len(cp_pitches))}
    cf = {"id": "CF", "name": "Cantus firmus", "given": True, "clef": _clef(cf_pitches), "events": cantus,
          "center": round(sum(p.midi for p in cf_pitches) / len(cf_pitches))}
    side = "above" if above else "below"
    return {
        "kind": "species", "species": species, "above": above, "fifths": 0, "mode": "minor" if mode == "aeolian" else "major",
        "keyName": f"{exercise.final.name} {mode.capitalize()}",
        "title": f"{ORDINAL[species]} species {side} the cantus",
        "layout": "parts", "voices": [cp, cf] if above else [cf, cp],
        "solution": {"CP": solution}, "rhythmEditable": rhythm, "template": {"CP": [dict(e) for e in counterpoint]},
        **({"solutionEvents": {"CP": solution_events}} if rhythm else {}),
        "prompt": (f"Write a {ORDINAL[species].lower()}-species counterpoint {side} this cantus firmus in "
                   f"{exercise.final.name} {mode}. "
                   + ("Choose the rhythm as well as the pitches: number keys set durations (3 eighth, 4 quarter, "
                      "5 half, 6 whole, . dot) and T ties into the next note." if rhythm
                      else "The rhythm is given; choose the pitches.")),
    }


def chorale_exercise(key="C", bars=4, given="S", chromatic=False, seed=None, nonchord=False):
    """Given a melody or bass, write the other voices. With ``nonchord``, the student also chooses the
    rhythm, so passing tones, neighbors and suspensions can be written (the given line may have them too)."""
    if given not in ("S", "B"):
        raise ValueError("The given voice must be the soprano or the bass.")
    _, reviewed, plan = compose_chorale(key, bars, seed=seed, chromatic=chromatic, embellished=nonchord)
    score = reviewed["score"]
    voices = []
    solution, solution_events, template = {}, {}, {}
    slots = [2.0] * (2 * bars - 2) + [4.0]  # one chord per half note, then a whole note
    for v, name, clef in (("S", "Soprano", "G"), ("A", "Alto", "G"), ("T", "Tenor", "F"), ("B", "Bass", "F")):
        notes = sorted((n for n in score.notes if n.voice == v), key=lambda n: n.start)
        is_given = v == given
        events = [{"dur": float(n.duration), "pitch": str(n.pitch), "tieFrom": n.tied,
                   "tieTo": i + 1 < len(notes) and notes[i + 1].tied} for i, n in enumerate(notes)]
        if is_given:
            shown = [dict(e, given=True) for e in events]
        elif nonchord:
            shown = [{"dur": d, "pitch": None} for d in slots]
            template[v] = [dict(e) for e in shown]
            solution_events[v] = events
        else:
            shown = [{"dur": e["dur"], "pitch": None} for e in events]
        voices.append({"id": v, "name": name, "given": is_given, "clef": clef, "center": CENTER[v], "events": shown})
        if not is_given:
            solution[v] = [e["pitch"] for e in events]
    k = KEYS[key]
    line = {"S": "melody", "B": "bass line"}[given]
    rhythm = ("Choose the rhythm too, to add passing tones, neighbors and suspensions: number keys set durations "
              "(3 eighth, 4 quarter, 5 half, 6 whole, . dot) and T ties into the next note."
              if nonchord else "One chord per half note.")
    return {
        "kind": "chorale", "fifths": k.fifths, "mode": k.mode, "keyName": key_name(key), "key": key,
        "title": f"Chorale in {key_name(key)}: given {line}",
        "layout": "grand", "voices": voices, "solution": solution, "chords": plan["chords"],
        "rhythmEditable": nonchord, **({"solutionEvents": solution_events, "template": template} if nonchord else {}),
        "prompt": (f"Write the other three voices for this {line} in {key_name(key)}, ending with an authentic cadence. "
                   + rhythm),
    }


def new_exercise(options):
    kind = options.get("kind", "species")
    seed = options.get("seed")
    if kind == "species":
        mode = options.get("mode", "dorian")
        if mode not in MODES:
            raise ValueError(f"Mode must be one of {', '.join(MODES)}.")
        return species_exercise(int(options.get("species", 1)), mode, bool(options.get("above", True)), seed)
    return chorale_exercise(options.get("key", "C"), int(options.get("bars", 4)), options.get("given", "S"),
                            bool(options.get("chromatic")), seed, bool(options.get("nonchord")))
