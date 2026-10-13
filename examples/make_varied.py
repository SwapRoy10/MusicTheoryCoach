"""A more informative CC0 classroom example: I, ii6, ii6/5, V, I."""
from fractions import Fraction
from pathlib import Path
import json
from coach.model import Note, Pitch, Score, VOICES
from coach.musicxml import write


def example():
    events = [
        ("1", 1, 4, ("G4", "E4", "C4", "C3")),
        ("2", 1, 2, ("A4", "F4", "D4", "F3")),
        ("2", 3, 2, ("A4", "D4", "C4", "F3")),
        ("3", 1, 4, ("G4", "D4", "B3", "G3")),
        ("4", 1, 4, ("G4", "E4", "C4", "C3")),
    ]
    notes = []
    for vi, voice in enumerate(VOICES):
        for measure, beat, duration, pitches in events:
            notes.append(Note(f"n{len(notes)+1}", voice, measure, int(measure)-1,
                              Fraction(beat), Fraction(duration), Pitch.parse(pitches[vi])))
    return Score(tuple(notes), ("1", "2", "3", "4"), 0)


if __name__ == "__main__":
    folder = Path(__file__).parent
    write(example(), folder / "varied-example.musicxml")
    (folder / "varied-assignment.json").write_text(json.dumps({
        "instructions": "Preserve the soprano and rhythm. Analyze the sounding chords; no chord progression is prescribed. End on tonic.",
        "preserve_soprano": True, "require_tonic_ending": True}, indent=2) + "\n", encoding="utf-8")
