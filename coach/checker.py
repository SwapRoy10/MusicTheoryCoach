from fractions import Fraction
from itertools import combinations

from .model import VOICES, RANGES, Pitch, perfect, scale
from .harmony import identify, vocabulary


def constraints_for(score, raw=None):
    raw = {} if raw is None else raw
    allowed = {"instructions", "preserve_soprano", "require_tonic_ending", "harmony", "voice_map"}
    if not isinstance(raw, dict) or set(raw) - allowed:
        raise ValueError("Unknown assignment fields; see examples/assignment.json")
    for field in ("preserve_soprano", "require_tonic_ending"):
        if field in raw and type(raw[field]) is not bool:
            raise ValueError(f"{field} must be a boolean")
    if not isinstance(raw.get("instructions", ""), str):
        raise ValueError("instructions must be text")
    harmony = raw.get("harmony", [])
    if not isinstance(harmony, list):
        raise ValueError("harmony must be a list")
    normalized = []
    for chord in harmony:
        if not isinstance(chord, dict) or set(chord) != {"measure", "beat", "pitches", "bass"}:
            raise ValueError("Each chord needs measure, beat, pitches (root/third/fifth), and bass")
        label = str(chord["measure"])
        beat = Fraction(str(chord["beat"]))
        if label not in score.measures or beat not in (1, 3):
            raise ValueError("Harmony must start at an existing measure, beat 1 or 3")
        names = chord["pitches"]
        if not isinstance(names, list) or len(names) not in (3, 4) or any(not isinstance(p, str) for p in names):
            raise ValueError("Supply three or four pitch names in root/third/fifth[/seventh] order")
        pitches = [Pitch.parse(p + "4") for p in names]
        root, third, fifth = pitches[:3]
        if ((third.diatonic-root.diatonic) % 7 != 2 or (third.midi-root.midi) % 12 not in (3, 4)
                or (fifth.diatonic-root.diatonic) % 7 != 4 or (fifth.midi-root.midi) % 12 not in (6, 7)):
            raise ValueError("Harmony must be a spelled major, minor or diminished triad")
        if any(p.alter != scale(score.fifths)[p.step] for p in pitches):
            raise ValueError("Harmony must be diatonic to the declared key")
        if names not in [c["pitches"] for c in vocabulary(score.fifths)]:
            raise ValueError("Harmony must be a diatonic triad or seventh chord in root/third/fifth[/seventh] order")
        if chord["bass"] not in names:
            raise ValueError("Expected bass must be a member of the triad")
        normalized.append({**chord, "measure": label, "beat": str(beat),
                           "offset": score.measures.index(label) * 4 + beat - 1})
    normalized.sort(key=lambda c: c["offset"])
    if normalized and (normalized[0]["offset"] != 0 or len({c["offset"] for c in normalized}) != len(normalized)):
        raise ValueError("Harmony must begin at measure 1, beat 1 and have unique starts")
    return {**raw, "harmony": normalized, "preserve_soprano": raw.get("preserve_soprano", True),
            "require_tonic_ending": raw.get("require_tonic_ending", False)}


def chord_at(assignment, time):
    return next((c for c in reversed(assignment["harmony"]) if c["offset"] <= time), None)


