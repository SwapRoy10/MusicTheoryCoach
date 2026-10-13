"""Annotate the input MusicXML, engrave with MuseScore, and append tutor notes.

PDF dependencies are optional and imported only when export is requested.
"""
from collections import defaultdict
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
from fractions import Fraction
from .harmony import analyze
from .notation import campania_text

RED = "#B42318"
AMBER = "#946200"
GREEN = "#16704A"


def renderer_path(explicit=None):
    candidates = [explicit, os.environ.get("MUSESCORE_EXE"),
                  shutil.which("MuseScore4"), shutil.which("mscore"), shutil.which("musescore"),
                  r"C:\Program Files\MuseScore 4\bin\MuseScore4.exe",
                  "/Applications/MuseScore 4.app/Contents/MacOS/mscore"]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    raise ValueError("PDF export needs MuseScore. Install it or supply --musescore PATH.")


def dependencies(explicit=None):
    try:
        import reportlab  # noqa: F401
        import pymupdf  # noqa: F401
    except ImportError as exc:
        raise ValueError("PDF export needs optional packages: python -m pip install reportlab pymupdf") from exc
    return renderer_path(explicit)


def annotated_xml(source, destination, findings, repair=None, score=None, harmony_events=None, paradigm_marks=None, layout_markers=False):
    """Copy the actual input rather than reconstructing its parts/layout.

    IDs follow the same part/measure/note traversal as musicxml.read().
    MusicXML layout information and non-note content are retained.
    """
    tree = ET.parse(source)
    root = tree.getroot()
    namespace = root.tag.split("}")[0] + "}" if "}" in root.tag else ""
    def tag(name):
        return namespace + name
    if namespace:
        ET.register_namespace("", namespace[1:-1])
    records, divisions_by_note, note_anchors = {}, {}, {}
    for part in root.findall(tag("part")):
        divisions = 1
        for measure in part.findall(tag("measure")):
            chord_anchor = None
            for note in measure:
                if note.tag == tag("attributes") and note.find(tag("divisions")) is not None:
                    divisions = int(note.findtext(tag("divisions")))
                if note.tag == tag("note"):
                    if note.find(tag("chord")) is None:
                        chord_anchor = note
                    note_id = f"n{len(records)+1}"
                    records[note_id] = (measure, note)
                    divisions_by_note[note_id] = divisions
                    note_anchors[note_id] = chord_anchor
    labels = defaultdict(list)
    colors = {}
    if repair:
        from .model import Pitch
        note_id = repair["note_id"]
        if note_id not in records:
            raise ValueError("Repair note is missing from the input MusicXML")
        _, note = records[note_id]
        pitch = Pitch.parse(repair["after"])
        element = note.find(tag("pitch"))
        element.find(tag("step")).text = pitch.step
        element.find(tag("octave")).text = str(pitch.octave)
        alter = element.find(tag("alter"))
        if alter is None:
            alter = ET.Element(tag("alter"))
            element.insert(1, alter)
        alter.text = str(pitch.alter)
        for accidental in note.findall(tag("accidental")):
            note.remove(accidental)
        labels[note_id].append("R1")
        colors[note_id] = GREEN
        if score is not None:
            score = score.change(note_id, pitch)
    else:
        for i, finding in enumerate(findings, 1):
            evidence = finding["notes"]
            for n in evidence:
                if finding["severity"] == "error":
                    colors[n["id"]] = RED
                else:
                    colors.setdefault(n["id"], AMBER)
            if evidence:
                # Mark one destination note; all implicated notes are colored.
                at_location = [n for n in evidence if n["measure"] == finding["measure"] and n["beat"] == finding["beat"]]
                anchor = (at_location or evidence)[0]
                labels[anchor["id"]].append(str(i))
    for note_id, color in colors.items():
        _, note = records[note_id]
        note.set("color", color)
        head = note.find(tag("notehead"))
        if head is not None:
            head.set("color", color)
    for note_id, markers in labels.items():
        measure, note = records[note_id]
        direction = ET.Element(tag("direction"), {"placement": "above"})
        kind = ET.SubElement(direction, tag("direction-type"))
        words = ET.SubElement(kind, tag("words"), {"font-weight": "bold", "font-size": "10",
                                                     "color": colors[note_id], "relative-y": "10"})
        words.text = "[" + ",".join(markers) + "]"
        for field in ("voice", "staff"):
            original = note.find(tag(field))
            if original is not None:
                ET.SubElement(direction, tag(field)).text = original.text
        measure.insert(list(measure).index(note_anchors[note_id]), direction)
    if score is not None:
        by_id = {n.id: n for n in score.notes}
        for chord in harmony_events if harmony_events is not None else analyze(score):
            anchor = chord["anchor"]
            if anchor is None:
                continue
            measure, note = records[anchor]
            direction = ET.Element(tag("direction"), {"placement": "below"})
            kind = ET.SubElement(direction, tag("direction-type"))
            ET.SubElement(kind, tag("words"), {"font-size": "14", "font-family": "Campania", "font-weight": "normal",
                                               "default-y": "-85" if harmony_events is not None else "-55",
                                               "color": "#193348"}).text = campania_text(chord["roman"])
            offset = (Fraction(chord["offset"]) - by_id[anchor].start) * divisions_by_note[anchor]
            if offset:
                ET.SubElement(direction, tag("offset")).text = str(offset.numerator) if offset.denominator == 1 else str(float(offset))
            for field in ("voice", "staff"):
                original = note.find(tag(field))
                if original is not None:
                    ET.SubElement(direction, tag(field)).text = original.text
            measure.insert(list(measure).index(note_anchors[anchor]), direction)
        for bracket_number,mark in enumerate(paradigm_marks or [],1):
            anchor = mark["anchor"]
            measure, note = records[anchor]
            direction = ET.Element(tag("direction"), placement="above")
            kind = ET.SubElement(direction, tag("direction-type"))
            ET.SubElement(kind, tag("words"), {"font-size": "2" if layout_markers else "7.5", "font-weight": "normal",
                                               "color": "#FFFFFF" if layout_markers else "#193348",
                                               "default-y": "80", "relative-x": "0"}).text = f"MTCSTART{bracket_number}" if layout_markers else mark["label"]
            if mark.get("end_anchor") and not layout_markers:
                bracket_kind=ET.SubElement(direction,tag("direction-type"))
                ET.SubElement(bracket_kind,tag("bracket"), {"type":"start","number":str(bracket_number),
                              "line-end":"down","line-type":"solid","end-length":"6",
                              "default-y":"62","relative-x":"-4","color":"#193348"})
            for field in ("voice", "staff"):
                original = note.find(tag(field))
                if original is not None:
                    ET.SubElement(direction, tag(field)).text = original.text
            measure.insert(list(measure).index(note_anchors[anchor]), direction)
            if mark.get("end_anchor"):
                end_anchor=mark["end_anchor"]
                end_measure,end_note=records[end_anchor]
                stop=ET.Element(tag("direction"),placement="above")
                stop_kind=ET.SubElement(stop,tag("direction-type"))
                if layout_markers:
                    ET.SubElement(stop_kind,tag("words"),{"font-size":"2","color":"#FFFFFF","default-y":"80",
                                                          "relative-x":"0"}).text=f"MTCEND{bracket_number}"
                else:
                    ET.SubElement(stop_kind,tag("bracket"), {"type":"stop","number":str(bracket_number),
                                  "line-end":"down","line-type":"solid","end-length":"6",
                                  "default-y":"62","relative-x":"8","color":"#193348"})
                for field in ("voice","staff"):
                    original=end_note.find(tag(field))
                    if original is not None:
                        ET.SubElement(stop,tag(field)).text=original.text
                end_measure.insert(list(end_measure).index(note_anchors[end_anchor]),stop)
    tree.write(destination, encoding="utf-8", xml_declaration=True)


