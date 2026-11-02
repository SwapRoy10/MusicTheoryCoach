# Two-voice species counterpoint rules

This is the project's reference for strict two-voice species counterpoint: the five exercise types Johann Joseph Fux codified in *Gradus ad Parnassum* (1725), as taught in current open textbooks. The data lives in [`references/species-counterpoint/rules.json`](../references/species-counterpoint/rules.json); this page is generated from it.

**Status:** Reference only. The automatic checker does not yet test species exercises.

Rules are paraphrased. Textbooks disagree on several points, so each rule lists where its sources differ instead of picking one silently. Search from the command line with `python -m coach.reference cambiata` or list one species with `python -m coach.reference --species 4`.

## Strength levels

| Level | Meaning |
|---|---|
| Required | The sources state it as a must or never. |
| Avoid | A strong caution; occasional exceptions occur in good exercises. |
| Preferred | Style guidance that makes a better exercise. |
| Allowed | An explicit permission, often relaxing a stricter rule. |

## The five species

| | Species | What it adds |
|---|---|---|
| — | Cantus firmus | The given melody, all whole notes, that each exercise is written against. |
| 1 | First species | Note against note (1:1): one whole note per cantus note, every interval consonant. |
| 2 | Second species | Two half notes per cantus note (2:1); dissonance enters as the weak-beat passing tone. |
| 3 | Third species | Four quarter notes per cantus note (4:1); adds neighbor tones, the double neighbor and the nota cambiata. |
| 4 | Fourth species | Syncopation: half notes tied across the bar line, producing prepared suspensions that resolve down by step. |
| 5 | Fifth species | Florid counterpoint: a free mixture of the first four species, with occasional eighth-note pairs. |

## Cantus firmus and melodic rules

