from dataclasses import replace
from fractions import Fraction
from pathlib import Path
import contextlib
import io
import json
import tempfile
import unittest

from coach.model import Note, Pitch, Score, perfect
from coach.musicxml import read, write
from coach.checker import check, constraints_for, errors
from coach.repair import propose
from coach.cli import main
from examples.make_examples import example

ROOT = Path(__file__).resolve().parents[1]


def motion(s1, b1, s2, b2):
    notes = tuple(Note(str(i), v, "1", 0, Fraction(beat), Fraction(2), Pitch.parse(p))
                  for i, (v, beat, p) in enumerate((("S", 1, s1), ("B", 1, b1), ("S", 3, s2), ("B", 3, b2))))
    return Score(notes, ("1", "2", "3", "4"), 0)


def rules(score):
    return [f["rule"] for f in check(score, constraints_for(score))]


class IntervalTests(unittest.TestCase):
    def test_parallel_fifths_exact_evidence(self):
        score = motion("G4", "C3", "A4", "D3")
        finding = next(f for f in check(score, constraints_for(score)) if f["rule"] == "parallel_fifth")
        self.assertEqual((finding["measure"], finding["beat"], finding["voices"]), ("1", "3", ["S", "B"]))
        self.assertEqual([n["pitch"] for n in finding["notes"]], ["G4", "C3", "A4", "D3"])

    def test_octaves_and_unisons(self):
        for pitches in (("C5", "C3", "D5", "D3"), ("C4", "C4", "D4", "D4")):
            self.assertIn("parallel_octave", rules(motion(*pitches)))

    def test_stationary_contrary_and_oblique(self):
        for pitches in (("G4", "C3", "G4", "C3"), ("G4", "C3", "A4", "D2"),
                        ("G4", "C3", "G4", "C4")):
            self.assertFalse(any(r.startswith("parallel") for r in rules(motion(*pitches))))

    def test_compound_interval_changes(self):
        self.assertIn("parallel_fifth", rules(motion("G4", "C3", "A5", "D3")))

    def test_enharmonic_spelling_not_perfect(self):
        self.assertEqual(Pitch.parse("F##4").midi, Pitch.parse("G4").midi)
        self.assertIsNone(perfect(Pitch.parse("F##4"), Pitch.parse("C4")))
        self.assertIsNone(perfect(Pitch.parse("B#3"), Pitch.parse("C4")))

    def test_asynchronous_motion_is_not_parallel(self):
        score = motion("G4", "C3", "A4", "D3")
        notes = [n for n in score.notes if n.id != "3"]
        notes[1] = replace(notes[1], duration=Fraction(4))
        self.assertNotIn("parallel_fifth", rules(replace(score, notes=tuple(notes))))


class CheckerTests(unittest.TestCase):
    def setUp(self):
        self.score = example()
        raw = json.loads((ROOT / "examples/assignment.json").read_text())
        self.assignment = constraints_for(self.score, raw)

    def test_hand_checked_valid(self):
        self.assertEqual(check(self.score, self.assignment), [])

    def test_deliberate_errors_and_repair(self):
        score = read(ROOT / "examples/deliberate-errors.musicxml")
        findings = check(score, self.assignment)
        self.assertEqual(sorted(f["rule"] for f in errors(findings)),
                         ["chord_membership", "parallel_fifth", "parallel_fifth"])
        candidates = propose(score, self.assignment)
        self.assertTrue(candidates)
        repaired, details = candidates[0]
        self.assertEqual((details["voice"], details["measure"], details["before"], details["after"]),
                         ("T", "2", "D4", "C4"))
        self.assertEqual(errors(check(repaired, self.assignment)), [])
        self.assertEqual([n for n in repaired.notes if n.voice == "S"], [n for n in score.notes if n.voice == "S"])

    def test_crossing_spacing_range_and_overlap(self):
        note = next(n for n in self.score.notes if n.voice == "A" and n.measure == "2")
        detected = rules(self.score.change(note.id, Pitch.parse("C6")))
        for rule in ("crossing", "spacing", "range", "overlap"):
            self.assertIn(rule, detected)

    def test_bad_rhythm_gap_and_length(self):
        note = self.score.notes[0]
        score = replace(self.score, notes=(replace(note, duration=Fraction(1)),) + self.score.notes[1:])
        self.assertIn("rhythm", rules(score))
        self.assertIn("measure_duration", rules(score))
        self.assertIn("measure_count", rules(replace(self.score, measures=("1",))))

    def test_missing_voice_in_measure(self):
        score = replace(self.score, notes=self.score.notes[1:])
        self.assertIn("measure_duration", rules(score))

    def test_harmony_change_under_sustained_notes(self):
        assignment = constraints_for(self.score, {"harmony": [
            {"measure": "1", "beat": 1, "pitches": ["C", "E", "G"], "bass": "C"},
            {"measure": "1", "beat": 3, "pitches": ["F", "A", "C"], "bass": "F"}]})
        findings = check(self.score, assignment)
        self.assertTrue(any(f["rule"] == "chord_membership" and f["measure"] == "1" and f["beat"] == "3" for f in findings))

    def test_contextual_advice_is_not_error(self):
        score = motion("B4", "G2", "D5", "G3")
        findings = check(score, constraints_for(score))
        self.assertTrue(any(f["rule"] == "leading_tone" and f["severity"] == "suggestion" for f in findings))
        score = motion("C5", "E3", "G5", "C4")
        self.assertIn("direct_outer_interval", rules(score))

    def test_half_note_timeline(self):
        notes = []
        for n in self.score.notes:
            notes.extend((replace(n, duration=Fraction(2)), replace(n, id=n.id + "b", beat=Fraction(3), duration=Fraction(2))))
        score = replace(self.score, notes=tuple(notes))
        self.assertEqual(check(score, self.assignment), [])
        self.assertEqual([t for t, _ in score.frames()], list(range(0, 16, 2)))

    def test_supplied_inversion(self):
        bass = next(n for n in self.score.notes if n.voice == "B" and n.measure == "1")
        score = self.score.change(bass.id, Pitch.parse("E3"))
        self.assertIn("inversion", [f["rule"] for f in check(score, self.assignment)])

    def test_unresolved_ending_allowed_when_requested(self):
        score = replace(self.score, notes=tuple(replace(n, pitch=Pitch.parse({"S":"G4", "A":"D4", "T":"B3", "B":"G2"}[n.voice]))
                                                if n.measure == "4" else n for n in self.score.notes))
        self.assertNotIn("tonic_ending", rules(score))
        assignment = constraints_for(score, {"require_tonic_ending": True})
        self.assertIn("tonic_ending", [f["rule"] for f in check(score, assignment)])

    def test_constraint_validation(self):
        for raw in ({"unknown": 1}, {"preserve_soprano": "false"}, {"harmony": "I"}, {"harmony": [{"measure": 1}]}):
            with self.assertRaises(ValueError):
                constraints_for(self.score, raw)

    def test_no_unsupported_validity_claim(self):
        score = replace(self.score, notes=tuple(replace(n, duration=Fraction(1)) for n in self.score.notes))
        self.assertEqual(propose(score, self.assignment), [])