def engrave(executable, source, target):
    kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    try:
        result = subprocess.run([executable, "-o", str(target.resolve()), str(source.resolve())],
                                capture_output=True, timeout=90, **kwargs)
    except subprocess.TimeoutExpired as exc:
        raise ValueError("MuseScore PDF export timed out after 90 seconds.") from exc
    if result.returncode or not target.exists() or not target.stat().st_size:
        detail = result.stderr.decode("utf-8", errors="replace")[-1200:]
        raise ValueError("MuseScore could not engrave the annotated score. " + detail)


def remove_layout_anchors(document):
    """Remove only the exact marker text objects, never rectangular page regions.

    Music-font glyph bounds can extend far outside visible noteheads. Rectangle
    redaction therefore erases notes even when the marker is above the staff.
    Qt/MuseScore and PyMuPDF write each marker as a self-contained BT/ET object.
    """
    for page in document:
        font_maps={}
        for font in page.get_fonts():
            xref,_,_,_,resource,encoding=font[:6]
            mapping={}
            kind,reference=document.xref_get_key(xref,"ToUnicode")
            if kind=="xref":
                cmap=document.xref_stream(int(reference.split()[0]))
                for block in re.findall(rb"beginbfchar(.*?)endbfchar",cmap,re.S):
                    for source,target in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>",block):
                        mapping[int(source,16)]=bytes.fromhex(target.decode()).decode("utf-16-be")
                for block in re.findall(rb"beginbfrange(.*?)endbfrange",cmap,re.S):
                    for start,end,target in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(\[[^\]]*\]|<[0-9A-Fa-f]+>)",block):
                        first,last=int(start,16),int(end,16)
                        values=re.findall(rb"<([0-9A-Fa-f]+)>",target)
                        if target.startswith(b"["):
                            for source,value in zip(range(first,last+1),values):
                                mapping[source]=bytes.fromhex(value.decode()).decode("utf-16-be")
                        elif values:
                            initial=int(values[0],16)
                            for source in range(first,last+1):
                                mapping[source]=chr(initial+source-first)
            font_maps[resource.encode()]=(mapping,encoding)

        def marker_object(match):
            block=match.group()
            font=re.search(rb"/([^\s/]+)\s+[-.0-9]+\s+Tf",block)
            if not font:
                return block
            mapping,encoding=font_maps.get(font.group(1),({},""))
            text=[]
            for hex_string,literal in re.findall(rb"<([0-9A-Fa-f]+)>|\(([^()]*)\)",block):
                raw=bytes.fromhex(hex_string.decode()) if hex_string else literal
                if encoding=="Identity-H":
                    text.append("".join(mapping.get(int.from_bytes(raw[i:i+2],"big"),"?") for i in range(0,len(raw),2)))
                else:
                    text.append(raw.decode("latin1"))
            return b"" if re.fullmatch(r"MTC(?:START|END)\d+","".join(text)) else block

        for xref in page.get_contents():
            original=document.xref_stream(xref)
            cleaned=re.sub(rb"\bBT\b.*?\bET\b",marker_object,original,flags=re.S)
            if cleaned!=original:
                document.update_stream(xref,cleaned)


