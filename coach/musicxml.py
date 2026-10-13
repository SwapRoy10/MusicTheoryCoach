"""Small, strict MusicXML adapter. Unsupported semantics fail visibly."""
from fractions import Fraction
from pathlib import Path
import xml.etree.ElementTree as ET

from .model import Note, Pitch, Score, VOICES

MAX_BYTES = 2_000_000


def read(path, voice_map=None):
    raw = Path(path).read_bytes()
    if len(raw) > MAX_BYTES:
        raise ValueError("MusicXML exceeds the 2 MB input limit")
    # Ordinary MusicXML external DOCTYPE is fine: ElementTree does not fetch it.
    if b"<!ENTITY" in raw.upper() or b"\x00" in raw:
        raise ValueError("Entity declarations and non-UTF-8 XML are unsupported")
    root = ET.fromstring(raw)
    for element in root.iter():
        element.tag = element.tag.split("}")[-1]
    if root.tag != "score-partwise":
        raise ValueError("Use uncompressed score-partwise MusicXML (.musicxml or .xml)")
    parts = root.findall("part")
    if not parts:
        raise ValueError("No parts in score")
    names = {p.get("id"): (p.findtext("part-name") or "").strip().lower()
             for p in root.findall("part-list/score-part")}
    aliases = {"soprano": "S", "alto": "A", "tenor": "T", "bass": "B",
               "s": "S", "a": "A", "t": "T", "b": "B"}
    if voice_map is not None and (not isinstance(voice_map, dict) or
                                  any(v not in VOICES for v in voice_map.values())):
        raise ValueError("voice_map must map 'part:voice' strings to S, A, T, B")
    measures = tuple(m.get("number", "") for m in parts[0].findall("measure"))
    if not measures or "" in measures or len(set(measures)) != len(measures):
        raise ValueError("Measures need unique, nonempty numbers")
    notes, keys, streams = [], set(), {}
    for part in parts:
        pid = part.get("id")
        if tuple(m.get("number", "") for m in part.findall("measure")) != measures:
            raise ValueError("Parts must have identical measure sequences")
        divisions = None
        key = None
        time = None
        for mi, measure in enumerate(part.findall("measure")):
            cursor = Fraction(0)
            if measure.get("implicit") == "yes":
                raise ValueError("Pickup/implicit measures are not supported")
            for el in measure:
                if el.tag == "attributes":
                    if cursor:
                        raise ValueError("Mid-measure attributes are unsupported")
                    if el.find("transpose") is not None:
                        raise ValueError("Transposing parts are unsupported; use concert pitch")
                    if el.find("divisions") is not None:
                        divisions = int(el.findtext("divisions"))
                        if divisions <= 0:
                            raise ValueError("Divisions must be positive")
                    if el.find("key") is not None:
                        key = int(el.findtext("key/fifths", "99"))
                        if el.findtext("key/mode", "major") != "major" or not -7 <= key <= 7:
                            raise ValueError("Only standard major keys are supported")
                        keys.add(key)
                    if el.find("time") is not None:
                        time = (el.findtext("time/beats"), el.findtext("time/beat-type"))
                    continue
                if el.tag in ("backup", "forward", "note"):
                    if divisions is None or key is None or time != ("4", "4"):
                        raise ValueError("Every part needs divisions, major key, and 4/4 metadata")
                    if el.tag == "note" and any(el.find(t) is not None for t in
                           ("chord", "rest", "grace", "cue", "tie", "time-modification", "unpitched", "dot")):
                        raise ValueError("Chords within a voice, rests, grace/cue notes, ties, tuplets and dots are unsupported")
                    duration = Fraction(el.findtext("duration", "0")) / divisions
                    if duration <= 0:
                        raise ValueError("Durations must be positive")
                    if el.tag == "backup":
                        cursor -= duration
                        if cursor < 0:
                            raise ValueError("Backup crosses the start of a measure")
                    elif el.tag == "forward":
                        cursor += duration
                    else:
                        stream = f"{pid}:{el.findtext('voice', '1')}"
                        voice = voice_map.get(stream) if voice_map is not None else aliases.get(names.get(pid, ""))
                        if voice not in VOICES:
                            raise ValueError(f"Cannot identify {stream}; name parts Soprano/Alto/Tenor/Bass or supply voice_map")
                        if voice in streams and streams[voice] != stream:
                            raise ValueError(f"Multiple streams assigned to {voice}")
                        streams[voice] = stream
                        pitch = el.find("pitch")
                        if pitch is None:
                            raise ValueError("Every note must have a pitch")
                        step = pitch.findtext("step")
                        alter = Fraction(pitch.findtext("alter", "0"))
                        octave = int(pitch.findtext("octave", "-99"))
                        if step not in tuple("CDEFGAB") or alter.denominator != 1 or abs(alter) > 2 or not 0 <= octave <= 9:
                            raise ValueError("Invalid or unsupported pitch")
                        notes.append(Note(f"n{len(notes)+1}", voice, measures[mi], mi,
                                          cursor + 1, duration, Pitch(step, int(alter), octave)))
                        cursor += duration
                elif el.tag == "barline" and (el.find("repeat") is not None or el.find("ending") is not None):
                    raise ValueError("Repeats and alternate endings must be unfolded first")
    if len(keys) != 1:
        raise ValueError("Key changes or inconsistent part keys are unsupported")
    if set(streams) != set(VOICES):
        raise ValueError("Exactly four identified voices S, A, T, B are required")
    for voice in VOICES:
        ordered = sorted((n for n in notes if n.voice == voice), key=lambda n: n.start)
        if any(a.end > b.start for a, b in zip(ordered, ordered[1:])):
            raise ValueError(f"Overlapping notes inside voice {voice}")
    return Score(tuple(notes), measures, keys.pop())


