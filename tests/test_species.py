import json
import unittest

from coach.reference import SPECIES_RULES, search, species_rules

STRENGTHS = {"required", "avoid", "preferred", "allowed"}
CATEGORIES = {"melody", "beginning", "ending", "harmony", "motion", "spacing", "rhythm", "dissonance", "suspension", "ornament", "combination"}


class SpeciesCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(SPECIES_RULES.read_text(encoding="utf-8"))

    def test_every_rule_is_well_formed_and_cited(self):
        sources = {s["id"] for s in self.data["sources"]}
        ids = [r["id"] for r in self.data["rules"]]
        self.assertEqual(len(ids), len(set(ids)))
        for rule in self.data["rules"]:
            self.assertIn(rule["strength"], STRENGTHS, rule["id"])
            self.assertIn(rule["category"], CATEGORIES, rule["id"])
            self.assertTrue(rule["rule"].strip(), rule["id"])
            self.assertTrue(rule["sources"] and set(rule["sources"]) <= sources, rule["id"])
            self.assertTrue(set(rule["species"]) <= {0, 1, 2, 3, 4, 5} and rule["species"], rule["id"])
            for variant in rule.get("variants", []):
                self.assertIn(variant["source"], sources, rule["id"])
        for source in self.data["sources"]:
            self.assertTrue(source["url"].startswith("https://"), source["id"])

    def test_each_species_has_its_defining_rules(self):
        for species, rule_id in [(1, "s1-all-consonant"), (2, "s2-passing-only"), (3, "s3-nota-cambiata"),
                                 (4, "s4-resolution"), (5, "s5-eighths"), (0, "cf-begin-end")]:
            self.assertIn(rule_id, {r["id"] for r in species_rules(species)})
        self.assertTrue(all(5 in r["species"] for r in species_rules(5)))

    def test_disagreements_between_sources_are_recorded(self):
        above = next(r for r in self.data["rules"] if r["id"] == "s4-suspensions-above")
        self.assertIn("mt21c", {v["source"] for v in above["variants"]})

    def test_search_reaches_species_rules(self):
        self.assertIn("s3-nota-cambiata", {r.get("id") for r in search("cambiata")})
        self.assertTrue(search("suspension resolves"))

    def test_guide_is_generated_from_current_data(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("render_doc", SPECIES_RULES.parent / "render_doc.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.DOC.read_text(encoding="utf-8"), module.render(self.data),
                         "Run: python references/species-counterpoint/render_doc.py")


if __name__ == "__main__":
    unittest.main()
