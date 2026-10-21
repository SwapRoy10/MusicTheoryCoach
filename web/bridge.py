"""Browser entry point: runs the same review pipeline as ``python -m coach.review``.

Pyodide loads this module in the page. It receives the uploaded file's bytes and
returns JSON with the analysis, the reviewed MusicXML (whose note IDs the
analysis refers to) and the plain-text report. Nothing leaves the browser.
"""
import json
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET
import zipfile

from coach.review import run_review

SUFFIXES = (".musicxml", ".xml", ".mxl")


def review_upload(name, data):
    suffix = Path(name).suffix.lower()
    if suffix not in SUFFIXES:
        return json.dumps({"error": "Choose a MusicXML file (.musicxml, .xml or compressed .mxl). "
                                    "Export one from MuseScore, Sibelius, Finale, Dorico or Noteflight."})
    work = Path(tempfile.mkdtemp())
    source = work / ("upload" + suffix)
    source.write_bytes(bytes(data))
    try:
        reviewed = run_review(source, work / "review")
    except (ValueError, TypeError, KeyError, ET.ParseError, zipfile.BadZipFile, ZeroDivisionError) as exc:
        return json.dumps({"error": str(exc) or exc.__class__.__name__})
    return json.dumps({"analysis": reviewed["result"],
                       "musicxml": reviewed["source"].read_text(encoding="utf-8"),
                       "report": reviewed["report"]}, ensure_ascii=False)
