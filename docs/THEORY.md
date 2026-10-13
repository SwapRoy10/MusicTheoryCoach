# Harmonic identification: conventions and checked examples

The program distinguishes **what notes form a chord** from **whether that chord meets an explicit assignment**. In C major, adding D to F-A-C gives D-F-A-C, a minor seventh chord on scale degree 2. That does not make D inherently wrong. A prescribed IV assignment can still disallow the substitution; the report now says so explicitly.

## Measure 2 and inversion

- A4-F4-D4-F3 contains D-F-A, not D-F-A-C. With F as its lowest note, it is **ii6**.
- A4-D4-C4-F3 contains all four members D-F-A-C. With F in the bass, it is **ii6/5**.
- F-A-C over D in the bass spells **ii7**, root position.

Lowercase ii indicates a minor triad/minor seventh chord in major. Uppercase II would indicate a major triad, which is not diatonic in C major. Inversion figures distinguish root-position sevenths (7) from first (6/5), second (4/3), and third (4/2) inversions. Data and prose use slash notation; engraved score labels use raised and vertically stacked figures through MuseScore's Campania font.

The underlying conventions were checked against the open textbook *Open Music Theory*: [Roman Numerals](https://viva.pressbooks.pub/openmusictheory/chapter/roman-numerals/) and [Inversion](https://viva.pressbooks.pub/openmusictheory/chapter/inversion/). Doubling and octave spacing do not change chord membership. Inversion comes from the lowest sounding chord member, not whichever voice happens to be labeled Bass.

## Resolution and limitations

The new example's chordal seventh C moves down by step to B at the change from ii6/5 to V. This follows the standard tendency described in [Predominant Seventh Chords](https://viva.pressbooks.pub/openmusictheory/chapter/predominant-seventh-chords/). The prototype treats deviations as advice because transfers, retained notes and other exceptions require broader context.

Identification matches complete diatonic triads and seventh chords in major keys. Missing thirds, omitted roots, suspensions and chromatic interpretations are not guessed. A label states an exact vertical pitch-set match, not proof of the chord's harmonic function or the only possible contextual interpretation. Source-grounded conventions and automated tests do not replace independent musician review.
