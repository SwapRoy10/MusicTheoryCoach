"""Rebuild the visually reviewed index. The source diagrams remain authoritative."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# page, source figure, family, name, progression (when confidently indexed), required soprano
PATTERNS = [
    (1, "1", "arpeggiated bass", "Authentic arpeggiation", ["I", "V", "I"], None),
    (1, "2", "arpeggiated bass", "Plagal arpeggiation", ["I", "IV", "I"], None),
    (1, "3", "arpeggiated bass", "Plagal with IV6", ["I", "IV6", "I"], None),
    (1, "4", "arpeggiated bass", "10-long", ["I", "IV6", "I6"], [3, 4, 5]),
    (1, "5", "neighbor bass", "Lower neighbor with V6/5", ["I", "V6/5", "I"], None),
    (1, "6", "neighbor bass", "Upper neighbor with V4/3", ["I", "V4/3", "I"], None),
    (1, "7", "neighbor bass", "Lower neighbor with V4/3", ["I6", "V4/3", "I6"], None),
    (1, "8", "neighbor bass", "Upper neighbor with V4/2", ["I6", "V4/2", "I6"], None),
    (1, "9a", "passing bass", "Voice exchange descending soprano", ["I", "vii°6", "I6"], [3, 2, 1]),
    (1, "9b", "passing bass", "Voice exchange ascending soprano", ["I6", "vii°6", "I"], [1, 2, 3]),
    (1, "10", "passing bass", "Parallel 10ths", ["I", "V4/3", "I6"], [3, 4, 5]),
    (1, "11", "passing bass", "Arpeggiation plus stepwise", [], None),
    (1, "12a", "incomplete neighbor bass", "Voice exchange with skips ascending bass", ["I", "V4/2", "I6"], [3, 1, 1]),
    (1, "12b", "incomplete neighbor bass", "Voice exchange with skips descending bass", ["I6", "V6/5", "I"], [1, 3, 3]),
    (1, "12c", "incomplete neighbor bass", "Both voice exchanges with skips", ["I", "V4/2", "I6", "V6/5", "I"], None),
    (2, "5b", "alternate neighbor bass", "Lower neighbor with vii°7 in minor", ["i", "vii°7", "i"], None),
    (2, "7b", "alternate neighbor bass", "Lower neighbor with vii°6/5 in minor", ["i6", "vii°6/5", "i6"], None),
    (2, "8b", "alternate neighbor bass", "Upper neighbor with vii°4/3 in minor", ["i6", "vii°4/3", "i6"], None),
    (2, "8c", "alternate neighbor bass", "Upper neighbor with IV", ["I6", "IV", "I6"], None),
    (2, "13", "double neighbor bass", "Using V4/3 and V6/5; order can reverse", ["I", "V4/3", "V6/5", "I"], None),
    (2, "9a", "alternate passing bass", "Voice exchange with V6/4 descending soprano", ["I", "V6/4", "I6"], [3, 2, 1]),
    (2, "9b", "alternate passing bass", "Voice exchange with V6/4 ascending soprano", ["I6", "V6/4", "I"], [1, 2, 3]),
    (2, "14", "predominant prolongation", "Passing voice exchange with I6/4", ["IV", "I6/4", "IV6"], None),
    (2, "15a", "predominant prolongation", "Passing voice exchange with I6 from ii7", ["ii7", "I6", "ii6/5"], None),
    (2, "15b", "predominant prolongation", "Passing voice exchange with I6 from ii6/5", ["ii6/5", "I6", "ii7"], None),
    (2, "16", "predominant prolongation", "Passing from IV to ii6/5; outer sixths", ["IV6", "I6", "ii6/5"], None),
    (2, "17", "dominant prolongation", "Passing voice exchange with i6/4 in minor", ["V6/5", "i6/4", "V4/3"], None),
    (2, "18", "dominant prolongation", "Voice exchange unfolding vii°7 with inversions of i", [], None),
    (3, "1", "embedded phrase models EPM", "BACH", ["I", "ii4/2", "V6/5", "I"], [3, 4, 4, 3]),
    (3, "2", "embedded phrase models EPM", "Bass ascent", ["I", "IV6", "V6/5", "I"], [3, 4, 4, 3]),
    (3, "3", "embedded phrase models EPM", "Soprano ascent 1", ["I", "IV", "V4/2", "I6"], [5, 6, 7, 1]),
    (3, "4", "embedded phrase models EPM", "Soprano ascent 2", ["I", "IV", "vii°6", "I6"], [5, 6, 7, 1]),
    (3, "5", "embedded phrase models EPM", "With IV7; cannot prepare seventh of V", ["I", "IV7", "V7", "I"], [3, 2, 2, 1]),
    (3, "6", "embedded phrase models EPM", "With ii7; omit fifth in ii7 or V7", ["I", "ii7", "V7", "I"], [1, 1, 7, 1]),
    (3, "7", "embedded phrase models EPM", "Inverted ii7 and V7 variant", ["I", "ii6/5", "V4/2", "I6"], None),
    (3, "8", "expansions with vi and iii", "vi bridging to IV", ["I", "vi", "IV", "V"], [3, 6, 6, 5]),
    (3, "9", "expansions with vi and iii", "iii bridging to IV", ["I", "iii", "IV", "I"], [1, 7, 6, 5]),
    (3, "10", "expansions with vi and iii", "iii7 bridging to IV", ["I", "iii7", "IV", "I"], [1, 7, 6, 5]),
    (3, "11", "expansions with vi and iii", "vi in deceptive motion; 8-7 and 6-5 figures", [], None),
    (3, "12a", "reharmonized 10 relative major minor", "III in reharmonized 10", [], None),
    (3, "12b", "reharmonized 10 relative major minor", "Alternate soprano", [], None),
    (3, "12c", "reharmonized 10 relative major minor", "Alternate bass", [], None),
    (4, "1", "lament bass", "Static soprano; typically minor", ["i", "v6", "iv6", "V"], None),
    (4, "2", "lament bass", "Ascending soprano; typically minor", ["i", "v6", "iv6", "V"], None),
    (4, "3", "lament bass", "Chromaticized bass; static soprano also works", ["i", "V6", "iv6", "IV6", "V"], None),
    (4, "1", "bass pedals", "Pedal IV6/4; alternate figured-bass reading", ["I", "IV6/4", "I"], None),
    (4, "2", "bass pedals", "Pedal I6/4; alternate figured-bass reading", ["V", "I6/4", "V"], None),
    (4, "3", "bass pedals", "EPM with tonic pedal; predominant or dominant substitutions", ["I", "IV", "V7", "I"], None),
    (4, "1", "bass pedal idioms", "Quiescenza Q-Line", [], None),
    (4, "2", "bass pedal idioms", "Minor Q-Line", [], None),
]


def build():
    patterns = []
    for index, (page, figure, family, name, progression, soprano) in enumerate(PATTERNS, 1):
        patterns.append({"id": f"pattern-{index:02d}", "source_id": "voice-leading-extended",
                         "pdf_page": page, "printed_page": page+11, "figure": figure,
                         "family": family, "name": name, "progression": progression,
                         "required_soprano_degrees": soprano,
                         "image": f"references/voice-leading-extended/pages/page-{page}.png",
                         "review_status": "visually indexed; inspect original diagram before realization",
                         "limitations": "Exact inner voices, durations, alternatives and annotations are not fully transcribed."})
    rules = [
        ("Soprano degree 1", "most often", "I"),
        ("Soprano degree 3", "most often", "I"),
        ("Soprano degree 5", "most often", "I6 or I"),
        ("Soprano degree 6", "most often", "IV"),
        ("Soprano degree 4", "most often", "V7"),
        ("Soprano degree 2", "usually", "V within an expansion; ii to V at a cadence"),
        ("V4/2 resolution", "ALWAYS in the supplied teaching framework", "I6"),
        ("IV6 soprano harmonization", "usually", "soprano degree 4"),
    ]
    considerations = [{"id": f"general-{i}", "source_id": "voice-leading-extended", "pdf_page": 5,
                       "printed_page": 16, "item": i, "name": name, "strength": strength,
                       "recommendation": recommendation,
                       "image": "references/voice-leading-extended/pages/page-5.png",
                       "checker_status": "reference guidance; not automatically enforced"}
                      for i, (name, strength, recommendation) in enumerate(rules, 1)]
    data = {"schema_version": 1, "sources": [{"id": "voice-leading-extended",
            "title": "Voice Leading Rules Summary - Extended", "provided_by": "user",
            "imported_on": "2026-10-13", "pdf": "references/voice-leading-extended/source.pdf",
            "sha256": hashlib.sha256((ROOT / "source.pdf").read_bytes()).hexdigest(),
            "pdf_pages": 5, "printed_pages": [12, 13, 14, 15, 16],
            "sections": ["F. Contrapuntal Expansions Summary", "G. General Considerations"],
            "author": "not identified in supplied excerpt", "usage_rights": "not specified; user project reference",
            "extraction_note": "Most notation is image-based; original diagrams and page images are retained.",
            "scope_note": "Major/minor, chromatic, pedal and incomplete-chord examples exceed current checker support."}],
            "patterns": patterns, "general_considerations": considerations}
    (ROOT / "catalog.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build()
