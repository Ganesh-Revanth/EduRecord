from __future__ import annotations

from abc import ABC, abstractmethod
from typing import NamedTuple

from errors import ValidationError


# grading scheme
class GradingScheme(ABC):
    @abstractmethod
    def grade_for(self, percentage: float) -> str: ...

    @abstractmethod
    def describe(self) -> list[str]: ...


# letter bands
class BandGradingScheme(GradingScheme):
    DEFAULT_BANDS = ((90, "A+"), (80, "A"), (70, "B"), (60, "C"),
                     (50, "D"), (40, "E"), (0, "F"))

    def __init__(self, bands=None):
        raw = [(float(m), str(g).strip()) for m, g in (bands or self.DEFAULT_BANDS)]
        self._bands = self._validate(raw)

    # validate bands
    @staticmethod
    def _validate(bands):
        if not bands:
            raise ValidationError("At least one grade band is required.")
        bands = sorted(bands, key=lambda b: -b[0])
        mins = [b[0] for b in bands]
        grades = [b[1] for b in bands]
        if any(m < 0 or m > 100 for m in mins):
            raise ValidationError("Band minimums must be between 0 and 100.")
        if mins[-1] != 0:
            raise ValidationError("The lowest band must start at 0.")
        if len(set(mins)) != len(mins):
            raise ValidationError("Two bands share the same minimum.")
        if any(not g for g in grades) or len(set(grades)) != len(grades):
            raise ValidationError("Grade labels must be non-empty and unique.")
        return bands

    @property
    def bands(self):
        return list(self._bands)

    def grade_for(self, percentage: float) -> str:
        for minimum, grade in self._bands:
            if percentage >= minimum:
                return grade
        return self._bands[-1][1]

    def describe(self) -> list[str]:
        lines, upper = [], None
        for lo, grade in self._bands:
            if upper is None:
                lines.append(f"{lo:g} to 100 : {grade}")
            else:
                lines.append(f"{lo:g} to below {upper:g} : {grade}")
            upper = lo
        return lines


# pass fail scheme
class PassFailGradingScheme(GradingScheme):
    def __init__(self, threshold: float = 40.0):
        self._threshold = threshold

    def grade_for(self, percentage: float) -> str:
        return "PASS" if percentage >= self._threshold else "FAIL"

    def describe(self) -> list[str]:
        return [f"{self._threshold:g} and above : PASS", f"Below {self._threshold:g} : FAIL"]


# ranked item
class RankedEntry(NamedTuple):
    rank: int
    result: object


# grade calculator
class GradeCalculator:
    def __init__(self, scheme: GradingScheme | None = None, pass_percentage: float = 40.0):
        self._scheme = scheme or BandGradingScheme()
        self.pass_percentage = pass_percentage

    @property
    def scheme(self) -> GradingScheme:
        return self._scheme

    @property
    def pass_percentage(self) -> float:
        return self._pass_percentage

    @pass_percentage.setter
    def pass_percentage(self, value: float) -> None:
        value = float(value)
        if not 0 <= value <= 100:
            raise ValidationError("Pass percentage must be between 0 and 100.")
        self._pass_percentage = value

    def grade(self, percentage: float) -> str:
        return self._scheme.grade_for(round(percentage, 2))

    # check subject
    def subject_passed(self, obtained: float, maximum: float) -> bool:
        return (obtained / maximum) * 100 >= self._pass_percentage - 1e-9

    # check overall
    def overall_passed(self, result) -> bool:
        return result.is_complete and not result.failed_subjects

    # calc ranks
    def rank(self, results, include_failed: bool = True) -> list[RankedEntry]:
        pool = [r for r in results if r.is_complete]
        if not include_failed:
            pool = [r for r in pool if self.overall_passed(r)]
        pool.sort(key=lambda r: (-r.percentage, -r.total_obtained, r.student.name.lower()))
        ranked, prev_pct, prev_rank = [], None, 0
        for index, result in enumerate(pool, start=1):
            if result.percentage != prev_pct:
                prev_rank, prev_pct = index, result.percentage
            ranked.append(RankedEntry(prev_rank, result))
        return ranked
