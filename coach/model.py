from dataclasses import dataclass, replace
from fractions import Fraction
import re

VOICES = ("S", "A", "T", "B")
STEPS = "CDEFGAB"
SEMITONES = (0, 2, 4, 5, 7, 9, 11)
RANGES = {"S": (60, 79), "A": (55, 74), "T": (48, 67), "B": (40, 60)}


@dataclass(frozen=True)
class Pitch:
    step: str
    alter: int
    octave: int

    @property
    def midi(self):
        return 12 * (self.octave + 1) + SEMITONES[STEPS.index(self.step)] + self.alter

    @property
    def diatonic(self):
        return 7 * self.octave + STEPS.index(self.step)

    @property
    def name(self):
        return self.step + ("#" * self.alter if self.alter >= 0 else "b" * -self.alter)

    def __str__(self):
        return f"{self.name}{self.octave}"

    @classmethod
    def parse(cls, value):
        match = re.fullmatch(r"([A-G])(#{1,2}|b{1,2})?(-?\d+)", value)
        if not match:
            raise ValueError(f"Invalid pitch: {value}")
        step, accidental, octave = match.groups()
        accidental = accidental or ""
        return cls(step, accidental.count("#") - accidental.count("b"), int(octave))


@dataclass(frozen=True)
class Note:
    id: str
    voice: str
    measure: str
    measure_index: int
    beat: Fraction
    duration: Fraction
    pitch: Pitch
    tied: bool = False  # continues a tie from the previous note in this voice (not a new attack)

    @property
    def start(self):
        return self.measure_index * 4 + self.beat - 1

    @property
    def end(self):
        return self.start + self.duration

    def data(self):
        data = {"id": self.id, "voice": self.voice, "measure": self.measure,
                "beat": str(self.beat), "duration": str(self.duration),
                "pitch": str(self.pitch), "midi": self.pitch.midi}
        if self.tied:
            data["tied"] = True
        return data


@dataclass(frozen=True)
class Score:
    notes: tuple[Note, ...]
    measures: tuple[str, ...]
    fifths: int
    mode: str = "major"

    def frames(self, extra_times=()):
        """(time, {voice: note}) at every onset and release."""
        for time in sorted({n.start for n in self.notes} | {n.end for n in self.notes} | set(extra_times)):
            sounding = {n.voice: n for n in self.notes if n.start <= time < n.end}
            if sounding:
                yield time, sounding

    @property
    def homophonic(self):
        """True when every voice attacks together in half and whole notes (the strict chorale format)."""
        starts = {}
        for n in self.notes:
            starts.setdefault(n.start, set()).add((n.voice, n.duration))
        return all(len(group) == 4 and len({d for _, d in group}) == 1 for group in starts.values()) and \
            not any(n.tied for n in self.notes)

    def change(self, note_id, pitch):
        return replace(self, notes=tuple(replace(n, pitch=pitch) if n.id == note_id else n
                                         for n in self.notes))

    def data(self):
        return {"key_fifths": self.fifths, "mode": self.mode, "time_signature": "4/4",
                "measures": list(self.measures), "notes": [n.data() for n in self.notes],
                "timeline": [{"offset": str(t), "notes": {v: n.id for v, n in f.items()}}
                             for t, f in self.frames()]}


def scale(fifths):
    alterations = dict.fromkeys(STEPS, 0)
    for step in ("FCGDAEB" if fifths >= 0 else "BEADGCF")[:abs(fifths)]:
        alterations[step] = 1 if fifths >= 0 else -1
    return alterations


def perfect(a, b):
    """Spelling-aware simple interval class, including compound intervals."""
    semitones = abs(a.midi - b.midi) % 12
    letters = abs(a.diatonic - b.diatonic) % 7
    if semitones == 7 and letters == 4:
        return "fifth"
    if semitones == 0 and letters == 0:
        return "octave"  # Includes unisons as the same independence convention.
    return None
