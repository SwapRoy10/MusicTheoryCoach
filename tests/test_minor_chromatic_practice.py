"""Minor keys, chromatic chords, and the practice exercises."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))

from coach.compose_chorale import KEYS, Key, compose_chorale, to_musicxml  # noqa: E402
from coach.harmonize import harmonize, parse_line  # noqa: E402
from coach.harmony import identify, vocabulary  # noqa: E402
from coach.model import Note, Pitch  # noqa: E402
from coach.practice import new_exercise  # noqa: E402
from coach.review import canonical_label, run_review  # noqa: E402


def frame(*names):
    return {v: Note(f"x{v}", v, "1", 0, 1, 2, Pitch.parse(p)) for v, p in zip("SATB", names)}


def review(chords, fifths, mode):
    voicings = [tuple(Pitch.parse(p) for p in c.split()) for c in chords]
    xml = to_musicxml(voicings, [None] * len(chords), fifths, "test", mode)
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "t.musicxml"
        path.write_text(xml, encoding="utf-8")
        return run_review(path, Path(folder) / "out")["result"]


def errors(findings):
    return [f["rule"] for f in findings if f["severity"] == "error"]


class IdentifyTests(unittest.TestCase):
    def test_minor_vocabulary_uses_the_raised_leading_tone(self):
        romans = {c["symbol"] + ("7" if c["size"] == 4 else ""): c["pitches"] for c in vocabulary(0, "minor") if c["kind"] == "diatonic"}
        self.assertEqual(romans["V"], ["E", "G#", "B"])
        self.assertEqual(romans["vii°7"], ["G#", "B", "D", "F"])
        self.assertEqual(romans["III"], ["C", "E", "G"])

    def test_chromatic_chords(self):
        cases = [
            ((0, "major"), ("D5", "C5", "A4", "F#3"), "V6/5/V"),
            ((0, "major"), ("Eb5", "C5", "A4", "F#3"), "vii°7/V"),
            ((0, "major"), ("F5", "Ab4", "Db4", "F3"), "N6"),
            ((0, "major"), ("F#5", "C5", "Eb4", "Ab2"), "Ger+6"),
            ((0, "major"), ("F#5", "D5", "C4", "Ab2"), "Fr+6"),
            ((0, "major"), ("F#5", "C5", "C4", "Ab2"), "It+6"),
            ((0, "major"), ("Eb5", "C5", "Ab4", "Ab2"), "bVI"),
            ((0, "major"), ("D5", "Ab4", "F4", "F3"), "ii°6"),
            ((0, "minor"), ("E5", "C#5", "A4", "A3"), "I"),
            ((-3, "minor"), ("D5", "Ab4", "F4", "B2"), "vii°7"),
            ((-3, "minor"), ("Ab4", "F4", "Db4", "F3"), "N6"),
        ]
        for (fifths, mode), names, expected in cases:
            with self.subTest(expected=expected, mode=mode):
                self.assertEqual(identify(frame(*names), fifths, mode)["roman"], expected)

    def test_written_numerals_are_normalized(self):
        for written, canonical in [("V65/V", "V6/5/V"), ("viio7/V", "vii°7/V"), ("Ger65", "Ger+6"), ("It6", "It+6"),
                                   ("N6", "N6"), ("♭VI", "bVI"), ("i64", "i6/4")]:
            self.assertEqual(canonical_label(written), canonical)


class MinorReviewTests(unittest.TestCase):
    def test_minor_progression_with_neapolitan_and_german_sixth(self):
        result = review(["E5 C5 A4 A3", "F5 D5 Bb4 D3", "E5 B4 G#4 E3", "E5 C5 A4 A3", "D#5 C5 A4 F3",
                         "E5 C5 A4 E3", "D5 B4 G#4 E3", "D5 B4 G#4 E3", "C5 A4 E4 A2"], 0, "minor")
        self.assertEqual(result["score"]["mode"], "minor")
        self.assertEqual([c["roman"] for c in result["harmony"]],
                         ["i", "N6", "V", "i", "Ger+6", "i6/4", "V7", "V7", "i"])
        self.assertNotIn("diatonic", errors(result["findings"]))  # G#, Bb and D# belong to recognized chords

    def test_applied_leading_tone_that_falls_is_noted(self):
        result = review(["E5 C5 G4 C3", "D5 C5 A4 F#3", "D5 B4 G4 F3", "E5 C5 G4 C3", "D5 B4 G4 G3", "E5 C5 G4 G3",
                         "D5 B4 G4 G3", "D5 B4 F4 G3", "C5 C5 E4 C3"], 0, "major")
        self.assertIn("applied_resolution", [f["rule"] for f in result["findings"]])

    def test_minor_is_inferred_from_the_final_bass(self):
        result = review(["C5 A4 E4 A2", "B4 G#4 E4 E3", "C5 A4 E4 A3", "B4 G#4 E4 E3", "C5 A4 E4 A2"], 0, "")
        self.assertEqual(result["score"]["mode"], "minor")


class ComposerTests(unittest.TestCase):
    def test_minor_and_chromatic_chorales_pass_review(self):
        for key in ("Am", "Cm", "F#m", "Bb", "E"):
            for chromatic in (False, True):
                with self.subTest(key=key, chromatic=chromatic):
                    _, reviewed, plan = compose_chorale(key, 5, seed=4, chromatic=chromatic)
                    self.assertEqual(errors(reviewed["result"]["findings"]), [])
                    self.assertEqual(reviewed["result"]["score"]["mode"], KEYS[key].mode)
                    if chromatic:
                        kinds = {identify_kind(c, KEYS[key]) for c in plan["chords"]}
                        self.assertTrue(kinds & {"applied", "mixture", "neapolitan", "aug6"}, plan["chords"])

    def test_harmonizer_handles_minor_and_chromatic_notes(self):
        cases = [("C5 B4 C5 D5 E5 D5 C5 B4 A4 G#4 A4", "S", "Am"), ("A2 B2 C3 D3 E3 E3 A2", "B", "Am"),
                 ("E5 F#5 G5 F5 E5 D5 C5", "S", "C"), ("C5 C#5 D5 B4 C5 D5 C5", "S", "C")]
        for text, voice, key in cases:
            with self.subTest(line=text):
                _, reviewed, plan = harmonize(parse_line(text), voice, key, seed=3)
                self.assertEqual(errors(reviewed["result"]["findings"]), [])
                kept = [c["notes"][voice]["pitch"] for c in reviewed["result"]["harmony"]]
                self.assertEqual(kept, text.split())


def identify_kind(label, key):
    from coach.compose_chorale import chord_info
    return chord_info(label, key)["kind"]


class PracticeTests(unittest.TestCase):
    def test_species_exercise(self):
        ex = new_exercise({"kind": "species", "species": 3, "above": False, "mode": "aeolian", "seed": 5})
        cp = next(v for v in ex["voices"] if v["id"] == "CP")
        cf = next(v for v in ex["voices"] if v["id"] == "CF")
        self.assertTrue(cf["given"] and not cp["given"])
        self.assertTrue(all(e["pitch"] for e in cf["events"]))
        self.assertTrue(all(e["pitch"] is None for e in cp["events"]))
        self.assertEqual(len(ex["solution"]["CP"]), len(cp["events"]))
        self.assertEqual(ex["voices"][0]["id"], "CF")  # the upper voice comes first

    def test_chorale_exercise(self):
        ex = new_exercise({"kind": "chorale", "key": "Gm", "bars": 4, "given": "S", "seed": 2})
        self.assertEqual((ex["mode"], ex["fifths"]), ("minor", -2))
        given = [v for v in ex["voices"] if v["given"]]
        self.assertEqual([v["id"] for v in given], ["S"])
        self.assertEqual(set(ex["solution"]), {"A", "T", "B"})
        for v in ex["voices"]:
            self.assertEqual(sum(e["dur"] for e in v["events"]), 16)


if __name__ == "__main__":
    unittest.main()


class RareChordTests(unittest.TestCase):
    def test_augmented_triads_and_ninths(self):
        cases = [((0, "major"), ("D#5", "B4", "G4", "G3"), "V+"), ((0, "major"), ("G#4", "E4", "C4", "C3"), "I+"),
                 ((0, "major"), ("F5", "D#5", "B4", "G3"), "V+7"), ((0, "major"), ("A4", "F4", "B3", "G2"), "V9"),
                 ((0, "minor"), ("G#4", "E4", "C4", "C3"), "III+"), ((0, "minor"), ("F5", "D5", "G#4", "E3"), "V9"),
                 ((0, "major"), ("Ab4", "F#4", "C4", "C3"), "It+6")]
        for (fifths, mode), names, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(identify(frame(*names), fifths, mode)["roman"], expected)

    def test_six_four_kinds_and_common_tone_seventh(self):
        result = review(["E5 G4 G3 C3", "D#5 F#4 A3 C3", "E5 G4 G3 C3", "F5 A4 C4 C3", "E5 G4 C4 C3",
                         "D5 G4 B3 D3", "E5 G4 C4 E3", "D5 F4 A3 F3", "C5 E4 C4 G2", "B4 D4 G3 G2", "C5 E4 G3 C3"],
                        0, "major")
        romans = [c["roman"] for c in result["harmony"]]
        self.assertEqual(romans[:3], ["I", "ct°7", "I"])
        kinds = {c["roman"]: c.get("six_four") for c in result["harmony"] if "six_four" in c}
        self.assertEqual(kinds, {"IV6/4": "pedal", "V6/4": "passing", "I6/4": "cadential"})
        self.assertNotIn("applied_resolution", [f["rule"] for f in result["findings"]])
        self.assertNotIn("six_four", [f["rule"] for f in result["findings"]])

    def test_unexplained_six_four_is_noted(self):
        result = review(["E5 C5 G4 C3", "F5 C5 A4 C3", "D5 B4 G4 G3", "E5 C5 G4 C3", "C5 G4 E4 C3"], 0, "major")
        self.assertIn("six_four", [f["rule"] for f in result["findings"]])

    def test_composer_uses_tonicizations_and_picardy(self):
        seen = set()
        for seed in range(12):
            _, reviewed, plan = compose_chorale("C", 7, seed=seed, chromatic=True)
            self.assertEqual(errors(reviewed["result"]["findings"]), [])
            seen |= {e["figure"] for e in plan["expansions"]}
        self.assertTrue(seen & {"tii", "tIV", "tvi", "tV", "ct"}, seen)
        _, reviewed, plan = compose_chorale("Cm", 5, seed=1, picardy=True)
        self.assertEqual(plan["chords"][-1], "I")
        self.assertEqual(errors(reviewed["result"]["findings"]), [])

    def test_harmonizer_pedal_six_four_and_augmented_dominant(self):
        _, reviewed, plan = harmonize(parse_line("C3 C3 C3 F3 G3 G3 C3"), "B", "C", seed=3)
        self.assertIn("IV6/4", plan["chords"])
        self.assertEqual(errors(reviewed["result"]["findings"]), [])
        _, reviewed, plan = harmonize(parse_line("C5 B4 C5 D5 E5 D5 C5 B4 A4 G#4 A4"), "S", "Am", seed=3, picardy=True)
        self.assertEqual(plan["chords"][-1], "I")

    def test_fifth_species_practice_lets_students_write_rhythm(self):
        ex = new_exercise({"kind": "species", "species": 5, "seed": 3})
        self.assertTrue(ex["rhythmEditable"])
        cp = next(v for v in ex["voices"] if v["id"] == "CP")
        self.assertEqual(sum(e["dur"] for e in cp["events"]), 4 * len(next(v for v in ex["voices"] if v["id"] == "CF")["events"]))
        self.assertTrue(cp["events"][0].get("rest"))
        self.assertEqual(sum(e["dur"] for e in ex["solutionEvents"]["CP"]), sum(e["dur"] for e in cp["events"]))
