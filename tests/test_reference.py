from pathlib import Path
import hashlib
import unittest
import json
from coach.reference import library, search, public_subset, CATALOG, PUBLIC_CATALOG, PUBLIC_PATTERN_FIELDS
from coach.review import PARADIGM_SPECS
from coach.notation import campania_text, roman_components
from coach.report import teaching_packet
from coach.checker import constraints_for
from examples.make_varied import example


FULL = unittest.skipUnless(CATALOG.exists(), "Full reference catalog is kept locally, not in the repository")


class PublicCatalogTests(unittest.TestCase):
    def test_public_catalog_covers_recognized_paradigms_with_locators_only(self):
        data = json.loads(PUBLIC_CATALOG.read_text(encoding="utf-8"))
        self.assertEqual({p["name"] for p in data["patterns"]}, {s[0] for s in PARADIGM_SPECS})
        self.assertEqual(data["general_considerations"], [])
        for pattern in data["patterns"]:
            self.assertLessEqual(set(pattern), set(PUBLIC_PATTERN_FIELDS))
            self.assertEqual(pattern["printed_page"], pattern["pdf_page"] + 11)

    @FULL
    def test_public_catalog_is_current(self):
        full = json.loads(CATALOG.read_text(encoding="utf-8"))
        expected = public_subset(full, [s[0] for s in PARADIGM_SPECS])
        self.assertEqual(json.loads(PUBLIC_CATALOG.read_text(encoding="utf-8")), expected,
                         "Run: python -m coach.reference --export-public")


@FULL
class ReferenceTests(unittest.TestCase):
    def test_all_source_locators_exist_and_copy_is_exact(self):
        data = library()
        root = CATALOG.parents[2]
        for source in data["sources"]:
            self.assertEqual(hashlib.sha256((root / source["pdf"]).read_bytes()).hexdigest(), source["sha256"])
        for record in data["patterns"] + data["general_considerations"]:
            self.assertTrue((root / record["image"]).is_file())
            self.assertEqual(record["printed_page"], record["pdf_page"] + 11)

    def test_search_finds_paradigm_and_retains_soprano_requirements(self):
        bach = search("BACH")
        self.assertEqual(len(bach), 1)
        self.assertEqual(bach[0]["required_soprano_degrees"], [3, 4, 4, 3])
        self.assertEqual(bach[0]["progression"], ["I", "ii4/2", "V6/5", "I"])
        self.assertTrue(search("lower neighbor"))
        self.assertEqual(len(search("lament")), 3)
        self.assertEqual(search("unmentioned-pattern"), [])

    def test_reference_packet_and_rule_strength(self):
        data = library()
        self.assertEqual(len(data["general_considerations"]), 8)
        score = example()
        packet = teaching_packet(score, constraints_for(score), [], [])
        self.assertEqual(packet["reference_library"]["sources"], data["sources"])
        self.assertIn("not operational instructions", packet["system_instruction"])


class NotationTests(unittest.TestCase):
    def test_raised_and_stacked_figures_preserve_semantics(self):
        for source, display in (("ii6", "ii6"), ("ii6/5", "ii65"), ("V4/3", "V43"),
                                ("I6/4", "I64"), ("V4/2", "V42"), ("vii°6", "viio6"),
                                ("viiø6/5", "vii065"), ("I", "I"), ("?", "?")):
            self.assertEqual(campania_text(source), display)
        self.assertEqual(roman_components("ii6/5"), ("ii", ("6", "5")))


if __name__ == "__main__":
    unittest.main()
