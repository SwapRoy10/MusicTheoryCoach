"""Assemble the static site into ``site/``.

    python web/build.py            # build
    python web/build.py --serve    # build, then serve at http://localhost:8000

The site needs no server-side code: the analyzer is the project's own Python
package, run in the browser by Pyodide. Netlify runs this script (netlify.toml).
"""
import argparse
import functools
import http.server
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
SITE = ROOT / "site"

PAGE_FILES = ["index.html", "style.css", "app.js", "overlay.js", "notation.js"]
# Python files Pyodide loads, keeping the repository layout so
# coach/reference.py still finds the catalog at ../references/.
PYTHON_FILES = [WEB / "bridge.py", *sorted((ROOT / "coach").glob("*.py")),
                # Only the public subset: the full reference index stays on the user's computer.
                ROOT / "references/voice-leading-extended/public-catalog.json"]
EXAMPLES = [
    ("Chorale with paradigms (13 bars)", ROOT / "examples/reviews/testScore/testScore.mxl"),
    ("Parallel fifths exercise", ROOT / "examples/deliberate-errors.musicxml"),
    ("ii6/5 progression", ROOT / "examples/varied-example.musicxml"),
    ("Clean progression", ROOT / "examples/valid.musicxml"),
]


def build():
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir()
    for name in PAGE_FILES:
        shutil.copy2(WEB / name, SITE / name)
    manifest = []
    for path in PYTHON_FILES:
        relative = path.name if path.parent == WEB else path.relative_to(ROOT).as_posix()
        destination = SITE / "py" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        manifest.append(relative)
    (SITE / "py" / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    examples = []
    (SITE / "examples").mkdir()
    for title, path in EXAMPLES:
        shutil.copy2(path, SITE / "examples" / path.name)
        examples.append({"title": title, "file": path.name})
    (SITE / "examples" / "index.json").write_text(json.dumps(examples, indent=1), encoding="utf-8")
    print(f"Built {SITE} ({len(manifest)} Python files, {len(examples)} examples)")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    build()
    if args.serve:
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
        print(f"Serving http://localhost:{args.port}/  (Ctrl+C to stop)")
        http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler).serve_forever()


if __name__ == "__main__":
    main()