def write(score, path):
    """Export normalized SATB parts, preserving pitches, timing and measure labels."""
    root = ET.Element("score-partwise", version="4.0")
    part_list = ET.SubElement(root, "part-list")
    for voice, name in zip(VOICES, ("Soprano", "Alto", "Tenor", "Bass")):
        score_part = ET.SubElement(part_list, "score-part", id=voice)
        ET.SubElement(score_part, "part-name").text = name
    for voice in VOICES:
        part = ET.SubElement(root, "part", id=voice)
        for mi, label in enumerate(score.measures):
            measure = ET.SubElement(part, "measure", number=label)
            if mi == 0:
                attr = ET.SubElement(measure, "attributes")
                ET.SubElement(attr, "divisions").text = "1"
                key = ET.SubElement(attr, "key")
                ET.SubElement(key, "fifths").text = str(score.fifths)
                ET.SubElement(key, "mode").text = "major"
                time = ET.SubElement(attr, "time")
                ET.SubElement(time, "beats").text = "4"
                ET.SubElement(time, "beat-type").text = "4"
                clef = ET.SubElement(attr, "clef")
                ET.SubElement(clef, "sign").text = "G" if voice in ("S", "A") else "F"
                ET.SubElement(clef, "line").text = "2" if voice in ("S", "A") else "4"
            cursor = Fraction(0)
            for note in sorted((n for n in score.notes if n.voice == voice and n.measure_index == mi), key=lambda n: n.beat):
                if note.beat - 1 != cursor or note.duration not in (2, 4):
                    raise ValueError("Export requires complete, valid half/whole-note measures")
                element = ET.SubElement(measure, "note")
                pitch = ET.SubElement(element, "pitch")
                ET.SubElement(pitch, "step").text = note.pitch.step
                if note.pitch.alter:
                    ET.SubElement(pitch, "alter").text = str(note.pitch.alter)
                ET.SubElement(pitch, "octave").text = str(note.pitch.octave)
                ET.SubElement(element, "duration").text = str(note.duration)
                ET.SubElement(element, "voice").text = "1"
                ET.SubElement(element, "type").text = "whole" if note.duration == 4 else "half"
                cursor += note.duration
            if cursor != 4:
                raise ValueError("Export requires full measures")
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
