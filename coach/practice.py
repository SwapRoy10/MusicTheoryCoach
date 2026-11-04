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
        "solution": {"CP": solution},
        "prompt": (f"Write a {ORDINAL[species].lower()}-species counterpoint {side} this cantus firmus in "
                   f"{exercise.final.name} {mode}. The rhythm is given; choose the pitches."),
    }


def chorale_exercise(key="C", bars=4, given="S", chromatic=False, seed=None):
    if given not in ("S", "B"):
        raise ValueError("The given voice must be the soprano or the bass.")
    _, reviewed, plan = compose_chorale(key, bars, seed=seed, chromatic=chromatic)
    score = reviewed["score"]
    voices = []
    solution = {}
    for v, name, clef in (("S", "Soprano", "G"), ("A", "Alto", "G"), ("T", "Tenor", "F"), ("B", "Bass", "F")):
        notes = sorted((n for n in score.notes if n.voice == v), key=lambda n: n.start)
        is_given = v == given
        voices.append({"id": v, "name": name, "given": is_given, "clef": clef, "center": CENTER[v],
                       "events": [{"dur": float(n.duration), "pitch": str(n.pitch) if is_given else None,
                                   "given": is_given} for n in notes]})
        if not is_given:
            solution[v] = [str(n.pitch) for n in notes]
    k = KEYS[key]
    line = {"S": "melody", "B": "bass line"}[given]
    return {
        "kind": "chorale", "fifths": k.fifths, "mode": k.mode, "keyName": key_name(key), "key": key,
        "title": f"Chorale in {key_name(key)}: given {line}",
        "layout": "grand", "voices": voices, "solution": solution, "chords": plan["chords"],
        "prompt": (f"Write the other three voices for this {line} in {key_name(key)}: one chord per half note, "
                   "ending with an authentic cadence."),
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
                            bool(options.get("chromatic")), seed)
