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


# The score on the page, kept so fixes can be searched and applied without re-uploading.
CURRENT = {}


def _species_reply(path, species=None, cantus=None, title=None):
    from coach.counterpoint import check_exercise, read_exercise, species_report
    exercise = read_exercise(path, cantus=cantus)
    analysis = check_exercise(exercise, species)
    musicxml = Path(path).read_text(encoding="utf-8") if Path(path).suffix != ".mxl" else ET.tostring(root_from_file(path), encoding="unicode")
    CURRENT.clear()
    CURRENT.update(kind="species", exercise=exercise, species=analysis["species"], cantus=cantus,
                   analysis=analysis, musicxml=musicxml, title=title)
    return {"analysis": analysis, "musicxml": musicxml, "report": species_report(analysis, title or "Species counterpoint review")}


def _chorale_reply(source, work, extra=None):
    reviewed = run_review(source, work / "review")
    musicxml = reviewed["source"].read_text(encoding="utf-8")
    CURRENT.clear()
    CURRENT.update(kind="chorale", score=reviewed["score"], assignment=reviewed["assignment"],
                   analysis=reviewed["result"], musicxml=musicxml)
    return {"kind": "chorale", "analysis": reviewed["result"], "musicxml": musicxml,
            "report": reviewed["report"], **(extra or {})}


def fixes_for(index):
    """Up to three single-note fixes for finding ``index`` of the score on the page."""
    from coach.fixes import chorale_fixes, species_fixes
    if not CURRENT:
        return json.dumps({"error": "No score is loaded."})
    finding = CURRENT["analysis"]["findings"][int(index)]
    if CURRENT["kind"] == "species":
        options = species_fixes(CURRENT["exercise"], CURRENT["species"], finding)
    else:
        options = chorale_fixes(CURRENT["score"], CURRENT["assignment"], finding)
    return json.dumps({"fixes": options})


def restore(musicxml):
    """Make ``musicxml`` (an earlier version from the page's undo history) current again."""
    work = Path(tempfile.mkdtemp())
    source = work / "restored.musicxml"
    source.write_text(musicxml, encoding="utf-8")
    try:
        if CURRENT.get("kind") == "species":
            side = "upper" if not CURRENT["exercise"].above else "lower"
            reply = _species_reply(source, CURRENT["species"], side, CURRENT.get("title"))
        else:
            reply = _chorale_reply(source, work)
    except FAILURES as exc:
        return json.dumps({"error": str(exc) or exc.__class__.__name__})
    return json.dumps({"ok": True, "same": reply["musicxml"] == musicxml})


def apply_fix(note_ids, pitch):
    """Change the given notes to ``pitch`` and review the result again."""
    from coach.fixes import apply_pitch
    from coach.model import Pitch
    if not CURRENT:
        return json.dumps({"error": "No score is loaded."})
    musicxml = apply_pitch(CURRENT["musicxml"], json.loads(note_ids), Pitch.parse(pitch))
    work = Path(tempfile.mkdtemp())
    source = work / "fixed.musicxml"
    source.write_text(musicxml, encoding="utf-8")
    try:
        if CURRENT["kind"] == "species":
            side = "upper" if not CURRENT["exercise"].above else "lower"
            reply = _species_reply(source, CURRENT["species"], side, CURRENT.get("title"))
            reply["kind"] = "species"
        else:
            reply = _chorale_reply(source, work)
    except FAILURES as exc:
        return json.dumps({"error": str(exc) or exc.__class__.__name__})
    return json.dumps(reply, ensure_ascii=False)


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
        streams = _streams(source)
        kind = options.get("kind") or {1: "line", 2: "species"}.get(streams, "chorale")
        if kind == "line":
            from coach.compose_chorale import ComposeError
            from coach.harmonize import read_line
            try:
                pitches, key, voice = read_line(source)
            except ComposeError as exc:
                return json.dumps({"error": str(exc), "kind": "line"})
            return harmonize(json.dumps({"pitches": [str(p) for p in pitches], "key": key, "voice": voice,
                                         "seed": options.get("seed")}))
        if kind == "species":
            reply = _species_reply(source, options.get("species"), options.get("cantus"))
            reply["kind"] = "species"
            return json.dumps(reply, ensure_ascii=False)
        reply = _chorale_reply(source, work)
    except FAILURES as exc:
        return json.dumps({"error": str(exc) or exc.__class__.__name__, "kind": kind if "kind" in locals() else None})
    return json.dumps(reply, ensure_ascii=False)


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
        musicxml, reviewed, plan = compose(options.get("key", "C"), int(options.get("bars", 4)), options.get("seed"),
                                           chromatic=bool(options.get("chromatic")))
    except ComposeError as exc:
        return json.dumps({"error": str(exc)})
    work = Path(tempfile.mkdtemp())
    source = work / "chorale.musicxml"
    source.write_text(musicxml, encoding="utf-8")
    reply = _chorale_reply(source, work, {"composed": True, "plan": plan})
    reply["report"] = "# Composed chorale\n\nProgression: " + " ".join(plan["chords"]) + "\n\n" + reply["report"]
    return json.dumps(reply, ensure_ascii=False)


def harmonize(options="{}"):
    """Harmonize a given soprano or bass. Options: text or pitches, voice ("S" or "B"), key, seed."""
    from coach.compose_chorale import ComposeError
    from coach.harmonize import harmonize as run, parse_line
    from coach.model import Pitch
    options = json.loads(options or "{}")
    try:
        if options.get("pitches"):
            line = [Pitch.parse(p) for p in options["pitches"]]
        else:
            line = parse_line(options.get("text", ""))
        musicxml, reviewed, plan = run(line, options.get("voice", "S"), options.get("key", "C"), options.get("seed"),
                                       chromatic=bool(options.get("chromatic")))
    except ComposeError as exc:
        return json.dumps({"error": str(exc), "kind": "line"})
    work = Path(tempfile.mkdtemp())
    source = work / "harmonized.musicxml"
    source.write_text(musicxml, encoding="utf-8")
    reply = _chorale_reply(source, work, {"composed": True, "plan": plan})
    given = {"S": "soprano", "B": "bass"}[plan["given"]]
    reply["report"] = (f"# Harmonization\n\nGiven {given} in {plan['key_name']}. Chords: " + " ".join(plan["chords"])
                       + "\n\n" + reply["report"])
    return json.dumps(reply, ensure_ascii=False)


def practice_new(options="{}"):
    """A new practice exercise for the page to edit. Options: kind ("species" or "chorale") and its settings."""
    from coach.compose_chorale import ComposeError
    from coach.compose_species import SearchFailed
    from coach.practice import new_exercise
    try:
        return json.dumps({"exercise": new_exercise(json.loads(options or "{}"))}, ensure_ascii=False)
    except (ComposeError, SearchFailed, ValueError) as exc:
        return json.dumps({"error": str(exc)})
