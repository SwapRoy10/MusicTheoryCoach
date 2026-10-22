# Music Theory Coach

**Try it online: [musictheorycoach.netlify.app](https://musictheorycoach.netlify.app/)** — upload a MusicXML chorale exercise and see the review marked on the score. Scores are analyzed in your browser and never uploaded.

A local first-milestone prototype for short SATB MusicXML exercises. It extracts a spelling-preserving timeline, reports supported voice-leading problems with note-level evidence, and searches for single-note repairs that pass a full recheck. Exported repairs are read back and checked again.

The [current annotated score](examples/reviews/testScore/annotated-score.pdf) demonstrates the latest format: named paradigm brackets, raised/stacked inversion figures, numeral corrections and findings. Its source and analysis are kept together in [examples/reviews/testScore](examples/reviews/testScore/README.md). Other reports are generated into ignored `output/` folders.

## Web interface

`web/` is a static site, deployed at [musictheorycoach.netlify.app](https://musictheorycoach.netlify.app/), that reviews a score in the browser and marks the results on the engraved score: errors in red, suggestions in amber, numbered findings above each system, named paradigm brackets, and the reviewed Roman numerals (with stacked figures) under each system. Clicking a finding, numeral or paradigm rings the notes involved; clicking a marked note opens its finding.

The analysis is this repository's own Python package running in the page through [Pyodide](https://pyodide.org), so scores are never uploaded and there is no server to run. [Verovio](https://www.verovio.org) engraves the reviewed MusicXML. The analyzer numbers `<note>` elements `n1`, `n2`, … in document order; the page writes those IDs into the MusicXML before engraving, and Verovio keeps them on the rendered notes, which links each finding to its notes.

```sh
python web/build.py --serve     # then open http://localhost:8000
```

`build.py` assembles `site/` (ignored by git) from `web/`, `coach/`, the public reference catalog (paradigm citations only) and four examples. `netlify.toml` runs the same build for deployment. The page uses the `coach.review` pipeline, so it accepts the same scores (see [Extended review](#extended-review-of-two-staff-chord-scores)). Pyodide and Verovio load from the jsDelivr CDN, so the first visit downloads roughly 15 MB.

## Set up a fresh checkout

Install Python 3.11 or newer and MuseScore for engraving, then run:

```sh
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[pdf]"
python -m unittest discover -s tests -v
```

The portable runtime on the original development machine is local only and is not included in the repository.

## Run on this machine

From this folder in PowerShell:

```powershell
.\run.ps1 -Score examples/varied-example.musicxml -Assignment examples/varied-assignment.json -Out output/my-analysis
```

The project contains a portable Python runtime under `.runtime/python` for this machine. It is ignored by version control. On another machine, install Python 3.11 or newer; the core has no third-party dependencies:

```sh
python run.py examples/varied-example.musicxml --assignment examples/varied-assignment.json --out output/my-analysis
python -m unittest discover -s tests -v
```

Use a new or empty output directory for each run. Existing output is never silently overwritten. Add `--allow-soprano` (PowerShell: `-AllowSoprano`) to allow soprano changes; otherwise repairs preserve it by default.

## Outputs

- `report.md`: readable findings, evidence and repair tradeoffs.
- `analysis.json`: every note, exact rational beat/duration, simultaneous-note timeline, structured assignment, findings and checked repairs.
- `repair-1.musicxml`, optionally `repair-2.musicxml`: normalized SATB scores. Open in notation software for engraving or playback.
- `teaching-packet.json`: provider-neutral grounding instructions and evidence for an existing language model. This version makes no model/API calls; its report uses deterministic explanations.

## Annotated score PDF

Add `-Pdf` to the PowerShell command (or `--pdf` to the Python command):

```powershell
.\run.ps1 -Score examples/varied-example.musicxml -Assignment examples/varied-assignment.json -Out output/my-pdf -Pdf
```

Open `output/my-pdf/annotated-score.pdf`. It shows the input score with red problem notes, amber advisory notes, numbered labels and explanations underneath. When a repair exists, a separate page shows the first checked candidate with the changed note in green. Long explanations can continue on additional pages. A marked note can be evidence for a transition, rather than itself being the note that needs changing.

Roman numerals appear beneath the bass staff in every measure and at chord changes within a measure. They describe the actual sounding notes; prescribed assignment harmony is checked separately. The corrected score gets its own recomputed numerals, and any changed harmony is explained.

Score labels use MuseScore's Campania Roman-numeral font: single inversion figures are raised, and paired figures are vertically stacked (6 over 5, 4 over 3, etc.). JSON and explanatory prose retain plain `ii6/5` notation for convenient searching and interchange.

The exporter annotates a copy of the **actual input MusicXML**, retaining its parts, note content and layout metadata. MuseScore re-engraves it, so exact spacing and line breaks may differ from the originating app. The original file is never edited. `annotated-original.musicxml` and, when available, `annotated-correction.musicxml` are also saved for opening in MuseScore. The PDF displays the first repair candidate; other candidates remain available as separate MusicXML files.

MuseScore and the optional Python packages `reportlab` and `pymupdf` are required; these are configured in this project's local runtime. On another machine:

```sh
python -m pip install -e ".[pdf]"
python run.py examples/varied-example.musicxml --assignment examples/varied-assignment.json --out output/my-pdf --pdf
```

If MuseScore is not found automatically, use `--musescore "path/to/MuseScore executable"` (PowerShell: `-MuseScore "path"`) or set `MUSESCORE_EXE`. Export relies on MuseScore's [documented command-line PDF conversion](https://musescore.org/en/print/book/export/html/38301).

The recommended `varied-example.musicxml` has I - ii6 - ii6/5 - V - I, with two half-note chords in measure 2 and a distinct dominant in measure 3. It has one parallel-fifth error. The first repair changes tenor D4 to C4 in measure 2, beat 1, changing ii6 to IV and removing the parallel. The earlier `deliberate-errors.musicxml` is retained as a regression fixture: two parallels plus a mismatch against its explicitly prescribed IV. Its actual measure-2 chord is ii6, not an inherently invalid sonority. `valid.musicxml` produces no findings with its assignment. These are synthetic exercises, not a held-out evaluation corpus.

## Accepted scores

Uncompressed `score-partwise` MusicXML, four to eight full 4/4 measures, one major key, concert pitch, half/whole notes and four monophonic voices. Name the four parts Soprano, Alto, Tenor, Bass (or S/A/T/B). For shared staves or differently named parts, supply an explicit mapping in the assignment:

```json
{
  "voice_map": {"P1:1": "S", "P1:2": "A", "P2:1": "T", "P2:2": "B"},
  "preserve_soprano": true,
  "require_tonic_ending": false,
  "instructions": "Leave the ending unresolved."
}
```

Mapping keys are MusicXML part ID plus voice ID, not staff number. Ambiguous mappings fail visibly. Backup/forward timing and inherited metadata are supported. Rests, ties, pickups, repeats, grace/cue notes, tuplets, dots, transposition, key changes, compressed `.mxl` and score-timewise are outside this version. Export preserves musical pitch/timing and measure labels, not source layout, lyrics, articulations or engraving.

## Assignment and harmony

See [examples/assignment.json](examples/assignment.json). Structured fields are enforced; free-text `instructions` are recorded but **not automatically interpreted or enforced**. `require_tonic_ending` defaults to false, so an intentionally unresolved ending is not rejected. When true it checks a complete root-position tonic chord, not a cadential formula.

Optional `harmony` entries prescribe a measure, beat, three or four spelled pitch names in root/third/fifth[/seventh] order, and expected bass pitch name. The first label must begin at the first measure's beat 1. Each remains active until the next label or score end, including beneath sustained notes. Unknown fields and malformed labels fail validation. A mismatch is an assignment error, not a claim that the pitch cannot form another valid chord.

Sounding harmony is identified independently, with or without prescribed labels. Identification requires all members of a complete diatonic triad or seventh chord, uses pitch spelling, and derives inversion from the lowest sounding pitch. Incomplete/chromatic/unmatched sonorities receive `?` and an uncertainty finding. Rootless interpretations, nonchord tones and contextual function are not inferred. Root-position triad doubling advice still requires supplied harmony. Seventh-resolution suggestions check descending stepwise motion when an identified seventh chord changes; retention and exceptional resolutions need contextual review. Theory references and hand-checked examples are in [docs/THEORY.md](docs/THEORY.md).

## Musical conventions and limits

See [docs/SPEC.md](docs/SPEC.md) for exact rule conventions. A passing repair means zero errors under these rules and the structured assignment. It does not certify every classroom convention, natural phrasing, or unrestricted assignment prose. Contextual leading-tone, direct-interval and doubling advice remains advisory.

Repair search changes one implicated note by at most an octave, retains timing, stays in the declared major key and respects voice ranges. Candidates are ranked by fewer advisory findings, then smaller pitch displacement. This is not phrase-quality optimization. If no candidate passes, the report says so. There may be fewer than two candidates.

## Tests and next milestones

```powershell
.\.runtime\python\python.exe -m unittest discover -s tests -v
```

Tests cover parallel/compound perfect intervals, stationary and contrary motion, enharmonic spelling, asynchronous entries, timing, range/spacing/crossing/overlap, supplied harmony, ending requirements, parser rejection, repairs and export round trips. The two authored fixtures are CC0; see [examples/README.md](examples/README.md). The chorale mentioned in the supplied outline was not attached.

Next: review real score fixtures with a musician, add a model adapter with checked structured edits, expand to multi-note revision, add an interactive notation/playback UI, and collect reviewed examples with rights and provenance. Annotated PDF export, complete diatonic seventh-chord identification, and basic seventh-resolution advice are available now. Contextual cadence/function analysis, musical-preference ranking, training and fine-tuning are not implemented. See [docs/ROADMAP.md](docs/ROADMAP.md).

The adapter is intentionally small and uses the standard library. Its duration/backup interpretation follows the [W3C MusicXML 4.0 duration reference](https://www.w3.org/2021/06/musicxml40/musicxml-reference/elements/duration/). A future music21 adapter can replace it behind the existing score model when the supported musical scope expands.

## Personal reference library

The supplied *Voice Leading Rules Summary - Extended* is visually indexed and searchable on the user's computer, but its PDF, page images and full index are not published: the repository keeps only `public-catalog.json`, with page and figure citations for the paradigms the reviewer recognizes. See [docs/REFERENCE_LIBRARY.md](docs/REFERENCE_LIBRARY.md). With the local files present, search paradigms with `python -m coach.reference "BACH"` or `python -m coach.reference "lament"`. Source conventions beyond the checker's domain are explicitly marked as reference guidance.

## Extended review of two-staff chord scores

When four aligned pitches are written as chords on two staves, and you explicitly want voices assigned bottom-up at every sonority, use the extended reviewer. It accepts `.mxl` as well as uncompressed MusicXML and reviews longer 4/4 major-key passages:

```powershell
.\.runtime\python\python.exe -m coach.review "C:\path\to\score.mxl" --out output/my-score-review --pdf
```

The reviewer preserves an input snapshot, keeps the original notation/labels, and creates `annotated-score.pdf`, `report.md` and `analysis.json`. Entirely silent trailing bars are omitted from the review engraving and documented. Voice assignment requires exactly four aligned pitches with equal durations at each onset; it cannot detect voice crossing because pitch ranking defines the voices in order. Ties, pickups, key changes and nonaligned rhythms are outside this adapter.

It compares chord labels encoded as MusicXML lyrics, recognizes a small set of reference paradigm schemes using actual bass/soprano motion, distinguishes starred-soprano variants, and interprets root/third/seventh sonorities with omitted fifths explicitly as contextual. Source paradigms outside these recognizers still need direct musical review; matching a Roman-numeral sequence alone is insufficient. The regular `run.py` prototype retains its original four-to-eight-measure convention.
