"""Write the one-line example the web page harmonizes (a melody in G major).

    python examples/harmonize/make_melody.py
"""
from pathlib import Path
import xml.etree.ElementTree as ET

MELODY = "G4 A4 B4 C5 D5 E5 C5 A4 G4 F#4 G4".split()

root = ET.Element("score-partwise", version="4.0")
ET.SubElement(ET.SubElement(root, "work"), "work-title").text = "Melody to harmonize"
score_part = ET.SubElement(ET.SubElement(root, "part-list"), "score-part", id="P1")
ET.SubElement(score_part, "part-name").text = "Soprano"
part = ET.SubElement(root, "part", id="P1")
for bar in range((len(MELODY) + 1) // 2):
    measure = ET.SubElement(part, "measure", number=str(bar + 1))
    if bar == 0:
        attributes = ET.SubElement(measure, "attributes")
        ET.SubElement(attributes, "divisions").text = "1"
        key = ET.SubElement(attributes, "key")
        ET.SubElement(key, "fifths").text = "1"
        ET.SubElement(key, "mode").text = "major"
        time = ET.SubElement(attributes, "time")
        ET.SubElement(time, "beats").text = "4"
        ET.SubElement(time, "beat-type").text = "4"
        clef = ET.SubElement(attributes, "clef")
        ET.SubElement(clef, "sign").text = "G"
        ET.SubElement(clef, "line").text = "2"
    for name in MELODY[2 * bar:2 * bar + 2]:
        whole = 2 * bar == len(MELODY) - 1
        note = ET.SubElement(measure, "note")
        pitch = ET.SubElement(note, "pitch")
        ET.SubElement(pitch, "step").text = name[0]
        if "#" in name:
            ET.SubElement(pitch, "alter").text = "1"
        ET.SubElement(pitch, "octave").text = name[-1]
        ET.SubElement(note, "duration").text = "4" if whole else "2"
        ET.SubElement(note, "type").text = "whole" if whole else "half"
ET.indent(root)
out = Path(__file__).with_name("melody-in-g.musicxml")
ET.ElementTree(root).write(out, encoding="utf-8", xml_declaration=True)
print("wrote", out)