def check(score, assignment, enforce_length=True):
    findings = []

    def add(rule, notes, message, severity="error", time=None, measure=None):
        notes = list(notes)
        if time is None:
            time = notes[-1].start if notes else 0
        mi = min(int(time // 4), len(score.measures) - 1)
        findings.append({"rule": rule, "severity": severity,
                         "measure": measure or score.measures[mi], "beat": str(time % 4 + 1),
                         "voices": list(dict.fromkeys(n.voice for n in notes)),
                         "notes": [n.data() for n in notes], "message": message})

    if enforce_length and not 4 <= len(score.measures) <= 8:
        add("measure_count", [], "The supported assignment requires four to eight measures.")
    for mi, label in enumerate(score.measures):
        for voice in VOICES:
            notes = sorted((n for n in score.notes if n.measure_index == mi and n.voice == voice), key=lambda n: n.beat)
            cursor = Fraction(1)
            valid = True
            for n in notes:
                if n.beat != cursor:
                    valid = False
                cursor = n.beat + n.duration
            if not valid or cursor != 5:
                add("measure_duration", notes, f"{voice} must fill this 4/4 measure with no gaps or overflow.",
                    time=mi * 4, measure=label)
                findings[-1]["voices"] = [voice]
    key_scale = scale(score.fifths)
    for n in score.notes:
        if n.duration not in (2, 4) or n.beat not in (1, 3) or n.beat + n.duration > 5:
            add("rhythm", [n], "Use half notes on beats 1/3 or a whole note on beat 1.")
        low, high = RANGES[n.voice]
        if not low <= n.pitch.midi <= high:
            add("range", [n], f"{n.voice} {n.pitch} is outside the configured classroom range.")
        if n.pitch.alter != key_scale[n.pitch.step]:
            add("diatonic", [n], f"{n.pitch} is outside the declared major-key spelling.")
    frames = list(score.frames(c["offset"] for c in assignment["harmony"]))
    for time, frame in frames:
        for upper, lower in zip(VOICES, VOICES[1:]):
            if upper not in frame or lower not in frame:
                continue
            u, l = frame[upper], frame[lower]
            if u.pitch.midi < l.pitch.midi:
                add("crossing", [u, l], f"{upper} sounds below {lower}.", time=time)
            if upper != "T" and u.pitch.midi - l.pitch.midi > 12:
                add("spacing", [u, l], f"{upper} and {lower} are more than an octave apart.", time=time)
        chord = chord_at(assignment, time)
        actual = identify(frame, score.fifths)
        if actual["status"] == "uncertain":
            add("harmony_uncertain", frame.values(), actual["reason"], "uncertain", time)
        if chord:
            for n in frame.values():
                if n.pitch.name not in chord["pitches"]:
                    description = f"The sounding chord is {actual['roman']}. " if actual["status"] == "identified" else ""
                    add("chord_membership", [n], f"Assignment mismatch: {n.pitch} is outside the prescribed {'-'.join(chord['pitches'])}. "
                        + description + "This tests the prescribed harmony, not whether the note can belong to another chord.", time=time)
            if "B" in frame and frame["B"].pitch.name != chord["bass"]:
                add("inversion", [frame["B"]], f"The supplied inversion requires {chord['bass']} in the bass.", time=time)
            if len(frame) == 4 and len({n.pitch.name for n in frame.values()} & set(chord["pitches"])) < len(chord["pitches"]):
                add("incomplete_triad" if len(chord["pitches"]) == 3 else "incomplete_seventh", frame.values(),
                    "A member of the prescribed chord is absent; this does not rule out a different sounding chord.", "suggestion", time)
            if len(chord["pitches"]) == 3 and len(frame) == 4 and chord["bass"] == chord["pitches"][0]:
                if sum(n.pitch.name == chord["bass"] for n in frame.values()) != 2:
                    add("doubling", frame.values(), "Root-position triads usually double the root; review the melodic context.", "suggestion", time)
    for (old_time, old), (time, new) in zip(frames, frames[1:]):
        old_chord, new_chord = identify(old, score.fifths), identify(new, score.fifths)
        if old_chord.get("size") == 4 and old_chord.get("pitches") != new_chord.get("pitches"):
            for voice, note in old.items():
                if note.pitch.name == old_chord["pitches"][3] and voice in new and note.end >= time:
                    target = new[voice]
                    if target.pitch == note.pitch:
                        continue  # Retention needs later harmonic context.
                    if not (note.pitch.diatonic - target.pitch.diatonic == 1 and note.pitch.midi - target.pitch.midi in (1, 2)):
                        add("seventh_resolution", [note, target], "The identified chordal seventh does not descend by step; review the harmonic context.", "suggestion", time)
        # Do not connect notes across a gap in either voice.
        for a, b in combinations(VOICES, 2):
            if not all(v in old and v in new and old[v].end >= time for v in (a, b)):
                continue
            oa, ob, na, nb = old[a], old[b], new[a], new[b]
            da, db = na.pitch.midi - oa.pitch.midi, nb.pitch.midi - ob.pitch.midi
            interval = perfect(oa.pitch, ob.pitch)
            if da * db > 0 and interval and interval == perfect(na.pitch, nb.pitch):
                add("parallel_" + interval, [oa, ob, na, nb],
                    f"{a} and {b} move in the same direction between perfect {interval}s.", time=time)
        for a, b in zip(VOICES, VOICES[1:]):
            if all(v in old and v in new and old[v].end >= time for v in (a, b)):
                if new[a].pitch.midi < old[b].pitch.midi or new[b].pitch.midi > old[a].pitch.midi:
                    add("overlap", [old[a], old[b], new[a], new[b]],
                        f"An adjacent voice moves beyond the other voice's previous pitch.", time=time)
        if all(v in old and v in new and old[v].end >= time for v in ("S", "B")):
            ds = new["S"].pitch.midi - old["S"].pitch.midi
            db = new["B"].pitch.midi - old["B"].pitch.midi
            target = perfect(new["S"].pitch, new["B"].pitch)
            if ds * db > 0 and abs(new["S"].pitch.diatonic - old["S"].pitch.diatonic) > 1 and target:
                if perfect(old["S"].pitch, old["B"].pitch) != target:
                    add("direct_outer_interval", [old["S"], old["B"], new["S"], new["B"]],
                        "Similar outer-voice motion enters a perfect interval with a soprano leap.", "suggestion", time)
    # Context-sensitive tendency-tone advice is deliberately not a hard rule.
    tonic_pc = (7 * score.fifths) % 12
    for voice in VOICES:
        notes = sorted((n for n in score.notes if n.voice == voice), key=lambda n: n.start)
        for a, b in zip(notes, notes[1:]):
            if a.end == b.start and a.pitch.midi % 12 == (tonic_pc - 1) % 12 and a.pitch != b.pitch:
                if b.pitch.midi != a.pitch.midi + 1:
                    add("leading_tone", [a, b], "The leading tone does not rise a semitone; check harmonic context and inner-voice exceptions.", "suggestion")
    if assignment["require_tonic_ending"] and frames:
        final = frames[-1][1]
        # Require root-position tonic with all three members, using declared key spellings.
        tonic_names = {Pitch(s, a, 4).name for s, a in key_scale.items()
                       if (Pitch(s, a, 4).midi - tonic_pc) % 12 in (0, 4, 7)}
        if (set(final) != set(VOICES) or {n.pitch.name for n in final.values()} != tonic_names
                or final["B"].pitch.midi % 12 != tonic_pc):
            add("tonic_ending", final.values(), "The assignment requires a complete root-position tonic ending.", time=frames[-1][0])
    return findings


def errors(findings):
    return [f for f in findings if f["severity"] == "error"]
