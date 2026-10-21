"""Read and search the project's provenance-bearing reference catalog.

The user's source PDF, page images and full catalog stay on their computer
(gitignored). The repository and the web interface carry only
``public-catalog.json``: names and page/figure locators for the paradigms the
reviewer recognizes. ``library()`` prefers the full local catalog when present.
"""
import argparse
import json
from pathlib import Path
import re

FOLDER = Path(__file__).resolve().parents[1] / "references/voice-leading-extended"
CATALOG = FOLDER / "catalog.json"                # full index, local only
PUBLIC_CATALOG = FOLDER / "public-catalog.json"  # committed subset
PUBLIC_PATTERN_FIELDS = ("id", "source_id", "name", "family", "pdf_page", "printed_page", "figure")
PUBLIC_SOURCE_FIELDS = ("id", "title", "provided_by", "pdf_pages", "printed_pages", "sections", "author", "usage_rights")


def library():
    for path in (CATALOG, PUBLIC_CATALOG):
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return {"sources": [], "patterns": [], "general_considerations": []}


def full_library_available():
    return CATALOG.exists()


def public_subset(data, names):
    """Locators for the named patterns only; no transcribed content."""
    patterns = [{k: p[k] for k in PUBLIC_PATTERN_FIELDS if k in p} for p in data["patterns"] if p["name"] in names]
    missing = set(names) - {p["name"] for p in patterns}
    if missing:
        raise ValueError(f"Patterns missing from the catalog: {sorted(missing)}")
    sources = [{**{k: s[k] for k in PUBLIC_SOURCE_FIELDS if k in s},
                "availability": "Original PDF, page images and full index are kept locally by the user, not published."}
               for s in data["sources"]]
    return {"schema_version": data.get("schema_version"), "scope": "public subset", "sources": sources,
            "patterns": patterns, "general_considerations": []}


def export_public():
    from .review import PARADIGM_SPECS
    if not CATALOG.exists():
        raise SystemExit(f"The full catalog is not on this computer ({CATALOG}).")
    subset = public_subset(json.loads(CATALOG.read_text(encoding="utf-8")), [s[0] for s in PARADIGM_SPECS])
    PUBLIC_CATALOG.write_text(json.dumps(subset, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {PUBLIC_CATALOG} ({len(subset['patterns'])} patterns)")


def search(query):
    data = library()
    terms = set(re.findall(r"[a-z0-9]+", query.lower()))
    if not terms:
        return []
    matches = []
    for item in data.get("patterns", []) + data.get("general_considerations", []):
        searchable = " ".join(str(v) for k, v in item.items() if k not in ("image", "source_id"))
        words = set(re.findall(r"[a-z0-9]+", searchable.lower()))
        score = len(terms & words)
        if score == len(terms):
            matches.append(item)
    return matches


def main():
    parser = argparse.ArgumentParser(description="Find paradigms in the user's local voice-leading reference")
    parser.add_argument("query", nargs="?")
    parser.add_argument("--export-public", action="store_true",
                        help="Regenerate public-catalog.json from the local full catalog")
    args = parser.parse_args()
    if args.export_public:
        export_public()
        return 0
    if not args.query:
        parser.error("give a search query or --export-public")
    if not full_library_available():
        print("Note: the full local catalog is absent; searching the public subset only.", flush=True)
    results = search(args.query)
    print(json.dumps(results, indent=2, ensure_ascii=True))
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())
