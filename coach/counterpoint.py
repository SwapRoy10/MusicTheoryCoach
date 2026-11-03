"""Two-voice species counterpoint: read, check and write exercises.

An exercise is a cantus firmus in whole notes plus one counterpoint in the
rhythm of a species (1-5). Findings use the rule ids of
``references/species-counterpoint/rules.json``, so every finding can cite its
rule text and sources. Severity comes from the rule's strength: "required"
rules give errors, the rest give suggestions.

Pitch space is diatonic in the key signature; the final is the cantus's last
note. A raised leading tone (and a raised sixth leading into it) is accepted
at the cadence, as musica ficta.
"""
from dataclasses import dataclass, replace
from fractions import Fraction
import json
import xml.etree.ElementTree as ET

from .model import Pitch, STEPS, scale, perfect
from .reference import SPECIES_RULES
from .score_import import root_from_file

BAR = Fraction(4)
CP, CF = "CP", "CF"
SEVERITY = {"required": "error", "avoid": "suggestion", "preferred": "suggestion", "allowed": "suggestion"}


# ---------------------------------------------------------------- model

@dataclass(frozen=True)
class Event:
    bar: int
    start: Fraction              # quarters after the bar line
    dur: Fraction                # in quarters
    pitch: Pitch | None          # None is a rest
    tie_from: bool = False       # continues the previous note
    tie_to: bool = False         # tied into the next note
    id: str | None = None

    @property
    def time(self):
        return self.bar * BAR + self.start

    @property
    def end(self):
        return self.time + self.dur


@dataclass(frozen=True)
class Exercise:
    cantus: tuple
    counterpoint: tuple
    fifths: int
    above: bool                  # counterpoint above the cantus
    measures: tuple
    cantus_assumed: str = ""     # how the cantus was identified, if not obvious

    @property
    def bars(self):
        return len(self.measures)

    @property
    def final(self):
        return self.cantus[-1].pitch


def rules_catalog():
    data = json.loads(SPECIES_RULES.read_text(encoding="utf-8"))
    return {r["id"]: r for r in data["rules"]}, {s["id"]: s for s in data["sources"]}


# ---------------------------------------------------------------- intervals

def interval(a, b):
    """Compound generic number (1 = unison) and absolute semitones."""
    return abs(a.diatonic - b.diatonic) + 1, abs(a.midi - b.midi)


def simple(number):
    return (number - 1) % 7 + 1


def consonant(a, b):
    number, semis = interval(a, b)
    n, s = simple(number), semis % 12
    return (n == 1 and s == 0) or (n == 3 and s in (3, 4)) or (n == 5 and s == 7) or (n == 6 and s in (8, 9))


def perfect_kind(a, b):
    """'unison', 'octave' (any compound octave) or 'fifth' (any compound fifth); else None."""
    kind = perfect(a, b)
    if kind == "octave" and a.midi == b.midi and a.diatonic == b.diatonic:
        return "unison"
    return kind


def imperfect_kind(a, b):
    if not consonant(a, b):
        return None
    n = simple(interval(a, b)[0])
    return {3: "third", 6: "sixth"}.get(n)


def label(a, b):
    number, _ = interval(a, b)
    return str(number) if number <= 15 else str(simple(number))


def step(a, b):
    number, semis = interval(a, b)
    return number == 2 and semis in (1, 2)


def direction(a, b):
    return (b.midi > a.midi) - (b.midi < a.midi)


def melodic_ok(a, b):
    """Consonant melodic interval: steps, thirds, P4, P5, P8 and the ascending minor sixth."""
    number, semis = interval(a, b)
    return ((number == 2 and semis in (1, 2)) or (number == 3 and semis in (3, 4)) or (number == 4 and semis == 5)
            or (number == 5 and semis == 7) or (number == 8 and semis == 12)
            or (number == 6 and semis == 8 and b.midi > a.midi))


def dissonant_span(a, b):
    """A melodic span (between turning points) that outlines a dissonance."""
    number, semis = interval(a, b)
    n, s = simple(number), semis % 12
    if number == 1:
        return False
    return (n in (2, 7) or (n == 4 and s != 5) or (n == 5 and s != 7) or (n == 3 and s not in (3, 4))
            or (n == 6 and s not in (8, 9)) or (n == 1 and s != 0))


def mode_alter(fifths):
    return scale(fifths)


def degree_of(pitch, final):
    """Scale degree relative to the final, 1-7, by letter."""
    return (STEPS.index(pitch.step) - STEPS.index(final.step)) % 7 + 1


# ---------------------------------------------------------------- reading MusicXML

