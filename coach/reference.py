"""Read and search the project's provenance-bearing reference catalog."""
import argparse
import json
from pathlib import Path
import re

CATALOG = Path(__file__).resolve().parents[1] / "references/voice-leading-extended/catalog.json"


def library():
    if not CATALOG.exists():
        return {"sources": [], "patterns": [], "general_considerations": []}
    return json.loads(CATALOG.read_text(encoding="utf-8"))


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
    parser.add_argument("query")
    args = parser.parse_args()
    results = search(args.query)
    print(json.dumps(results, indent=2, ensure_ascii=True))
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())
