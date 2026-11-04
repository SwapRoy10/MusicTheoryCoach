"""Single-note fixes for one finding, each confirmed by rerunning the checker.

A fix changes one note so that the chosen finding disappears and no new error
appears. The search is local: a chorale is rechecked on the bars around the
finding, a species exercise in full (it is small). Nothing here claims a fix is
the best musical choice, only that it passes the rules the checker supports.
"""
from dataclasses import replace
import re

from .checker import check
from .model import RANGES, Pitch, Score, STEPS, scale

ORDER = {"A": 0, "T": 1, "B": 2, "S": 3}  # inner voices first: the soprano is usually the given melody


def _key(finding):
    return (finding["rule"], tuple(sorted(n["id"] for n in finding["notes"])), finding.get("measure"), finding.get("beat"))


def _errors(findings):
    return {_key(f) for f in findings if f["severity"] == "error"}


def _pitches_near(pitch, fifths, low, high, span=7, extra=()):
    alter = scale(fifths)
    out = []
    for octave in range(1, 8):
        for step in STEPS:
            for a in {alter[step], *[x for s, x in extra if s == step]}:
                p = Pitch(step, a, octave)
                if p != pitch and low <= p.midi <= high and abs(p.midi - pitch.midi) <= span:
                    out.append(p)
    return out


def _window(score, first, last):
    """The bars first..last as a score of their own (same note IDs and labels)."""
    notes = tuple(replace(n, measure_index=n.measure_index - first)
                  for n in score.notes if first <= n.measure_index <= last)
    return Score(notes, score.measures[first:last + 1], score.fifths, score.mode)


def chorale_fixes(score, assignment, finding, limit=3):
    if finding["severity"] != "error" or not finding["notes"]:
        return []
    ids = {n["id"] for n in finding["notes"]}
    notes = [n for n in score.notes if n.id in ids]
    mi = min(n.measure_index for n in notes)
    first, last = max(0, mi - 1), min(len(score.measures) - 1, max(n.measure_index for n in notes) + 1)
    window = _window(score, first, last)
    before = check(window, assignment, enforce_length=False)
    target = _key(finding)
    if target not in _errors(before):
        return []
    old_errors = _errors(before)
    old_suggestions = sum(f["severity"] == "suggestion" for f in before)
    from .harmony import tonic_pc
    tonic = tonic_pc(score.fifths, score.mode)
    options = []
    for note in notes:
        extra = ()
        if score.mode == "minor":  # the raised sixth and seventh
            from .harmony import degree_pitch
            extra = tuple(degree_pitch(d, score.fifths, "minor", 1) for d in (6, 7))
        signature = scale(score.fifths)
        if note.pitch.alter != signature[note.pitch.step]:
            # A chromatic note may need another chromatic spelling (in an applied chord or augmented sixth, say).
            extra = extra + tuple((st, signature[st] + d) for st in STEPS for d in (-1, 1))
        for pitch in _pitches_near(note.pitch, score.fifths, *RANGES[note.voice], extra=extra):
            candidate = window.change(note.id, pitch)
            after = check(candidate, assignment, enforce_length=False)
            new_errors = _errors(after)
            if target in new_errors or new_errors - old_errors:
                continue
            suggestions = sum(f["severity"] == "suggestion" for f in after)
            removed = sorted({k[0] for k in old_errors - new_errors})
            options.append(((len(new_errors), suggestions, ORDER[note.voice], pitch.alter != signature[pitch.step],
                             abs(pitch.midi - note.pitch.midi), pitch.midi % 12 == (tonic - 1) % 12),
                            {"note_id": note.id, "voice": note.voice, "measure": note.measure, "beat": str(note.beat),
                             "before": str(note.pitch), "after": str(pitch), "removes": removed,
                             "fixed_errors": len(old_errors - new_errors),
                             "suggestion_change": suggestions - old_suggestions}))
    options.sort(key=lambda o: o[0])
    seen, out = set(), []
    for _, option in options:
        if (option["note_id"], option["after"]) not in seen:
            seen.add((option["note_id"], option["after"]))
            out.append(option)
        if len(out) == limit:
            break
    return out


def species_fixes(exercise, species, finding, limit=3):
    from .counterpoint import _beat, check_exercise
    if finding["severity"] != "error" or not finding["notes"]:
        return []
    before = check_exercise(exercise, species)["findings"]
    target = _key(finding)
    old_errors = _errors(before)
    if target not in old_errors:
        return []
    old_suggestions = sum(f["severity"] == "suggestion" for f in before)
    ids = {n["id"] for n in finding["notes"]}
    events = list(exercise.counterpoint)
    lo, hi = min(e.pitch.midi for e in exercise.cantus), max(e.pitch.midi for e in exercise.cantus)
    low, high = (lo - 2, hi + 19) if exercise.above else (lo - 19, hi + 2)
    # Allow the raised leading tone and raised sixth used at cadences.
    final = exercise.final
    raised = [(STEPS[(STEPS.index(final.step) + k) % 7], 1 + scale(exercise.fifths)[STEPS[(STEPS.index(final.step) + k) % 7]])
              for k in (5, 6)]
    options = []
    for i, e in enumerate(events):
        if e.id not in ids or e.pitch is None:
            continue
        # A tied pair moves together.
        group = [i]
        j = i
        while events[j].tie_from and j > 0:
            j -= 1
            group.append(j)
        j = i
        while events[j].tie_to and j + 1 < len(events):
            j += 1
            group.append(j)
        cadence = e.bar >= exercise.bars - 3
        for pitch in _pitches_near(e.pitch, exercise.fifths, low, high, extra=raised if cadence else ()):
            changed = list(events)
            for g in group:
                changed[g] = replace(events[g], pitch=pitch)
            candidate = replace(exercise, counterpoint=tuple(changed))
            after = check_exercise(candidate, species)["findings"]
            new_errors = _errors(after)
            if target in new_errors or new_errors - old_errors:
                continue
            suggestions = sum(f["severity"] == "suggestion" for f in after)
            options.append(((len(new_errors), suggestions, abs(pitch.midi - e.pitch.midi), pitch.alter != e.pitch.alter),
                            {"note_id": e.id, "note_ids": sorted({events[g].id for g in group}), "voice": "CP",
                             "measure": exercise.measures[e.bar], "beat": _beat(e.start),
                             "before": str(e.pitch), "after": str(pitch),
                             "removes": sorted({k[0] for k in old_errors - new_errors}),
                             "fixed_errors": len(old_errors - new_errors),
                             "suggestion_change": suggestions - old_suggestions}))
    options.sort(key=lambda o: o[0])
    return [o for _, o in options[:limit]]


_NOTE = re.compile(r"<note\b.*?</note>", re.S)


def apply_pitch(musicxml, note_ids, pitch):
    """Rewrite the pitch of the n-th <note> elements (IDs n1, n2, ... in document order)."""
    wanted = {int(i[1:]) for i in note_ids}
    counter = 0

    def edit(match):
        nonlocal counter
        counter += 1
        text = match.group(0)
        if counter not in wanted:
            return text
        alter = f"<alter>{pitch.alter}</alter>" if pitch.alter else ""
        text = re.sub(r"<pitch>.*?</pitch>",
                      f"<pitch><step>{pitch.step}</step>{alter}<octave>{pitch.octave}</octave></pitch>", text, flags=re.S)
        return re.sub(r"\s*<accidental\b[^>]*>.*?</accidental>|\s*<accidental\b[^>]*/>", "", text, flags=re.S)
    return _NOTE.sub(edit, musicxml)