def read_exercise(path, cantus=None):
    """Read a two-voice exercise. ``cantus`` may be 'upper' or 'lower' to override detection."""
    root = root_from_file(path)
    parts = root.findall("part")
    if not parts:
        raise ValueError("The file has no parts.")
    measures = tuple(m.get("number") for m in parts[0].findall("measure"))
    streams, names, keys = {}, {}, set()
    for p in root.iter("score-part"):
        names[p.get("id")] = (p.findtext("part-name") or "").lower()
    index = 0
    for part in parts:
        if tuple(m.get("number") for m in part.findall("measure")) != measures:
            raise ValueError("Every part needs the same measures.")
        divisions = None
        for mi, measure in enumerate(part.findall("measure")):
            if measure.get("implicit") == "yes":
                raise ValueError("Pickup measures are not supported in species exercises.")
            cursor = Fraction(0)
            for el in measure:
                if el.tag == "attributes":
                    if el.find("divisions") is not None:
                        divisions = int(el.findtext("divisions"))
                    if el.find("key/fifths") is not None:
                        keys.add(int(el.findtext("key/fifths")))
                    t = el.find("time")
                    if t is not None and (t.findtext("beats"), t.findtext("beat-type")) not in (("4", "4"), ("2", "2")):
                        raise ValueError("Species exercises must be in 4/4 or 2/2, one cantus note per bar.")
                elif el.tag == "backup":
                    cursor -= Fraction(el.findtext("duration")) / divisions
                elif el.tag == "forward":
                    cursor += Fraction(el.findtext("duration")) / divisions
                elif el.tag == "note":
                    index += 1
                    if not divisions:
                        raise ValueError("Missing divisions in the MusicXML.")
                    if el.find("chord") is not None:
                        raise ValueError("Each voice must sound one note at a time.")
                    if any(el.find(t) is not None for t in ("grace", "cue", "time-modification", "unpitched")):
                        raise ValueError("Grace notes, cue notes, tuplets and unpitched notes are not supported.")
                    dur = Fraction(el.findtext("duration", "0")) / divisions
                    pitch = None
                    if el.find("pitch") is not None:
                        p = el.find("pitch")
                        pitch = Pitch(p.findtext("step"), int(float(p.findtext("alter", "0"))), int(p.findtext("octave")))
                    ties = {t.get("type") for t in el.findall("tie")}
                    voice = (part.get("id"), el.findtext("voice", "1"))
                    streams.setdefault(voice, []).append(Event(mi, cursor, dur, pitch, "stop" in ties, "start" in ties, f"n{index}"))
                    cursor += dur
    if len(keys) > 1:
        raise ValueError("Key changes are not supported.")
    fifths = keys.pop() if keys else 0
    streams = {k: v for k, v in streams.items() if any(e.pitch for e in v)}
    if len(streams) != 2:
        raise ValueError("A species exercise needs exactly two voices: a cantus firmus and a counterpoint.")
    # Drop trailing bars where both voices rest.
    last = max(e.bar for v in streams.values() for e in v if e.pitch)
    measures = measures[:last + 1]
    streams = {k: [e for e in v if e.bar <= last] for k, v in streams.items()}
    for key, events in streams.items():
        for bar in range(len(measures)):
            in_bar = [e for e in events if e.bar == bar]
            cursor = Fraction(0)
            for e in in_bar:
                if e.start != cursor:
                    raise ValueError(f"Bar {measures[bar]}: a voice has a gap or overlap.")
                cursor += e.dur
            if cursor != BAR:
                raise ValueError(f"Bar {measures[bar]}: each voice must fill the bar (one whole note's worth).")

    def whole_notes(events):
        return all(e.pitch and e.dur == BAR and e.start == 0 and not e.tie_from for e in events)

    (k1, s1), (k2, s2) = streams.items()
    mean = lambda ev: sum(e.pitch.midi for e in ev if e.pitch) / sum(1 for e in ev if e.pitch)
    upper, lower = ((s1, k1), (s2, k2)) if mean(s1) >= mean(s2) else ((s2, k2), (s1, k1))
    candidates = [(ev, key) for ev, key in (upper, lower) if whole_notes(ev)]
    assumed = ""
    if cantus in ("upper", "lower"):
        cf, cf_key = upper if cantus == "upper" else lower
        if not whole_notes(cf):
            raise ValueError(f"The {cantus} voice is not in whole notes, so it cannot be the cantus firmus.")
    elif len(candidates) == 1:
        cf, cf_key = candidates[0]
    elif len(candidates) == 2:
        named = [(ev, key) for ev, key in candidates if any(w in names.get(key[0], "") for w in ("cantus", "c.f", "cf"))]
        if len(named) == 1:
            cf, cf_key = named[0]
        else:
            cf, cf_key = lower
            assumed = "Both voices are in whole notes, so the lower voice was taken as the cantus firmus."
    else:
        raise ValueError("Neither voice is in whole notes, so no cantus firmus was found.")
    cp = upper[0] if cf is lower[0] else lower[0]
    return Exercise(tuple(cf), tuple(cp), fifths, cp is upper[0], measures, assumed)


def detect_species(ex):
    cp = list(ex.counterpoint)
    body = [e for e in cp if e.bar < ex.bars - 1]
    if all(e.dur == BAR for e in cp):
        return 1
    pitched = [e for e in body if e.pitch]
    if any(e.tie_from or e.tie_to for e in body) and all(e.dur == 2 for e in body):
        return 4
    penult = [e for e in body if e.bar == ex.bars - 2]
    core = [e for e in pitched if not (e.bar == ex.bars - 2 and len(penult) == 1)]
    if core and all(e.dur == 2 for e in core) and not any(e.tie_from or e.tie_to for e in body):
        return 2
    if core and all(e.dur == 1 for e in core) and not any(e.tie_from or e.tie_to for e in body):
        return 3
    return 5


# ---------------------------------------------------------------- checking

def check_cantus(pitches, fifths):
    """Findings for a cantus firmus given as a list of Pitch (used by the composer and for typed input)."""
    findings = []

    def add(rule, message, at=None):
        findings.append({"rule": rule, "severity": "error" if rule in ("cf-begin-end", "cf-approach-final", "mel-melodic-consonance", "mel-leap-recovery") else "suggestion",
                         "index": at, "message": message})
    if not 8 <= len(pitches) <= 16:
        add("cf-length", "A cantus firmus is usually 8 to 16 notes long.")
    if pitches[0].name != pitches[-1].name:
        add("cf-begin-end", "The cantus must begin and end on the final.")
    if len(pitches) > 1 and not step(pitches[-2], pitches[-1]):
        add("cf-approach-final", "The final must be approached by step.", len(pitches) - 1)
    alter = scale(fifths)
    for i, (a, b) in enumerate(zip(pitches, pitches[1:])):
        if a.midi == b.midi:
            add("mel-mostly-steps", "Avoid repeated notes in a cantus firmus.", i + 1)
        elif not melodic_ok(a, b):
            add("mel-melodic-consonance", f"{a}–{b} is not a consonant melodic interval.", i + 1)
    for i in range(len(pitches) - 2):
        a, b, c = pitches[i:i + 3]
        if interval(a, b)[0] >= 4 and not (step(b, c) and direction(a, b) != direction(b, c)):
            add("mel-leap-recovery", f"The leap {a}–{b} is not followed by a step in the opposite direction.", i + 2)
    high = max(p.midi for p in pitches)
    if sum(p.midi == high for p in pitches) > 1:
        add("mel-single-climax", "The high point occurs more than once.")
    if max(p.midi for p in pitches) - min(p.midi for p in pitches) > 16:
        add("mel-range", "The cantus spans more than a tenth.")
    for p in pitches[:-2]:
        if p.alter != alter[p.step]:
            add("mel-leading-tone", f"{p} is outside the key signature.")
    return findings


