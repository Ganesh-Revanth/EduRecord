"""Domain model: Person, Student, Subject, Exam, SubjectMark, Result."""
from __future__ import annotations

import math
import re
from abc import ABC, abstractmethod
from datetime import date, datetime

from errors import ValidationError
from grading import GradeCalculator

EXAM_TYPES = ("Internal", "Midterm", "Final", "Quiz", "Practical", "Supplementary")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+?[0-9][0-9\- ]{6,14}$")


def fmt_num(value: float) -> str:
    return f"{value:g}"


def to_number(value, label: str) -> float:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a number.") from None
    if math.isnan(number) or math.isinf(number):
        raise ValidationError(f"{label} must be a finite number.")
    return number


def clean_max_marks(value, label="Maximum marks") -> float:
    number = to_number(value, label)
    if not 0 < number <= 1000:
        raise ValidationError(f"{label} must be greater than 0 and at most 1000.")
    return number


class Entity(ABC):
    """Abstract root of all domain objects: each must describe itself."""

    @abstractmethod
    def to_dict(self) -> dict: ...

    @abstractmethod
    def summary(self) -> str: ...

    def __str__(self) -> str:
        return self.summary()


# --------------------------------------------------------------------- Person
class Person(Entity):
    """Base class: common identity and contact details (protected attributes)."""

    def __init__(self, name, email="", phone="", address=""):
        self.name = name
        self.email = email
        self.phone = phone
        self.address = address

    # validators (reused by the CLI so prompts can re-ask on bad input)
    @staticmethod
    def clean_name(value) -> str:
        value = " ".join((value or "").split())
        if len(value) < 2 or not value[0].isalpha() or \
                not all(c.isalpha() or c in " .'-" for c in value):
            raise ValidationError("Name must be at least 2 letters (letters, space . ' - only).")
        return value

    @staticmethod
    def clean_email(value) -> str:
        value = (value or "").strip().lower()
        if value and not _EMAIL_RE.match(value):
            raise ValidationError("Invalid email address.")
        return value

    @staticmethod
    def clean_phone(value) -> str:
        value = (value or "").strip()
        if value and not _PHONE_RE.match(value):
            raise ValidationError("Invalid phone number (7-15 digits, optional leading +).")
        return value

    @staticmethod
    def clean_text(value) -> str:
        return " ".join((value or "").split())

    @property
    def name(self): return self._name

    @name.setter
    def name(self, value): self._name = self.clean_name(value)

    @property
    def email(self): return self._email

    @email.setter
    def email(self, value): self._email = self.clean_email(value)

    @property
    def phone(self): return self._phone

    @phone.setter
    def phone(self, value): self._phone = self.clean_phone(value)

    @property
    def address(self): return self._address

    @address.setter
    def address(self, value): self._address = self.clean_text(value)

    def get_role(self) -> str:
        return "Person"

    def describe(self) -> str:
        return f"{self.get_role()}: {self._name} | {self._email or 'no email'} | {self._phone or 'no phone'}"

    def summary(self) -> str:
        return self.describe()

    def to_dict(self) -> dict:
        return {"name": self._name, "email": self._email, "phone": self._phone,
                "address": self._address}


class Student(Person):
    """A student: a Person plus academic information."""

    def __init__(self, name, department, semester, email="", phone="", address="",
                 enrollment_year=None, student_id=None):
        super().__init__(name, email, phone, address)
        self.__student_id = None          # private: assigned once by the database
        if student_id is not None:
            self.student_id = student_id
        self.department = department
        self.semester = semester
        self.enrollment_year = enrollment_year if enrollment_year else date.today().year

    @staticmethod
    def clean_department(value) -> str:
        value = " ".join((value or "").split())
        if len(value) < 2:
            raise ValidationError("Department is required.")
        return value

    @staticmethod
    def clean_semester(value) -> int:
        number = to_number(value, "Semester")
        if number != int(number) or not 1 <= number <= 12:
            raise ValidationError("Semester must be a whole number from 1 to 12.")
        return int(number)

    @staticmethod
    def clean_year(value) -> int:
        number = to_number(value, "Enrollment year")
        if number != int(number) or not 1990 <= number <= date.today().year + 1:
            raise ValidationError(f"Enrollment year must be between 1990 and {date.today().year + 1}.")
        return int(number)

    @property
    def student_id(self): return self.__student_id

    @student_id.setter
    def student_id(self, value):
        if self.__student_id is not None and self.__student_id != value:
            raise ValidationError("Student ID cannot be changed once assigned.")
        self.__student_id = int(value)

    @property
    def department(self): return self._department

    @department.setter
    def department(self, value): self._department = self.clean_department(value)

    @property
    def semester(self): return self._semester

    @semester.setter
    def semester(self, value): self._semester = self.clean_semester(value)

    @property
    def enrollment_year(self): return self._enrollment_year

    @enrollment_year.setter
    def enrollment_year(self, value): self._enrollment_year = self.clean_year(value)

    # --- overriding
    def get_role(self) -> str:
        return "Student"

    def describe(self) -> str:
        return (f"[{self.student_id}] {self.name} | {self._department} | "
                f"Sem {self._semester} | {self.email or 'no email'}")

    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update(student_id=self.student_id, department=self._department,
                    semester=self._semester, enrollment_year=self._enrollment_year)
        return data