class MusicXMLTests(unittest.TestCase):
    def transform(self, source, transform, voice_map=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.musicxml"
            path.write_text(transform(source), encoding="utf-8")
            return read(path, voice_map)

    def test_round_trip(self):
        score = example()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.musicxml"
            write(score, path)
            parsed = read(path)
            self.assertEqual(score, parsed)

    def test_spelling_preserved(self):
        score = example().change("n1", Pitch.parse("F#4"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.xml"
            write(score, path)
            self.assertEqual(str(read(path).notes[0].pitch), "F#4")

    def test_divisions_and_namespaces(self):
        source = (ROOT / "examples/valid.musicxml").read_text()
        parsed = self.transform(source, lambda s: s.replace('<score-partwise version="4.0">', '<score-partwise xmlns="urn:test" version="4.0">')
                                .replace("<divisions>1</divisions>", "<divisions>8</divisions>")
                                .replace("<duration>4</duration>", "<duration>32</duration>"))
        self.assertEqual(parsed, example())

    def test_backup_and_explicit_voice_map(self):
        import xml.etree.ElementTree as ET
        root = ET.parse(ROOT / "examples/valid.musicxml").getroot()
        parts = root.findall("part")
        first = parts[0]
        first.set("id", "Choir")
        for mi, measure in enumerate(first.findall("measure")):
            for vi, part in enumerate(parts[1:], 2):
                backup = ET.SubElement(measure, "backup")
                ET.SubElement(backup, "duration").text = "4"
                note = part.findall("measure")[mi].find("note")
                note.find("voice").text = str(vi)
                measure.append(note)
        for part in parts[1:]:
            root.remove(part)
        parsed = self.transform(ET.tostring(root, encoding="unicode"), lambda s: s,
                                {"Choir:1":"S", "Choir:2":"A", "Choir:3":"T", "Choir:4":"B"})
        self.assertEqual(len(parsed.notes), 16)
        self.assertEqual(errors(check(parsed, constraints_for(parsed))), [])

    def test_unsupported_notation_rejected(self):
        source = (ROOT / "examples/valid.musicxml").read_text()
        for tag in ("rest", "tie", "grace", "chord", "time-modification"):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                self.transform(source, lambda s: s.replace("<note>", f"<note><{tag}/>", 1))

    def test_key_change_and_bad_backup_rejected(self):
        source = (ROOT / "examples/valid.musicxml").read_text()
        with self.assertRaises(ValueError):
            self.transform(source, lambda s: s.replace("<fifths>0</fifths>", "<fifths>1</fifths>", 1))
        with self.assertRaises(ValueError):
            self.transform(source, lambda s: s.replace("<note>", "<backup><duration>4</duration></backup><note>", 1))

    def test_cli_artifacts_and_exported_repair(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            out = Path(directory) / "report"
            args = [str(ROOT / "examples/deliberate-errors.musicxml"), "--assignment", str(ROOT / "examples/assignment.json"), "--out", str(out)]
            self.assertEqual(main(args), 0)
            report = json.loads((out / "analysis.json").read_text())
            self.assertTrue(report["repairs"])
            score = read(out / "repair-1.musicxml")
            assignment = constraints_for(score, json.loads((ROOT / "examples/assignment.json").read_text()))
            self.assertEqual(errors(check(score, assignment)), [])
            self.assertTrue((out / "teaching-packet.json").exists())
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args), 2)


if __name__ == "__main__":
    unittest.main()
