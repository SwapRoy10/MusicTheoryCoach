"""Free rhythm, ties and nonchord tones in four-voice chorales."""
from fractions import Fraction
from pathlib import Path
import random
import tempfile
import unittest

from coach.compose_chorale import compose_chorale, embellish, voices_to_musicxml, KEYS
from coach.harmonize import harmonize, parse_line
from coach.model import Pitch
from coach.practice import new_exercise
from coach.review import run_review
from coach.score_import import read_ranked

ROOT = Path(__file__).resolve().parents[1]


def lines(**voices):
    out = {}
    for v, spec in voices.items():
        events = []
        for token in spec.split():
            tie = token.endswith("~")
            pitch, dur = token.rstrip("~").split("/")
            events.append((Fraction(dur), Pitch.parse(pitch), tie))
        out[v] = events
    return out


def review(voices, fifths=0, mode="major"):
    xml = voices_to_musicxml(voices, fifths, "test", mode)
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "t.musicxml"
        path.write_text(xml, encoding="utf-8")
        return run_review(path, Path(folder) / "out")["result"]


def errors(findings):
    return [f["rule"] for f in findings if f["severity"] == "error"]


class ImportTests(unittest.TestCase):
    def test_voice_layers_keep_their_rhythms_and_ties(self):
        xml = voices_to_musicxml(lines(S="E5/1 D5/1 C5/2~ C5/1 B4/1 C5/2", A="G4/2 E4/2 G4/2 G4/2",
                                       T="C4/2 C4/2 D4/2 E4/2", B="C3/2 A2/2 G2/2 C3/2"), 0, "t")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "t.musicxml"
            path.write_text(xml, encoding="utf-8")
            score, _, scope = read_ranked(path)
        soprano = sorted((n for n in score.notes if n.voice == "S"), key=lambda n: n.start)
        self.assertEqual([str(n.pitch) for n in soprano], ["E5", "D5", "C5", "C5", "B4", "C5"])
        self.assertEqual([n.tied for n in soprano], [False, False, False, True, False, False])
        self.assertFalse(score.homophonic)
        self.assertIn("voice layers", scope["voice_assignment"])


class NonchordToneTests(unittest.TestCase):
    def test_passing_tone_suspension_and_neighbor(self):
        result = review(lines(S="E5/1 D5/1 C5/2~ C5/1 B4/1 C5/2 B4/2 C5/2",
                              A="G4/2 E4/2 G4/2 G4/1 A4/1 G4/2 G4/2",
                              T="C4/2 C4/2 D4/2 E4/2 D4/2 E4/2",
                              B="C3/2 A2/2 G2/2 C3/2 G2/2 C3/2"))
        labels = {(n["measure"], n["beat"], n["voice"]): n["label"] for n in result["nonchord_tones"]}
        self.assertEqual(labels[("1", "2", "S")], "PT")
        self.assertEqual(labels[("2", "1", "S")], "4-3")
        self.assertEqual(labels[("2", "4", "A")], "NT")
        self.assertEqual([c["roman"] for c in result["harmony"]], ["I", "vi", "V", "I", "V", "I"])
        self.assertNotIn("nonchord_tone", errors(result["findings"]))

    def test_unexplained_dissonance(self):
        result = review(lines(S="G5/1 D5/1 C5/2 B4/2 C5/2", A="G4/2 E4/2 G4/2 G4/2",
                              T="C4/2 C4/2 D4/2 E4/2", B="C3/2 A2/2 G2/2 C3/2"))
        self.assertIn("nonchord_tone", errors(result["findings"]))  # D5: leapt to, then continuing down (not an appoggiatura)

    def test_escape_tone(self):
        result = review(lines(S="E5/1 F5/1 C5/2 B4/2 C5/2", A="G4/2 E4/2 G4/2 G4/2",
                              T="C4/2 C4/2 D4/2 E4/2", B="C3/2 A2/2 G2/2 C3/2"))
        self.assertEqual(result["nonchord_tones"][0]["type"], "ET")

    def test_passing_tone_that_spells_a_chord_is_still_a_passing_tone(self):
        # The alto's passing F makes a momentary "ii" sonority over the held bass; it is a passing tone in I.
        result = review(lines(S="E5/2 D5/2 C5/4", A="G4/1 F4/1 G4/2 E4/4", T="C4/2 B3/2 G3/4", B="C3/2 G2/2 C3/4"))
        self.assertEqual([c["roman"] for c in result["harmony"]], ["I", "V", "I"])


class ComposerTests(unittest.TestCase):
    def test_embellished_chorales_keep_their_chords(self):
        types = set()
        for seed in range(8):
            _, reviewed, plan = compose_chorale(["G", "Cm", "F", "Em"][seed % 4], 6, seed=seed, embellished=True)
            result = reviewed["result"]
            self.assertEqual(errors(result["findings"]), [])
            self.assertEqual([c["roman"] for c in result["harmony"]], plan["chords"])
            types |= {n["type"] for n in result["nonchord_tones"]}
        self.assertTrue({"PT", "S"} <= types, types)

    def test_harmonizer_embellishes_only_the_other_voices(self):
        text = "E5 F5 G5 F5 E5 D5 C5"
        _, reviewed, plan = harmonize(parse_line(text), "S", "C", seed=2, embellished=True)
        result = reviewed["result"]
        soprano = [n["pitch"] for n in result["score"]["notes"] if n["voice"] == "S"]
        self.assertEqual(soprano, text.split())
        self.assertEqual(errors(result["findings"]), [])

    def test_example_file(self):
        with tempfile.TemporaryDirectory() as folder:
            result = run_review(ROOT / "examples/nonchord/chorale-with-nonchord-tones.musicxml", folder)["result"]
        self.assertEqual(errors(result["findings"]), [])
        self.assertGreaterEqual(len(result["nonchord_tones"]), 5)


class PracticeTests(unittest.TestCase):
    def test_nonchord_practice_lets_students_choose_rhythm(self):
        ex = new_exercise({"kind": "chorale", "key": "F", "bars": 4, "given": "S", "nonchord": True, "seed": 3})
        self.assertTrue(ex["rhythmEditable"])
        for v in ex["voices"]:
            self.assertEqual(sum(e["dur"] for e in v["events"]), 16)
            if not v["given"]:
                self.assertEqual(sum(e["dur"] for e in ex["solutionEvents"][v["id"]]), 16)
                self.assertEqual(ex["template"][v["id"]], v["events"])


if __name__ == "__main__":
    unittest.main()
