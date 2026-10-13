# User-supplied musical reference library

The user's *Voice Leading Rules Summary - Extended* is stored at `references/voice-leading-extended/source.pdf`. Its five PDF pages correspond to printed pages 12–16. It contains sections F (Contrapuntal Expansions Summary) and G (General Considerations); earlier sections are not present in the supplied file.

`catalog.json` contains source metadata, page locators, searchable pattern families, selected progression/soprano/bass summaries, and the eight general considerations. The original notation is retained in the PDF and five page images. The notation on the first four pages is largely embedded as images: text extraction alone would lose the paradigms.

## Using it

```powershell
.\.runtime\python\python.exe -m coach.reference "lower neighbor"
.\.runtime\python\python.exe -m coach.reference "lament"
.\.runtime\python\python.exe -m coach.reference "BACH"
```

Each match gives the relevant PDF/printed page, source figure identifier, and page image. Inspect that diagram before writing a realization. Asterisks identify required soprano lines in the source; paired “can swap” indications and alternate harmonizations must be read in context. Records retain uncertain or untranscribed details explicitly.

The library is automatically included in `teaching-packet.json` as musical reference data, with page provenance and scope limitations. A future model adapter can use it without mistaking the reference preferences for already implemented checker rules. `AGENTS.md` also directs future Codex work in this project to consult it for paradigm requests.

## Scope and provenance

These are the user's teaching conventions, not a new universal voice-leading standard. The material includes major/minor examples, chromatic patterns, pedals, contrapuntal expansions and incomplete chords beyond the checker's current domain. Source wording such as “most often,” “usually,” and “ALWAYS” is retained with its strength; preferences are not silently promoted to hard constraints.

The original author's identity and usage rights are not specified in the supplied excerpt. Store and use it for this user's project reference; do not classify it as CC0, redistribute it publicly, or add it to trusted training data on that assumption. Review status: visually inspected and indexed during implementation; exact notation remains authoritative. The index is not a fully transcribed, independently checked SATB corpus.

Persistence is local to this project. It does not change the assistant's global training, establish an account-wide memory, or make the material available automatically in unrelated chats.