class _Checker:
    def __init__(self, ex, species):
        self.ex, self.species = ex, species
        self.rules, _ = rules_catalog()
        self.findings, self.seen = [], set()
        self.cf = list(ex.cantus)
        self.cp = list(ex.counterpoint)
        self.notes = [e for e in self.cp if e.pitch]
        self.attacks = [e for e in self.notes if not e.tie_from]
        self.final = ex.final
        self.alter = scale(ex.fifths)

    # -- helpers
    def cf_at(self, e):
        return self.cf[e.bar]

    def data(self, e, voice):
        return {"id": e.id, "voice": voice, "measure": self.ex.measures[e.bar], "beat": _beat(e.start),
                "duration": str(e.dur), "pitch": str(e.pitch), "midi": e.pitch.midi}

    def add(self, rule, events, message, severity=None):
        events = [x for x in events if x is not None]
        key = (rule, tuple((v, e.id) for v, e in events))
        if key in self.seen:
            return
        self.seen.add(key)
        strength = self.rules.get(rule, {}).get("strength", "required")
        anchor = events[-1][1] if events else self.cp[0]
        cp_events = [e for v, e in events if v == CP]
        anchor = cp_events[-1] if cp_events else anchor
        self.findings.append({"rule": rule, "severity": severity or SEVERITY[strength],
                              "measure": self.ex.measures[anchor.bar], "beat": _beat(anchor.start),
                              "voices": list(dict.fromkeys(v for v, _ in events)),
                              "notes": [self.data(e, v) for v, e in events], "message": message})

    def pair(self, e):
        return [(CP, e), (CF, self.cf_at(e))]

    def vertical(self, e):
        return self.cf_at(e).pitch

    # -- shared checks
    def check_rhythm(self):
        s, bars = self.species, self.ex.bars
        allowed = {1: {(0, 4)}, 2: {(0, 2), (2, 2)}, 3: {(0, 1), (1, 1), (2, 1), (3, 1)}, 4: {(0, 2), (2, 2)}}
        problems = []
        for e in self.cp:
            final_bar = e.bar == bars - 1
            if final_bar:
                if e.pitch is None or e.dur != BAR:
                    problems.append(e)
                continue
            if e.pitch is None:
                if not (e.bar == 0 and e.start == 0 and s in (2, 3, 4, 5)):
                    problems.append(e)
                continue
            if s in allowed and (int(e.start), int(e.dur)) not in allowed[s] | ({(0, 4)} if s == 2 and e.bar == bars - 2 else set()):
                problems.append(e)
            if s == 5:
                ok_pos = {Fraction(4): {0}, Fraction(3): {0}, Fraction(2): {0, 2}, Fraction(1): {0, 1, 2, 3},
                          Fraction(1, 2): {Fraction(1), Fraction(3, 2), Fraction(3), Fraction(7, 2)}}
                if e.dur not in ok_pos or e.start not in ok_pos[e.dur] or (e.dur == BAR and e.bar < bars - 1):
                    problems.append(e)
        names = {1: "s1-rhythm", 2: "s2-rhythm", 3: "s3-rhythm", 4: "s4-rhythm", 5: "s5-run-limits"}
        for e in problems[:3]:
            self.add(names[s], [(CP, e)] if e.pitch else [], f"This rhythm does not fit species {s}.", "error")
        if s in (1, 2, 3) and any(e.tie_from or e.tie_to for e in self.cp):
            tied = next(e for e in self.cp if e.tie_from or e.tie_to)
            self.add(names[s], [(CP, tied)], f"Species {s} has no ties.", "error")
        return not problems

    def check_diatonic(self):
        attacks = self.attacks
        for i, e in enumerate(attacks):
            p = e.pitch
            if p.alter == self.alter[p.step]:
                continue
            nxt = attacks[i + 1].pitch if i + 1 < len(attacks) else None
            raised_lt = (p.alter == self.alter[p.step] + 1 and nxt and nxt.name == self.final.name and nxt.midi - p.midi == 1)
            raised_six = (p.alter == self.alter[p.step] + 1 and nxt and i + 2 < len(attacks)
                          and nxt.midi - p.midi == 2 and attacks[i + 2].pitch.name == self.final.name and attacks[i + 2].pitch.midi - nxt.midi == 1)
            if not (raised_lt or raised_six):
                self.add("mel-leading-tone", [(CP, e)], f"{p} is outside the mode; chromatic notes are only used for the raised leading tone at the cadence.", "suggestion")

    def check_melody(self):
        a = self.attacks
        moves = [(x, y) for x, y in zip(a, a[1:])]
        for x, y in moves:
            if x.pitch.midi != y.pitch.midi and not melodic_ok(x.pitch, y.pitch):
                number, _ = interval(x.pitch, y.pitch)
                self.add("mel-melodic-consonance", [(CP, x), (CP, y)],
                         f"{x.pitch}–{y.pitch} is not an allowed melodic interval (augmented, diminished, a seventh, a descending or major sixth, or larger than an octave).")
        for i in range(len(a) - 2):
            x, y, z = a[i:i + 3]
            if x.pitch.midi == y.pitch.midi:
                continue
            if interval(x.pitch, y.pitch)[0] >= 4 and not (step(y.pitch, z.pitch) and direction(x.pitch, y.pitch) != direction(y.pitch, z.pitch)):
                self.add("mel-leap-recovery", [(CP, x), (CP, y), (CP, z)],
                         f"The leap {x.pitch}–{y.pitch} should be followed by a step in the opposite direction.")
        leaps = [interval(x.pitch, y.pitch)[0] >= 3 for x, y in moves]
        for i in range(len(moves) - 1):
            (x, y), (_, z) = moves[i], moves[i + 1]
            if leaps[i] and leaps[i + 1] and direction(x.pitch, y.pitch) == direction(y.pitch, z.pitch):
                if not consonant(x.pitch, z.pitch) or interval(x.pitch, z.pitch)[0] > 8:
                    self.add("mel-consecutive-leaps", [(CP, x), (CP, y), (CP, z)],
                             "Two leaps in the same direction should outline a consonant triad.")
            if i + 2 < len(moves) and leaps[i] and leaps[i + 1] and leaps[i + 2]:
                self.add("mel-consecutive-leaps", [(CP, x), (CP, moves[i + 2][1])], "More than two leaps in a row.")
        # Spans between turning points.
        turns = [a[0]]
        for i in range(1, len(a) - 1):
            d1, d2 = direction(a[i - 1].pitch, a[i].pitch), direction(a[i].pitch, a[i + 1].pitch)
            if d1 and d2 and d1 != d2:
                turns.append(a[i])
        turns.append(a[-1])
        for x, y in zip(turns, turns[1:]):
            if dissonant_span(x.pitch, y.pitch) and interval(x.pitch, y.pitch)[0] > 2:
                self.add("mel-no-dissonant-outline", [(CP, x), (CP, y)], f"The line outlines a dissonant interval from {x.pitch} to {y.pitch}.")
        high = max(e.pitch.midi for e in a)
        tops = [e for e in a if e.pitch.midi == high]
        if len(tops) > 1:
            self.add("mel-single-climax", [(CP, e) for e in tops[:3]], "The high point appears more than once; give the line a single climax.")
        elif tops[0] is a[-1]:
            self.add("mel-single-climax", [(CP, tops[0])], "The climax should not be the last note.")
        cf_high = max(e.pitch.midi for e in self.cf)
        cf_tops = [e for e in self.cf if e.pitch.midi == cf_high]
        if len(tops) == 1 and len(cf_tops) == 1 and tops[0].bar == cf_tops[0].bar:
            self.add("mel-climaxes-apart", [(CP, tops[0]), (CF, cf_tops[0])], "Both lines reach their climax in the same bar.")

    def check_repeats(self):
        repeats = [(x, y) for x, y in zip(self.attacks, self.attacks[1:]) if x.pitch.midi == y.pitch.midi]
        if self.species == 1:
            if len(repeats) > 1:
                self.add("s1-repeated-notes", [(CP, repeats[1][0]), (CP, repeats[1][1])], "Repeat a note at most once in first species.")
        elif self.species in (2, 3, 4):
            rule = {2: "s2-no-repeats", 3: "s3-no-repeats", 4: "s4-no-repeats"}[self.species]
            for x, y in repeats:
                self.add(rule, [(CP, x), (CP, y)], "Repeated note: move to a new pitch.")
        elif repeats:
            x, y = repeats[0]
            self.add("mel-mostly-steps", [(CP, x), (CP, y)], "Repeated notes weaken the line in florid counterpoint.", "suggestion")

    def check_spacing(self):
        for e in self.notes:
            c = self.vertical(e)
            if (self.ex.above and e.pitch.midi < c.midi) or (not self.ex.above and e.pitch.midi > c.midi):
                self.add("comb-no-crossing-overlap", self.pair(e), "The voices cross.")
            if abs(e.pitch.midi - c.midi) > 19:
                self.add("comb-spacing", self.pair(e), "The voices are more than a twelfth apart.")
        for x, y in zip(self.attacks, self.attacks[1:]):
            if y.bar > x.bar:
                prev_cf, new_cf = self.cf[x.bar].pitch, self.cf[y.bar].pitch
                if self.ex.above and (y.pitch.midi < prev_cf.midi or new_cf.midi > x.pitch.midi):
                    self.add("comb-no-crossing-overlap", [(CP, x), (CP, y), (CF, self.cf[y.bar])], "Voice overlap: one voice moves past the other's previous note.")
                if not self.ex.above and (y.pitch.midi > prev_cf.midi or new_cf.midi < x.pitch.midi):
                    self.add("comb-no-crossing-overlap", [(CP, x), (CP, y), (CF, self.cf[y.bar])], "Voice overlap: one voice moves past the other's previous note.")

    def check_begin_end(self):
        first, last = self.attacks[0], self.notes[-1]
        kind = perfect_kind(first.pitch, self.vertical(first))
        if self.ex.above:
            ok = kind in ("unison", "octave", "fifth") and degree_of(first.pitch, self.final) in (1, 5)
        else:
            ok = kind in ("unison", "octave") and first.pitch.name == self.final.name
        if not ok:
            where = "above" if self.ex.above else "below"
            need = "do or sol (a unison, fifth or octave)" if self.ex.above else "do (a unison or octave)"
            self.add("comb-begin", self.pair(first), f"Begin {where} the cantus on {need}.")
        if last.bar != self.ex.bars - 1 or perfect_kind(last.pitch, self.vertical(last)) not in ("unison", "octave") or last.pitch.name != self.final.name:
            self.add("comb-clausula-vera", self.pair(last), "End on the final, a unison or octave with the cantus.")
        # Penultimate attack: contrary stepwise approach (clausula vera).
        if self.species != 4 and len(self.attacks) >= 2:
            pen = self.attacks[-2] if not self.notes[-1].tie_from else None
            if pen is not None and last.bar == self.ex.bars - 1:
                cfp, cff = self.cf[-2].pitch, self.cf[-1].pitch
                good = step(pen.pitch, last.pitch) and step(cfp, cff) and direction(pen.pitch, last.pitch) == -direction(cfp, cff)
                num = simple(interval(pen.pitch, cfp)[0])
                good = good and ((self.ex.above and num == 6) or (not self.ex.above and num == 3)) and consonant(pen.pitch, cfp)
                if not good:
                    self.add("comb-clausula-vera", [(CP, pen), (CP, last), (CF, self.cf[-2]), (CF, self.cf[-1])],
                             "Approach the final by contrary step: ti–do against re–do, with a sixth (counterpoint above) or third (below) before the octave.")
                elif not ((last.pitch.midi - pen.pitch.midi) % 12 in (1, 11) or (cff.midi - cfp.midi) % 12 in (1, 11)):
                    self.add("mel-leading-tone", [(CP, pen), (CP, last)], "At the cadence one voice should move by semitone into the final; raise the leading tone.")
        if self.species == 4:
            self.check_s4_cadence()

    def motion(self, x, y):
        """Motion between two consecutive verticals (x, y are CP events)."""
        cx, cy = self.vertical(x), self.vertical(y)
        dcp, dcf = direction(x.pitch, y.pitch), direction(cx, cy)
        return dcp, dcf, cx, cy

    def check_pair_rules(self, x, y, rules):
        """First-species motion rules between two verticals."""
        dcp, dcf, cx, cy = self.motion(x, y)
        events = [(CP, x), (CP, y), (CF, self.cf_at(x)), (CF, self.cf_at(y))] if x.bar != y.bar else [(CP, x), (CP, y), (CF, self.cf_at(y))]
        k1, k2 = perfect(x.pitch, cx), perfect(y.pitch, cy)
        if dcp and dcf and dcp == dcf and k1 and k1 == k2:
            self.add(rules["parallel"], events, f"Parallel {k2}s.")
            return
        if dcp and dcf and dcp == -dcf and k1 and k1 == k2 and "contrary" in rules:
            self.add(rules["contrary"], events, f"Two {k2}s in a row (by contrary motion).")
        if "direct" in rules and dcp and dcf and dcp == dcf and k2 and not k1:
            self.add(rules["direct"], events, f"Similar motion into {'an' if k2 in ('octave', 'unison') else 'a'} {k2}: approach perfect consonances by contrary or oblique motion.")

    # -- species-specific checks
    def species_1(self):
        notes = self.notes
        for e in notes:
            if not consonant(e.pitch, self.vertical(e)):
                self.add("s1-all-consonant", self.pair(e), f"Dissonant interval ({label(e.pitch, self.vertical(e))}).")
            elif perfect_kind(e.pitch, self.vertical(e)) == "unison" and 0 < e.bar < self.ex.bars - 1:
                self.add("s1-unison", self.pair(e), "Unisons belong only at the beginning and end.")
        for x, y in zip(notes, notes[1:]):
            self.check_pair_rules(x, y, {"parallel": "comb-no-parallel-perfect", "contrary": "comb-no-consecutive-same-perfect",
                                         "direct": "comb-no-direct-perfect"})
            dcp, dcf, _, _ = self.motion(x, y)
            if dcp and dcp == dcf and interval(x.pitch, y.pitch)[0] >= 4:
                self.add("comb-no-similar-leaps", [(CP, x), (CP, y)], "Similar motion combined with a leap.")
        self.imperfect_runs(notes, "comb-imperfect-run")

    def imperfect_runs(self, events, rule):
        run, kind = [], None
        for e in events:
            k = imperfect_kind(e.pitch, self.vertical(e))
            if k and k == kind:
                run.append(e)
            else:
                run, kind = [e], k
            if kind and len(run) == 4:
                self.add(rule, [(CP, x) for x in run], f"Four {kind}s in a row: use at most three.")

    def downbeats(self):
        return [e for e in self.notes if e.start == 0]

    def species_2(self):
        notes = self.notes
        for i, e in enumerate(notes):
            c = self.vertical(e)
            if e.start == 0:
                if not consonant(e.pitch, c):
                    self.add("s2-downbeat-consonant", self.pair(e), "Downbeats must be consonant.")
                elif perfect_kind(e.pitch, c) == "unison" and 0 < e.bar < self.ex.bars - 1:
                    self.add("s2-downbeat-consonant", self.pair(e), "Avoid unisons on downbeats.", "suggestion")
            elif not consonant(e.pitch, c):
                prev, nxt = (notes[i - 1] if i else None), (notes[i + 1] if i + 1 < len(notes) else None)
                passing = prev and nxt and step(prev.pitch, e.pitch) and step(e.pitch, nxt.pitch) and direction(prev.pitch, e.pitch) == direction(e.pitch, nxt.pitch)
                if not passing:
                    self.add("s2-passing-only", self.pair(e), "A weak-beat dissonance must be a passing tone (step in, step on in the same direction).")
        for x, y in zip(notes, notes[1:]):
            if y.bar > x.bar and y.start == 0:
                self.check_pair_rules(x, y, {"parallel": "s2-barline", "contrary": "comb-no-consecutive-same-perfect", "direct": "s2-barline"})
        beats = self.downbeats()
        for x, y in zip(beats, beats[1:]):
            k1, k2 = perfect(x.pitch, self.vertical(x)), perfect(y.pitch, self.vertical(y))
            if k1 and k1 == k2 and y.bar == x.bar + 1:
                self.add("s2-downbeat-perfect", [(CP, x), (CP, y)], f"Consecutive bars begin with {k2}s.")
            if y.bar == x.bar + 1 and dissonant_span(x.pitch, y.pitch) and interval(x.pitch, y.pitch)[0] > 2:
                self.add("s2-downbeat-melody", [(CP, x), (CP, y)], "Consecutive downbeats outline a dissonant interval.")
        self.imperfect_runs(beats, "s2-downbeat-imperfect-run")

    def species_3(self):
        notes = self.notes
        cons = [consonant(e.pitch, self.vertical(e)) for e in notes]
        figure_ok = set()
        # Recognise cambiata and double-neighbor figures first.
        for i in range(len(notes) - 4):
            w = notes[i:i + 5]
            if w[0].start in (0, 2) and w[1].bar == w[0].bar:
                p = [e.pitch for e in w]
                d = direction(p[0], p[1])
                if (step(p[0], p[1]) and interval(p[1], p[2])[0] == 3 and direction(p[1], p[2]) == d
                        and step(p[2], p[3]) and step(p[3], p[4]) and direction(p[2], p[3]) == -d == direction(p[3], p[4])
                        and cons[i] and cons[i + 2] and cons[i + 4]):
                    figure_ok.update({w[1].id, w[3].id})
                    self.figures.append(("Nota cambiata", w[0], w[4]))
        for i in range(len(notes) - 4):
            w = notes[i:i + 5]
            if w[0].start == 0 and all(e.bar == w[0].bar for e in w[:4]):
                p = [e.pitch for e in w]
                if (p[0].midi == p[3].midi and step(p[0], p[1]) and step(p[0], p[2]) and direction(p[0], p[1]) == -direction(p[0], p[2])
                        and step(p[3], p[4]) and direction(p[2], p[3]) == direction(p[3], p[4])):
                    figure_ok.update({w[1].id, w[2].id})
                    self.figures.append(("Double neighbor", w[0], w[3]))
        for i, e in enumerate(notes):
            c = self.vertical(e)
            if e.start == 0 and e.bar < self.ex.bars - 1:
                if not cons[i]:
                    self.add("s3-downbeat-consonant", self.pair(e), "Beat 1 must be consonant.")
                elif perfect_kind(e.pitch, c) == "unison" and e.bar > 0:
                    self.add("s3-downbeat-consonant", self.pair(e), "Beat 1 must not be a unison.")
                continue
            if cons[i] or e.id in figure_ok:
                continue
            prev, nxt = (notes[i - 1] if i else None), (notes[i + 1] if i + 1 < len(notes) else None)
            ok = prev and nxt and step(prev.pitch, e.pitch) and step(e.pitch, nxt.pitch)
            passing = ok and direction(prev.pitch, e.pitch) == direction(e.pitch, nxt.pitch)
            neighbor = ok and direction(prev.pitch, e.pitch) == -direction(e.pitch, nxt.pitch) and prev.pitch.midi == nxt.pitch.midi
            if not (passing or neighbor):
                self.add("s3-dissonance-types", self.pair(e),
                         "This dissonance is not a passing tone, neighbor tone, double neighbor or cambiata: approach and leave it by step.")
        for i, (x, y) in enumerate(zip(notes, notes[1:])):
            # The cambiata and double neighbor leap a third away from a dissonance by definition.
            if interval(x.pitch, y.pitch)[0] >= 3 and not (cons[i] and cons[i + 1]) and x.id not in figure_ok:
                self.add("s3-leaps-consonant", [(CP, x), (CP, y)], "Leaps must connect two consonant notes.")
            if y.bar > x.bar and y.start == 0:
                self.check_pair_rules(x, y, {"parallel": "s3-barline", "contrary": "comb-no-consecutive-same-perfect", "direct": "s3-barline"})
        beats = self.downbeats()
        by_bar = {}
        for e in notes:
            by_bar.setdefault(e.bar, []).append(e)
        for b in beats:
            kind = perfect(b.pitch, self.vertical(b))
            prev = by_bar.get(b.bar - 1, [])
            if kind == "fifth":
                bad = [e for e in prev if e.start in (2, 3) and perfect(e.pitch, self.vertical(e)) == "fifth"]
            elif kind == "octave":
                bad = [e for e in prev if e.start in (1, 2, 3) and perfect(e.pitch, self.vertical(e)) == "octave"]
            else:
                bad = []
            for e in bad[:1]:
                self.add("s3-downbeat-parallels", [(CP, e), (CP, b), (CF, self.cf_at(b))], f"The downbeat {kind} echoes a {kind} late in the previous bar.")
        for x, y, z in zip(beats, beats[1:], beats[2:]):
            ks = [perfect(e.pitch, self.vertical(e)) for e in (x, y, z)]
            if ks[0] and ks[0] == ks[1] == ks[2] and z.bar == x.bar + 2:
                self.add("s3-downbeat-perfect-run", [(CP, x), (CP, y), (CP, z)], f"Three bars in a row begin with {ks[0]}s.")
        self.imperfect_runs(beats, "s3-downbeat-imperfect-run")

    def species_4(self):
        notes, bars = self.notes, self.ex.bars
        susp_kinds, broken = [], 0
        for i, e in enumerate(notes):
            c = self.vertical(e)
            nxt = notes[i + 1] if i + 1 < len(notes) else None
            if e.start == 2 and e.bar < bars - 1:
                if not consonant(e.pitch, c):
                    self.add("s4-preparation", self.pair(e), "The weak beat (which prepares the tie) must be consonant.")
            if e.start != 0 or e.bar in (0, bars - 1):
                continue
            if not e.tie_from:
                broken += 1
                if not consonant(e.pitch, c):
                    self.add("s4-breaking-species", self.pair(e), "When species is broken, the downbeat must be consonant.", "error")
                susp_kinds.append(None)
                continue
            n = simple(interval(e.pitch, c)[0])
            if consonant(e.pitch, c):
                rn = simple(interval(nxt.pitch, self.vertical(nxt))[0]) if nxt and nxt.bar == e.bar else None
                susp_kinds.append(f"{n}-{rn}" if rn else None)
                continue
            if not (nxt and nxt.bar == e.bar and step(e.pitch, nxt.pitch) and nxt.pitch.midi < e.pitch.midi and consonant(nxt.pitch, self.vertical(nxt))):
                self.add("s4-resolution", [(CP, e), (CP, nxt), (CF, self.cf_at(e))] if nxt else self.pair(e),
                         "A dissonant suspension must resolve down by step to a consonance.")
                susp_kinds.append(None)
                continue
            rn = simple(interval(nxt.pitch, self.vertical(nxt))[0])
            where = [(CP, e), (CP, nxt), (CF, self.cf_at(e))]
            if self.ex.above:
                kind = {7: "7-6", 4: "4-3", 2: "9-8"}.get(n, f"{n}-{rn}")
                if n == 2:
                    self.add("s4-suspensions-above", where,
                             "9–8 is accepted by Open Music Theory but excluded by Hutchinson; prefer 7–6 or 4–3.", "suggestion")
                elif n not in (7, 4):
                    self.add("s4-suspensions-above", where, f"An unusual suspension above the cantus ({n}–{rn}).", "suggestion")
            else:
                kind = {2: "2-3", 4: "4-5", 7: "7-8"}.get(n, f"{n}-{rn}")
                if n == 7:
                    self.add("s4-no-7-8-below", where, "Avoid the 7–8 suspension below the cantus.")
                elif n not in (2, 4):
                    self.add("s4-suspensions-below", where, f"An unusual suspension below the cantus ({n}–{rn}).", "suggestion")
            susp_kinds.append(kind)
            self.figures.append((kind.replace("-", "–") + " suspension", e, nxt))
        interior = max(1, bars - 2)
        if len([k for k in susp_kinds if k in ("7-6", "4-3", "9-8", "2-3", "4-5", "7-8")]) < interior / 3:
            self.add("s4-max-suspensions", [], "Few dissonant suspensions: they are the point of fourth species.")
        run_kind, run = None, 0
        for i, k in enumerate(susp_kinds):
            run = run + 1 if k and k == run_kind else 1
            run_kind = k
            if k in ("9-8", "4-5", "6-5") and i and susp_kinds[i - 1] == k:
                self.add("s4-suspension-runs", [], f"Two {k.replace('-', '–')} suspensions in a row.")
            if k and run == 4:
                self.add("s4-suspension-runs", [], f"Four {k.replace('-', '–')} suspensions in a row: use at most three.")
        weak = [e for e in notes if e.start == 2 and e.bar < bars - 1]
        for x, y in zip(weak, weak[1:]):
            k1, k2 = perfect(x.pitch, self.vertical(x)), perfect(y.pitch, self.vertical(y))
            if k1 and k1 == k2 and y.bar == x.bar + 1:
                self.add("s4-after-beat-parallels", [(CP, x), (CP, y)], f"{k2.capitalize()}s on consecutive weak beats.")
        if broken > 1:
            self.add("s4-breaking-species", [], f"Species is broken {broken} times; break it at most once.")
        for x, y in zip(notes, notes[1:]):
            if not y.tie_from and y.bar > x.bar:
                self.check_pair_rules(x, y, {"parallel": "comb-no-parallel-perfect", "direct": "comb-no-direct-perfect"})

    def check_s4_cadence(self):
        cf = self.cf
        if not (step(cf[-2].pitch, cf[-1].pitch) and cf[-2].pitch.midi > cf[-1].pitch.midi):
            self.add("s4-cadence", [(CF, cf[-2]), (CF, cf[-1])], "Fourth species needs a cantus ending re–do.")
            return
        pen = [e for e in self.notes if e.bar == self.ex.bars - 2]
        good = (len(pen) == 2 and pen[0].tie_from and pen[0].pitch.name == self.final.name and step(pen[0].pitch, pen[1].pitch)
                and pen[1].pitch.midi < pen[0].pitch.midi)
        if good:
            n = simple(interval(pen[0].pitch, cf[-2].pitch)[0])
            good = (self.ex.above and n == 7) or (not self.ex.above and n == 2)
        if not good:
            self.add("s4-cadence", [(CP, e) for e in pen] + [(CF, cf[-2])], "The cadence is a tied do resolving to ti: 7–6 above the cantus or 2–3 below it.")

    def species_5(self):
        notes, bars = self.notes, self.ex.bars
        cons = [consonant(e.pitch, self.vertical(e)) for e in notes]
        for i, e in enumerate(notes):
            prev, nxt = (notes[i - 1] if i else None), (notes[i + 1] if i + 1 < len(notes) else None)
            if e.dur == Fraction(1, 2):
                if not (prev and nxt and step(prev.pitch, e.pitch) and step(e.pitch, nxt.pitch)):
                    self.add("s5-eighths", [(CP, e)], "Eighth notes are approached and left by step.")
            if e.bar == bars - 1 or cons[i]:
                continue
            if e.start == 0:
                if e.tie_from and prev and cons[i - 1]:
                    later = [x for x in notes[i + 1:] if x.bar == e.bar]
                    res = next((x for x in later if x.start >= 2), None) if e.dur < 2 else (later[0] if later else None)
                    decor = [x for x in later if x.start < 2]
                    ok = res and step(e.pitch, res.pitch) and res.pitch.midi < e.pitch.midi and consonant(res.pitch, self.vertical(res))
                    ok = ok and all(consonant(x.pitch, self.vertical(x)) or x.dur == Fraction(1, 2) for x in decor)
                    if ok:
                        self.figures.append(("Suspension", e, res))
                    else:
                        self.add("s4-resolution", [(CP, e), (CF, self.cf_at(e))], "A suspension must resolve down by step to a consonance (by beat 3 if decorated).")
                else:
                    self.add("comb-vertical-consonance", self.pair(e), "An untied downbeat must be consonant.")
                continue
            if e.dur == Fraction(1, 2):
                continue
            ok = prev and nxt and step(prev.pitch, e.pitch) and step(e.pitch, nxt.pitch)
            passing = ok and direction(prev.pitch, e.pitch) == direction(e.pitch, nxt.pitch)
            neighbor = ok and direction(prev.pitch, e.pitch) == -direction(e.pitch, nxt.pitch) and prev.pitch.midi == nxt.pitch.midi and e.dur <= 1
            if e.tie_to and not cons[i]:
                self.add("s4-preparation", self.pair(e), "A note tied into the next bar must be consonant.")
            elif not (passing or neighbor):
                self.add("s3-dissonance-types", self.pair(e), "Dissonance here must be a passing or neighbor tone, approached and left by step.")
        # Ties: never a quarter tied to a following half.
        for x, y in zip(notes, notes[1:]):
            if x.tie_to and x.dur < y.dur:
                self.add("s5-strong-beat-weight", [(CP, x), (CP, y)], "A shorter note is never tied to a longer one.")
        # Eighths: one pair per bar on a weak quarter.
        for bar in range(bars):
            eighths = [e for e in notes if e.bar == bar and e.dur == Fraction(1, 2)]
            if len(eighths) > 2 or (eighths and len(eighths) % 2):
                self.add("s5-eighths", [(CP, e) for e in eighths], "Use eighth notes as a single pair per bar.")
        # Run limits.
        halves = quarters = 0
        for e in self.attacks[:-1]:
            halves = halves + 1 if e.dur == 2 else 0
            quarters = quarters + 1 if e.dur == 1 else 0
            if halves == 4:
                self.add("s5-run-limits", [(CP, e)], "More than three half notes in a row.")
            if quarters == 9:
                self.add("s5-run-limits", [(CP, e)], "More than eight quarter notes in a row.")
        for x, y in zip(notes, notes[1:]):
            if y.bar > x.bar and y.start == 0 and not y.tie_from:
                self.check_pair_rules(x, y, {"parallel": "comb-no-parallel-perfect", "direct": "comb-no-direct-perfect"})
        beats = self.downbeats()
        for x, y in zip(beats, beats[1:]):
            k1, k2 = perfect(x.pitch, self.vertical(x)), perfect(y.pitch, self.vertical(y))
            if k1 and k1 == k2 and y.bar == x.bar + 1 and interval(x.pitch, y.pitch)[0] >= 4:
                self.add("comb-no-parallel-perfect", [(CP, x), (CP, y)], f"{k2.capitalize()}s on consecutive downbeats, emphasised by a leap.", "suggestion")
        if not any(e.tie_from for e in notes):
            self.add("s5-mixture", [], "Include some suspensions so that all four species appear.")

    def run(self):
        self.figures = []
        if not self.check_rhythm():
            return
        self.check_diatonic()
        self.check_melody()
        self.check_repeats()
        self.check_spacing()
        self.check_begin_end()
        getattr(self, f"species_{self.species}")()