def draw_paradigm_brackets(document, marks):
    """Place compact labels/brackets using engraving-resolved note anchors.

    MuseScore does not reliably import MusicXML direction brackets. White layout
    anchors let us use its exact note positions and retain vector engraving.
    """
    import pymupdf
    resolved=[]
    for number,mark in enumerate(marks,1):
        positions={}
        for page_index,page in enumerate(document):
            for end,prefix in (("start","MTCSTART"),("end","MTCEND")):
                matches=page.search_for(prefix+str(number))
                if matches:
                    positions[end]=(page_index,matches[0])
        if set(positions)!={"start","end"}:
            raise ValueError("Could not locate both engraving anchors for "+mark["name"])
        start_page,start=positions["start"];end_page,end=positions["end"]
        if start_page!=end_page or abs(start.y0-end.y0)>30:
            raise ValueError("This bracket spans a system/page break and needs separate segments: "+mark["name"])
        resolved.append({"page":start_page,"start":start,"end":end,"mark":mark,
                         "y":min(start.y0,end.y0)-4})
    # Adjacent paradigms share a level within each system.
    for item in resolved:
        neighbors=[r["y"] for r in resolved if r["page"]==item["page"] and abs(r["y"]-item["y"])<25]
        item["level"]=min(neighbors)
    def music_glyphs():
        return [(span['font'],char) for page in document for span in page.get_texttrace()
                if any(name in span['font'] for name in ('Leland','Bravura','Gonville','Emmentaler','MuseJazz'))
                for char in span['chars']]
    original_music=music_glyphs()
    remove_layout_anchors(document)
    if music_glyphs()!=original_music:
        raise ValueError("Layout-anchor cleanup changed the original music glyphs")
    navy=(.10,.20,.28)
    for item in resolved:
        page=document[item["page"]]
        x0,x1=item["start"].x0+2.5,item["end"].x0+2.5
        y=item["level"]
        page.draw_polyline([(x0,y+4),(x0,y),(x1,y),(x1,y+4)],color=navy,width=.6)
        available=max(25,x1-x0-5)
        font_size=8
        lines=[]
        for paragraph in item["mark"]["label"].splitlines():
            line=""
            for word in paragraph.split():
                candidate=(line+" "+word).strip()
                if line and pymupdf.get_text_length(candidate,fontname="tiro",fontsize=font_size)>available:
                    lines.append(line);line=word
                else:
                    line=candidate
            if line:
                lines.append(line)
        for index,line in enumerate(lines):
            text_width=pymupdf.get_text_length(line,fontname="tiro",fontsize=font_size)
            baseline=y-4-(len(lines)-index-1)*8.5
            page.insert_text(((x0+x1-text_width)/2,baseline),line,fontname="tiro",fontsize=font_size,color=navy)


