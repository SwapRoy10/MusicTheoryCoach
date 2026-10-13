"""Import compressed MusicXML and explicit pitch-ranked four-note sonorities."""
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET
from .model import Note, Pitch, Score

MAX_XML = 2_000_000


def root_from_file(path):
    path = Path(path)
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            container_info = archive.getinfo("META-INF/container.xml")
            if container_info.file_size > 100_000:
                raise ValueError("Oversized compressed MusicXML container")
            container = ET.fromstring(archive.read(container_info))
            rootfiles = [e.get("full-path") for e in container.iter() if e.tag.split("}")[-1] == "rootfile"]
            if not rootfiles:
                raise ValueError("Compressed MusicXML has no rootfile")
            info = archive.getinfo(rootfiles[0])
            if info.file_size > MAX_XML:
                raise ValueError("MusicXML exceeds the 2 MB uncompressed input limit")
            raw = archive.read(info)
    else:
        if path.stat().st_size > MAX_XML:
            raise ValueError("MusicXML exceeds the 2 MB input limit")
        raw = path.read_bytes()
    if b"<!ENTITY" in raw.upper() or b"\x00" in raw:
        raise ValueError("Entity declarations and non-UTF-8 XML are unsupported")
    root = ET.fromstring(raw)
    for e in root.iter():
        e.tag = e.tag.split("}")[-1]
    if root.tag != "score-partwise":
        raise ValueError("Only score-partwise MusicXML is supported")
    return root


def read_ranked(path):
    """Return score, original labels and scope; rank only aligned four-note groups.

    Rank assignment follows explicit user instructions; it cannot detect crossings.
    Source IDs count *all* note elements, including trailing rests, for annotation.
    """
    root = root_from_file(path)
    parts = root.findall("part")
    if not parts:
        raise ValueError("No parts in score")
    measures = tuple(m.get("number") for m in parts[0].findall("measure"))
    if not measures or None in measures or len(set(measures)) != len(measures):
        raise ValueError("Unique measure labels are required")
    groups = defaultdict(list)
    keys, supplied = set(), []
    source_index = 0
    for part in parts:
        if tuple(m.get("number") for m in part.findall("measure")) != measures:
            raise ValueError("Parts must have matching measure sequences")
        divisions, time, key = None, None, None
        for mi, measure in enumerate(part.findall("measure")):
            cursor, chord_start = Fraction(0), None
            if measure.get("implicit") == "yes":
                raise ValueError("Pickup measures require a different timing adapter")
            for el in measure:
                if el.tag == "attributes":
                    if cursor:
                        raise ValueError("Mid-measure attribute changes are unsupported")
                    if el.find("transpose") is not None:
                        raise ValueError("Use concert-pitch MusicXML")
                    if el.find("divisions") is not None:
                        divisions = int(el.findtext("divisions"))
                    if el.find("key") is not None:
                        key = int(el.findtext("key/fifths"))
                        if el.findtext("key/mode", "major") != "major" or not -7 <= key <= 7:
                            raise ValueError("Ranked import currently requires a standard major key")
                        keys.add(key)
                    if el.find("time") is not None:
                        time = (el.findtext("time/beats"), el.findtext("time/beat-type"))
                elif el.tag in ("backup", "forward", "note"):
                    if not divisions or key is None or time != ("4", "4"):
                        raise ValueError("4/4, major key and positive divisions metadata are required")
                    duration = Fraction(el.findtext("duration", "0")) / divisions
                    if duration <= 0:
                        raise ValueError("Positive durations are required")
                    if el.tag == "backup":
                        cursor -= duration
                        chord_start = None
                        if cursor < 0:
                            raise ValueError("Backup crosses the measure boundary")
                    elif el.tag == "forward":
                        cursor += duration
                        chord_start = None
                    else:
                        source_index += 1
                        is_chord = el.find("chord") is not None
                        if is_chord and chord_start is None:
                            raise ValueError("Chord note without an anchor")
                        start = chord_start if is_chord else cursor
                        if any(el.find(t) is not None for t in ("grace", "cue", "tie", "time-modification", "unpitched", "dot")):
                            raise ValueError("Grace notes, ties, tuplets, unpitched notes and dots are unsupported")
                        pitch_element = el.find("pitch")
                        if pitch_element is not None:
                            pitch = Pitch(pitch_element.findtext("step"), int(pitch_element.findtext("alter", "0")),
                                          int(pitch_element.findtext("octave")))
                            groups[(mi, start)].append((f"n{source_index}", duration, pitch))
                        elif el.find("rest") is None:
                            raise ValueError("A note needs pitch or rest")
                        for lyric in el.findall("lyric"):
                            text = "".join(t.text or "" for t in lyric.findall("text"))
                            if text:
                                supplied.append({"measure": measures[mi], "beat": str(start+1), "text": text,
                                                 "note_id": f"n{source_index}", "part": part.get("id")})
                        if not is_chord:
                            chord_start, cursor = start, cursor + duration
                elif el.tag == "barline" and (el.find("repeat") is not None or el.find("ending") is not None):
                    raise ValueError("Unfold repeats before ranked import")
    if len(keys) != 1 or not groups:
        raise ValueError("One consistent major key and pitched notes are required")
    last_music = max(mi for mi, _ in groups)
    notes = []
    for (mi, start), group in sorted(groups.items()):
        if len(group) != 4 or len({dur for _, dur, _ in group}) != 1:
            raise ValueError(f"m. {measures[mi]}, beat {start+1}: expected four aligned pitches of equal duration")
        for voice, (note_id, duration, pitch) in zip(("B", "T", "A", "S"), sorted(group, key=lambda n: n[2].midi)):
            notes.append(Note(note_id, voice, measures[mi], mi, start+1, duration, pitch))
    score = Score(tuple(notes), measures[:last_music+1], keys.pop())
    for voice in ("S", "A", "T", "B"):
        line = sorted((n for n in notes if n.voice == voice), key=lambda n: n.start)
        if any(a.end > b.start for a, b in zip(line, line[1:])):
            raise ValueError("Ranked import requires aligned monophonic voices without overlapping events")
    scope = {"input_measures": len(measures), "reviewed_measures": len(score.measures),
             "trailing_empty_measures": list(measures[last_music+1:]),
             "voice_assignment": "Ascending pitch rank at each aligned sonority: B, T, A, S. Crossing cannot be assessed."}
    return score, supplied, scope