def _beat(start):
    beat = start + 1
    return str(int(beat)) if beat == int(beat) else str(float(beat))


def check_exercise(ex, species=None):
    """Check an exercise; returns the analysis dictionary the web interface shows."""
    species = species or detect_species(ex)
    checker = _Checker(ex, species)
    checker.run()
    rules, sources = rules_catalog()
    order = {e.id: i for i, e in enumerate(checker.cp + checker.cf)}
    findings = sorted(checker.findings, key=lambda f: (order.get(f["notes"][0]["id"], 0) if f["notes"] else -1, f["severity"] != "error"))
    intervals = []
    for e in checker.notes:
        c = checker.cf_at(e)
        intervals.append({"anchor": e.id, "roman": label(e.pitch, c.pitch), "measure": ex.measures[e.bar],
                          "beat": _beat(e.start), "offset": str(e.time), "status": "identified" if consonant(e.pitch, c.pitch) else "dissonant",
                          "reason": "Consonant" if consonant(e.pitch, c.pitch) else "Dissonant",
                          "notes": {CP: checker.data(e, CP), CF: checker.data(c, CF)}, "original_label": None, "label_matches": None})
    marks = [{"anchor": a.id, "end_anchor": b.id, "label": name, "name": name} for name, a, b in getattr(checker, "figures", [])]
    used = {f["rule"] for f in findings}
    final = ex.final
    mode = {1: "Ionian (major)", 2: "Dorian", 3: "Phrygian", 4: "Lydian", 5: "Mixolydian", 6: "Aeolian (minor)", 7: "Locrian"}
    tonic_degree = (STEPS.index(final.step) - (4 * ex.fifths) % 7) % 7 + 1
    return {
        "kind": "species", "species": species, "above": ex.above,
        "mode": f"{final.name} {mode[tonic_degree]}",
        "scope": {"reviewed_measures": ex.bars, "cantus_assumption": ex.cantus_assumed},
        "findings": findings, "harmony": intervals,
        "review": {"marks": marks}, "paradigms": [],
        "rules": {r: {k: rules[r][k] for k in ("rule", "strength", "sources", "category")} | ({"variants": rules[r]["variants"]} if "variants" in rules[r] else {})
                  for r in used if r in rules},
        "sources": {s: {"title": v["title"], "work": v["work"], "url": v["url"]} for s, v in sources.items()},
        "cantus": [str(e.pitch) for e in ex.cantus],
    }


