"""Harmonizing a given line, and single-note fixes for findings."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))

from coach.compose_chorale import ComposeError  # noqa: E402
from coach.counterpoint import check_exercise, read_exercise  # noqa: E402
from coach.fixes import apply_pitch, chorale_fixes, species_fixes  # noqa: E402
from coach.harmonize import harmonize, parse_line, read_line  # noqa: E402
from coach.model import Pitch  # noqa: E402
from coach.review import run_review  # noqa: E402
import bridge  # noqa: E402

LINES = [
    ("E5 F5 G5 F5 E5 D5 C5", "S", "C"),
    ("G4 A4 B4 C5 D5 E5 C5 A4 G4 F#4 G4", "S", "G"),
    ("A4 Bb4 C5 A4 D5 C5 Bb4 A4 G4 E4 F4", "S", "F"),
    ("E5 D5 C5 B4 A4 G4 A4 B4 D5 C5 C5 B4 C5", "S", "C"),
    ("C3 D3 E3 F3 G3 G3 C3", "B", "C"),
    ("Eb3 F3 G3 Ab3 Bb2 Bb2 Eb3", "B", "Eb"),
    ("D3 E3 F#3 G3 A3 B3 G3 A3 D3", "B", "D"),
]


def errors(findings):
    return [f["rule"] for f in findings if f["severity"] == "error"]


class HarmonizeTests(unittest.TestCase):
    def test_lines_are_kept_and_settings_pass_review(self):
        for text, voice, key in LINES:
            with self.subTest(line=text):
                given = parse_line(text)
                _, reviewed, plan = harmonize(given, voice, key, seed=2)
                result = reviewed["result"]
                self.assertEqual(errors(result["findings"]), [])
                kept = [c["notes"][voice]["pitch"] for c in result["harmony"]]
                self.assertEqual(kept, [str(p) for p in given])
                self.assertEqual([c["roman"] for c in result["harmony"]], plan["chords"])
                self.assertIn(plan["chords"][-2], ("V", "V7"))
                self.assertEqual(plan["chords"][-1], "I")

    def test_explains_what_cannot_be_harmonized(self):
        with self.assertRaisesRegex(ComposeError, "tonic"):
            harmonize(parse_line("E5 F5 G5 F5 E5 D5 D5"), "S", "C")
        with self.assertRaisesRegex(ComposeError, "odd number"):
            harmonize(parse_line("E5 F5 G5 C5"), "S", "C")
        with self.assertRaisesRegex(ComposeError, "not in C major"):
            harmonize(parse_line("E5 F#5 G5 F5 E5 D5 C5"), "S", "C")
        with self.assertRaisesRegex(ComposeError, "range"):
            harmonize(parse_line("E6 F6 G6 F6 E6 D6 C6"), "S", "C")
        with self.assertRaisesRegex(ComposeError, "Write pitches like"):
            parse_line("E5 H5")

    def test_one_line_upload_is_harmonized(self):
        path = ROOT / "examples/harmonize/melody-in-g.musicxml"
        pitches, key, voice = read_line(path)
        self.assertEqual((key, voice, len(pitches)), ("G", "S", 11))
        reply = json.loads(bridge.review_upload(path.name, path.read_bytes()))
        self.assertTrue(reply["composed"])
        self.assertEqual(reply["plan"]["given"], "S")
        self.assertEqual(errors(reply["analysis"]["findings"]), [])


class FixTests(unittest.TestCase):
    def test_chorale_fix_clears_the_parallel_fifths(self):
        path = ROOT / "examples/deliberate-errors.musicxml"
        with tempfile.TemporaryDirectory() as folder:
            reviewed = run_review(path, folder)
            musicxml = reviewed["source"].read_text(encoding="utf-8")
        finding = next(f for f in reviewed["result"]["findings"] if f["rule"] == "parallel_fifth")
        options = chorale_fixes(reviewed["score"], reviewed["assignment"], finding)
        self.assertTrue(options)
        best = options[0]
        fixed = apply_pitch(musicxml, [best["note_id"]], Pitch.parse(best["after"]))
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "fixed.musicxml"
            source.write_text(fixed, encoding="utf-8")
            again = run_review(source, Path(folder) / "out")["result"]
        self.assertNotIn("parallel_fifth", errors(again["findings"]))
        self.assertLess(len(errors(again["findings"])), len(errors(reviewed["result"]["findings"])))

    def test_species_fixes_are_rechecked(self):
        exercise = read_exercise(ROOT / "examples/species/second-species-errors.musicxml")
        analysis = check_exercise(exercise)
        for finding in analysis["findings"]:
            if finding["severity"] != "error" or not finding["notes"]:
                continue
            for option in species_fixes(exercise, analysis["species"], finding):
                self.assertGreaterEqual(option["fixed_errors"], 1)
                self.assertIn(finding["rule"], option["removes"])

    def test_bridge_round_trip_and_undo(self):
        path = ROOT / "examples/deliberate-errors.musicxml"
        first = json.loads(bridge.review_upload(path.name, path.read_bytes()))
        index = next(i for i, f in enumerate(first["analysis"]["findings"]) if f["severity"] == "error")
        option = json.loads(bridge.fixes_for(index))["fixes"][0]
        fixed = json.loads(bridge.apply_fix(json.dumps([option["note_id"]]), option["after"]))
        self.assertLess(len(errors(fixed["analysis"]["findings"])), len(errors(first["analysis"]["findings"])))
        self.assertTrue(json.loads(bridge.restore(first["musicxml"]))["ok"])
        again = json.loads(bridge.fixes_for(index))["fixes"]
        self.assertEqual(again[0]["before"], option["before"])  # the original score is current again


if __name__ == "__main__":
    unittest.main()
