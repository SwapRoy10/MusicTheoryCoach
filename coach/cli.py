import argparse
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

from .checker import check, constraints_for, errors
from .musicxml import read, write
from .repair import propose
from .report import markdown, save_json, teaching_packet
from .harmony import analyze


def main(argv=None):
    parser = argparse.ArgumentParser(description="Analyze a short SATB MusicXML score and recheck single-note repairs.")
    parser.add_argument("score", type=Path)
    parser.add_argument("--assignment", type=Path)
    parser.add_argument("--out", type=Path, default=Path("output"))
    parser.add_argument("--allow-soprano", action="store_true", help="Permit soprano edits in repair search")
    parser.add_argument("--pdf", action="store_true", help="Export input score with markings, explanations and a checked correction")
    parser.add_argument("--musescore", help="Path to MuseScore executable for PDF engraving")
    args = parser.parse_args(argv)
    try:
        if args.pdf:
            from .pdf_export import dependencies
            dependencies(args.musescore)
        raw = json.loads(args.assignment.read_text(encoding="utf-8-sig")) if args.assignment else {}
        if not isinstance(raw, dict):
            raise ValueError("Assignment must be a JSON object")
        score = read(args.score, raw.get("voice_map"))
        assignment = constraints_for(score, raw)
        if args.allow_soprano:
            assignment["preserve_soprano"] = False
        findings = check(score, assignment)
        proposals = propose(score, assignment)
        # Avoid leaving stale repairs from an older run or overwriting source files.
        if args.out.exists() and any(args.out.iterdir()):
            raise ValueError("Output directory must be empty or new; choose a fresh --out path")
        args.out.mkdir(parents=True, exist_ok=True)
        repairs = []
        for i, (candidate, details) in enumerate(proposals, 1):
            destination = args.out / f"repair-{i}.musicxml"
            write(candidate, destination)
            exported = read(destination)
            if errors(check(exported, assignment)):
                raise ValueError("Exported repair failed recheck")
            repairs.append({**details, "file": destination.name})
        save_json(args.out / "analysis.json", {"score": score.data(), "assignment": assignment,
                                                "harmony": analyze(score), "findings": findings, "repairs": repairs})
        save_json(args.out / "teaching-packet.json", teaching_packet(score, assignment, findings, repairs))
        (args.out / "report.md").write_text(markdown(score, assignment, findings, repairs), encoding="utf-8")
        if args.pdf:
            from .pdf_export import export_pdf
            pdf = export_pdf(args.score, score, assignment, findings, repairs, args.out, args.musescore)
            print(f"Annotated score PDF: {pdf}")
        print(f"{len(errors(findings))} violation(s); {len(repairs)} checked repair(s). Report: {args.out / 'report.md'}")
        return 0
    except (ValueError, TypeError, KeyError, OSError, ET.ParseError, ZeroDivisionError) as exc:
        print(f"Cannot analyze score: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