# ---------------------------------------------------------------- writing MusicXML

TYPES = {Fraction(4): ("whole", 0), Fraction(3): ("half", 1), Fraction(2): ("half", 0),
         Fraction(1): ("quarter", 0), Fraction(1, 2): ("eighth", 0)}


def write_exercise(ex, title=None):
    """MusicXML (score-partwise) with the upper voice first."""
    root = ET.Element("score-partwise", version="4.0")
    if title:
        work = ET.SubElement(root, "work")
        ET.SubElement(work, "work-title").text = title
    voices = [("P1", "Counterpoint" if ex.above else "Cantus firmus", ex.counterpoint if ex.above else ex.cantus),
              ("P2", "Cantus firmus" if ex.above else "Counterpoint", ex.cantus if ex.above else ex.counterpoint)]
    part_list = ET.SubElement(root, "part-list")
    for pid, name, _ in voices:
        sp = ET.SubElement(part_list, "score-part", id=pid)
        ET.SubElement(sp, "part-name").text = name
    alter = scale(ex.fifths)
    for pid, name, events in voices:
        part = ET.SubElement(root, "part", id=pid)
        mean = sum(e.pitch.midi for e in events if e.pitch) / sum(1 for e in events if e.pitch)
        treble = mean >= 59
        for bar, number in enumerate(ex.measures):
            measure = ET.SubElement(part, "measure", number=number)
            if bar == 0:
                attr = ET.SubElement(measure, "attributes")
                ET.SubElement(attr, "divisions").text = "2"
                key = ET.SubElement(attr, "key")
                ET.SubElement(key, "fifths").text = str(ex.fifths)
                time = ET.SubElement(attr, "time")
                ET.SubElement(time, "beats").text = "4"
                ET.SubElement(time, "beat-type").text = "4"
                clef = ET.SubElement(attr, "clef")
                ET.SubElement(clef, "sign").text = "G" if treble else "F"
                ET.SubElement(clef, "line").text = "2" if treble else "4"
            in_bar = [e for e in events if e.bar == bar]
            accidentals = {}
            for i, e in enumerate(in_bar):
                el = ET.SubElement(measure, "note")
                if e.pitch is None:
                    ET.SubElement(el, "rest")
                else:
                    p = ET.SubElement(el, "pitch")
                    ET.SubElement(p, "step").text = e.pitch.step
                    if e.pitch.alter:
                        ET.SubElement(p, "alter").text = str(e.pitch.alter)
                    ET.SubElement(p, "octave").text = str(e.pitch.octave)
                ET.SubElement(el, "duration").text = str(int(e.dur * 2))
                if e.tie_from:
                    ET.SubElement(el, "tie", type="stop")
                if e.tie_to:
                    ET.SubElement(el, "tie", type="start")
                ET.SubElement(el, "voice").text = "1"
                kind, dots = TYPES[e.dur]
                ET.SubElement(el, "type").text = kind
                for _ in range(dots):
                    ET.SubElement(el, "dot")
                if e.pitch is not None:
                    key = (e.pitch.step, e.pitch.octave)
                    expected = accidentals.get(key, alter[e.pitch.step])
                    if e.pitch.alter != expected and not e.tie_from:
                        ET.SubElement(el, "accidental").text = {-1: "flat", 0: "natural", 1: "sharp"}.get(e.pitch.alter, "sharp")
                    accidentals[key] = e.pitch.alter
                if e.dur == Fraction(1, 2):
                    first = i + 1 < len(in_bar) and in_bar[i + 1].dur == Fraction(1, 2) and in_bar[i + 1].start == e.start + Fraction(1, 2)
                    ET.SubElement(el, "beam", number="1").text = "begin" if first else "end"
                if e.tie_from or e.tie_to:
                    notations = ET.SubElement(el, "notations")
                    if e.tie_from:
                        ET.SubElement(notations, "tied", type="stop")
                    if e.tie_to:
                        ET.SubElement(notations, "tied", type="start")
    ET.indent(root)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")


