"""Original synthetic exercises, CC0. Run from the repository root."""
from fractions import Fraction
from pathlib import Path
import json

from coach.model import Note, Pitch, Score, VOICES
from coach.musicxml import write


def example():
    chords = [("G4", "E4", "C4", "C3"), ("A4", "F4", "C4", "F3"),
              ("G4", "E4", "C4", "C3"), ("G4", "E4", "C4", "C3")]
    notes = []
    for vi, voice in enumerate(VOICES):
        for mi, chord in enumerate(chords):
            notes.append(Note(f"n{len(notes)+1}", voice, str(mi+1), mi,
                              Fraction(1), Fraction(4), Pitch.parse(chord[vi])))
    return Score(tuple(notes), ("1", "2", "3", "4"), 0)


if __name__ == "__main__":
    folder = Path(__file__).parent
    score = example()
    write(score, folder / "valid.musicxml")
    tenor = next(n for n in score.notes if n.voice == "T" and n.measure == "2")
    write(score.change(tenor.id, Pitch.parse("D4")), folder / "deliberate-errors.musicxml")
    assignment = {"instructions": "Keep the soprano and whole-note rhythm. End on tonic.",
                  "preserve_soprano": True, "require_tonic_ending": True,
                  "harmony": [{"measure": str(i+1), "beat": 1,
                               "pitches": ["F", "A", "C"] if i == 1 else ["C", "E", "G"],
                               "bass": "F" if i == 1 else "C"} for i in range(4)]}
    (folder / "assignment.json").write_text(json.dumps(assignment, indent=2) + "\n", encoding="utf-8")
