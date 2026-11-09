from __future__ import annotations

import sqlite3

from errors import DatabaseError, ValidationError
from grading import BandGradingScheme, GradeCalculator
from models import Exam, Result, Student, Subject

SCHEMA = """
CREATE TABLE IF NOT EXISTS students(
    student_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, email TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '', department TEXT NOT NULL,
    semester INTEGER NOT NULL CHECK(semester BETWEEN 1 AND 12),
    enrollment_year INTEGER NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS ux_students_email ON students(email) WHERE email <> '';
CREATE TABLE IF NOT EXISTS subjects(
    subject_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, code TEXT NOT NULL UNIQUE,
    max_marks REAL NOT NULL CHECK(max_marks > 0));
CREATE TABLE IF NOT EXISTS exams(
    exam_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, exam_type TEXT NOT NULL, exam_date TEXT NOT NULL,
    max_marks REAL NOT NULL CHECK(max_marks > 0));
CREATE TABLE IF NOT EXISTS exam_subjects(
    exam_id INTEGER NOT NULL, subject_id INTEGER NOT NULL,
    max_marks REAL NOT NULL CHECK(max_marks > 0),
    PRIMARY KEY(exam_id, subject_id),
    FOREIGN KEY(exam_id) REFERENCES exams(exam_id) ON DELETE CASCADE,
    FOREIGN KEY(subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS marks(
    student_id INTEGER NOT NULL, exam_id INTEGER NOT NULL, subject_id INTEGER NOT NULL,
    marks_obtained REAL NOT NULL CHECK(marks_obtained >= 0),
    PRIMARY KEY(student_id, exam_id, subject_id),
    FOREIGN KEY(student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY(exam_id, subject_id) REFERENCES exam_subjects(exam_id, subject_id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS grading_scale(
    grade TEXT PRIMARY KEY, min_percentage REAL NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


# database connection
class Database:
    def __init__(self, path: str = "exam_system.db"):
        try:
            self._conn = sqlite3.connect(path)
        except sqlite3.Error as exc:
            raise DatabaseError(f"Cannot open database: {exc}") from exc
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        self._conn.execute("INSERT OR IGNORE INTO settings(key, value) VALUES('pass_percentage','40')")
        if not self.query("SELECT 1 FROM grading_scale LIMIT 1"):
            self._conn.executemany("INSERT INTO grading_scale(grade, min_percentage) VALUES(?,?)",
                                   [(g, m) for m, g in BandGradingScheme.DEFAULT_BANDS])
        self._conn.commit()

    def execute(self, sql: str, params=()) -> sqlite3.Cursor:
        try:
            cursor = self._conn.execute(sql, params)
            self._conn.commit()
            return cursor
        except sqlite3.IntegrityError:
            self._conn.rollback()
            raise
        except sqlite3.Error as exc:
            self._conn.rollback()
            raise DatabaseError(str(exc)) from exc

    def query(self, sql: str, params=()) -> list[sqlite3.Row]:
        try:
            return self._conn.execute(sql, params).fetchall()
        except sqlite3.Error as exc:
            raise DatabaseError(str(exc)) from exc

    def close(self) -> None:
        self._conn.close()


# student repo
class StudentRepository:
    def __init__(self, db: Database):
        self._db = db

    @staticmethod
    def _build(row) -> Student:
        return Student(row["name"], row["department"], row["semester"], row["email"],
                       row["phone"], row["address"], row["enrollment_year"], row["student_id"])

    def add(self, s: Student) -> Student:
        try:
            cur = self._db.execute(
                "INSERT INTO students(name,email,phone,address,department,semester,enrollment_year)"
                " VALUES(?,?,?,?,?,?,?)",
                (s.name, s.email, s.phone, s.address, s.department, s.semester, s.enrollment_year))
        except sqlite3.IntegrityError:
            raise ValidationError("A student with this email already exists.") from None
        s.student_id = cur.lastrowid
        return s

    def get(self, student_id: int) -> Student | None:
        rows = self._db.query("SELECT * FROM students WHERE student_id=?", (student_id,))
        return self._build(rows[0]) if rows else None

    def all(self) -> list[Student]:
        return [self._build(r) for r in self._db.query("SELECT * FROM students ORDER BY student_id")]

    def search(self, term: str) -> list[Student]:
        term = term.strip()
        sid = int(term) if term.isdigit() else -1
        rows = self._db.query("SELECT * FROM students WHERE student_id=? OR name LIKE ? "
                              "ORDER BY student_id", (sid, f"%{term}%"))
        return [self._build(r) for r in rows]

    def update(self, s: Student) -> None:
        try:
            self._db.execute(
                "UPDATE students SET name=?,email=?,phone=?,address=?,department=?,semester=?,"
                "enrollment_year=? WHERE student_id=?",
                (s.name, s.email, s.phone, s.address, s.department, s.semester,
                 s.enrollment_year, s.student_id))
        except sqlite3.IntegrityError:
            raise ValidationError("Another student already uses this email.") from None

    def delete(self, student_id: int) -> bool:
        return self._db.execute("DELETE FROM students WHERE student_id=?", (student_id,)).rowcount > 0


# subject repo
class SubjectRepository:
    def __init__(self, db: Database):
        self._db = db

    @staticmethod
    def build(row) -> Subject:
        return Subject(row["name"], row["code"], row["max_marks"], row["subject_id"])

    def add(self, s: Subject) -> Subject:
        try:
            cur = self._db.execute("INSERT INTO subjects(name,code,max_marks) VALUES(?,?,?)",
                                   (s.name, s.code, s.max_marks))
        except sqlite3.IntegrityError:
            raise ValidationError(f"Subject code {s.code} already exists.") from None
        s.subject_id = cur.lastrowid
        return s

    def get(self, subject_id: int) -> Subject | None:
        rows = self._db.query("SELECT * FROM subjects WHERE subject_id=?", (subject_id,))
        return self.build(rows[0]) if rows else None

    def all(self) -> list[Subject]:
        return [self.build(r) for r in self._db.query("SELECT * FROM subjects ORDER BY code")]

    def update(self, s: Subject) -> None:
        try:
            self._db.execute("UPDATE subjects SET name=?,code=?,max_marks=? WHERE subject_id=?",
                             (s.name, s.code, s.max_marks, s.subject_id))
        except sqlite3.IntegrityError:
            raise ValidationError(f"Subject code {s.code} already exists.") from None

    def delete(self, subject_id: int) -> bool:
        return self._db.execute("DELETE FROM subjects WHERE subject_id=?", (subject_id,)).rowcount > 0


# exam repo
class ExamRepository:
    def __init__(self, db: Database):
        self._db = db

    def _build(self, row) -> Exam:
        exam = Exam(row["name"], row["exam_type"], row["exam_date"], row["max_marks"], row["exam_id"])
        papers = self._db.query(
            "SELECT s.*, es.max_marks AS paper_max FROM exam_subjects es "
            "JOIN subjects s ON s.subject_id = es.subject_id WHERE es.exam_id=?", (exam.exam_id,))
        for p in papers:
            exam.load_paper(SubjectRepository.build(p), p["paper_max"])
        return exam

    def add(self, e: Exam) -> Exam:
        cur = self._db.execute("INSERT INTO exams(name,exam_type,exam_date,max_marks) VALUES(?,?,?,?)",
                               (e.name, e.exam_type, e.exam_date.isoformat(), e.max_marks))
        e.exam_id = cur.lastrowid
        return e

    def get(self, exam_id: int) -> Exam | None:
        rows = self._db.query("SELECT * FROM exams WHERE exam_id=?", (exam_id,))
        return self._build(rows[0]) if rows else None

    def all(self) -> list[Exam]:
        return [self._build(r) for r in self._db.query("SELECT * FROM exams ORDER BY exam_date, exam_id")]

    def update(self, e: Exam) -> None:
        self._db.execute("UPDATE exams SET name=?,exam_type=?,exam_date=?,max_marks=? WHERE exam_id=?",
                         (e.name, e.exam_type, e.exam_date.isoformat(), e.max_marks, e.exam_id))

    def delete(self, exam_id: int) -> bool:
        return self._db.execute("DELETE FROM exams WHERE exam_id=?", (exam_id,)).rowcount > 0

    def assign_subject(self, exam: Exam, subject: Subject, paper_max=None) -> float:
        paper_max = exam.add_subject(subject, paper_max)
        self._db.execute("INSERT INTO exam_subjects(exam_id,subject_id,max_marks) VALUES(?,?,?)",
                         (exam.exam_id, subject.subject_id, paper_max))
        return paper_max

    def remove_subject(self, exam: Exam, subject_id: int) -> None:
        self._db.execute("DELETE FROM exam_subjects WHERE exam_id=? AND subject_id=?",
                         (exam.exam_id, subject_id))
        exam.remove_subject(subject_id)


# result repo
class ResultRepository:
    def __init__(self, db: Database, students: StudentRepository, exams: ExamRepository):
        self._db, self._students, self._exams = db, students, exams

    def load_result(self, student: Student, exam: Exam, calc: GradeCalculator) -> Result:
        result = Result(student, exam, calc)
        rows = self._db.query("SELECT subject_id, marks_obtained FROM marks "
                              "WHERE student_id=? AND exam_id=?", (student.student_id, exam.exam_id))
        for row in rows:
            result.set_marks(row["subject_id"], row["marks_obtained"])
        return result

    def save_marks(self, result: Result, subject_id: int) -> None:
        mark = result.mark_for(subject_id)
        if not mark.is_entered:
            raise ValidationError("No marks to save.")
        self._db.execute(
            "INSERT INTO marks(student_id,exam_id,subject_id,marks_obtained) VALUES(?,?,?,?) "
            "ON CONFLICT(student_id,exam_id,subject_id) DO UPDATE SET marks_obtained=excluded.marks_obtained",
            (result.student.student_id, result.exam.exam_id, subject_id, mark.obtained))

    def delete_marks(self, student_id: int, exam_id: int, subject_id: int) -> bool:
        return self._db.execute("DELETE FROM marks WHERE student_id=? AND exam_id=? AND subject_id=?",
                                (student_id, exam_id, subject_id)).rowcount > 0

    def results_for_exam(self, exam: Exam, calc: GradeCalculator) -> list[Result]:
        rows = self._db.query("SELECT DISTINCT student_id FROM marks WHERE exam_id=?", (exam.exam_id,))
        results = []
        for row in rows:
            student = self._students.get(row["student_id"])
            if student:
                results.append(self.load_result(student, exam, calc))
        return results

    def results_for_student(self, student: Student, calc: GradeCalculator) -> list[Result]:
        rows = self._db.query("SELECT DISTINCT exam_id FROM marks WHERE student_id=? ORDER BY exam_id",
                              (student.student_id,))
        return [self.load_result(student, self._exams.get(r["exam_id"]), calc) for r in rows]


# grading repo
class GradingRepository:
    def __init__(self, db: Database):
        self._db = db

    def get_bands(self) -> list[tuple[float, str]]:
        rows = self._db.query("SELECT min_percentage, grade FROM grading_scale ORDER BY min_percentage DESC")
        return [(r["min_percentage"], r["grade"]) for r in rows]

    def set_bands(self, bands) -> None:
        validated = BandGradingScheme(bands).bands
        self._db.execute("DELETE FROM grading_scale")
        for minimum, grade in validated:
            self._db.execute("INSERT INTO grading_scale(grade,min_percentage) VALUES(?,?)", (grade, minimum))

    def reset_default(self) -> None:
        self.set_bands(BandGradingScheme.DEFAULT_BANDS)
        self.set_pass_percentage(40)

    def get_pass_percentage(self) -> float:
        return float(self._db.query("SELECT value FROM settings WHERE key='pass_percentage'")[0]["value"])

    def set_pass_percentage(self, value) -> None:
        calc = GradeCalculator(pass_percentage=value)
        self._db.execute("UPDATE settings SET value=? WHERE key='pass_percentage'",
                         (str(calc.pass_percentage),))

    def build_calculator(self) -> GradeCalculator:
        return GradeCalculator(BandGradingScheme(self.get_bands()), self.get_pass_percentage())
