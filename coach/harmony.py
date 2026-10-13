"""Conservative, spelling-aware identification of complete diatonic chords.

This describes the sounding vertical sonority, not its contextual function.
It never invents an absent root, third, fifth, or seventh.
"""
from .model import Pitch, STEPS, VOICES, scale


def vocabulary(fifths):
    alterations = scale(fifths)
    tonic = (4 * fifths) % 7
    names = [Pitch(STEPS[(tonic+i) % 7], alterations[STEPS[(tonic+i) % 7]], 4).name for i in range(7)]
    for degree, roman in enumerate(("I", "ii", "iii", "IV", "V", "vi", "vii")):
        for size in (3, 4):
            members = [names[(degree + 2*j) % 7] for j in range(size)]
            symbol = roman + ("°" if size == 3 else "ø") if degree == 6 else roman
            yield {"degree": degree+1, "symbol": symbol, "pitches": members, "size": size}


def identify(frame, fifths):
    names = {n.pitch.name for n in frame.values()}
    result = {"roman": "?", "status": "uncertain", "pitches": sorted(names),
              "reason": "Not a complete diatonic triad or seventh chord; contextual review is needed."}
    if set(frame) != set(VOICES):
        return {**result, "reason": "Four sounding voices are required for this analysis."}
    bass = min(frame.values(), key=lambda n: n.pitch.midi).pitch.name
    for chord in vocabulary(fifths):
        if set(chord["pitches"]) == names:
            inversion = chord["pitches"].index(bass)
            figures = ("", "6", "6/4") if chord["size"] == 3 else ("7", "6/5", "4/3", "4/2")
            return {**chord, "roman": chord["symbol"] + figures[inversion], "status": "identified",
                    "bass": bass, "inversion": inversion, "reason": "Exact match to the complete spelled pitch set."}
    return result


def analyze(score):
    events = []
    for time, frame in score.frames():
        mi = int(time // 4)
        if mi >= len(score.measures):
            continue
        chord = identify(frame, score.fifths)
        # Repeat at every measure, but only label changes inside a measure.
        if events and time % 4 and chord["roman"] == events[-1]["roman"] and chord["pitches"] == events[-1]["pitches"]:
            continue
        events.append({**chord, "measure": score.measures[mi], "beat": str(time % 4 + 1),
                       "offset": str(time), "anchor": frame["B"].id if "B" in frame else None})
    return events
