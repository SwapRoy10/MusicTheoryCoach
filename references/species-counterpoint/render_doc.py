"""Render docs/SPECIES_COUNTERPOINT.md from rules.json, so the guide and the data never drift.

    python references/species-counterpoint/render_doc.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOC = HERE.parents[1] / "docs/SPECIES_COUNTERPOINT.md"
LABEL = {"required": "Required", "avoid": "Avoid", "preferred": "Preferred", "allowed": "Allowed"}


def render(data):
    sources = {s["id"]: s for s in data["sources"]}
    cite = lambda ids: ", ".join(f"[{i}](#source-{i})" for i in ids)
    lines = [f"# {data['title']}", "",
             "This is the project's reference for strict two-voice species counterpoint: the five exercise types "
             "Johann Joseph Fux codified in *Gradus ad Parnassum* (1725), as taught in current open textbooks. "
             "The data lives in [`references/species-counterpoint/rules.json`](../references/species-counterpoint/rules.json); "
             "this page is generated from it.", "",
             f"**Status:** {data['checker_status']}", "",
             "Rules are paraphrased. Textbooks disagree on several points, so each rule lists where its sources "
             "differ instead of picking one silently. Search from the command line with "
             "`python -m coach.reference cambiata` or list one species with `python -m coach.reference --species 4`.", "",
             "## Strength levels", "", "| Level | Meaning |", "|---|---|"]
    lines += [f"| {LABEL[k]} | {v} |" for k, v in data["strength_levels"].items()]
    lines += ["", "## The five species", "", "| | Species | What it adds |", "|---|---|---|"]
    lines += [f"| {s['id'] or '—'} | {s['name']} | {s['summary']} |" for s in data["species"]]
    shared = [r for r in data["rules"] if set(r["species"]) >= {1, 2, 3, 4, 5}]
    shared_ids = {r["id"] for r in shared}
    sections = [("Cantus firmus and melodic rules", [r for r in data["rules"] if 0 in r["species"] and r["id"] not in shared_ids or r["id"] in shared_ids and 0 in r["species"]]),
                ("Rules for every species (two voices)", [r for r in shared if 0 not in r["species"]])]
    sections += [(s["name"], [r for r in data["rules"] if s["id"] in r["species"] and r["id"] not in shared_ids])
                 for s in data["species"] if s["id"]]
    for title, rules in sections:
        lines += ["", f"## {title}", ""]
        for r in rules:
            lines.append(f"- **{LABEL[r['strength']]}** · {r['rule']} <sub>`{r['id']}` · {cite(r['sources'])}</sub>")
            for v in r.get("variants", []):
                lines.append(f"  - *{v['source']}:* {v['says']}")
            if r.get("note"):
                lines.append(f"  - *Note:* {r['note']}")
    lines += ["", "## Sources", ""]
    for s in data["sources"]:
        extra = f" {s['note']}" if s.get("note") else ""
        lines.append(f'- <a id="source-{s["id"]}"></a>**{s["id"]}**: {s["authors"]}, "{s["title"]}," *{s["work"]}*. '
                     f"[Link]({s['url']}). License: {s['license']}.{extra}")
    lines += ["", "Open Music Theory text is licensed CC BY-SA 4.0; rules drawn from it are paraphrased with attribution. "
              "Copyrighted course handouts are cited for their rules, not reproduced.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    DOC.write_text(render(json.loads((HERE / "rules.json").read_text(encoding="utf-8"))), encoding="utf-8")
    print(f"Wrote {DOC}")
