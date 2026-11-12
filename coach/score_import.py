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


def infer_mode(notes, fifths, declared=()):
    """Minor if the file says so, or if the final bass is the relative minor's tonic.

    Notation programs often omit <mode> or write "major" for any key signature,
    so the final bass decides unless minor is declared.
    """
    if "minor" in declared:
        return "minor"
    if not notes:
        return "major"
    end = max(n.start for n in notes)
    bass = min((n for n in notes if n.start == end), key=lambda n: n.pitch.midi)
    return "minor" if bass.pitch.midi % 12 == (7 * fifths + 9) % 12 else "major"


def _parse(path):
    """Every note and rest with its stream (part, staff, voice), timing, pitch, ties and lyrics."""
    root = root_from_file(path)
    parts = root.findall("part")
    if not parts:
        raise ValueError("No parts in score")
    measures = tuple(m.get("number") for m in parts[0].findall("measure"))
    if not measures or None in measures or len(set(measures)) != len(measures):
        raise ValueError("Unique measure labels are required")
    events = []
    keys, supplied, modes = set(), [], set()
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
                        mode = (el.findtext("key/mode") or "").strip().lower()
                        if mode not in ("", "major", "minor") or not -7 <= key <= 7:
                            raise ValueError("Use a standard major or minor key signature")
                        keys.add(key)
                        if mode:
                            modes.add(mode)
                    if el.find("time") is not None:
                        time = (el.findtext("time/beats"), el.findtext("time/beat-type"))
                elif el.tag in ("backup", "forward", "note"):
                    if not divisions or key is None or time != ("4", "4"):
                        raise ValueError("4/4, a key signature and positive divisions metadata are required")
                    if el.tag == "note" and el.find("grace") is not None:
                        source_index += 1
                        raise ValueError("Grace notes are unsupported; write ornaments out in real note values")
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
                        if any(el.find(t) is not None for t in ("cue", "time-modification", "unpitched")):
                            raise ValueError("Cue notes, tuplets and unpitched notes are unsupported")
                        if start + duration > 4:
                            raise ValueError(f"m. {measures[mi]}: a note runs past the bar line; use a tie")
                        ties = {t.get("type") for t in el.findall("tie")}
                        pitch_element = el.find("pitch")
                        pitch = None
                        if pitch_element is not None:
                            pitch = Pitch(pitch_element.findtext("step"), int(pitch_element.findtext("alter", "0")),
                                          int(pitch_element.findtext("octave")))
                        elif el.find("rest") is None:
                            raise ValueError("A note needs pitch or rest")
                        stream = (part.get("id"), el.findtext("staff", "1"), el.findtext("voice", "1"))
                        events.append({"id": f"n{source_index}", "stream": stream, "mi": mi, "start": start,
                                       "duration": duration, "pitch": pitch, "chord": is_chord,
                                       "tie_stop": "stop" in ties, "tie_start": "start" in ties})
                        for lyric in el.findall("lyric"):
                            text = "".join(t.text or "" for t in lyric.findall("text"))
                            if text:
                                supplied.append({"measure": measures[mi], "beat": str(start+1), "text": text,
                                                 "note_id": f"n{source_index}", "part": part.get("id")})
                        if not is_chord:
                            chord_start, cursor = start, cursor + duration
                elif el.tag == "barline" and (el.find("repeat") is not None or el.find("ending") is not None):
                    raise ValueError("Unfold repeats before ranked import")
    if len(keys) != 1 or not any(e["pitch"] for e in events):
        raise ValueError("One consistent key and pitched notes are required")
    return measures, events, keys.pop(), modes, supplied


def read_ranked(path):
    """Return score, original labels and scope.

    Two layouts are read. Chords written in one voice (block chords) are assigned
    by pitch rank at each onset (B, T, A, S); they must sound together. Four
    separate voices (two per staff, or four staves) keep their own rhythms, so
    passing tones, suspensions and other nonchord tones can be written; ties are
    kept as separate notes marked ``tied``. Source IDs count *all* note elements,
    including rests, for annotation.
    """
    measures, events, fifths, modes, supplied = _parse(path)
    pitched = [e for e in events if e["pitch"] is not None]
    last_music = max(e["mi"] for e in pitched)
    notes = []
    if any(e["chord"] for e in events):
        groups = defaultdict(list)
        for e in pitched:
            if e["tie_stop"] or e["tie_start"]:
                raise ValueError("Ties need each voice written separately (two voices per staff), not block chords")
            groups[(e["mi"], e["start"])].append(e)
        for (mi, start), group in sorted(groups.items()):
            if len(group) != 4 or len({e["duration"] for e in group}) != 1:
                raise ValueError(f"m. {measures[mi]}, beat {start+1}: expected four aligned pitches of equal duration. "
                                 "To write passing tones or suspensions, put each voice in its own voice layer.")
            for voice, e in zip(("B", "T", "A", "S"), sorted(group, key=lambda n: n["pitch"].midi)):
                notes.append(Note(e["id"], voice, measures[mi], mi, start+1, e["duration"], e["pitch"]))
        assignment = "Ascending pitch rank at each aligned sonority: B, T, A, S. Crossing cannot be assessed."
    else:
        streams = {}
        for e in pitched:
            streams.setdefault(e["stream"], []).append(e)
        if len(streams) != 4:
            raise ValueError(f"Expected four voices (soprano, alto, tenor, bass) but found {len(streams)}. Write two voices "
                             "per staff, or one voice on each of four staves.")
        order = sorted(streams, key=lambda k: -sum(e["pitch"].midi for e in streams[k]) / len(streams[k]))
        for voice, key in zip(("S", "A", "T", "B"), order):
            line = sorted(streams[key], key=lambda e: e["mi"] * 4 + e["start"])
            for a, b in zip(line, line[1:]):
                if a["mi"] * 4 + a["start"] + a["duration"] > b["mi"] * 4 + b["start"]:
                    raise ValueError(f"m. {measures[b['mi']]}: the {voice} voice has overlapping notes; write one note at a time per voice")
            for e in line:
                notes.append(Note(e["id"], voice, measures[e["mi"]], e["mi"], e["start"] + 1, e["duration"], e["pitch"],
                                  tied=bool(e["tie_stop"])))
        assignment = ("Voices read from the score's four voice layers, highest to lowest: S, A, T, B. "
                      "Each keeps its own rhythm, so crossings within a beat are not assessed.")
    notes.sort(key=lambda n: (n.start, "SATB".index(n.voice)))
    score = Score(tuple(notes), measures[:last_music+1], fifths, infer_mode(notes, fifths, modes))
    for voice in ("S", "A", "T", "B"):
        line = sorted((n for n in notes if n.voice == voice), key=lambda n: n.start)
        if any(a.end > b.start for a, b in zip(line, line[1:])):
            raise ValueError("Each voice must be monophonic, without overlapping events")
    scope = {"input_measures": len(measures), "reviewed_measures": len(score.measures),
             "trailing_empty_measures": list(measures[last_music+1:]),
             "voice_assignment": assignment}
    return score, supplied, scope
