from dataclasses import replace
from fractions import Fraction
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from coach.model import Note, Pitch, Score, VOICES
from coach.harmony import identify, analyze
from coach.checker import check, constraints_for, errors
from coach.repair import propose
from coach.pdf_export import annotated_xml
from coach.musicxml import write, read
from examples.make_varied import example


def frame(pitches):
    return {voice: Note(voice, voice, "1", 0, Fraction(1), Fraction(4), Pitch.parse(pitch))
            for voice, pitch in zip(VOICES, pitches)}


class HarmonyTests(unittest.TestCase):
    def test_actual_measure_two_is_ii6_not_seventh(self):
        chord = identify(frame(("A4", "F4", "D4", "F3")), 0)
        self.assertEqual(chord["roman"], "ii6")
        self.assertEqual(chord["pitches"], ["D", "F", "A"])

    def test_seventh_requires_all_four_members_and_tracks_inversion(self):
        for pitches, expected in [(("A4", "F4", "C4", "D3"), "ii7"),
                                  (("A4", "D4", "C4", "F3"), "ii6/5"),
                                  (("F4", "D4", "C4", "A2"), "ii4/3"),
                                  (("A4", "F4", "D4", "C3"), "ii4/2")]:
            self.assertEqual(identify(frame(pitches), 0)["roman"], expected)

    def test_quality_and_spelling(self):
        cases = [(("B4", "G4", "D4", "G3"), 0, "V"),
                 (("F4", "D4", "B3", "B2"), 0, "vii°"),
                 (("A4", "F4", "D4", "B2"), 0, "viiø7"),
                 (("A4", "F#4", "D4", "D3"), 1, "V"),
                 (("G4", "Eb4", "C4", "C3"), -1, "v"),
                 (("G4", "E4", "B3", "C3"), 0, "I7")]
        # C-Eb-G is chromatic in F major: do not invent a diatonic numeral.
        for pitches, key, expected in cases:
            actual = identify(frame(pitches), key)
            self.assertEqual(actual["roman"], "?" if expected == "v" else expected)
        self.assertEqual(identify(frame(("G4", "E4", "C4", "B#2")), 0)["roman"], "?")

    def test_ambiguous_or_incomplete_sonorities_not_guessed(self):
        for pitches in (("G4", "C4", "C4", "C3"), ("A4", "E4", "D4", "C3")):
            self.assertEqual(identify(frame(pitches), 0)["status"], "uncertain")

    def test_bass_is_lowest_sounding_pitch_even_if_voices_cross(self):
        self.assertEqual(identify(frame(("G4", "C4", "E2", "C3")), 0)["roman"], "I6")

    def test_varied_example_and_verified_repair(self):
        score = example()
        self.assertEqual([c["roman"] for c in analyze(score)], ["I", "ii6", "ii6/5", "V", "I"])
        self.assertNotEqual([n.pitch for n in score.notes if n.measure == "3"],
                            [n.pitch for n in score.notes if n.measure == "1"])
        assignment = constraints_for(score, {"require_tonic_ending": True})
        findings = check(score, assignment)
        self.assertEqual([f["rule"] for f in errors(findings)], ["parallel_fifth"])
        self.assertNotIn("seventh_resolution", [f["rule"] for f in findings])
        candidate, details = propose(score, assignment)[0]
        self.assertEqual((details["measure"], details["before"], details["after"]), ("2", "D4", "C4"))
        self.assertEqual([c["roman"] for c in analyze(candidate)], ["I", "IV", "ii6/5", "V", "I"])
        self.assertEqual(errors(check(candidate, assignment)), [])

    def test_assignment_mismatch_is_not_a_general_harmonic_error(self):
        score = example()
        free = check(score, constraints_for(score))
        self.assertNotIn("chord_membership", [f["rule"] for f in free])
        assignment = constraints_for(score, {"harmony": [
            {"measure": "1", "beat": 1, "pitches": ["C", "E", "G"], "bass": "C"},
            {"measure": "2", "beat": 1, "pitches": ["F", "A", "C"], "bass": "F"}]})
        finding = next(f for f in check(score, assignment) if f["rule"] == "chord_membership")
        self.assertIn("Assignment mismatch", finding["message"])
        self.assertIn("ii6", finding["message"])

    def test_supplied_seventh_and_resolution_warning(self):
        score = example()
        seventh = next(n for n in score.notes if n.voice == "T" and n.measure == "2" and n.beat == 3)
        next_note = next(n for n in score.notes if n.voice == "T" and n.measure == "3")
        altered = score.change(next_note.id, Pitch.parse("D4"))
        self.assertIn("seventh_resolution", [f["rule"] for f in check(altered, constraints_for(altered))])
        assignment = constraints_for(score, {"harmony": [
            {"measure": "1", "beat": 1, "pitches": ["D", "F", "A", "C"], "bass": "F"}]})
        self.assertEqual(len(assignment["harmony"][0]["pitches"]), 4)

    def test_pdf_numerals_follow_repaired_notes_and_preserve_source(self):
        score = example()
        repair = propose(score, constraints_for(score))[0][1]
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / "source.xml", Path(folder) / "target.xml"
            write(score, source)
            annotated_xml(source, target, [], score=score)
            self.assertEqual(read(target), score)
            labels = ET.parse(target).getroot().findall(".//direction[@placement='below']/direction-type/words")
            self.assertEqual([w.text for w in labels], ["I", "ii6", "ii65", "V", "I"])
            self.assertTrue(all(w.get("font-family") == "Campania" for w in labels))
            annotated_xml(source, target, [], repair, score=score)
            labels = ET.parse(target).getroot().findall(".//direction[@placement='below']/direction-type/words")
            self.assertEqual([w.text for w in labels], ["I", "IV", "ii65", "V", "I"])

    def test_change_over_held_bass_gets_correct_offset(self):
        score = example()
        bass = [n for n in score.notes if n.voice == "B" and n.measure == "2"]
        score = replace(score, notes=tuple(replace(n, duration=Fraction(4)) if n.id == bass[0].id else n
                                          for n in score.notes if n.id != bass[1].id))
        # Re-import to regenerate sequential source IDs after removing a note.
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / "source.xml", Path(folder) / "target.xml"
            write(score, source)
            score = read(source)
            annotated_xml(source, target, [], score=score)
            direction = next(d for d in ET.parse(target).getroot().findall(".//direction")
                             if d.findtext("direction-type/words") == "ii65")
            self.assertEqual(direction.findtext("offset"), "2")


if __name__ == "__main__":
    unittest.main()
