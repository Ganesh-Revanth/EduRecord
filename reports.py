"""Report card and merit list rendering (abstract ReportCard, two formats)."""
from __future__ import annotations

import csv
import io
import os
from abc import ABC, abstractmethod

from models import Result, fmt_num

W = 76


class ReportCard(ABC):
    """Abstract report card: subclasses decide how it is rendered."""

    extension = "txt"

    def __init__(self, result: Result, rank: int | None = None, ranked_total: int | None = None):
        self._result, self._rank, self._ranked_total = result, rank, ranked_total

    @abstractmethod
    def render(self) -> str: ...

    def filename(self) -> str:
        r = self._result
        return f"report_card_S{r.student.student_id}_E{r.exam.exam_id}.{self.extension}"

    def save(self, directory: str = "reports") -> str:
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, self.filename())
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(self.render())
        return path

    def _rank_text(self) -> str:
        if self._rank is None:
            return "Not ranked (marks incomplete)"
        return f"{self._rank} of {self._ranked_total}"


class TextReportCard(ReportCard):
    extension = "txt"

    def render(self) -> str:
        r, st, ex = self._result, self._result.student, self._result.exam
        calc = r.calculator
        out = ["=" * W, "STUDENT REPORT CARD".center(W), "=" * W,
               f"Exam       : {ex.name} ({ex.exam_type}) - {ex.exam_date:%d %b %Y}",
               f"Student ID : {st.student_id}",
               f"Name       : {st.name}",
               f"Department : {st.department}    Semester: {st.semester}",
               "-" * W,
               f"{'Code':<10}{'Subject':<28}{'Max':>7}{'Marks':>8}{'%':>8}{'Grade':>7}{'Result':>8}",
               "-" * W]
        for m in r.marks:
            name = m.subject.name[:26]
            if m.is_entered:
                out.append(f"{m.subject.code:<10}{name:<28}{fmt_num(m.max_marks):>7}"
                           f"{fmt_num(m.obtained):>8}{m.percentage:>8.2f}{r.subject_grade(m):>7}"
                           f"{'PASS' if r.subject_passed(m) else 'FAIL':>8}")
            else:
                out.append(f"{m.subject.code:<10}{name:<28}{fmt_num(m.max_marks):>7}"
                           f"{'-':>8}{'-':>8}{'-':>7}{'N/E':>8}")
        out += ["-" * W,
                f"Total Marks : {fmt_num(r.total_obtained)} / {fmt_num(r.total_max)}",
                f"Percentage  : {r.percentage:.2f}%",
                f"Grade       : {r.grade}",
                f"Rank        : {self._rank_text()}",
                f"Overall     : {r.status}"]
        if r.failed_subjects:
            out.append("Failed in   : " + ", ".join(m.subject.code for m in r.failed_subjects))
        if not r.is_complete:
            out.append("Note        : N/E = marks not entered yet.")
        out.append(f"(Pass mark: {calc.pass_percentage:g}% in every subject)")
        out.append("=" * W)
        return "\n".join(out) + "\n"


class CsvReportCard(ReportCard):
    extension = "csv"

    def render(self) -> str:
        r, st, ex = self._result, self._result.student, self._result.exam
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Student ID", st.student_id, "Name", st.name])
        w.writerow(["Exam", ex.name, "Type", ex.exam_type, "Date", ex.exam_date.isoformat()])
        w.writerow([])
        w.writerow(["Code", "Subject", "Max", "Obtained", "Percentage", "Grade", "Result"])
        for m in r.marks:
            if m.is_entered:
                w.writerow([m.subject.code, m.subject.name, fmt_num(m.max_marks), fmt_num(m.obtained),
                            f"{m.percentage:.2f}", r.subject_grade(m),
                            "PASS" if r.subject_passed(m) else "FAIL"])
            else:
                w.writerow([m.subject.code, m.subject.name, fmt_num(m.max_marks), "", "", "", "NOT ENTERED"])
        w.writerow([])
        w.writerow(["Total", fmt_num(r.total_obtained), "Of", fmt_num(r.total_max)])
        w.writerow(["Percentage", f"{r.percentage:.2f}", "Grade", r.grade])
        w.writerow(["Rank", self._rank_text(), "Overall", r.status])
        return buf.getvalue()


class MeritListReport:
    """Formats ranked entries (from GradeCalculator.rank) as a merit list."""

    def __init__(self, exam, ranked_entries):
        self._exam, self._entries = exam, ranked_entries

    def render(self) -> str:
        out = ["=" * W, f"MERIT LIST - {self._exam.name} ({self._exam.exam_type})".center(W), "=" * W,
               f"{'Rank':<6}{'ID':<6}{'Name':<26}{'Total':>12}{'%':>9}{'Grade':>7}{'Status':>9}",
               "-" * W]
        if not self._entries:
            out.append("No complete results available to rank.")
        for e in self._entries:
            r = e.result
            total = f"{fmt_num(r.total_obtained)}/{fmt_num(r.total_max)}"
            out.append(f"{e.rank:<6}{r.student.student_id:<6}{r.student.name[:24]:<26}"
                       f"{total:>12}{r.percentage:>9.2f}{r.grade:>7}{r.status:>9}")
        out.append("=" * W)
        out.append("Equal percentages share a rank; the next rank is skipped (1, 2, 2, 4).")
        return "\n".join(out) + "\n"

    def to_csv(self) -> str:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Rank", "Student ID", "Name", "Total", "Max", "Percentage", "Grade", "Status"])
        for e in self._entries:
            r = e.result
            w.writerow([e.rank, r.student.student_id, r.student.name, fmt_num(r.total_obtained),
                        fmt_num(r.total_max), f"{r.percentage:.2f}", r.grade, r.status])
        return buf.getvalue()
