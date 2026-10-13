# First-milestone specification

**Goal:** accept a short, explicitly voiced SATB MusicXML exercise and return inspectable notes, exact-location findings and at least one rechecked correction on the deliberate-error fixture. Do not present unsupported interpretation as fact.

**Domain:** 4–8 full measures in 4/4, a single major key, concert pitch, half/whole notes, complete diatonic triads and seventh chords. Four named parts or an explicit part/voice map. Beat 1 is the first quarter-note beat. Measure labels are preserved verbatim; ordering uses score position. Timing uses exact fractions. Durations and pitch alterations come from MusicXML, not visual accidental glyphs.

## Hard rules

| Check | Convention |
|---|---|
| Parallel perfect intervals | Check all six voice pairs across successive sounding frames. Both voices must move in the same direction and both intervals must be spelled perfect fifths or octave/unison-class intervals. Compound intervals reduce to the same class. Stationary/oblique and contrary motion are excluded. |
| Crossing | An upper voice sounding strictly below its adjacent lower voice. Equal pitches are permitted. |
| Adjacent overlap | A new upper note below the lower voice's previous pitch, or new lower note above the upper voice's previous pitch. Equality is permitted. |
| Ranges | S C4–G5, A G3–D5, T C3–G4, B E2–C4, inclusive; classroom defaults, not physiological limits. |
| Spacing | S–A and A–T at most an octave. No T–B spacing limit. |
| Rhythm and meter | Every voice fills each measure continuously; whole note at beat 1 or half notes at beats 1 and 3. |
| Key | Every note uses the declared major key's diatonic spelling. |
| Supplied harmony | Notes must belong to the prescribed triad/seventh chord; bass must match its supplied inversion. These are assignment checks; actual sounding harmony is identified independently. |
| Required ending | Optional complete root-position tonic triad. This does not prove an authentic cadence. |

## Advisory rules

Leading tones that move without rising a semitone generate suggestions; held notes and final notes are exempt. Context, especially inner-voice exceptions, needs review. Direct outer perfect intervals generate suggestions for similar motion and a soprano leap greater than a diatonic step; parallels are reported separately. Supplied root-position triads preferably double the root; omitted chord members generate suggestions. Inversion-specific doubling, doubled leading tones, cadence strength and melodic-leap recovery require further work.

## Evidence and repair contract

Complete diatonic triads and seventh chords receive Roman numerals with inversion figures. Identification uses exact spelled pitch sets and the lowest sounding pitch. Unmatched sonorities receive uncertainty, not an invented chord. See [THEORY.md](THEORY.md). Chordal sevenths that move at a chord change without descending by step generate advisory findings; held sevenths, voice transfers, and exceptions need contextual review. Repairs may change the harmony when no progression is prescribed; PDF numerals are recomputed and those changes are disclosed. Repairs are rejected if they turn an identified event into an unidentified sonority.

Each finding has a rule ID, severity (`error`, `suggestion`, `uncertain`), measure, beat, voices, and the relevant original notes including their own onset/duration. Harmonic checks can occur while a note is held; a finding's beat may therefore differ from that note's onset. The original timeline remains separate from findings and textual explanations.

Single-note repairs retain durations, voice IDs, key, meter and measure labels. Soprano preservation is the default. Every candidate is checked against the whole score and structured assignment. Accepted candidates have zero hard-rule errors; advisory findings remain visible. MusicXML export is re-imported and checked before the CLI reports success. The source file is never edited.

## Acceptance evidence

1. The valid authored four-measure fixture has no findings when supplied its harmony.
2. The error fixture produces S–T parallel fifths at m. 2 beat 1 and m. 3 beat 1, plus a tenor chord-membership error at m. 2 beat 1.
3. Changing m. 2 tenor D4 to C4 passes all supported rules, preserves soprano, and survives MusicXML round trip.
4. Regression examples exercise motion direction, compound intervals, enharmonic spelling, explicit voice maps and unsupported notation.

**Third passage:** the user's prior chorale is pending because no MusicXML for it was included. Synthetic regression cases are not a substitute for musician-reviewed real-world evaluation.