# -------------------------------------------------------------------- Subject
class Subject(Entity):
    def __init__(self, name, code, max_marks=100, subject_id=None):
        self.__subject_id = None
        if subject_id is not None:
            self.subject_id = subject_id
        self.name = name
        self.code = code
        self.max_marks = max_marks

    @staticmethod
    def clean_name(value) -> str:
        value = " ".join((value or "").split())
        if len(value) < 2:
            raise ValidationError("Subject name must have at least 2 characters.")
        return value

    @staticmethod
    def clean_code(value) -> str:
        value = (value or "").strip().upper()
        if not re.fullmatch(r"[A-Z0-9\-]{2,12}", value):
            raise ValidationError("Subject code: 2-12 letters/digits/hyphens (e.g. CS101).")
        return value

    @property
    def subject_id(self): return self.__subject_id

    @subject_id.setter
    def subject_id(self, value):
        if self.__subject_id is not None and self.__subject_id != value:
            raise ValidationError("Subject ID cannot be changed once assigned.")
        self.__subject_id = int(value)

    @property
    def name(self): return self._name

    @name.setter
    def name(self, value): self._name = self.clean_name(value)

    @property
    def code(self): return self._code

    @code.setter
    def code(self, value): self._code = self.clean_code(value)

    @property
    def max_marks(self): return self._max_marks

    @max_marks.setter
    def max_marks(self, value): self._max_marks = clean_max_marks(value)

    def summary(self) -> str:
        return f"[{self.subject_id}] {self._code} - {self._name} (max {fmt_num(self._max_marks)})"

    def to_dict(self) -> dict:
        return {"subject_id": self.subject_id, "name": self._name, "code": self._code,
                "max_marks": self._max_marks}


# ----------------------------------------------------------------------- Exam
class Exam(Entity):
    """An examination and the subjects (papers) assigned to it.

    The maximum for a paper is min(exam.max_marks, subject.max_marks), fixed
    when the subject is assigned.
    """

    def __init__(self, name, exam_type, exam_date, max_marks=100, exam_id=None):
        self.__exam_id = None
        if exam_id is not None:
            self.exam_id = exam_id
        self.name = name
        self.exam_type = exam_type
        self.exam_date = exam_date
        self.max_marks = max_marks
        self._papers: dict[int, tuple[Subject, float]] = {}

    @staticmethod
    def clean_name(value) -> str:
        value = " ".join((value or "").split())
        if len(value) < 3:
            raise ValidationError("Exam name must have at least 3 characters.")
        return value

    @staticmethod
    def clean_type(value) -> str:
        value = (value or "").strip().lower()
        for option in EXAM_TYPES:
            if option.lower() == value:
                return option
        raise ValidationError("Exam type must be one of: " + ", ".join(EXAM_TYPES))

    @staticmethod
    def clean_date(value) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        for pattern in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(str(value).strip(), pattern).date()
            except ValueError:
                continue
        raise ValidationError("Date must look like 2026-12-15 or 15-12-2026.")

    @property
    def exam_id(self): return self.__exam_id

    @exam_id.setter
    def exam_id(self, value):
        if self.__exam_id is not None and self.__exam_id != value:
            raise ValidationError("Exam ID cannot be changed once assigned.")
        self.__exam_id = int(value)

    @property
    def name(self): return self._name

    @name.setter
    def name(self, value): self._name = self.clean_name(value)

    @property
    def exam_type(self): return self._exam_type

    @exam_type.setter
    def exam_type(self, value): self._exam_type = self.clean_type(value)

    @property
    def exam_date(self): return self._exam_date

    @exam_date.setter
    def exam_date(self, value): self._exam_date = self.clean_date(value)

    @property
    def max_marks(self): return self._max_marks

    @max_marks.setter
    def max_marks(self, value): self._max_marks = clean_max_marks(value, "Exam maximum marks")

    # --- composition of subjects
    def add_subject(self, subject: Subject, paper_max=None) -> float:
        if subject.subject_id is None:
            raise ValidationError("Subject must be saved before it is assigned.")
        if self.has_subject(subject.subject_id):
            raise ValidationError(f"{subject.code} is already assigned to this exam.")
        ceiling = min(self._max_marks, subject.max_marks)
        paper_max = ceiling if paper_max is None else clean_max_marks(paper_max, "Paper maximum")
        if paper_max > ceiling:
            raise ValidationError(f"Paper maximum cannot exceed {fmt_num(ceiling)}.")
        self._papers[subject.subject_id] = (subject, paper_max)
        return paper_max

    def load_paper(self, subject: Subject, paper_max: float) -> None:
        """Restore a stored paper exactly as saved (used by the repository)."""
        self._papers[subject.subject_id] = (subject, float(paper_max))

    def remove_subject(self, subject_id: int) -> None:
        self._papers.pop(subject_id, None)

    def has_subject(self, subject_id: int) -> bool:
        return subject_id in self._papers

    @property
    def subjects(self) -> list[Subject]:
        return sorted((s for s, _ in self._papers.values()), key=lambda s: s.code)

    def paper_max(self, subject_id: int) -> float:
        return self._papers[subject_id][1]

    @property
    def total_max(self) -> float:
        return sum(m for _, m in self._papers.values())

    def summary(self) -> str:
        return (f"[{self.exam_id}] {self._name} | {self._exam_type} | "
                f"{self._exam_date:%d %b %Y} | max {fmt_num(self._max_marks)} | "
                f"{len(self._papers)} subject(s)")

    def to_dict(self) -> dict:
        return {"exam_id": self.exam_id, "name": self._name, "exam_type": self._exam_type,
                "exam_date": self._exam_date.isoformat(), "max_marks": self._max_marks,
                "subjects": [{"code": s.code, "max": self.paper_max(s.subject_id)}
                             for s in self.subjects]}