# ---------------------------------------------------------------- text input

def parse_pitches(text):
    """'D4 F4 E4 ...' (sharps '#', flats 'b') to a list of Pitch."""
    return [Pitch.parse(tok.strip()) for tok in text.replace(",", " ").split() if tok.strip()]


def exercise_from_text(cantus, counterpoint, fifths=0, above=True):
    """Build an Exercise from text.

    ``cantus`` is whole notes ("D4 F4 ..."). ``counterpoint`` lists bars separated by "|";
    each token is PITCH/QUARTERS ("A4/2"), "r/QUARTERS" for a rest, and a trailing "~"
    ties the note into the next one. Ids are assigned in reading order.
    """
    cf_pitches = parse_pitches(cantus)
    bars = [b.split() for b in counterpoint.split("|")]
    if len(bars) != len(cf_pitches):
        raise ValueError("The counterpoint needs one bar per cantus note.")
    cp, tie = [], False
    for bar, tokens in enumerate(bars):
        start = Fraction(0)
        for tok in tokens:
            tie_to = tok.endswith("~")
            name, _, dur = tok.rstrip("~").partition("/")
            dur = Fraction(dur or "4")
            pitch = None if name.lower() == "r" else Pitch.parse(name)
            cp.append(Event(bar, start, dur, pitch, tie, tie_to))
            tie, start = tie_to, start + dur
    cf = [Event(i, Fraction(0), BAR, p) for i, p in enumerate(cf_pitches)]
    ids = iter(range(1, 10_000))
    cp = tuple(replace(e, id=f"n{next(ids)}") for e in cp)
    cf = tuple(replace(e, id=f"n{next(ids)}") for e in cf)
    return Exercise(cf, cp, fifths, above, tuple(str(i + 1) for i in range(len(cf))))


