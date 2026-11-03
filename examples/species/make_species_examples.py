"""Write the species counterpoint examples the web page offers.

    python examples/species/make_species_examples.py
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from coach.counterpoint import check_exercise, exercise_from_text, write_exercise

HERE = Path(__file__).parent
CANTUS = "D4 F4 E4 D4 G4 F4 A4 G4 F4 E4 D4"  # Fux's Dorian cantus firmus

EXAMPLES = {
    # Fux, Gradus ad Parnassum (1725), first species above the Dorian cantus.
    "first-species-fux.musicxml": ("First species above the cantus (Fux)",
                                   "A4|A4|G4|A4|B4|C5|C5|B4|D5|C#5|D5", True, 0),
    # Two deliberate mistakes: octaves on consecutive downbeats (bars 3-4) and a
    # weak-beat dissonance approached by leap (bar 7).
    "second-species-errors.musicxml": ("Second species with mistakes",
                                       "r/2 A4/2|D5/2 C5/2|E5/2 G5/2|D5/2 F5/2|E5/2 D5/2|F5/2 D5/2|C5/2 G4/2|B4/2 C5/2|D5/2 A4/2|B4/2 C#5/2|D5",
                                       True, None),
}

for name, (title, counterpoint, above, expected) in EXAMPLES.items():
    exercise = exercise_from_text(CANTUS, counterpoint, 0, above)
    errors = sum(f["severity"] == "error" for f in check_exercise(exercise)["findings"])
    if expected is not None:
        assert errors == expected, (name, errors)
    (HERE / name).write_text(write_exercise(exercise, title=title), encoding="utf-8")
    print(name, errors, "errors")
