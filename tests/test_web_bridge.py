import json
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))

from bridge import review_upload  # noqa: E402


class WebBridgeTests(unittest.TestCase):
    def review(self, path):
        return json.loads(review_upload(path.name, path.read_bytes()))

    def test_every_referenced_note_exists_in_returned_musicxml(self):
        # The page numbers <note> elements n1..nN in document order; the
        # analysis must only cite IDs that numbering can produce.
        reply = self.review(ROOT / "examples/reviews/testScore/testScore.mxl")
        notes = len(list(ET.fromstring(reply["musicxml"].encode()).iter("note")))
        analysis = reply["analysis"]
        cited = {n["id"] for f in analysis["findings"] for n in f["notes"]}
        cited |= {c["anchor"] for c in analysis["harmony"]}
        cited |= {n["id"] for c in analysis["harmony"] for n in c["notes"].values()}
        for mark in analysis["review"]["marks"]:
            cited |= {mark["anchor"], mark["end_anchor"]}
        self.assertTrue(cited)
        self.assertTrue(all(1 <= int(i[1:]) <= notes for i in cited))
        self.assertEqual(len(analysis["paradigms"]), 5)

    def test_matches_command_line_review(self):
        from coach.review import run_review
        import tempfile
        path = ROOT / "examples/deliberate-errors.musicxml"
        with tempfile.TemporaryDirectory() as folder:
            expected = run_review(path, folder)["result"]
        self.assertEqual(self.review(path)["analysis"]["findings"], json.loads(json.dumps(expected["findings"])))

    def test_unsupported_input_returns_message(self):
        reply = json.loads(review_upload("score.pdf", b"%PDF"))
        self.assertIn("MusicXML", reply["error"])
        reply = json.loads(review_upload("broken.musicxml", b"<score-partwise"))
        self.assertIn("error", reply)


if __name__ == "__main__":
    unittest.main()