def export_pdf(source, score, assignment, findings, repairs, output, executable=None, reader=None, review=None):
    executable = dependencies(executable)
    import pymupdf
    from PIL import Image, ImageChops
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Flowable, KeepTogether
    from .musicxml import read
    from .checker import check, errors
    from .model import Pitch
    reader = reader or (lambda path: read(path, assignment.get("voice_map")))
    harmony_events = review["harmony"] if review else analyze(score)

    output = Path(output)
    destination = output / "annotated-score.pdf"
    original_xml = output / "annotated-original.musicxml"
    annotated_xml(source, original_xml, findings, score=score, harmony_events=harmony_events if review else None,
                  paradigm_marks=review.get("marks") if review else None)
    original = reader(original_xml)
    if original != score:
        raise ValueError("Annotation changed the musical content of the input")
    correction_xml = None
    if repairs:
        correction_xml = output / "annotated-correction.musicxml"
        annotated_xml(source, correction_xml, [], repairs[0], score=score)
        corrected = reader(correction_xml)
        expected = score.change(repairs[0]["note_id"], Pitch.parse(repairs[0]["after"]))
        if corrected != expected or errors(check(corrected, assignment)):
            raise ValueError("Annotated correction failed the full musical recheck")

    placements, pdfs = [], []
    width, height, margin = 612, 792, 42
    usable = width - 2 * margin
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("CoachTitle", fontName="Helvetica-Bold", fontSize=21, leading=25,
                              textColor=colors.HexColor("#193348"), spaceAfter=8))
    styles.add(ParagraphStyle("CoachBody", fontName="Helvetica", fontSize=10, leading=14,
                              textColor=colors.HexColor("#263645"), spaceAfter=7))
    styles.add(ParagraphStyle("CoachNote", parent=styles["CoachBody"], fontSize=9, leading=12, spaceAfter=5))
    def paragraph(text, style="CoachBody"):
        return Paragraph(text, styles[style])

    class EngravedPage(Flowable):
        def __init__(self, doc_index, page_index, clip):
            super().__init__()
            self.doc_index, self.page_index, self.clip = doc_index, page_index, clip
            factor = min(usable / clip.width, 470 / clip.height, 1.15)
            self.width, self.height = clip.width * factor, clip.height * factor
            self.hAlign = "CENTER"

        def draw(self):
            x, y = self.canv.absolutePosition(0, 0)
            placements.append((self.canv.getPageNumber()-1, self.doc_index, self.page_index,
                               (x, height-y-self.height, x+self.width, height-y), self.clip))

    def score_flowables(document):
        doc_index = len(pdfs)
        pdfs.append(document)
        result = []
        for pi, page in enumerate(document):
            # Locate ink on a small raster; the output embeds the original vectors.
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1, 1), alpha=False, colorspace=pymupdf.csRGB)
            raster = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            bbox = ImageChops.difference(raster, Image.new("RGB", raster.size, "white")).getbbox()
            clip = (pymupdf.Rect(bbox) + (-5, -5, 5, 5)) & page.rect if bbox else page.rect
            result += [EngravedPage(doc_index, pi, clip), Spacer(1, 12)]
        return result

    def finding_paragraph(index, finding):
        color = RED if finding["severity"] == "error" else AMBER
        location = f"m. {finding['measure']}, beat {finding['beat']}"
        evidence = "; ".join(f"{n['voice']} {n['pitch']} (m. {n['measure']}, b. {n['beat']})" for n in finding["notes"])
        text = (f'<b><font color="{color}">[{index}] {escape(finding["severity"].upper())}</font> '
                f'{escape(location)} - {escape(finding["rule"].replace("_", " "))}</b><br/>'
                f'{escape(finding["message"])}')
        if evidence:
            text += "<br/>" + escape(evidence)
        return paragraph(text, "CoachNote")

    with tempfile.TemporaryDirectory(prefix="score-pdf-", dir=output) as temp:
        folder = Path(temp)
        original_pdf = folder / "original.pdf"
        layout_xml=original_xml
        if review and review.get("marks"):
            layout_xml=folder/"layout-anchors.musicxml"
            annotated_xml(source,layout_xml,findings,score=score,harmony_events=harmony_events,
                          paradigm_marks=review["marks"],layout_markers=True)
        engrave(executable, layout_xml, original_pdf)
        original_doc = pymupdf.open(original_pdf)
        if review and review.get("marks"):
            draw_paradigm_brackets(original_doc,review["marks"])
        story = [paragraph("Your score, annotated", "CoachTitle"),
                 paragraph(escape(review.get("input_name", Path(source).name) if review else Path(source).name) + " | Input notes unchanged", "CoachNote"),
                 paragraph(f'<font color="{RED}"><b>Red</b></font>: notes involved in errors. '
                           f'<font color="{AMBER}"><b>Amber</b></font>: advisory findings. '
                           'Numbered labels refer to the notes below. A red note may also have advisory findings.', "CoachNote")]
        story += score_flowables(original_doc)
        if review:
            story.append(paragraph("Roman numeral corrections", "Heading2"))
            for note in review["label_notes"]:
                story.append(paragraph(escape(note), "CoachNote"))
            for note in review.get("correction_notes", []):
                story.append(paragraph(escape(note), "CoachNote"))
            story.append(paragraph("Paradigms and phrase structure", "Heading2"))
            for note in review["paradigm_notes"]:
                story.append(paragraph(escape(note), "CoachNote"))
        story.append(paragraph("Findings and explanations", "Heading2"))
        if not findings:
            story.append(paragraph("No violations or suggestions found by the supported checks."))
        for i, finding in enumerate(findings, 1):
            story.append(KeepTogether([finding_paragraph(i, finding)]))
        if review:
            story.append(paragraph("This export reviews the supplied score. No complete corrected realization is certified.", "CoachNote"))
        elif not repairs and errors(findings):
            story.append(paragraph("No single-note correction passed all supported hard rules. No valid correction is claimed."))
        if correction_xml:
            corrected_pdf = folder / "corrected.pdf"
            engrave(executable, correction_xml, corrected_pdf)
            corrected_doc = pymupdf.open(corrected_pdf)
            repair = repairs[0]
            story += [PageBreak(), paragraph("A checked correction", "CoachTitle"),
                      paragraph(f'<font color="{GREEN}"><b>Green [R1]</b></font>: the changed note. All other input notes are retained.', "CoachNote")]
            story += score_flowables(corrected_doc)
            before_harmony = {(c["measure"], c["beat"]): c["roman"] for c in analyze(score)}
            for chord in analyze(corrected):
                before = before_harmony.get((chord["measure"], chord["beat"]))
                if before and before != chord["roman"]:
                    story.append(paragraph(escape(f"Harmony changes at m. {chord['measure']}, beat {chord['beat']}: {before} to {chord['roman']}."), "CoachNote"))
            story += [paragraph("What changed", "Heading2"),
                      paragraph(f"<b>[R1] m. {escape(repair['measure'])}, beat {escape(repair['beat'])}, {escape(repair['voice'])}: "
                                f"{escape(repair['before'])} to {escape(repair['after'])}.</b> "
                                "The entire corrected score passes the supported hard rules after MusicXML re-import."),
                      paragraph("This is the first ranked single-note candidate. It changes the voice's melodic contour; "
                                "phrase quality still needs musical review. Rhythms and all other notes are preserved.", "CoachNote")]
            remaining = repair["remaining_findings"]
            if remaining:
                story.append(paragraph("Remaining advisory findings / uncertainty", "Heading2"))
                for finding in remaining:
                    story.append(paragraph(escape(f"m. {finding['measure']}, beat {finding['beat']}: {finding['message']}"), "CoachNote"))
            else:
                story.append(paragraph("No advisory findings remain under the implemented checks.", "CoachNote"))
        def page_frame(canvas, doc):
            canvas.setStrokeColor(colors.HexColor("#D7DFE5"))
            canvas.line(margin, 36, width-margin, 36)
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(colors.HexColor("#5C6B77"))
            canvas.drawString(margin, 23, "MUSIC THEORY COACH | Score review")
            canvas.drawRightString(width-margin, 23, str(doc.page))

        layout = folder / "layout.pdf"
        try:
            SimpleDocTemplate(str(layout), pagesize=(width, height), leftMargin=margin, rightMargin=margin,
                              topMargin=36, bottomMargin=49, title="Music Theory Coach - annotated score",
                              author="Music Theory Coach").build(story, onFirstPage=page_frame, onLaterPages=page_frame)
            with pymupdf.open(layout) as final:
                for page_index, doc_index, source_page, rect, clip in placements:
                    final[page_index].show_pdf_page(pymupdf.Rect(rect), pdfs[doc_index], source_page, clip=clip)
                final.save(destination, garbage=4, deflate=True)
        finally:
            for document in pdfs:
                document.close()
    return destination
