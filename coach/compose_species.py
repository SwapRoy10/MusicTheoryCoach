"""Compose a cantus firmus and species counterpoint against it.

The search fills one note at a time, pruning with the same interval helpers the
checker uses. Every finished candidate is re-checked by
``coach.counterpoint.check_exercise``; only results with no errors are
returned, and among those the one with the fewest suggestions wins.
"""
from dataclasses import replace
from fractions import Fraction
import random

from .model import Pitch, STEPS, scale, perfect
from .counterpoint import (BAR, Event, Exercise, check_cantus, check_exercise, consonant, direction, dissonant_span,
                           imperfect_kind, interval, melodic_ok, perfect_kind, simple, step)

MODES = {"dorian": "D", "phrygian": "E", "mixolydian": "G", "aeolian": "A", "ionian": "C"}
HALF, QUARTER, EIGHTH = Fraction(2), Fraction(1), Fraction(1, 2)


class SearchFailed(ValueError):
    pass


def collection(fifths, low, high):
    alter = scale(fifths)
    pitches = []
    for octave in range(1, 7):
        for s in STEPS:
            p = Pitch(s, alter[s], octave)
            if low <= p.midi <= high:
                pitches.append(p)
    return sorted(pitches, key=lambda p: p.midi)


def shifted(p, steps, fifths):
    """The diatonic neighbour ``steps`` letters away, spelled in the key."""
    d = p.diatonic + steps
    s = STEPS[d % 7]
    return Pitch(s, scale(fifths)[s], d // 7)


def leading_tone(final, fifths):
    """Step below the final, raised to a semitone unless the mode is Phrygian-like."""
    lt = shifted(final, -1, fifths)
    if final.midi - lt.midi == 2:
        lt = Pitch(lt.step, lt.alter + 1, lt.octave)
    return lt


# ---------------------------------------------------------------- cantus firmus

def suspension_ready(third_last, final):
    """Whether do can sound against the cantus's third-to-last note on either side of it.

    The fourth- and fifth-species cadence ties do over from that bar, so do must be
    consonant with it above and below: a unison, third or sixth (not a fourth or fifth).
    """
    n = simple(interval(third_last, final)[0])
    return n in (1, 3, 6, 8)


def compose_cantus(final_step="D", fifths=0, length=None, rng=None, node_limit=20000):
    rng = rng or random.Random()
    length = length or rng.randint(9, 12)
    alter = scale(fifths)
    final = Pitch(final_step, alter[final_step], 4)
    if final.midi > 67:
        final = Pitch(final_step, alter[final_step], 3)
    pool = [p for p in collection(fifths, final.midi - 5, final.midi + 16)]
    re = shifted(final, 1, fifths)
    nodes = 0
    climax_at = rng.randint(length // 3, (2 * length) // 3)

    def candidates(seq):
        i = len(seq)
        if i == length - 1:
            return [final]
        if i == length - 2:
            return [re]
        last = seq[-1]
        options = []
        for p in pool:
            if p.midi == last.midi or not melodic_ok(last, p):
                continue
            n = interval(last, p)[0]
            weight = {2: 6, 3: 3, 4: 1.4, 5: 1, 6: 0.4, 8: 0.3}.get(n, 0)
            toward = 1 if i < climax_at else -1
            if direction(last, p) == toward:
                weight *= 1.6
            options.append((weight * rng.random(), p))
        return [p for _, p in sorted(options, key=lambda x: -x[0])]

    def ok(seq):
        a = seq
        if len(a) >= 3:
            x, y, z = a[-3:]
            if interval(x, y)[0] >= 4 and not (step(y, z) and direction(x, y) != direction(y, z)):
                return False
            if interval(x, y)[0] >= 3 and interval(y, z)[0] >= 3 and direction(x, y) == direction(y, z):
                return False
        if len(a) >= 4 and a[-4] == a[-2] and a[-3] == a[-1]:
            return False  # x-y-x-y oscillation
        if len(a) >= 4 and any(tuple(a[-3:]) == tuple(a[i:i + 3]) for i in range(len(a) - 3)):
            return False  # a three-note figure repeated
        if len(a) == length and max(p.midi for p in a) - min(p.midi for p in a) < 7:
            return False  # span at least a fifth
        if len(a) == length - 2 and not suspension_ready(a[-1], final):
            return False
        if max(p.midi for p in a) - min(p.midi for p in a) > 16:
            return False
        if sum(interval(x, y)[0] >= 3 for x, y in zip(a, a[1:])) > max(2, length // 3):
            return False
        return True

    def search(seq):
        nonlocal nodes
        nodes += 1
        if nodes > node_limit:
            raise SearchFailed("cantus")
        if len(seq) == length:
            return seq if not check_cantus(seq, fifths) else None
        for p in candidates(seq):
            nxt = seq + [p]
            if ok(nxt):
                found = search(nxt)
                if found:
                    return found
        return None

    for _ in range(40):
        nodes = 0
        try:
            result = search([final])
        except SearchFailed:
            result = None
        if result:
            return result
        climax_at = rng.randint(length // 3, (2 * length) // 3)
    raise SearchFailed("Could not compose a cantus firmus; try again.")


# ---------------------------------------------------------------- rhythm plans

def rhythm_plan(species, bars, rng):
    """List of slots: (bar, start, dur, tie_from, tie_to). Rests are separate entries with pitch None."""
    plan = []
    last = bars - 1
    if species == 1:
        return [(b, Fraction(0), BAR, False, False) for b in range(bars)]
    if species == 2:
        plan.append((0, Fraction(0), HALF, "rest", False))
        plan.append((0, HALF, HALF, False, False))
        for b in range(1, last):
            plan += [(b, Fraction(0), HALF, False, False), (b, HALF, HALF, False, False)]
    elif species == 3:
        plan.append((0, Fraction(0), QUARTER, "rest", False))
        plan += [(0, Fraction(q), QUARTER, False, False) for q in (1, 2, 3)]
        for b in range(1, last):
            plan += [(b, Fraction(q), QUARTER, False, False) for q in range(4)]
    elif species == 4:
        plan.append((0, Fraction(0), HALF, "rest", False))
        plan.append((0, HALF, HALF, False, True))
        for b in range(1, last):
            plan += [(b, Fraction(0), HALF, True, False), (b, HALF, HALF, False, b < last - 1)]
    elif species == 5:
        plan = florid_plan(bars, rng)
        return plan
    plan.append((last, Fraction(0), BAR, False, False))
    return plan


FREE = [  # (start, dur) bar templates for florid counterpoint
    ((0, 2), (2, 2)),
    ((0, 1), (1, 1), (2, 1), (3, 1)),
    ((0, 2), (2, 1), (3, 1)),
    ((0, 1), (1, 1), (2, 2)),
    ((0, 3), (3, 1)),
    ((0, 2), (2, 1), (3, 0.5), (3.5, 0.5)),
    ((0, 1), (1, 0.5), (1.5, 0.5), (2, 2)),
]
TIED = [  # templates whose first note continues a tie from the previous bar
    ((0, 2), (2, 2)),
    ((0, 2), (2, 1), (3, 1)),
    ((0, 1), (1, 1), (2, 2)),
    ((0, 1), (1, 0.5), (1.5, 0.5), (2, 2)),
]


def florid_plan(bars, rng):
    last = bars - 1
    plan = [(0, Fraction(0), HALF, "rest", False), (0, HALF, HALF, False, True)]
    tied = True
    previous = None
    for b in range(1, last):
        ends_on_half = lambda t: tuple(t[-1]) == (2, 2)
        if b == last - 1:
            template = rng.choice([TIED[0], TIED[2]])  # suspension cadence, plain or decorated
        elif b == last - 2:  # must end with a half note tied into the cadence
            template = rng.choice([t for t in (TIED if tied else FREE) if ends_on_half(t)])
        elif tied:
            template = rng.choice([t for t in TIED if t != previous] or TIED)
        else:
            template = rng.choice([t for t in FREE if t != previous])
        previous = template
        slots = [(b, Fraction(s).limit_denominator(2), Fraction(d).limit_denominator(2)) for s, d in template]
        for i, (bar, start, dur) in enumerate(slots):
            tie_from = tied and i == 0
            ends_half = i == len(slots) - 1 and dur == HALF and start == HALF
            tie_to = ends_half and (b == last - 2 or (b < last - 2 and rng.random() < 0.55))
            plan.append((bar, start, dur, tie_from, tie_to))
        tied = plan[-1][4]
    plan.append((last, Fraction(0), BAR, False, False))
    # Respect run limits: at most three halves and eight quarters in a row (checked again later).
    return plan


# ---------------------------------------------------------------- counterpoint search

class _Composer:
    def __init__(self, cantus, fifths, species, above, rng, node_limit):
        self.cf = cantus
        self.fifths, self.species, self.above, self.rng = fifths, species, above, rng
        self.node_limit = node_limit
        self.bars = len(cantus)
        self.final = cantus[-1]
        lo, hi = min(p.midi for p in cantus), max(p.midi for p in cantus)
        if above:
            self.pool = collection(fifths, lo, hi + 14)
        else:
            self.pool = collection(fifths, lo - 14, hi)
        self.lt = leading_tone(self.final, fifths)
        self.cf_up_end = cantus[-2].midi > cantus[-1].midi  # cantus ends re-do

    # -- forced pitches for the cadence
    def finals(self, prev):
        options = [p for p in self.pool + [Pitch(self.final.step, self.final.alter, o) for o in range(2, 7)]
                   if p.name == self.final.name and perfect_kind(p, self.final) in ("unison", "octave")
                   and ((self.above and p.midi >= self.final.midi) or (not self.above and p.midi <= self.final.midi))]
        options = sorted(set(options), key=lambda p: abs(p.midi - prev.midi) if prev else 0)
        return [p for p in options if not prev or step(prev, p)]

    def penultimate(self):
        """The counterpoint's note against the cantus's penultimate note."""
        if self.cf_up_end:  # cantus re-do: counterpoint ti-do
            lt = self.lt if (self.final.midi - shifted(self.final, -1, self.fifths).midi == 2 and
                             self.cf[-2].midi - self.final.midi == 2) else shifted(self.final, -1, self.fifths)
            name = lt
        else:  # cantus ti-do: counterpoint re-do
            name = shifted(self.final, 1, self.fifths)
        return [p for p in (Pitch(name.step, name.alter, o) for o in range(2, 7))
                if (self.above and p.midi > self.cf[-2].midi) or (not self.above and p.midi < self.cf[-2].midi)]

    def compose(self, plan, max_soft=0):
        self.max_soft, self.soft_used, self._soft = max_soft, 0, 0
        self.plan = plan
        self.pitched = [i for i, s in enumerate(plan) if s[3] != "rest"]
        self.result = [None] * len(plan)
        self.broken = set()
        self.nodes = 0
        try:
            return self.fill(0)
        except _Budget:
            return None

    def fill(self, k):
        self.nodes += 1
        if self.nodes > self.node_limit:
            raise _Budget()
        if k == len(self.plan):
            return list(self.result)
        bar, start, dur, tie_from, tie_to = self.plan[k]
        if tie_from == "rest":
            self.result[k] = None
            return self.fill(k + 1)
        base = self.soft_used
        for p in self.candidates(k):
            if self.accept(k, p, base):
                self.result[k] = p
                done = self.fill(k + 1)
                if done:
                    return done
            self.soft_used = base
        # Break species: move on the downbeat instead of tying (once in fourth species).
        extra = 0 if self.species == 5 or not self.broken else 1  # a second break is a style fault
        if tie_from is True and bar < self.bars - 2 and base + extra <= self.max_soft:
            self.broken.add(k)
            for p in self.candidates(k):
                if self.accept(k, p, base + extra):
                    self.result[k] = p
                    done = self.fill(k + 1)
                    if done:
                        return done
                self.soft_used = base
            self.broken.discard(k)
        self.result[k] = None
        return None

    def accept(self, k, p, base):
        """Hard rules must hold; 'avoid' rules may be bent within the soft budget."""
        self._soft = 0
        if not self.ok(k, p):
            return False
        if base + self._soft > self.max_soft:
            return False
        self.soft_used = base + self._soft
        return True

    def soft(self):
        self._soft += 1
        return True

    def tied(self, i):
        return self.plan[i][3] is True and i not in self.broken

    # -- helpers on the partial result
    def prev_index(self, k):
        j = k - 1
        while j >= 0 and self.result[j] is None:
            j -= 1
        return j if j >= 0 else None

    def attack_indices(self, upto):
        return [i for i in range(upto) if self.result[i] is not None and not self.plan[i][3] is True]

    def candidates(self, k):
        bar, start, dur, tie_from, tie_to = self.plan[k]
        j = self.prev_index(k)
        prev = self.result[j] if j is not None else None
        if self.tied(k):
            return [prev]
        last_bar = self.bars - 1
        if bar == last_bar:
            return self.finals(prev)
        # The final attack of the penultimate bar is ti (or re).
        is_last_in_pen = bar == last_bar - 1 and (k + 1 == len(self.plan) - 1)
        if is_last_in_pen:
            return [p for p in self.penultimate() if not prev or (melodic_ok(prev, p) and prev.midi != p.midi)]
        extra = []
        if k + 2 == len(self.plan) - 1 and self.penultimate():
            lt = self.penultimate()[0]
            six = shifted(lt, -1, self.fifths)
            if (lt.midi - six.midi) % 12 == 3:  # augmented second: raise the sixth as well
                extra = [Pitch(six.step, six.alter + 1, o) for o in range(2, 7)]
        if self.species in (4, 5) and bar == last_bar - 2 and tie_to:
            # The note tied into the penultimate bar must lead to the cadence note: ideally the step
            # above it (the 7-6 / 2-3 / 4-3 cadential suspension), otherwise any consonant approach.
            # It is do, which becomes the 7-6 (above) or 2-3 (below) cadential suspension.
            return [p for p in self.pool if p.name == self.final.name and (prev is None or melodic_ok(prev, p))]
        c = self.cf[bar]
        scored = []
        for p in self.pool + extra:
            if prev is not None and not melodic_ok(prev, p):
                continue
            w = 1.0
            if prev is not None:
                n = interval(prev, p)[0]
                w *= {2: 5, 3: 2.2, 4: 1.1, 5: 0.8, 6: 0.25, 8: 0.25}.get(n, 0.1)
            if consonant(p, c):
                w *= 1.8 if imperfect_kind(p, c) else 1.0
            elif self.species in (2, 3, 5) and start != 0:
                w *= 0.7
            scored.append((w * (0.35 + self.rng.random()), p))
        scored.sort(key=lambda x: -x[0])
        return [p for _, p in scored]

    def ok(self, k, p):
        bar, start, dur, tie_from, tie_to = self.plan[k]
        c = self.cf[bar]
        sp = self.species
        # Range, spacing, crossing.
        if abs(p.midi - c.midi) > 19 or (self.above and p.midi < c.midi) or (not self.above and p.midi > c.midi):
            return False
        j = self.prev_index(k)
        prev = self.result[j] if j is not None else None
        pslot = self.plan[j] if j is not None else None
        attack = not self.tied(k)
        tie_from = self.tied(k)
        cons = consonant(p, c)
        first = prev is None
        if first:
            kind = perfect_kind(p, c)
            if self.above:
                return kind in ("unison", "octave", "fifth") and (p.name == self.final.name or kind == "fifth")
            return kind in ("unison", "octave") and p.name == self.final.name
        if attack:
            if p.midi == prev.midi:
                return False
            if not melodic_ok(prev, p):
                return False
            # Overlap at a bar line.
            if bar > pslot[0]:
                pc = self.cf[pslot[0]]
                if self.above and (p.midi < pc.midi or c.midi > prev.midi):
                    return False
                if not self.above and (p.midi > pc.midi or c.midi < prev.midi):
                    return False
            attacks = [i for i in range(k) if self.result[i] is not None and not self.tied(i)]
            if len(attacks) >= 2:
                a2, a1 = self.result[attacks[-2]], self.result[attacks[-1]]
                if interval(a2, a1)[0] >= 4 and not (step(a1, p) and direction(a2, a1) != direction(a1, p)):
                    return False
                if interval(a2, a1)[0] >= 3 and interval(a1, p)[0] >= 3 and direction(a2, a1) == direction(a1, p):
                    if not consonant(a2, p) or interval(a2, p)[0] > 8:
                        self.soft()
                if len(attacks) >= 3:
                    a3 = self.result[attacks[-3]]
                    if a3.midi == a1.midi and a2.midi == p.midi:  # x-y-x-y oscillation is aimless
                        return False
                    if all(interval(x, y)[0] >= 3 for x, y in ((a3, a2), (a2, a1), (a1, p))):
                        self.soft()
                # Turning-point spans should not outline a dissonance.
                if direction(a2, a1) != direction(a1, p):
                    turn = self.last_turn(attacks)
                    if turn is not None and dissonant_span(turn, a1) and interval(turn, a1)[0] > 2:
                        self.soft()
            # Keep the line within a tenth (a style preference).
            seen = [self.result[i] for i in attacks] + [p]
            if max(x.midi for x in seen) - min(x.midi for x in seen) > 16:
                return False
        # Dissonance left by the previous note must be completed correctly now.
        if not self.resolve_previous(k, p):
            return False
        return getattr(self, f"ok{sp}")(k, p, c, prev, pslot, cons)

    def last_turn(self, attacks):
        seq = [self.result[i] for i in attacks]
        turn = seq[0]
        for i in range(1, len(seq) - 1):
            d1, d2 = direction(seq[i - 1], seq[i]), direction(seq[i], seq[i + 1])
            if d1 and d2 and d1 != d2:
                turn = seq[i]
        return turn

    def resolve_previous(self, k, p):
        j = self.prev_index(k)
        if j is None:
            return True
        b, s, d, tf, tt = self.plan[j]
        q = self.result[j]
        if consonant(q, self.cf[b]) or self.tied(j):
            return True
        i = self.prev_index(j)
        if i is None:
            return False
        o = self.result[i]
        if not (step(o, q) and step(q, p)):
            return False
        passing = direction(o, q) == direction(q, p)
        neighbor = direction(o, q) == -direction(q, p) and o.midi == p.midi
        if self.species == 2:
            return passing
        return passing or neighbor

    def motion_ok(self, prev, pc, p, c, direct=True, contrary_same=True):
        dcp, dcf = direction(prev, p), direction(pc, c)
        k1, k2 = perfect(prev, pc), perfect(p, c)
        if dcp and dcf and dcp == dcf and k2 and (k1 == k2 or direct):
            return False
        if contrary_same and k1 and k1 == k2:
            return False
        return True

    def run_ok(self, points, p, c, limit=3):
        """No more than ``limit`` of the same imperfect consonance in a row."""
        kind = imperfect_kind(p, c)
        if not kind:
            return True
        run = 1
        for q, qc in reversed(points):
            if imperfect_kind(q, qc) == kind:
                run += 1
            else:
                break
        return run <= limit

    def history(self, k, where):
        out = []
        for i in range(k):
            q = self.result[i]
            if q is not None and where(self.plan[i]):
                out.append((q, self.cf[self.plan[i][0]], self.plan[i]))
        return out

    # -- species rules (pruning)
    def ok1(self, k, p, c, prev, pslot, cons):
        if not cons:
            return False
        if perfect_kind(p, c) == "unison" and 0 < self.plan[k][0] < self.bars - 1:
            return False
        pc = self.cf[pslot[0]]
        if not self.motion_ok(prev, pc, p, c):
            return False
        if direction(prev, p) == direction(pc, c) and interval(prev, p)[0] >= 4:
            self.soft()
        hist = [(q, qc) for q, qc, _ in self.history(k, lambda s: True)]
        perfects = sum(1 for q, qc in hist if perfect(q, qc))
        if perfect(p, c) and 0 < self.plan[k][0] < self.bars - 1 and perfects >= len(hist) // 2:
            return False
        if not self.run_ok(hist, p, c):
            self.soft()
        return True

    def downbeat_rules(self, k, p, c, kind_limit=2):
        beats = [(q, qc, s) for q, qc, s in self.history(k, lambda s: s[1] == 0 and s[3] != "rest")]
        if not beats:
            return True
        q, qc, s = beats[-1]
        if s[0] == self.plan[k][0] - 1:
            same = perfect(q, qc) and perfect(q, qc) == perfect(p, c)
            if same and (self.species == 2 or len(beats) >= 2 and perfect(beats[-2][0], beats[-2][1]) == perfect(p, c)):
                return False
            if self.species == 2 and dissonant_span(q, p) and interval(q, p)[0] > 2:
                self.soft()
        if not self.run_ok([(x, y) for x, y, _ in beats], p, c):
            self.soft()
        return True

    def ok2(self, k, p, c, prev, pslot, cons):
        bar, start = self.plan[k][0], self.plan[k][1]
        if start == 0:
            if not cons or (perfect_kind(p, c) == "unison" and bar < self.bars - 1):
                return False
            if not self.motion_ok(prev, self.cf[pslot[0]], p, c):
                return False
            if bar == self.bars - 2 and not self.cadence_reachable(prev, p, c):
                return False
            return self.downbeat_rules(k, p, c)
        if not cons:
            j = self.prev_index(k)
            return step(self.result[j], p)
        return True

    def cadence_reachable(self, prev, p, c):
        """Penultimate downbeat: it must lead properly to the cadence note, and not form the final's perfect kind."""
        if perfect(p, c) and perfect(p, c) == perfect(self.final, self.final):
            return False
        big = interval(prev, p)[0] >= 4
        for q in self.penultimate():
            if q.midi == p.midi or not melodic_ok(p, q):
                continue
            if big and not (step(p, q) and direction(prev, p) != direction(p, q)):
                continue
            return True
        return False

    def ok3(self, k, p, c, prev, pslot, cons):
        bar, start = self.plan[k][0], self.plan[k][1]
        if not cons:
            if start == 0:
                return False
            return step(prev, p)
        # Leaps connect consonances.
        if interval(prev, p)[0] >= 3 and not consonant(prev, self.cf[pslot[0]]):
            return False
        if start == 0:
            if perfect_kind(p, c) == "unison" and bar < self.bars - 1:
                return False
            if not self.motion_ok(prev, self.cf[pslot[0]], p, c):
                return False
            kind = perfect(p, c)
            prev_bar = [(q, qc, s) for q, qc, s in self.history(k, lambda s: s[0] == bar - 1)]
            for q, qc, s in prev_bar:
                if kind == "fifth" and s[1] in (2, 3) and perfect(q, qc) == "fifth":
                    return False
                if kind == "octave" and s[1] in (1, 2, 3) and perfect(q, qc) == "octave":
                    return False
            return self.downbeat_rules(k, p, c)
        return True

    def suspension_ok(self, p, c):
        """Allowed dissonant suspension intervals for the composer (the preferred ones)."""
        n = simple(interval(p, c)[0])
        return n in ((7, 4, 2) if self.above else (2, 4))

    def ok4(self, k, p, c, prev, pslot, cons):
        bar, start, dur, tie_from, tie_to = self.plan[k]
        if k in self.broken:  # species broken: second-species downbeat
            return cons and perfect_kind(p, c) != "unison" and self.motion_ok(prev, self.cf[pslot[0]], p, c)
        if tie_from is True:
            return self.held_ok(p, c)
        # Weak beat.
        if not cons:
            return False
        pi = self.prev_index(k)
        down = self.result[pi]
        if self.plan[pi][0] == bar and not consonant(down, c):  # resolve the suspension down by step
            if not (step(down, p) and p.midi < down.midi):
                return False
        if tie_to and not self.held_ok(p, self.cf[bar + 1]):
            return False
        weak = [(q, qc) for q, qc, s in self.history(k, lambda s: s[1] == HALF and s[3] is not True)]
        if weak and perfect(weak[-1][0], weak[-1][1]) and perfect(weak[-1][0], weak[-1][1]) == perfect(p, c):
            self.soft()
        return True

    def held_ok(self, p, c):
        """A note held over the bar line: consonant, or a suspension whose step-down resolution is consonant."""
        if consonant(p, c):
            return True
        return self.suspension_ok(p, c) and consonant(shifted(p, -1, self.fifths), c)

    def ok5(self, k, p, c, prev, pslot, cons):
        bar, start, dur, tie_from, tie_to = self.plan[k]
        tie_from = self.tied(k)
        if tie_from:
            return self.held_ok(p, c)
        down_i = next((i for i in range(k) if self.plan[i][0] == bar and self.plan[i][1] == 0 and self.result[i] is not None), None)
        down = self.result[down_i] if down_i is not None else None
        suspended = down_i is not None and self.tied(down_i) and not consonant(down, c)
        if suspended:
            if start == 2:
                return cons and step(down, p) and p.midi < down.midi
            if dur == QUARTER:
                return cons
            return step(prev, p)  # eighth decoration
        if start == 0:
            if not cons or (perfect_kind(p, c) == "unison" and bar < self.bars - 1):
                return False
            return self.motion_ok(prev, self.cf[pslot[0]], p, c) and self.downbeat_rules(k, p, c)
        if dur == EIGHTH:
            return step(prev, p)
        if tie_to:
            return cons and self.held_ok(p, self.cf[bar + 1])
        if not cons:
            return step(prev, p)
        if interval(prev, p)[0] >= 3 and not consonant(prev, self.cf[pslot[0]]):
            return False
        return True


class _Budget(Exception):
    pass


def to_exercise(cantus, plan, pitches, fifths, above, broken=()):
    cf = tuple(Event(i, Fraction(0), BAR, p, id=f"c{i}") for i, p in enumerate(cantus))
    cp = []
    for n, ((bar, start, dur, tie_from, tie_to), p) in enumerate(zip(plan, pitches)):
        tied_in = tie_from is True and n not in broken
        tied_out = bool(tie_to) and n + 1 not in broken
        cp.append(Event(bar, start, dur, p, tied_in, tied_out, id=f"p{n}"))
    return Exercise(cf, tuple(cp), fifths, above, tuple(str(i + 1) for i in range(len(cantus))))


def compose_counterpoint(cantus, fifths, species, above=True, seed=None, tries=200, node_limit=1200, seconds=2.0):
    """Return (exercise, analysis) with zero errors and the fewest suggestions found.

    Many short randomized searches (restarts) beat one long one: an unlucky early
    choice otherwise traps the search.
    """
    import time
    if species in (4, 5):
        if not (len(cantus) >= 3 and step(cantus[-2], cantus[-1]) and cantus[-2].midi > cantus[-1].midi):
            raise SearchFailed("The fourth- and fifth-species cadence needs a cantus that ends re–do (stepping down to the final).")
        if not suspension_ready(cantus[-3], cantus[-1]):
            raise SearchFailed("The cadential suspension ties do over from the cantus's third-to-last note, so that note must "
                               "form a unison, third or sixth with the final. Change it (for example to mi or la) and try again.")
    rng = random.Random(seed)
    best = None
    deadline = time.monotonic() + seconds
    for attempt in range(tries):
        if time.monotonic() > deadline and best:
            break
        if time.monotonic() > deadline + seconds:
            break
        plan = rhythm_plan(species, len(cantus), rng)
        composer = _Composer(cantus, fifths, species, above, rng, node_limit)
        # Strict first; then allow a growing number of style faults ('avoid' rules), by time or attempts.
        elapsed = 1 - max(0.0, deadline - time.monotonic()) / seconds
        level = max(0 if elapsed < 0.3 else 1 if elapsed < 0.65 else 2, min(3, attempt // 25))
        pitches = composer.compose(plan, max_soft=level)
        if not pitches:
            continue
        ex = to_exercise(cantus, plan, pitches, fifths, above, composer.broken)
        analysis = check_exercise(ex, species)
        errors = sum(f["severity"] == "error" for f in analysis["findings"])
        if errors:
            continue
        score = len(analysis["findings"])
        if best is None or score < best[0]:
            best = (score, ex, analysis)
        if score == 0:
            break
    if best is None:
        raise SearchFailed("No counterpoint satisfying every required rule was found for this cantus. Try another cantus, or the other side of it.")
    return best[1], best[2]


ORDINAL = {1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth"}


def compose_species(species, mode="dorian", above=True, cantus=None, seed=None, length=None, seconds=2.0):
    """Compose a complete exercise: (musicxml, exercise, analysis).

    ``cantus`` is an optional list of Pitch (or text such as "D4 F4 E4 D4"); when it
    is omitted a cantus is composed in ``mode`` (white-note modes) and replaced with a
    fresh one if no counterpoint against it passes every required rule.
    """
    from .counterpoint import check_cantus, parse_pitches, write_exercise
    if species not in ORDINAL:
        raise ValueError("Species must be 1 to 5.")
    rng = random.Random(seed)
    if isinstance(cantus, str):
        cantus = parse_pitches(cantus)
    if cantus:
        if len(cantus) < 5:
            raise SearchFailed("A cantus firmus needs at least five notes.")
        problems = [f for f in check_cantus(cantus, 0) if f.get("severity") == "error"]
        if problems:
            raise SearchFailed("The cantus breaks a required rule: " + problems[0]["message"])
        ex, analysis = compose_counterpoint(cantus, 0, species, above, seed=rng.random(), seconds=seconds)
    else:
        if mode not in MODES:
            raise ValueError(f"Mode must be one of {', '.join(MODES)}.")
        last = None
        for _ in range(4):
            cantus = compose_cantus(MODES[mode], 0, length, rng)
            try:
                ex, analysis = compose_counterpoint(cantus, 0, species, above, seed=rng.random(), seconds=seconds)
                break
            except SearchFailed as error:
                last = error
        else:
            raise last
    side = "above" if above else "below"
    title = f"{ORDINAL[species]} species, counterpoint {side} the cantus"
    return write_exercise(ex, title=title), ex, analysis