def species_report(analysis, title="Species counterpoint review"):
    """Plain Markdown summary of a species analysis (the web page's download)."""
    ordinal = {1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth"}[analysis["species"]]
    side = "above" if analysis["above"] else "below"
    lines = [f"# {title}", "",
             f"{ordinal} species, counterpoint {side} the cantus firmus, {analysis['mode']}. "
             f"{analysis['scope']['reviewed_measures']} bars.", ""]
    if analysis["scope"].get("cantus_assumption"):
        lines += [analysis["scope"]["cantus_assumption"], ""]
    lines += ["Cantus firmus: " + " ".join(analysis["cantus"]), "", "## Findings", ""]
    if not analysis["findings"]:
        lines.append("No rule is broken under the species rules this checker supports.")
    for i, f in enumerate(analysis["findings"], 1):
        rule = analysis["rules"].get(f["rule"], {})
        where = f"m. {f['measure']}, beat {f['beat']}" if f["notes"] else "Whole exercise"
        lines.append(f"{i}. {f['severity'].upper()} - {where} - {f['rule']}: {f['message']}"
                     + (f" Rule ({rule['strength']}): {rule['rule']}" if rule else ""))
    figures = analysis["review"]["marks"]
    if figures:
        lines += ["", "## Figures", ""] + [f"- {m['name']}" for m in figures]
    used = sorted({s for r in analysis["rules"].values() for s in r["sources"]})
    if used:
        lines += ["", "## Sources", ""] + [f"- {analysis['sources'][s]['work']}: {analysis['sources'][s]['title']} <{analysis['sources'][s]['url']}>"
                                           for s in used if s in analysis["sources"]]
    return "\n".join(lines) + "\n"
