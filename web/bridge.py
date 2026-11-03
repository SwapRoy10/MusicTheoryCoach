"""Browser entry point: runs the same pipelines as the command-line tools.

Pyodide loads this module in the page. Every function returns JSON with the
analysis, the MusicXML the analysis refers to (note IDs n1, n2, ... in document
order) and a Markdown report. Nothing leaves the browser.
"""
import json
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET
import zipfile

from coach.review import run_review
from coach.score_import import root_from_file

SUFFIXES = (".musicxml", ".xml", ".mxl")
FAILURES = (ValueError, TypeError, KeyError, ET.ParseError, zipfile.BadZipFile, ZeroDivisionError)


def _streams(path):
    """Number of distinct (part, voice) streams that contain pitched notes."""
    root = root_from_file(path)
    streams = set()
    for part in root.findall("part"):
        for note in part.iter("note"):
            if note.find("pitch") is not None and note.find("chord") is None:
                streams.add((part.get("id"), note.findtext("voice", "1"), note.findtext("staff", "1")))
            elif note.find("chord") is not None:
                return 4  # chords inside a voice: a keyboard-style chorale
    return len(streams)


def _species_reply(path, species=None, cantus=None, title=None):
    from coach.counterpoint import check_exercise, read_exercise, species_report
    exercise = read_exercise(path, cantus=cantus)
    analysis = check_exercise(exercise, species)
    musicxml = Path(path).read_text(encoding="utf-8") if Path(path).suffix != ".mxl" else ET.tostring(root_from_file(path), encoding="unicode")
    return {"analysis": analysis, "musicxml": musicxml, "report": species_report(analysis, title or "Species counterpoint review")}


def review_upload(name, data, options="{}"):
    """Review an uploaded score: a two-voice species exercise or a four-voice chorale."""
    options = json.loads(options or "{}")
    suffix = Path(name).suffix.lower()
    if suffix not in SUFFIXES:
        return json.dumps({"error": "Choose a MusicXML file (.musicxml, .xml or compressed .mxl). "
                                    "Export one from MuseScore, Sibelius, Finale, Dorico or Noteflight."})
    work = Path(tempfile.mkdtemp())
    source = work / ("upload" + suffix)
    source.write_bytes(bytes(data))
    try:
        kind = options.get("kind") or ("species" if _streams(source) == 2 else "chorale")
        if kind == "species":
            reply = _species_reply(source, options.get("species"), options.get("cantus"))
            reply["kind"] = "species"
            return json.dumps(reply, ensure_ascii=False)
        reviewed = run_review(source, work / "review")
    except FAILURES as exc:
        return json.dumps({"error": str(exc) or exc.__class__.__name__, "kind": kind if "kind" in locals() else None})
    return json.dumps({"kind": "chorale", "analysis": reviewed["result"],
                       "musicxml": reviewed["source"].read_text(encoding="utf-8"),
                       "report": reviewed["report"]}, ensure_ascii=False)


def compose_species(options="{}"):
    """Compose species counterpoint. Options: species, mode, above, cantus (text), seed."""
    from coach.compose_species import SearchFailed, compose_species as compose
    options = json.loads(options or "{}")
    try:
        musicxml, _, analysis = compose(int(options.get("species", 1)), options.get("mode", "dorian"),
                                        bool(options.get("above", True)), options.get("cantus") or None,
                                        options.get("seed"))
    except (SearchFailed, ValueError) as exc:
        return json.dumps({"error": str(exc)})
    work = Path(tempfile.mkdtemp())
    path = work / "composed.musicxml"
    path.write_text(musicxml, encoding="utf-8")
    # Re-read the written file so note IDs match the engraving exactly.
    side = "upper" if not options.get("above", True) else "lower"
    reply = _species_reply(path, analysis["species"], side, "Composed species counterpoint")
    reply["kind"] = "species"
    reply["composed"] = True
    return json.dumps(reply, ensure_ascii=False)


def compose_chorale(options="{}"):
    """Compose a four-part chorale phrase. Options: key, bars, seed."""
    from coach.compose_chorale import ComposeError, compose_chorale as compose
    options = json.loads(options or "{}")
    try:
        musicxml, reviewed, plan = compose(options.get("key", "C"), int(options.get("bars", 4)), options.get("seed"))
    except ComposeError as exc:
        return json.dumps({"error": str(exc)})
    report = "# Composed chorale\n\nProgression: " + " ".join(plan["chords"]) + "\n\n" + reviewed["report"]
    return json.dumps({"kind": "chorale", "composed": True, "plan": plan, "analysis": reviewed["result"],
                       "musicxml": musicxml, "report": report}, ensure_ascii=False)
