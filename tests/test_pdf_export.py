import importlib.util
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from coach.checker import check, constraints_for
from coach.musicxml import read
from coach.pdf_export import annotated_xml, export_pdf, draw_paradigm_brackets
from coach.repair import propose

ROOT = Path(__file__).resolve().parents[1]
PDF_READY = all(importlib.util.find_spec(package) for package in ("reportlab", "pymupdf"))


class AnnotationTests(unittest.TestCase):
    def setUp(self):
        self.source = ROOT / "examples/deliberate-errors.musicxml"
        self.score = read(self.source)
        self.assignment = constraints_for(self.score, json.loads((ROOT / "examples/assignment.json").read_text()))
        self.findings = check(self.score, self.assignment)
        self.candidates = propose(self.score, self.assignment)

    def test_annotations_preserve_source_and_every_note(self):
        before = self.source.read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "annotated.xml"
            annotated_xml(self.source, destination, self.findings)
            self.assertEqual(read(destination), self.score)
            root = ET.parse(destination).getroot()
            labels = [w.text for w in root.findall(".//direction/ direction-type/words".replace(" ", ""))]
            self.assertEqual(set(labels), {"[1]", "[2,3]", "[4]"})
            self.assertTrue(any(n.get("color") == "#B42318" for n in root.findall(".//note")))
        self.assertEqual(self.source.read_bytes(), before)

    def test_correction_changes_only_checked_note(self):
        candidate, repair = self.candidates[0]
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "corrected.xml"
            annotated_xml(self.source, destination, [], repair)
            self.assertEqual(read(destination), candidate)
            notes = ET.parse(destination).getroot().findall(".//note")
            self.assertEqual(sum(n.get("color") == "#16704A" for n in notes), 1)

    def test_namespace_and_layout_metadata_retained(self):
        with tempfile.TemporaryDirectory() as folder:
            source, destination = Path(folder) / "source.xml", Path(folder) / "annotated.xml"
            root = ET.parse(self.source).getroot()
            root.set("xmlns", "http://www.musicxml.org/ns/musicxml")
            credit = ET.SubElement(root, "credit", page="1")
            ET.SubElement(credit, "credit-words", {"default-x": "80", "default-y": "900"}).text = "Original title"
            measure = root.find("part/measure")
            ET.SubElement(measure, "print", {"new-system": "yes"})
            ET.ElementTree(root).write(source, encoding="utf-8", xml_declaration=True)
            annotated_xml(source, destination, self.findings)
            self.assertEqual(read(destination), self.score)
            copied = ET.parse(destination).getroot()
            ns = {"m": "http://www.musicxml.org/ns/musicxml"}
            self.assertEqual(copied.find("m:credit/m:credit-words", ns).text, "Original title")
            self.assertEqual(copied.find("m:part/m:measure/m:print", ns).get("new-system"), "yes")

    @unittest.skipUnless(PDF_READY, "Optional PDF dependencies are not installed")
    def test_pdf_pagination_and_vector_score_embedding(self):
        import pymupdf
        from reportlab.pdfgen import canvas

        def fake_engrave(executable, source, destination):
            c = canvas.Canvas(str(destination), pagesize=(612, 792))
            c.setFont("Helvetica", 12)
            c.drawString(50, 700, "Engraved score test marker")
            for y in range(550, 600, 10):
                c.line(50, y, 550, y)
            c.save()

        with tempfile.TemporaryDirectory() as folder, patch("coach.pdf_export.dependencies", return_value="renderer"), patch("coach.pdf_export.engrave", side_effect=fake_engrave):
            output = Path(folder)
            destination = export_pdf(self.source, self.score, self.assignment, self.findings * 6,
                                     [self.candidates[0][1]], output)
            with pymupdf.open(destination) as doc:
                text = "\n".join(page.get_text() for page in doc)
                self.assertIn("Findings and explanations", text)
                self.assertIn("A checked correction", text)
                self.assertEqual(text.count("Engraved score test marker"), 2)
                self.assertIn("[24]", text)
                self.assertGreater(len(doc), 2)
                # Score objects remain vector content, not a screenshot.
                self.assertTrue(any(page.get_drawings() for page in doc))

    @unittest.skipUnless(PDF_READY, "Optional PDF dependencies are not installed")
    def test_named_brackets_use_both_note_positions_without_erasing_music(self):
        import pymupdf
        with pymupdf.open() as doc:
            page=doc.new_page()
            page.insert_text((90,140),'MTCSTART1',fontsize=2)
            page.insert_text((210,140),'MTCEND1',fontsize=2)
            page.insert_text((210,140),'MTCSTART2',fontsize=2)
            page.insert_text((330,140),'MTCEND2',fontsize=2)
            page.draw_circle((100,175),3,color=(0,0,0))
            # Music fonts often have oversized character bounds intersecting a
            # marker above the visible note. Region redaction erased these.
            page.insert_text((90,230),'O',fontsize=100)
            original_glyphs=[s['chars'] for s in page.get_texttrace() if s['size']==100]
            draw_paradigm_brackets(doc,[
                {'name':'Voice exchange with skips','label':'Voice exchange\nwith skips\n(variant)'},
                {'name':'Upper neighbor with V4/2','label':'Upper neighbor\nV4/2'}])
            text=page.get_text()
            self.assertNotIn('MTCSTART',text)
            self.assertNotIn('MTCEND',text)
            self.assertIn('Voice exchange',text)
            self.assertIn('Upper neighbor',text)
            drawings=page.get_drawings()
            brackets=[d for d in drawings if d['color'] and abs(d['color'][0]-.1)<.001]
            self.assertEqual(len(brackets),2)
            self.assertAlmostEqual(brackets[0]['rect'].x0,92.5,places=1)
            self.assertAlmostEqual(brackets[0]['rect'].x1,212.5,places=1)
            self.assertTrue(any(d['rect'].y1>175 for d in drawings))
            self.assertEqual([s['chars'] for s in page.get_texttrace() if s['size']==100],original_glyphs)


if __name__ == "__main__":
    unittest.main()