# --------------------------------------------------------------------- Result
class SubjectMark:
    """Marks of one student in one subject of an exam (validated)."""

    def __init__(self, subject: Subject, max_marks: float, obtained=None):
        self._subject = subject
        self._max_marks = float(max_marks)
        self._obtained = None
        if obtained is not None:
            self.obtained = obtained

    @property
    def subject(self): return self._subject

    @property
    def max_marks(self): return self._max_marks

    @property
    def obtained(self): return self._obtained

    @obtained.setter
    def obtained(self, value):
        number = to_number(value, "Marks")
        if number < 0:
            raise ValidationError("Marks cannot be negative.")
        if number > self._max_marks:
            raise ValidationError(f"Marks cannot exceed the maximum of {fmt_num(self._max_marks)}.")
        self._obtained = number

    def clear(self) -> None:
        self._obtained = None

    @property
    def is_entered(self) -> bool:
        return self._obtained is not None

    @property
    def percentage(self) -> float | None:
        return None if self._obtained is None else self._obtained / self._max_marks * 100


class Result(Entity):
    """One student's result in one exam.

    Composed of a Student, an Exam and one SubjectMark (-> Subject) per paper.
    """

    def __init__(self, student: Student, exam: Exam, calculator: GradeCalculator | None = None):
        self._student = student
        self._exam = exam
        self._calculator = calculator or GradeCalculator()
        self._marks = {s.subject_id: SubjectMark(s, exam.paper_max(s.subject_id))
                       for s in exam.subjects}

    @property
    def student(self): return self._student

    @property
    def exam(self): return self._exam

    @property
    def calculator(self): return self._calculator

    @property
    def marks(self) -> list[SubjectMark]:
        return list(self._marks.values())

    def mark_for(self, subject_id: int) -> SubjectMark:
        try:
            return self._marks[subject_id]
        except KeyError:
            raise ValidationError("That subject is not part of this exam.") from None

    def set_marks(self, subject_id: int, value) -> float:
        mark = self.mark_for(subject_id)
        mark.obtained = value
        return mark.obtained

    @property
    def entered(self) -> list[SubjectMark]:
        return [m for m in self._marks.values() if m.is_entered]

    @property
    def is_complete(self) -> bool:
        return bool(self._marks) and len(self.entered) == len(self._marks)

    @property
    def total_obtained(self) -> float:
        return sum(m.obtained for m in self.entered)

    @property
    def total_max(self) -> float:
        return sum(m.max_marks for m in self.entered)

    @property
    def percentage(self) -> float:
        return round(self.total_obtained / self.total_max * 100, 2) if self.total_max else 0.0

    @property
    def grade(self) -> str:
        return self._calculator.grade(self.percentage)

    def subject_grade(self, mark: SubjectMark) -> str:
        return self._calculator.grade(round(mark.percentage, 2))

    def subject_passed(self, mark: SubjectMark) -> bool:
        return self._calculator.subject_passed(mark.obtained, mark.max_marks)

    @property
    def passed_subjects(self) -> list[SubjectMark]:
        return [m for m in self.entered if self.subject_passed(m)]

    @property
    def failed_subjects(self) -> list[SubjectMark]:
        return [m for m in self.entered if not self.subject_passed(m)]

    @property
    def status(self) -> str:
        if not self.is_complete:
            return "INCOMPLETE"
        return "PASS" if self._calculator.overall_passed(self) else "FAIL"

    def summary(self) -> str:
        return (f"{self._student.name} | {self._exam.name} | "
                f"{fmt_num(self.total_obtained)}/{fmt_num(self.total_max)} | "
                f"{self.percentage:.2f}% | {self.grade} | {self.status}")

    def to_dict(self) -> dict:
        return {"student_id": self._student.student_id, "exam_id": self._exam.exam_id,
                "total_obtained": self.total_obtained, "total_max": self.total_max,
                "percentage": self.percentage, "grade": self.grade, "status": self.status,
                "subjects": [{"code": m.subject.code, "obtained": m.obtained, "max": m.max_marks}
                             for m in self._marks.values()]}
