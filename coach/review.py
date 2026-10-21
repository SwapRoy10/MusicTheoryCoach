"""Extended review of explicitly pitch-ranked, aligned SATB chord scores.

Run: python -m coach.review score.mxl --out output/review
Preserves the source notation and separates contextual interpretation from checks.
"""
import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET

from .score_import import read_ranked, root_from_file
from .checker import check, constraints_for
from .harmony import identify, vocabulary
from .model import VOICES
from .reference import library
from .report import save_json


def canonical_label(text):
    text = text.strip().replace("º", "°")
    match = re.fullmatch(r"([iIvV]+)([o°ø0]?)([0-9/]{0,4})", text)
    if not match:
        return None
    numeral, quality, figures = match.groups()
    quality = {"o": "°", "0": "ø"}.get(quality, quality)
    digits = figures.replace("/", "")
    if digits in ("64", "65", "43", "42"):
        figures = digits[0] + "/" + digits[1]
    elif digits in ("", "6", "7"):
        figures = digits
    else:
        return None
    return numeral + quality + figures


def review_harmony(score, supplied):
    labels = {(r["measure"], r["beat"]): r["text"] for r in supplied if canonical_label(r["text"])}
    events = []
    for time, frame in score.frames():
        chord = identify(frame, score.fifths)
        if chord["status"] == "uncertain" and len(frame) == 4:
            names = {n.pitch.name for n in frame.values()}
            candidates = [c for c in vocabulary(score.fifths)
                          if c["size"] == 4 and set(c["pitches"]) - {c["pitches"][2]} == names]
            if len(candidates) == 1:
                candidate = candidates[0]
                bass = min(frame.values(), key=lambda n: n.pitch.midi).pitch.name
                inv = candidate["pitches"].index(bass)
                chord = {**candidate, "roman": candidate["symbol"] + ("7", "6/5", "4/3", "4/2")[inv],
                         "status": "interpreted", "bass": bass, "inversion": inv,
                         "reason": "Root, third and seventh are present; fifth is omitted. Contextual interpretation.",
                         "omitted": candidate["pitches"][2], "sounding_pitches": sorted(names)}
        mi = int(time // 4)
        measure, beat = score.measures[mi], str(time % 4 + 1)
        original = labels.get((measure, beat))
        events.append({**chord, "measure": measure, "beat": beat, "offset": str(time),
                       "anchor": frame["B"].id, "original_label": original,
                       "label_matches": canonical_label(original) == chord["roman"] if original else None,
                       "notes": {v: n.data() for v, n in frame.items()}})
    return events


def degree(pitch, fifths):
    from .model import STEPS
    return (STEPS.index(pitch.step) - (4 * fifths) % 7) % 7 + 1


# Paradigms the reviewer recognizes: name, numerals, bass degrees, required soprano.
# Names must match the reference catalog; public-catalog.json carries these entries.
PARADIGM_SPECS = [
    ("Lower neighbor with V6/5", ["I", "V6/5", "I"], [1, 7, 1], None),
    ("Upper neighbor with V4/2", ["I6", "V4/2", "I6"], [3, 4, 3], None),
    ("Voice exchange with skips ascending bass", ["I", "V4/2", "I6"], [1, 4, 3], [3, 1, 1]),
    ("Voice exchange with skips descending bass", ["I6", "V6/5", "I"], [3, 7, 1], [1, 3, 3]),
    ("Parallel 10ths", ["I", "V4/3", "I6"], [1, 2, 3], [3, 4, 5]),
]


def paradigms(score, harmony):
    """Narrow recognition of source schemes, with actual bass/soprano checks."""
    specs = PARADIGM_SPECS
    patterns = library()["patterns"]
    frames = list(score.frames())
    matches = []
    for index in range(len(harmony)-2):
        window = harmony[index:index+3]
        frame_window = [f for _, f in frames[index:index+3]]
        bass = [degree(f["B"].pitch, score.fifths) for f in frame_window]
        soprano = [degree(f["S"].pitch, score.fifths) for f in frame_window]
        romans = [c["roman"] for c in window]
        for name, expected, expected_bass, expected_soprano in specs:
            alternative_passing = name == "Parallel 10ths" and romans == ["I", "viiø6/5", "I6"]
            if bass != expected_bass or (romans != expected and not alternative_passing):
                continue
            source = next(p for p in patterns if p["name"] == name)
            soprano_matches = expected_soprano is None or soprano == expected_soprano
            variant = alternative_passing or not soprano_matches
            description = f"{'Variant of' if variant else 'Matches the harmonic/bass scheme of'} {name}; bass degrees {bass}, soprano degrees {soprano}."
            if not soprano_matches:
                description += f" The starred source requires soprano {expected_soprano}; this realization does not match it."
            if alternative_passing:
                description += " The middle chord is viiø6/5, not the source's V4/3. Outer thirds are octave-displaced from the source's tenths."
            if any(c.get("omitted") for c in window):
                description += " The middle seventh chord omits its fifth, so the voicing differs from the source diagram."
            matches.append({"id": f"P{len(matches)+1}", "start": {"measure": window[0]["measure"], "beat": window[0]["beat"]},
                            "end": {"measure": window[-1]["measure"], "beat": window[-1]["beat"]},
                            "name": name, "status": "variant" if variant else "scheme_match", "description": description,
                            "source_pdf_page": source["pdf_page"], "source_printed_page": source["printed_page"],
                            "source_figure": source["figure"], "source_pattern_id": source["id"],
                            "anchor": frame_window[0]["S"].id})
    return matches


def paradigm_marks(score, matches):
    by_location = {(n.measure,str(n.beat)): n for n in score.notes if n.voice == "S"}
    names = {p["id"]: p["name"] for p in library()["patterns"]}
    display_names = {
        "Voice exchange with skips ascending bass": "Voice exchange\nwith skips\nAscending bass",
        "Voice exchange with skips descending bass": "Voice exchange\nwith skips\nDescending bass",
        "Upper neighbor with V4/2": "Upper neighbor\nV4/2",
        "Lower neighbor with V6/5": "Lower neighbor\nV6/5",
        "Parallel 10ths": "Parallel 10ths",
    }
    marks = []
    for p in matches:
        name = p.get("name") or names[p["source_pattern_id"]]
        p["name"] = name
        start = by_location[(p["start"]["measure"],p["start"]["beat"])]
        end = by_location[(p["end"]["measure"],p["end"]["beat"])]
        marks.append({"anchor": start.id, "end_anchor": end.id, "label": display_names.get(name,name), "name": name})
    return marks


def main(argv=None):
    parser = argparse.ArgumentParser(description="Review a longer chord-staff SATB score using explicit bottom-up voice ranking")
    parser.add_argument("score", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--pdf", action="store_true")
    parser.add_argument("--musescore")
    args = parser.parse_args(argv)
    if args.out.exists() and any(args.out.iterdir()):
        raise ValueError("Choose a new or empty output directory")
    score, _, scope = read_ranked(args.score)
    args.out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.score, args.out / ("input-snapshot" + args.score.suffix))
    root = root_from_file(args.score)
    # The complete input snapshot is retained. Remove only all-rest trailing bars for engraving.
    for part in root.findall("part"):
        for m in list(part.findall("measure"))[len(score.measures):]:
            part.remove(m)
    source = args.out / "review-input.musicxml"
    ET.ElementTree(root).write(source, encoding="utf-8", xml_declaration=True)
    score, supplied, _ = read_ranked(source)
    assignment = constraints_for(score, {"instructions": "Review the full score. Voices assigned bottom-up by pitch. Original numerals are labels to audit, not required harmony."})
    harmony = review_harmony(score, supplied)
    findings = check(score, assignment, enforce_length=False)
    contextual = {(c["measure"], c["beat"]) for c in harmony if c["status"] == "interpreted"}
    findings = [f for f in findings if not (f["rule"] == "harmony_uncertain" and (f["measure"],f["beat"]) in contextual)]
    by_id = {n.id: n for n in score.notes}
    for chord in harmony:
        if chord.get("omitted"):
            findings.append({"rule": "incomplete_seventh", "severity": "suggestion", "measure": chord["measure"], "beat": chord["beat"],
                             "voices": list(VOICES), "notes": list(chord["notes"].values()),
                             "message": f"Interpreted as {chord['roman']}: {chord['omitted']} (the fifth) is absent. An omitted fifth can be legitimate; this is a contextual interpretation."})
        if chord["original_label"] and not chord["label_matches"]:
            findings.append({"rule": "roman_numeral", "severity": "suggestion" if chord["status"] == "interpreted" else "error", "measure": chord["measure"], "beat": chord["beat"],
                             "voices": list(VOICES), "notes": list(chord["notes"].values()),
                             "message": f"Your label {chord['original_label']} differs from {chord['roman']}. " + chord["reason"]})
    # Seventh advice also covers the contextual incomplete-chord interpretations.
    for old, new in zip(harmony, harmony[1:]):
        if old["status"] != "interpreted" or old.get("size") != 4 or old["pitches"] == new["pitches"]:
            continue
        seventh = old["pitches"][3]
        for voice, data in old["notes"].items():
            note, target = by_id[data["id"]], by_id[new["notes"][voice]["id"]]
            if note.pitch.name == seventh and target.pitch != note.pitch:
                if not (note.pitch.diatonic-target.pitch.diatonic == 1 and note.pitch.midi-target.pitch.midi in (1,2)):
                    findings.append({"rule": "seventh_resolution", "severity": "suggestion", "measure": new["measure"], "beat": new["beat"],
                                     "voices": [voice], "notes": [note.data(),target.data()],
                                     "message": f"Under the {old['roman']} interpretation, its seventh {note.pitch} moves to {target.pitch}, rather than descending by step."})
    # Doubled leading tones are apparent even when supplied harmony was not prescribed.
    tonic_pc = (7*score.fifths) % 12
    for chord in harmony:
        leading = [by_id[n["id"]] for n in chord["notes"].values() if by_id[n["id"]].pitch.midi % 12 == (tonic_pc-1)%12]
        if len(leading) > 1:
            findings.append({"rule": "doubled_leading_tone", "severity": "suggestion", "measure": chord["measure"], "beat": chord["beat"],
                             "voices": [n.voice for n in leading], "notes": [n.data() for n in leading],
                             "message": "The leading tone is doubled; review tendency-tone resolution in these voices."})
    phrase_starts = set()
    for annotation in supplied:
        if annotation["text"].upper() in ("HC", "PAC"):
            mi = score.measures.index(annotation["measure"])
            if mi+1 < len(score.measures):
                phrase_starts.add(score.measures[mi+1])
    for f in findings:
        if f["measure"] in phrase_starts and f["beat"] == "1" and f["rule"] in ("parallel_fifth", "parallel_octave", "leading_tone", "overlap"):
            f["severity"] = "suggestion"
            f["message"] += " This is across the marked cadence/phrase boundary; review whether a breath separates the phrases."
    findings.sort(key=lambda f: (score.measures.index(f["measure"]), Fraction(f["beat"]), f["rule"]))
    matches = paradigms(score, harmony)
    label_notes = [f"m. {c['measure']}, beat {c['beat']}: {c['original_label']} -> {c['roman']}. {c['reason']}"
                   for c in harmony if c["original_label"] and not c["label_matches"]]
    label_notes += [f"m. {c['measure']}, beat {c['beat']}: {c['original_label']} is defensible as {c['roman']} with its fifth {c['omitted']} omitted."
                    for c in harmony if c.get("omitted") and c["label_matches"]]
    label_notes.append("Other supplied chord labels match the reviewed complete pitch sets or the stated incomplete-chord interpretations.")
    for annotation in supplied:
        if annotation["text"].upper() not in ("HC", "PAC"):
            continue
        index = next((i for i,c in enumerate(harmony) if c["measure"] == annotation["measure"] and c["beat"] == annotation["beat"]), None)
        if index is None:
            continue
        current = harmony[index]
        if annotation["text"].upper() == "HC":
            description = "A root-position dominant ending supports the marked half cadence." if current["roman"] == "V" else "The marked HC requires contextual review."
        else:
            before = harmony[index-1] if index else None
            tonic_soprano = by_id[current["notes"]["S"]["id"]].pitch.midi % 12 == tonic_pc
            confirmed = before and before["roman"] in ("V", "V7") and current["roman"] == "I" and tonic_soprano
            description = "Root-position V-I with tonic in the soprano supports the marked perfect authentic cadence." if confirmed else "The marked PAC does not meet the simple root-position V-I / tonic-soprano check."
        label_notes.append(f"m. {annotation['measure']}, beat {annotation['beat']}, {annotation['text']}: {description}")
    tonic_name = next(c for c in vocabulary(score.fifths) if c["degree"] == 1 and c["size"] == 3)["pitches"][0]
    scope_notes = [f"Reviewed all {len(score.measures)} populated measures in {tonic_name} major, with {len(harmony)} aligned sonorities. The input contains {scope['input_measures']} measures; all-rest trailing measures {scope['trailing_empty_measures'][0]}-{scope['trailing_empty_measures'][-1]} are omitted from this engraving." if scope["trailing_empty_measures"] else f"Reviewed all {len(score.measures)} measures in {tonic_name} major.",
                   scope["voice_assignment"], "Your original lyrics/numerals are preserved. The additional dark-blue row gives reviewed harmony. Numbered findings and named paradigm brackets link to this report.",
                   "Checks cover exact parallels, ranges, spacing, overlap, basic tendency-tone advice and numeral comparison. Incomplete sevenths and paradigm variants are explicitly contextual. No corrected score is claimed."]
    paradigm_notes = [f"{p['name']}: m. {p['start']['measure']} b. {p['start']['beat']} to m. {p['end']['measure']} b. {p['end']['beat']}: {p['description']} Reference printed p. {p['source_printed_page']}, figure {p['source_figure']}." for p in matches]
    for index, chord in enumerate(harmony):
        if [c["roman"] for c in harmony[index:index+4]] == ["iii", "IV", "I6/4", "I"]:
            last = harmony[index+3]
            paradigm_notes.append(f"m. {chord['measure']} beat {chord['beat']} to m. {last['measure']} beat {last['beat']}: iii-IV-I6/4-I resembles the iii-to-IV connection in printed p. 14, figure 9, but lacks its opening I and adds I6/4. It is a fragment/variant, not a full source match.")
        if chord["roman"] == "I6/4" and index+1 < len(harmony):
            following = harmony[index+1]
            if following["roman"] not in ("V", "V7") or following.get("bass") != chord.get("bass"):
                paradigm_notes.append(f"m. {chord['measure']} beat {chord['beat']}: I6/4 is correctly spelled, but this is not the standard cadential 6/4-to-V over a held dominant bass. Review the intended tonic-expansion function.")
    paradigm_notes.append("Other passages were not confidently named from the supplied paradigms. Matching a few numerals alone is insufficient; required soprano lines and bass motion matter.")
    local_proposals = []
    for chord in harmony:
        if chord["roman"] == "viiø6/5" and canonical_label(chord["original_label"] or "") == "V4/3":
            alto = by_id[chord["notes"]["A"]["id"]]
            dominant_root = next(c for c in vocabulary(score.fifths) if c["degree"] == 5 and c["size"] == 3)["pitches"][0]
            from .model import Pitch
            replacement = Pitch.parse(dominant_root + str(alto.pitch.octave))
            candidate = score.change(alto.id,replacement)
            before_errors = {(f["rule"],f["measure"],f["beat"],tuple(f["voices"])) for f in check(score,assignment,enforce_length=False) if f["severity"] == "error"}
            after_errors = {(f["rule"],f["measure"],f["beat"],tuple(f["voices"])) for f in check(candidate,assignment,enforce_length=False) if f["severity"] == "error"}
            if not after_errors-before_errors:
                proposal = f"Local option at m. {chord['measure']}, beat {chord['beat']}: change alto {alto.pitch} to {replacement} if V4/3 and the source passing-bass paradigm were intended. This restores V4/3 and removes {len(before_errors-after_errors)} supported voice-leading error(s), with no newly detected hard-rule errors in a full recheck. Other score issues remain; this is not a certified full revision."
                local_proposals.append(proposal)
    scope_notes += local_proposals
    marks = paradigm_marks(score,matches)
    review = {"input_name": args.score.name, "harmony": harmony, "scope_notes": scope_notes, "label_notes": label_notes,
              "correction_notes": local_proposals, "paradigm_notes": paradigm_notes, "marks": marks}
    result = {"input_sha256": hashlib.sha256(args.score.read_bytes()).hexdigest(), "scope": scope,
              "score": score.data(), "supplied_labels": supplied, "harmony": harmony, "findings": findings,
              "paradigms": matches, "local_proposals": local_proposals, "review": review}
    save_json(args.out / "analysis.json", result)
    report = ["# Score review", "", "## Roman numerals", "", *label_notes, *local_proposals,
              "", "## Paradigms", "", *paradigm_notes, "", "## Findings", ""]
    report += [f"{i}. {f['severity'].upper()} - m. {f['measure']}, beat {f['beat']} - {f['rule']}: {f['message']} Evidence: "
               + "; ".join(f"{n['voice']} {n['pitch']} (m. {n['measure']}, b. {n['beat']})" for n in f["notes"])
               for i,f in enumerate(findings,1)]
    (args.out / "report.md").write_text("\n\n".join(report)+"\n", encoding="utf-8")
    if args.pdf:
        from .pdf_export import export_pdf
        export_pdf(source, score, assignment, findings, [], args.out, args.musescore,
                   reader=lambda path: read_ranked(path)[0], review=review)
    print(f"Reviewed {len(score.measures)} musical measures, {len(harmony)} sonorities; {dict(Counter(f['severity'] for f in findings))}; {len(matches)} paradigm schemes/variants.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