- **Preferred** · A cantus firmus is about 8 to 16 notes long, all whole notes. <sub>`cf-length` · [omt2-intro](#source-omt2-intro)</sub>
- **Required** · The cantus firmus begins and ends on the final (do). <sub>`cf-begin-end` · [omt2-intro](#source-omt2-intro)</sub>
- **Required** · The cantus approaches its final by step, usually re–do and sometimes ti–do. <sub>`cf-approach-final` · [omt2-intro](#source-omt2-intro)</sub>
  - *omt2-s4:* Fourth species needs a cantus ending re–do; a ti–do ending does not allow the suspension cadence.
- **Required** · Melodic intervals are consonant: steps, thirds, perfect fourths, perfect fifths, the octave and the ascending minor sixth. Augmented and diminished intervals, sevenths, other sixths and anything larger than an octave are not used. <sub>`mel-melodic-consonance` · [omt2-intro](#source-omt2-intro), [mt21c](#source-mt21c)</sub>
  - *wikipedia:* An ascending minor sixth should be followed by downward motion.
  - *omt2-intro:* Treats the ascending minor sixth as 'perhaps' acceptable rather than freely available.
- **Avoid** · Do not outline a dissonant interval (a tritone, augmented or diminished interval, or a seventh) between melodic turning points. <sub>`mel-no-dissonant-outline` · [omt2-intro](#source-omt2-intro), [mt21c](#source-mt21c)</sub>
  - *wikipedia:* Phrases it as avoiding tritones and sevenths within three notes.
- **Required** · After a leap of a fourth or larger, move by step in the opposite direction. <sub>`mel-leap-recovery` · [omt2-intro](#source-omt2-intro), [omt2-s3](#source-omt2-s3)</sub>
- **Avoid** · Use no more than two leaps in a row, and do not make consecutive leaps in the same direction (except outlining a consonant triad, as in Fux's F-mode cantus). <sub>`mel-consecutive-leaps` · [omt2-intro](#source-omt2-intro), [wikipedia](#source-wikipedia)</sub>
- **Preferred** · Move mostly by step, with occasional small leaps and rare large ones. <sub>`mel-mostly-steps` · [omt2-intro](#source-omt2-intro), [omt2-s1](#source-omt2-s1)</sub>
- **Preferred** · Keep the cantus within a tenth, and usually within an octave. <sub>`mel-range` · [omt2-intro](#source-omt2-intro)</sub>
- **Preferred** · Give each line one high point that is not repeated, not at the end, and ideally reached by leap. Later species may add one or two secondary high points. <sub>`mel-single-climax` · [omt2-intro](#source-omt2-intro), [omt2-s2](#source-omt2-s2), [omt2-s3](#source-omt2-s3)</sub>
- **Required** · The leading tone moves to the final. In modes with a whole step below the final, raise the seventh at the cadence (musica ficta), except in Phrygian. <sub>`mel-leading-tone` · [omt2-intro](#source-omt2-intro), [mt21c](#source-mt21c), [wikipedia](#source-wikipedia)</sub>
  - *Note:* Hutchinson names the raised notes: F♯ in G mixolydian, C♯ in D dorian, G♯ in A aeolian.
- **Avoid** · Do not repeat motives or melodic patterns within the cantus. <sub>`mel-no-motives` · [omt2-intro](#source-omt2-intro)</sub>

## Rules for every species (two voices)

- **Avoid** · The two lines should not reach their climaxes at the same time. <sub>`mel-climaxes-apart` · [omt2-intro](#source-omt2-intro), [omt2-s1](#source-omt2-s1)</sub>
- **Required** · Begin on a perfect consonance. Above the cantus the first note is do or sol (unison, fifth or octave); below the cantus it must be do (unison or octave). <sub>`comb-begin` · [omt2-s1](#source-omt2-s1), [rothgeb](#source-rothgeb), [mt21c](#source-mt21c)</sub>
  - *mt21c:* Simplifies this to beginning on an octave or unison.
  - *omt2-s1:* Explains that sol below the cantus would form a fourth with it, and fa would be heard as do–sol.
- **Required** · End on a unison or octave with do in both voices, approached by contrary stepwise motion: ti–do against re–do. The penultimate interval is therefore a sixth (counterpoint above) or a third or tenth (counterpoint below). <sub>`comb-clausula-vera` · [omt2-s1](#source-omt2-s1), [rothgeb](#source-rothgeb), [mt21c](#source-mt21c)</sub>
- **Required** · Consonances are the unison, thirds, the perfect fifth, sixths, the octave and their compounds. Seconds, sevenths, the tritone and the perfect fourth (between the two voices) are dissonant. <sub>`comb-vertical-consonance` · [omt2-s1](#source-omt2-s1), [rothgeb](#source-rothgeb), [mt21c](#source-mt21c)</sub>
  - *Note:* Where each later species may place a dissonance is set out in its own rules.
- **Required** · No parallel unisons, fifths or octaves, including compound forms (a fifth to a twelfth counts). <sub>`comb-no-parallel-perfect` · [omt2-s1](#source-omt2-s1), [mt21c](#source-mt21c), [wikipedia](#source-wikipedia)</sub>
- **Required** · Never place two perfect consonances of the same size in a row, even by contrary motion. A different perfect interval next (octave then fifth) is allowed but best avoided. <sub>`comb-no-consecutive-same-perfect` · [omt2-s1](#source-omt2-s1)</sub>
- **Avoid** · Use no more than three of the same imperfect consonance (thirds or sixths) in a row. <sub>`comb-imperfect-run` · [omt2-s1](#source-omt2-s1), [mt21c](#source-mt21c)</sub>
- **Preferred** · Prefer imperfect consonances to perfect ones everywhere except the first and last intervals. <sub>`comb-prefer-imperfect` · [omt2-s1](#source-omt2-s1), [rothgeb](#source-rothgeb)</sub>
- **Preferred** · Favor contrary motion and vary the types of motion through the exercise. <sub>`comb-contrary-motion` · [omt2-s1](#source-omt2-s1), [wikipedia](#source-wikipedia)</sub>
- **Avoid** · Avoid similar motion combined with leaps, especially large ones. <sub>`comb-no-similar-leaps` · [omt2-s1](#source-omt2-s1)</sub>
- **Avoid** · Avoid voice crossing and voice overlap. <sub>`comb-no-crossing-overlap` · [omt2-s1](#source-omt2-s1)</sub>
- **Avoid** · Keep the voices within an octave where possible, exceed a tenth only briefly when unavoidable, and never exceed a twelfth. <sub>`comb-spacing` · [omt2-s1](#source-omt2-s1), [wikipedia](#source-wikipedia)</sub>

## First species

- **Required** · Approach a perfect consonance only by contrary or oblique motion, never by similar motion (no direct or hidden fifths and octaves). <sub>`comb-no-direct-perfect` · [omt2-s1](#source-omt2-s1), [rothgeb](#source-rothgeb), [mt21c](#source-mt21c), [wikipedia](#source-wikipedia)</sub>
- **Required** · One whole note against each whole note of the cantus. <sub>`s1-rhythm` · [omt2-s1](#source-omt2-s1), [rothgeb](#source-rothgeb)</sub>
- **Required** · Every vertical interval is consonant. <sub>`s1-all-consonant` · [omt2-s1](#source-omt2-s1), [rothgeb](#source-rothgeb), [mt21c](#source-mt21c)</sub>
- **Required** · Use the unison only for the first and last intervals. <sub>`s1-unison` · [omt2-s1](#source-omt2-s1), [rothgeb](#source-rothgeb), [wikipedia](#source-wikipedia)</sub>
- **Avoid** · Avoid repeating a note; at most one repetition in the exercise. <sub>`s1-repeated-notes` · [omt2-s1](#source-omt2-s1), [mt21c](#source-mt21c)</sub>
  - *rothgeb:* Allows the added voice to repeat a tone in first species.

## Second species

- **Required** · Two half notes against each cantus note; the final bar is a whole note. <sub>`s2-rhythm` · [omt2-s2](#source-omt2-s2), [rothgeb](#source-rothgeb), [mt21c](#source-mt21c)</sub>
- **Allowed** · The first bar may begin with a half rest followed by a half note, or with two half notes. <sub>`s2-start` · [omt2-s2](#source-omt2-s2), [rothgeb](#source-rothgeb), [mt21c](#source-mt21c)</sub>
  - *omt2-s2:* Calls the opening half rest 'often preferable'.
- **Required** · Every downbeat is consonant; prefer thirds and sixths there and avoid the unison. <sub>`s2-downbeat-consonant` · [omt2-s2](#source-omt2-s2), [rothgeb](#source-rothgeb), [mt21c](#source-mt21c)</sub>
- **Required** · A weak-beat dissonance must be a passing tone: approached by step and left by step in the same direction. No other dissonance is permitted. <sub>`s2-passing-only` · [omt2-s2](#source-omt2-s2), [rothgeb](#source-rothgeb), [mt21c](#source-mt21c)</sub>
  - *wikipedia:* Also lists neighbor and escape tones for second species. The textbooks cited here do not allow them.
- **Preferred** · A consonant weak beat should fit a recognised pattern: consonant passing tone, consonant neighbor, substitution, skipped passing tone, interval subdivision, change of register, or delay of melodic progression. <sub>`s2-consonant-weak-beats` · [omt2-s2](#source-omt2-s2)</sub>
- **Required** · Motion from a weak beat into the next downbeat follows first-species rules: no parallel perfect intervals, and perfect consonances approached only by contrary motion. <sub>`s2-barline` · [omt2-s2](#source-omt2-s2), [mt21c](#source-mt21c), [rothgeb](#source-rothgeb)</sub>
- **Required** · Do not begin consecutive bars with the same perfect interval. <sub>`s2-downbeat-perfect` · [omt2-s2](#source-omt2-s2), [rothgeb](#source-rothgeb)</sub>
  - *mt21c:* Forbids consecutive downbeat octaves, but allows consecutive downbeat fifths when a leap of a fourth follows the first fifth.
- **Avoid** · Do not begin more than three bars in a row with the same imperfect consonance. <sub>`s2-downbeat-imperfect-run` · [omt2-s2](#source-omt2-s2)</sub>
- **Avoid** · Consecutive downbeat notes should not form a dissonant melodic interval (except after an octave leap that steps back). <sub>`s2-downbeat-melody` · [omt2-s2](#source-omt2-s2)</sub>
- **Allowed** · Direct fifths and octaves between successive downbeats are acceptable, because the intervening note weakens them. <sub>`s2-direct-between-downbeats` · [omt2-s2](#source-omt2-s2)</sub>
  - *rothgeb:* Requires every downbeat perfect consonance to be approached by contrary or oblique motion.
- **Preferred** · Leap from strong to weak beat within the bar rather than across the bar line. <sub>`s2-leap-placement` · [omt2-s2](#source-omt2-s2)</sub>
- **Required** · Do not repeat a note, within the bar or across the bar line. <sub>`s2-no-repeats` · [rothgeb](#source-rothgeb), [mt21c](#source-mt21c)</sub>
  - *mt21c:* States the prohibition only across bar lines.
- **Allowed** · A unison may occur on the weak beat; not on a downbeat except at the start and end. <sub>`s2-unison` · [omt2-s2](#source-omt2-s2), [rothgeb](#source-rothgeb)</sub>
- **Allowed** · The penultimate bar may be a whole note or two half notes, ending in the clausula vera. <sub>`s2-penultimate` · [omt2-s2](#source-omt2-s2), [rothgeb](#source-rothgeb)</sub>
  - *mt21c:* Gives fixed formulas: with the cantus below, a fifth then a sixth into the octave; with the cantus above, a fifth then a third; Phrygian has its own formula.

## Third species

- **Required** · Four quarter notes against each cantus note (the first bar may open with a quarter rest); the final bar is a whole note. <sub>`s3-rhythm` · [omt2-s3](#source-omt2-s3), [rothgeb](#source-rothgeb), [mt21c](#source-mt21c)</sub>
- **Required** · Beat 1 is always consonant and never a unison; prefer imperfect consonances there. <sub>`s3-downbeat-consonant` · [omt2-s3](#source-omt2-s3), [rothgeb](#source-rothgeb), [mt21c](#source-mt21c)</sub>
- **Required** · Dissonance may fall only on beats 2, 3 or 4, and only as a passing tone, a neighbor tone, part of a double neighbor, or the second note of a nota cambiata. <sub>`s3-dissonance-types` · [omt2-s3](#source-omt2-s3), [rothgeb](#source-rothgeb)</sub>
  - *mt21c:* Lists only passing tones and the cambiata as allowed dissonances.
- **Required** · Approach and leave every dissonance by step, except within the double neighbor and the nota cambiata. <sub>`s3-dissonance-by-step` · [omt2-s3](#source-omt2-s3), [rothgeb](#source-rothgeb)</sub>
- **Allowed** · Two dissonant passing tones in a row are acceptable when the line keeps moving by step in one direction off the downbeats (for example P4 then d5). <sub>`s3-double-passing` · [omt2-s3](#source-omt2-s3)</sub>
- **Required** · The nota cambiata is five notes from downbeat to downbeat: a step, a leap of a third in the same direction, then two steps back. Only the second note is dissonant; notes 1, 3 and 5 are consonant. <sub>`s3-nota-cambiata` · [omt2-s3](#source-omt2-s3), [rothgeb](#source-rothgeb), [mt21c](#source-mt21c)</sub>
- **Required** · In a double neighbor, beats 1 and 4 share a pitch, beats 2 and 3 are the steps above and below, and the line continues by step into the next downbeat. <sub>`s3-double-neighbor` · [omt2-s3](#source-omt2-s3)</sub>
- **Required** · Every melodic leap connects two consonant notes. <sub>`s3-leaps-consonant` · [omt2-s3](#source-omt2-s3)</sub>
- **Preferred** · Place leaps within the bar rather than across the bar line, and move mostly by step. <sub>`s3-leap-placement` · [omt2-s3](#source-omt2-s3)</sub>
- **Required** · Beat 4 into the next downbeat follows first-species rules; no parallel perfect intervals from beat 3 or 4 into the downbeat. <sub>`s3-barline` · [omt2-s3](#source-omt2-s3), [rothgeb](#source-rothgeb), [mt21c](#source-mt21c)</sub>
- **Required** · If a downbeat is a fifth, beats 3 and 4 of the previous bar must not be fifths; if a downbeat is an octave, beats 2, 3 and 4 of the previous bar must not be octaves. Intervening notes do not cancel parallel fifths or octaves. <sub>`s3-downbeat-parallels` · [omt2-s3](#source-omt2-s3), [rothgeb](#source-rothgeb)</sub>
  - *rothgeb:* States only that beat 3 and the next beat 1 may not form parallel perfect consonances.
  - *mt21c:* Forbids direct fifths and octaves into any downbeat.
- **Required** · No three consecutive bars may begin with the same perfect interval; two in a row are acceptable in third species, and direct fifths and octaves between successive downbeats are allowed. <sub>`s3-downbeat-perfect-run` · [omt2-s3](#source-omt2-s3)</sub>
  - *mt21c:* Does not allow direct fifths and octaves into a downbeat.
- **Avoid** · Do not begin more than three bars in a row with the same imperfect consonance. <sub>`s3-downbeat-imperfect-run` · [omt2-s3](#source-omt2-s3)</sub>
- **Required** · Do not repeat a note within the bar or across the bar line. <sub>`s3-no-repeats` · [rothgeb](#source-rothgeb), [mt21c](#source-mt21c)</sub>
- **Allowed** · A unison is allowed on any beat except beat 1. <sub>`s3-unison` · [omt2-s3](#source-omt2-s3), [rothgeb](#source-rothgeb)</sub>
- **Required** · The last quarter of the penultimate bar is ti over re (or re under ti), leading by contrary step into the final unison or octave. <sub>`s3-penultimate` · [omt2-s3](#source-omt2-s3), [rothgeb](#source-rothgeb)</sub>
  - *mt21c:* Gives fixed penultimate-bar figures, including a cambiata-based one.

## Fourth species

- **Required** · Begin with a half rest; each weak-beat half note is tied over the bar line to the next downbeat, so the counterpoint is offset from the cantus by a half note. <sub>`s4-rhythm` · [omt2-s4](#source-omt2-s4), [omt1-s4](#source-omt1-s4), [rothgeb](#source-rothgeb), [mt21c](#source-mt21c)</sub>
- **Required** · Because each voice moves while the other holds, pure fourth species proceeds entirely in oblique motion. <sub>`s4-oblique-motion` · [omt2-s4](#source-omt2-s4), [omt1-s4](#source-omt1-s4)</sub>
- **Required** · The weak-beat note that prepares a tie is always consonant. <sub>`s4-preparation` · [omt2-s4](#source-omt2-s4), [rothgeb](#source-rothgeb), [mt21c](#source-mt21c)</sub>
- **Required** · A dissonant suspension on the downbeat resolves down by step to a consonance on the weak beat. <sub>`s4-resolution` · [omt2-s4](#source-omt2-s4), [omt1-s4](#source-omt1-s4), [rothgeb](#source-rothgeb), [mt21c](#source-mt21c)</sub>
- **Preferred** · Above the cantus, the dissonant suspensions are 7–6 and 4–3 (preferred, resolving to imperfect consonances) and 9–8. <sub>`s4-suspensions-above` · [omt2-s4](#source-omt2-s4), [omt1-s4](#source-omt1-s4)</sub>
  - *mt21c:* Allows only 7–6 and 4–3 above; 9–8 and 2–1 are not allowed.
  - *rothgeb:* Allows 2–1, 4–3, 7–6 and 9–8 above.
- **Preferred** · Below the cantus, 2–3 is the main dissonant suspension; 4–5 is also available. <sub>`s4-suspensions-below` · [omt2-s4](#source-omt2-s4), [omt1-s4](#source-omt1-s4)</sub>
  - *rothgeb:* Allows 2–3, 4–5 and 9–10 below.
  - *omt2-s4:* Mentions only 2–3 below as a dissonant suspension.
- **Avoid** · Avoid the 7–8 suspension below the cantus. <sub>`s4-no-7-8-below` · [omt1-s4](#source-omt1-s4), [rothgeb](#source-rothgeb)</sub>
  - *omt1-s4:* Possible in theory but sounds less pleasing.
  - *rothgeb:* Calls it not usable.
- **Allowed** · A tied note that is consonant on the downbeat (such as 5–6 or 6–5) is a consonant syncope; it may be left by step or leap. <sub>`s4-consonant-syncope` · [omt2-s4](#source-omt2-s4), [mt21c](#source-mt21c)</sub>
- **Preferred** · Use dissonant suspensions as often as possible; they are the point of the species. <sub>`s4-max-suspensions` · [omt2-s4](#source-omt2-s4), [omt1-s4](#source-omt1-s4)</sub>
- **Avoid** · Use no more than three suspensions of the same kind in a row, and never two 9–8, 4–5 or 6–5 in a row (their resolutions make consecutive perfect intervals). <sub>`s4-suspension-runs` · [omt2-s4](#source-omt2-s4), [omt1-s4](#source-omt1-s4)</sub>
- **Avoid** · Avoid fifths or octaves on consecutive weak beats ('after-beat' parallels); a dissonant suspension between them does not hide them. <sub>`s4-after-beat-parallels` · [omt2-s4](#source-omt2-s4), [omt1-s4](#source-omt1-s4), [rothgeb](#source-rothgeb)</sub>
- **Preferred** · Suspensions pull the line downward; include one or two upward leaps (from a downbeat consonance) to keep it in range. <sub>`s4-upward-leaps` · [omt2-s4](#source-omt2-s4), [omt1-s4](#source-omt1-s4)</sub>
- **Allowed** · Break species (move without a tie, following second-species rules) only when neither a dissonant suspension nor a consonant tie works; resume ties at once, and do it at most once in an exercise. <sub>`s4-breaking-species` · [omt2-s4](#source-omt2-s4), [omt1-s4](#source-omt1-s4)</sub>
  - *rothgeb:* Allows it once or twice; if breaking after a weak-beat unison, leave the unison by contrary motion.
- **Required** · Do not repeat a tone (other than the tie itself). <sub>`s4-no-repeats` · [rothgeb](#source-rothgeb)</sub>
- **Required** · The cantus must end re–do. The penultimate bar holds a tied do resolving to ti: a 7–6 suspension above or a 2–3 below. The final note is a whole-note do. <sub>`s4-cadence` · [omt2-s4](#source-omt2-s4), [omt1-s4](#source-omt1-s4), [rothgeb](#source-rothgeb), [mt21c](#source-mt21c)</sub>

## Fifth species

- **Preferred** · Combine the four earlier species freely, so that no single species dominates. <sub>`s5-mixture` · [omt2-s5](#source-omt2-s5), [mt21c](#source-mt21c), [wikipedia](#source-wikipedia)</sub>
- **Required** · While a passage uses a given species, that species' rules apply, including when entering and leaving it. <sub>`s5-species-rules-apply` · [magnuson](#source-magnuson)</sub>
- **Preferred** · Keep runs short: whole notes only in the last bar, no more than three half notes in succession, no more than eight quarters, and no more than two tied pairs. <sub>`s5-run-limits` · [magnuson](#source-magnuson)</sub>
  - *cmu-s5:* Stays in one note value for no more than two bars.
- **Required** · Place longer values on stronger beats; a quarter note is never tied to a following half note. <sub>`s5-strong-beat-weight` · [magnuson](#source-magnuson), [cmu-s5](#source-cmu-s5)</sub>
- **Required** · Eighth notes come in stepwise pairs, approached and left by step, on a weak quarter (the second or fourth quarter of the bar), at most one pair per bar. <sub>`s5-eighths` · [omt2-s5](#source-omt2-s5), [magnuson](#source-magnuson), [cmu-s5](#source-cmu-s5)</sub>
  - *cmu-s5:* Eighths may sit on the second or the fourth quarter, but not both in one bar.
- **Preferred** · Decorate most suspension resolutions (for example with an anticipation or a turn); the decorating note is consonant, and the same decoration should not be used twice in a row. <sub>`s5-decorated-suspensions` · [omt2-s5](#source-omt2-s5), [cmu-s5](#source-cmu-s5)</sub>
- **Preferred** · Begin slowly with longer values and stepwise motion, then accelerate toward the climax; avoid rhythmic patterns that chop the line into segments. <sub>`s5-rhythmic-flow` · [cmu-s5](#source-cmu-s5)</sub>
- **Preferred** · Begin with a perfect consonance, preferably after a rest in second- or fourth-species rhythm. <sub>`s5-begin` · [omt2-s5](#source-omt2-s5), [cmu-s5](#source-cmu-s5)</sub>
- **Required** · End with a clausula vera, usually as a fourth-species suspension cadence with a decorated resolution. <sub>`s5-cadence` · [omt2-s5](#source-omt2-s5), [magnuson](#source-magnuson), [cmu-s5](#source-cmu-s5)</sub>

## Sources

- <a id="source-omt2-intro"></a>**omt2-intro**: Mark Gotham et al., "Introduction to Species Counterpoint," *Open Music Theory 2e*. [Link](https://human.libretexts.org/Bookshelves/Music/Music_Theory/Open_Music_Theory_2e_(Gotham_et_al.)/02%3A_Counterpoint_and_Galant_Schemas/2.01%3A_Introduction_to_Species_Counterpoint). License: CC BY-SA 4.0.
- <a id="source-omt2-s1"></a>**omt2-s1**: Mark Gotham, Kris Shaffer, "First-Species Counterpoint," *Open Music Theory 2e*. [Link](https://viva.pressbooks.pub/openmusictheory/chapter/first-species-counterpoint/). License: CC BY-SA 4.0.
- <a id="source-omt2-s2"></a>**omt2-s2**: Mark Gotham, Kris Shaffer, "Second-Species Counterpoint," *Open Music Theory 2e*. [Link](https://viva.pressbooks.pub/openmusictheory/chapter/second-species-counterpoint/). License: CC BY-SA 4.0.
- <a id="source-omt2-s3"></a>**omt2-s3**: Mark Gotham, Kris Shaffer, "Third-Species Counterpoint," *Open Music Theory 2e*. [Link](https://viva.pressbooks.pub/openmusictheory/chapter/third-species-counterpoint/). License: CC BY-SA 4.0.
- <a id="source-omt2-s4"></a>**omt2-s4**: Mark Gotham, Kris Shaffer, "Fourth-Species Counterpoint," *Open Music Theory 2e*. [Link](https://viva.pressbooks.pub/openmusictheory/chapter/fourth-species-counterpoint/). License: CC BY-SA 4.0.
- <a id="source-omt2-s5"></a>**omt2-s5**: Mark Gotham, Kris Shaffer, "Fifth-Species Counterpoint," *Open Music Theory 2e*. [Link](https://viva.pressbooks.pub/openmusictheory/chapter/fifth-species-counterpoint/). License: CC BY-SA 4.0.
- <a id="source-omt1-s4"></a>**omt1-s4**: Robin Wharton, Kris Shaffer (eds.), "Composing a Fourth-Species Counterpoint," *Open Music Theory 1e*. [Link](https://human.libretexts.org/Bookshelves/Music/Music_Theory/Open_Music_Theory_1e_(Wharton_and_Shaffer_Eds)/02%3A_Voice-Leading_and_Model_Composition/2.06%3A_Strict_Two-Voice_Composition_-_Composing_a_Fourth-Species_Counterpoint). License: CC BY-SA.
- <a id="source-mt21c"></a>**mt21c**: Robert Hutchinson, "Introduction to Counterpoint (ch. 30)," *Music Theory for the 21st-Century Classroom*. [Link](https://musictheory.pugetsound.edu/mt21c/FirstSpecies.html). License: GNU FDL (per the book). Rules are 'slightly modified and simplified' from Fux. Species pages: FirstSpecies, SecondSpecies, ThirdSpecies, FourthSpecies, FifthSpecies.html
- <a id="source-rothgeb"></a>**rothgeb**: John Rothgeb, "Music 103 species handouts (2 voices)," *UCSB course materials*. [Link](https://rothfarb.faculty.music.ucsb.edu/courses/103/First_Species(2v).html). License: Copyright; cited, not copied. Handouts for first through fourth species at the same path (Second_Species(2v).html etc.).
- <a id="source-magnuson"></a>**magnuson**: Phillip Magnuson, "Species V in Two Voices," *Sound Patterns*. [Link](https://tobyrush.com/soundpatterns/speciesctpt/spV.html). License: CC BY 3.0.
- <a id="source-cmu-s5"></a>**cmu-s5**: Not named on the page, "Fifth Species (course handout)," *Carnegie Mellon course materials*. [Link](https://www.andrew.cmu.edu/user/johnito/music_theory/CTP/species/5thSpecies.pdf). License: Unstated; cited, not copied. Secondary source used only for fifth-species rhythm detail; author unconfirmed.
- <a id="source-wikipedia"></a>**wikipedia**: Wikipedia contributors, "Counterpoint: Species counterpoint," *Wikipedia*. [Link](https://en.wikipedia.org/wiki/Counterpoint). License: CC BY-SA 4.0. Tertiary summary; used for cross-checking only.

Open Music Theory text is licensed CC BY-SA 4.0; rules drawn from it are paraphrased with attribution. Copyrighted course handouts are cited for their rules, not reproduced.
