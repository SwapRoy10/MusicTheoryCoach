"""The composers: every result must pass the same checkers that review uploads."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))

from coach.compose_chorale import ComposeError, compose_chorale, progression  # noqa: E402
from coach.compose_species import SearchFailed, compose_species  # noqa: E402
from coach.counterpoint import check_exercise, read_exercise  # noqa: E402
from coach.model import Pitch  # noqa: E402
from coach.review import run_review  # noqa: E402
import bridge  # noqa: E402

FUX = "D4 F4 E4 D4 G4 F4 A4 G4 F4 E4 D4"


def errors(findings):
    return [f["rule"] for f in findings if f["severity"] == "error"]


class SpeciesComposerTests(unittest.TestCase):
    def reread(self, musicxml):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "composed.musicxml"
            path.write_text(musicxml, encoding="utf-8")
            return check_exercise(read_exercise(path))

    def test_every_species_on_both_sides_passes_the_checker(self):
        for species in (1, 2, 3, 4, 5):
            for above in (True, False):
                for mode in ("dorian", "aeolian"):
                    with self.subTest(species=species, above=above, mode=mode):
                        musicxml, exercise, analysis = compose_species(species, mode, above, seed=species * 7 + above)
                        self.assertEqual(errors(analysis["findings"]), [])
                        # The written file is detected and judged the same way as an upload.
                        again = self.reread(musicxml)
                        self.assertEqual(again["species"], species)
                        self.assertEqual(again["above"], above)
                        self.assertEqual(errors(again["findings"]), [])
                        self.assertEqual(exercise.cantus[0].pitch.name, exercise.cantus[-1].pitch.name)

    def test_composes_against_a_given_cantus(self):
        _, exercise, analysis = compose_species(4, cantus=FUX, above=True, seed=3)
        self.assertEqual([str(e.pitch) for e in exercise.cantus], FUX.split())
        self.assertEqual(errors(analysis["findings"]), [])
        pen = [e for e in exercise.counterpoint if e.bar == exercise.bars - 2]
        self.assertTrue(pen[0].tie_from and pen[0].pitch.name == "D")  # 7-6 cadential suspension

    def test_rejects_an_unusable_cantus_with_a_reason(self):
        with self.assertRaisesRegex(SearchFailed, "leap"):
            compose_species(1, cantus="D4 G4 C4 D4 F4 E4 D4")
        with self.assertRaisesRegex(SearchFailed, "re–do"):
            compose_species(4, cantus="D4 F4 E4 G4 F4 A4 G4 E4 C4 D4")  # ends rising to the final

    def test_generated_cantus_is_singable(self):
        from coach.compose_species import compose_cantus
        import random
        for seed in range(10):
            cantus = compose_cantus("D", 0, rng=random.Random(seed))
            self.assertTrue(8 <= len(cantus) <= 16)
            self.assertGreaterEqual(max(p.midi for p in cantus) - min(p.midi for p in cantus), 7)
            self.assertEqual(cantus[-2], Pitch("E", 0, 4))


class SpeciesCheckerTests(unittest.TestCase):
    def test_fux_first_species_is_clean(self):
        analysis = check_exercise(read_exercise(ROOT / "examples/species/first-species-fux.musicxml"))
        self.assertEqual((analysis["species"], errors(analysis["findings"])), (1, []))

    def test_deliberate_mistakes_are_found(self):
        analysis = check_exercise(read_exercise(ROOT / "examples/species/second-species-errors.musicxml"))
        self.assertEqual(analysis["species"], 2)
        found = set(errors(analysis["findings"]))
        self.assertIn("s2-downbeat-perfect", found)   # octaves on consecutive downbeats, bars 3-4
        self.assertIn("s2-passing-only", found)       # weak-beat dissonance approached by leap, bar 7
        for f in analysis["findings"]:
            self.assertIn(f["rule"], analysis["rules"])  # every finding cites the catalog


class ChoraleComposerTests(unittest.TestCase):
    def test_phrases_pass_the_full_review(self):
        for key, bars, seed in [("C", 4, 1), ("G", 5, 2), ("F", 6, 3), ("Bb", 7, 4), ("D", 8, 5), ("Eb", 8, 6), ("A", 4, 7)]:
            with self.subTest(key=key, bars=bars):
                musicxml, reviewed, plan = compose_chorale(key, bars, seed=seed)
                result = reviewed["result"]
                self.assertEqual(errors(result["findings"]), [])
                self.assertEqual(len(result["score"]["measures"]), bars)
                self.assertEqual(len(plan["chords"]), 2 * bars - 1)
                self.assertEqual([c["roman"] for c in result["harmony"]], plan["chords"])
                self.assertEqual(plan["chords"][-2:], ["V", "I"])
                final = result["harmony"][-1]["notes"]
                self.assertEqual(Pitch.parse(final["S"]["pitch"]).name, Pitch.parse(final["B"]["pitch"]).name)
                self.assertEqual(len(list(ET.fromstring(musicxml.encode()).iter("note"))), 4 * len(plan["chords"]))

    def test_required_soprano_lines_are_realized(self):
        named = 0
        for seed in range(15):
            _, reviewed, plan = compose_chorale("C", 6, seed=seed)
            for paradigm in reviewed["result"]["paradigms"]:
                named += 1
                self.assertEqual(paradigm["status"], "scheme_match", paradigm["description"])
        self.assertGreater(named, 5)

    def test_progressions_fill_the_bars(self):
        import random
        for bars in range(4, 9):
            chords, _ = progression(bars, random.Random(bars))
            self.assertEqual(len(chords), 2 * bars - 1)
            self.assertEqual(chords[0], "I")

    def test_bad_settings(self):
        with self.assertRaises(ComposeError):
            compose_chorale("H", 4)
        with self.assertRaises(ComposeError):
            compose_chorale("C", 12)


class ReferenceSopranoTests(unittest.TestCase):
    def test_voice_exchanges_with_skips_match_the_source(self):
        # Reference p. 12, figures 12a/12b: soprano 3-7-1 over I-V4/2-I6 and 1-4-3 over I6-V6/5-I.
        with tempfile.TemporaryDirectory() as folder:
            result = run_review(ROOT / "examples/reviews/testScore/testScore.mxl", folder)["result"]
        status = {p["name"]: p["status"] for p in result["paradigms"]}
        self.assertEqual(status["Voice exchange with skips ascending bass"], "scheme_match")
        self.assertEqual(status["Voice exchange with skips descending bass"], "scheme_match")


class BridgeTests(unittest.TestCase):
    def cited_ids_exist(self, reply):
        notes = len(list(ET.fromstring(reply["musicxml"].encode()).iter("note")))
        a = reply["analysis"]
        cited = {n["id"] for f in a["findings"] for n in f["notes"]} | {c["anchor"] for c in a["harmony"]}
        cited |= {n["id"] for c in a["harmony"] for n in c["notes"].values()}
        for mark in a["review"]["marks"]:
            cited |= {mark["anchor"], mark["end_anchor"]}
        self.assertTrue(cited and all(1 <= int(i[1:]) <= notes for i in cited))

    def test_compose_species_reply(self):
        reply = json.loads(bridge.compose_species(json.dumps({"species": 5, "mode": "mixolydian", "above": False, "seed": 4})))
        self.assertEqual((reply["kind"], reply["analysis"]["species"], reply["analysis"]["above"]), ("species", 5, False))
        self.cited_ids_exist(reply)

    def test_compose_chorale_reply(self):
        reply = json.loads(bridge.compose_chorale(json.dumps({"key": "D", "bars": 5, "seed": 9})))
        self.assertEqual(reply["kind"], "chorale")
        self.assertEqual(errors(reply["analysis"]["findings"]), [])
        self.cited_ids_exist(reply)

    def test_uploads_are_routed_by_voice_count(self):
        species = ROOT / "examples/species/second-species-errors.musicxml"
        reply = json.loads(bridge.review_upload(species.name, species.read_bytes()))
        self.assertEqual(reply["kind"], "species")
        self.cited_ids_exist(reply)
        chorale = ROOT / "examples/valid.musicxml"
        self.assertEqual(json.loads(bridge.review_upload(chorale.name, chorale.read_bytes()))["kind"], "chorale")

    def test_compose_errors_are_messages(self):
        reply = json.loads(bridge.compose_species(json.dumps({"species": 2, "cantus": "D4 E4"})))
        self.assertIn("error", reply)


if __name__ == "__main__":
    unittest.main()
