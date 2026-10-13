"""Bounded, single-note repair search. No validity claims beyond checked rules."""
from .checker import check, errors
from .model import Pitch, RANGES, scale
from .harmony import analyze


def propose(score, assignment, limit=2):
    original = check(score, assignment)
    if not errors(original):
        return []
    implicated = {n["id"] for f in errors(original) for n in f["notes"]}
    candidates = []
    identified_before = {c["offset"] for c in analyze(score) if c["status"] == "identified"}
    for note in score.notes:
        if note.id not in implicated or (assignment["preserve_soprano"] and note.voice == "S"):
            continue
        low, high = RANGES[note.voice]
        for octave in range(2, 6):
            for step, alter in scale(score.fifths).items():
                pitch = Pitch(step, alter, octave)
                if pitch == note.pitch or not low <= pitch.midi <= high or abs(pitch.midi - note.pitch.midi) > 12:
                    continue
                candidate = score.change(note.id, pitch)
                findings = check(candidate, assignment)
                if errors(findings):
                    continue
                candidate_harmony = analyze(candidate)
                if any(c["status"] == "uncertain" and c["offset"] in identified_before for c in candidate_harmony):
                    continue
                suggestions = sum(f["severity"] == "suggestion" for f in findings)
                candidates.append((suggestions, abs(pitch.midi - note.pitch.midi), note.id, str(pitch),
                                   candidate, {"note_id": note.id, "voice": note.voice,
                                               "measure": note.measure, "beat": str(note.beat),
                                               "before": str(note.pitch), "after": str(pitch),
                                               "harmony": candidate_harmony,
                                               "remaining_findings": findings}))
    candidates.sort(key=lambda c: c[:4])
    return [(c[4], c[5]) for c in candidates[:limit]]
