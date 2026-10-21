# User-supplied musical reference library

The user's *Voice Leading Rules Summary - Extended* has five PDF pages, corresponding to printed pages 12–16. It contains sections F (Contrapuntal Expansions Summary) and G (General Considerations); earlier sections are not present in the supplied file.

## What is published and what stays local

The original's author and usage rights are unknown, so the material is **not published**. These files live only on the user's computer and are listed in `.gitignore`:

| Local file (in `references/voice-leading-extended/`) | Contents |
|---|---|
| `source.pdf` | The original document (SHA-256 `b7562cfc…0fc3`) |
| `pages/page-1.png` … `page-5.png` | Page images; most notation is embedded as images |
| `catalog.json` | Full searchable index: all 50 patterns, progressions, soprano requirements and the eight general considerations |
| `build_catalog.py` | Rebuilds `catalog.json` |

The repository and the web interface carry only `public-catalog.json`: for the five paradigms the reviewer recognizes, each one's name, family and PDF/printed page and figure number, so reports can cite the source. `coach.reference.library()` uses the full local catalog when it exists and falls back to the public subset otherwise; review results are identical either way. After changing the recognized paradigms in `coach/review.py` or rebuilding the catalog, regenerate the subset:

```sh
python -m coach.reference --export-public
```

On a fresh clone, restore the four local items from the user's backup (`voice-leading-reference-backup.zip`) into `references/voice-leading-extended/`. Tests that need them skip when they are absent. They were also removed from the repository's git history.

## Using it

```powershell
.\.runtime\python\python.exe -m coach.reference "lower neighbor"
.\.runtime\python\python.exe -m coach.reference "lament"
.\.runtime\python\python.exe -m coach.reference "BACH"
```

With the local files present, each match gives the relevant PDF/printed page, source figure identifier, and page image. Inspect that diagram before writing a realization. Asterisks identify required soprano lines in the source; paired “can swap” indications and alternate harmonizations must be read in context. Records retain uncertain or untranscribed details explicitly.

The library is automatically included in `teaching-packet.json` as musical reference data, with page provenance and scope limitations. A future model adapter can use it without mistaking the reference preferences for already implemented checker rules. `AGENTS.md` also directs future Codex work in this project to consult it for paradigm requests.

## Scope and provenance

These are the user's teaching conventions, not a new universal voice-leading standard. The material includes major/minor examples, chromatic patterns, pedals, contrapuntal expansions and incomplete chords beyond the checker's current domain. Source wording such as “most often,” “usually,” and “ALWAYS” is retained with its strength; preferences are not silently promoted to hard constraints.

The original author's identity and usage rights are not specified in the supplied excerpt. Store and use it locally for this user's project reference; do not commit the originals or the full index, classify it as CC0, redistribute it publicly, or add it to trusted training data on that assumption. Review status: visually inspected and indexed during implementation; exact notation remains authoritative. The index is not a fully transcribed, independently checked SATB corpus.

Persistence is local to this project. It does not change the assistant's global training, establish an account-wide memory, or make the material available automatically in unrelated chats.
