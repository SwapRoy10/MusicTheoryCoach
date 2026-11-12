"""Write the nonchord-tone example the web page offers: a composed chorale with passing tones,
neighbors and suspensions (a fixed seed, so the file is reproducible).

    python examples/nonchord/make_example.py
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from coach.compose_chorale import compose_chorale  # noqa: E402

SEED = 8
xml, review, plan = compose_chorale("G", 6, seed=SEED, embellished=True)
result = review["result"]
assert not [f for f in result["findings"] if f["severity"] == "error"]
out = Path(__file__).with_name("chorale-with-nonchord-tones.musicxml")
out.write_text(xml, encoding="utf-8")
print("wrote", out, "-", ", ".join(f"{n['label']} m.{n['measure']}" for n in result["nonchord_tones"]))
