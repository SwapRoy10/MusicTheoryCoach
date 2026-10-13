# Current annotated review

This is the approved current example of the coach's review format.

- `testScore.mxl`: the user's original compressed score, including trailing empty measures.
- `annotated-score.pdf`: the current three-page report, with the original notes visible, named paradigm brackets, professional inversion figures, numeral corrections and findings.
- `annotated-score.musicxml`: the annotated musical source; PDF bracket placement is completed separately after engraving.
- `analysis.json`: note-level evidence, source labels, contextual interpretations, paradigm matches and provenance.
- `report.md`: the readable analysis and musical suggestions.

The PDF omits Review scope and Sounding harmony sections and parenthetical variant tags in score labels. Rendering checks confirmed that all 112 original music glyphs survived annotation. Earlier generated versions and temporary render images have been removed.

To generate a fresh review from the source:

```sh
python -m coach.review examples/reviews/testScore/testScore.mxl --out output/testScore --pdf
```

Requires the optional PDF dependencies and MuseScore. The current example is user-supplied material; it is separate from the synthetic CC0 regression fixtures.
