"""Menu-driven console interface for the Student Examination & Grade Management System."""
from __future__ import annotations

import os
from datetime import date

from database import (Database, ExamRepository, GradingRepository, ResultRepository,
                      StudentRepository, SubjectRepository)
from errors import DatabaseError, ValidationError
from models import (EXAM_TYPES, Exam, Person, Student, Subject, clean_max_marks, fmt_num,
                    to_number)
from reports import CsvReportCard, MeritListReport, TextReportCard


# ------------------------------------------------------------------ helpers
def ask_field(label, cleaner, default=None):
    """Prompt until `cleaner` accepts the input. Blank keeps `default` ('-' clears it)."""
    suffix = f" [{default}]" if default not in (None, "") else ""
    while True:
        raw = input(f"{label}{suffix}: ").strip()
        if default is not None:
            if raw == "":
                return cleaner(str(default)) if default != "" else cleaner("")
            if raw == "-":
                raw = ""
        try:
            return cleaner(raw)
        except ValidationError as exc:
            print(f"  [!] {exc}")


def ask_int(label, default=None):
    while True:
        raw = input(f"{label}: ").strip()
        if raw == "" and default is not None:
            return default
        if raw.isdigit():
            return int(raw)
        print("  [!] Please enter a whole number.")


def confirm(question) -> bool:
    return input(f"{question} (y/n): ").strip().lower() in ("y", "yes")


def print_table(headers, rows):
    if not rows:
        print("  (nothing to show)")
        return
    widths = [max(len(str(h)), *(len(str(r[i])) for r in rows)) for i, h in enumerate(headers)]
    line = "  ".join(f"{h:<{w}}" for h, w in zip(headers, widths))
    print(line)
    print("-" * len(line))
    for r in rows:
        print("  ".join(f"{str(c):<{w}}" for c, w in zip(r, widths)))


def run_menu(title, options, back_label="Back"):
    """Generic menu loop; errors from actions are reported, not fatal."""
    while True:
        print(f"\n===== {title} =====")
        for i, (label, _) in enumerate(options, 1):
            print(f"  {i}. {label}")
        print(f"  0. {back_label}")
        choice = input("Choose an option: ").strip()
        if choice == "0":
            return
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            try:
                options[int(choice) - 1][1]()
            except (ValidationError, DatabaseError) as exc:
                print(f"\n  [!] {exc}")
        else:
            print("  [!] Invalid choice.")


# ---------------------------------------------------------------------- app
class ExamManagementApp:
    def __init__(self, db_path="exam_system.db", report_dir="reports"):
        self.db = Database(db_path)
        self.report_dir = report_dir
        self.students = StudentRepository(self.db)
        self.subjects = SubjectRepository(self.db)
        self.exams = ExamRepository(self.db)
        self.grading = GradingRepository(self.db)
        self.results = ResultRepository(self.db, self.students, self.exams)

    @property
    def calc(self):
        return self.grading.build_calculator()      # always reflects current configuration

    # ---- pickers
    def pick_student(self) -> Student:
        student = self.students.get(ask_int("Student ID"))
        if not student:
            raise ValidationError("Student not found.")
        return student

    def pick_subject(self) -> Subject:
        subject = self.subjects.get(ask_int("Subject ID"))
        if not subject:
            raise ValidationError("Subject not found.")
        return subject

    def pick_exam(self) -> Exam:
        self.list_exams()
        exam = self.exams.get(ask_int("Exam ID"))
        if not exam:
            raise ValidationError("Exam not found.")
        return exam

    # ---- main loop
    def run(self):
        print("\n" + "=" * 60)
        print(" STUDENT EXAMINATION AND GRADE MANAGEMENT SYSTEM")
        print("=" * 60)
        try:
            run_menu("MAIN MENU", [
                ("Student Management", self.student_menu),
                ("Subject Management", self.subject_menu),
                ("Examination Management", self.exam_menu),
                ("Marks & Results", self.marks_menu),
                ("Rankings / Merit List", self.merit_list),
                ("Report Cards", self.report_menu),
                ("Grading Settings", self.grading_menu),
            ], back_label="Exit")
        except (EOFError, KeyboardInterrupt):
            print()
        finally:
            self.db.close()
        print("Goodbye!")

    # ================================================================ students
    def student_menu(self):
        run_menu("STUDENT MANAGEMENT", [
            ("Add student", self.add_student), ("View all students", self.list_students),
            ("Search students (ID or name)", self.search_students),
            ("Update student", self.update_student), ("Delete student", self.delete_student)])

    def _student_rows(self, students):
        return [(s.student_id, s.name, s.department, s.semester, s.enrollment_year,
                 s.email or "-", s.phone or "-") for s in students]

    def _show_students(self, students):
        print_table(["ID", "Name", "Department", "Sem", "Year", "Email", "Phone"], self._student_rows(students))

    def add_student(self):
        print("\n-- Add Student --")
        s = Student(
            ask_field("Name", Person.clean_name),
            ask_field("Department", Student.clean_department),
            ask_field("Semester (1-12)", Student.clean_semester),
            ask_field("Email (optional)", Person.clean_email),
            ask_field("Phone (optional)", Person.clean_phone),
            ask_field("Address (optional)", Person.clean_text),
            ask_field("Enrollment year", Student.clean_year, date.today().year))
        self.students.add(s)
        print(f"  Student added with ID {s.student_id}.")

    def list_students(self):
        self._show_students(self.students.all())

    def search_students(self):
        term = input("Enter student ID or name: ").strip()
        self._show_students(self.students.search(term))

    def update_student(self):
        s = self.pick_student()
        print("Press Enter to keep a value ('-' clears optional fields).")
        s.name = ask_field("Name", Person.clean_name, s.name)
        s.department = ask_field("Department", Student.clean_department, s.department)
        s.semester = ask_field("Semester", Student.clean_semester, s.semester)
        s.email = ask_field("Email", Person.clean_email, s.email)
        s.phone = ask_field("Phone", Person.clean_phone, s.phone)
        s.address = ask_field("Address", Person.clean_text, s.address)
        s.enrollment_year = ask_field("Enrollment year", Student.clean_year, s.enrollment_year)
        self.students.update(s)
        print("  Student updated.")

    def delete_student(self):
        s = self.pick_student()
        if confirm(f"Delete {s.name} and all of their marks?"):
            self.students.delete(s.student_id)
            print("  Student deleted.")

    # ================================================================ subjects
    def subject_menu(self):
        run_menu("SUBJECT MANAGEMENT", [
            ("Add subject", self.add_subject), ("View subjects", self.list_subjects),
            ("Update subject", self.update_subject), ("Delete subject", self.delete_subject)])

    def add_subject(self):
        s = Subject(ask_field("Subject name", Subject.clean_name),
                    ask_field("Subject code (e.g. CS101)", Subject.clean_code),
                    ask_field("Maximum marks", clean_max_marks, 100))
        self.subjects.add(s)
        print(f"  Subject added with ID {s.subject_id}.")

    def list_subjects(self):
        print_table(["ID", "Code", "Name", "Max marks"],
                    [(s.subject_id, s.code, s.name, fmt_num(s.max_marks)) for s in self.subjects.all()])

    def update_subject(self):
        self.list_subjects()
        s = self.pick_subject()
        s.name = ask_field("Name", Subject.clean_name, s.name)
        s.code = ask_field("Code", Subject.clean_code, s.code)
        s.max_marks = ask_field("Maximum marks", clean_max_marks, fmt_num(s.max_marks))
        self.subjects.update(s)
        print("  Subject updated (papers already in exams keep their stored maximum).")

    def delete_subject(self):
        self.list_subjects()
        s = self.pick_subject()
        if confirm(f"Delete {s.code}? It will also be removed from exams along with its marks"):
            self.subjects.delete(s.subject_id)
            print("  Subject deleted.")

    # ================================================================== exams
    def exam_menu(self):
        run_menu("EXAMINATION MANAGEMENT", [
            ("Create exam", self.create_exam), ("View all exams", self.list_exams),
            ("View exam details", self.exam_details), ("Update exam", self.update_exam),
            ("Delete exam", self.delete_exam), ("Assign subject to exam", self.assign_subject),
            ("Remove subject from exam", self.remove_subject)])

    def create_exam(self):
        print("Exam types: " + ", ".join(EXAM_TYPES))
        e = Exam(ask_field("Exam name", Exam.clean_name),
                 ask_field("Exam type", Exam.clean_type),
                 ask_field("Date (YYYY-MM-DD)", Exam.clean_date),
                 ask_field("Maximum marks per subject", lambda v: clean_max_marks(v, "Exam maximum marks"), 100))
        self.exams.add(e)
        print(f"  Exam created with ID {e.exam_id}. Now assign subjects to it.")

    def list_exams(self):
        print_table(["ID", "Name", "Type", "Date", "Max", "Subjects"],
                    [(e.exam_id, e.name, e.exam_type, e.exam_date.isoformat(), fmt_num(e.max_marks),
                      len(e.subjects)) for e in self.exams.all()])

    def exam_details(self):
        e = self.pick_exam()
        print(f"\n{e.summary()}")
        print_table(["Subject ID", "Code", "Subject", "Paper max"],
                    [(s.subject_id, s.code, s.name, fmt_num(e.paper_max(s.subject_id))) for s in e.subjects])
        print(f"Total maximum marks: {fmt_num(e.total_max)}")

    def update_exam(self):
        e = self.pick_exam()
        e.name = ask_field("Name", Exam.clean_name, e.name)
        e.exam_type = ask_field("Type", Exam.clean_type, e.exam_type)
        e.exam_date = ask_field("Date", Exam.clean_date, e.exam_date.isoformat())
        e.max_marks = ask_field("Maximum marks", lambda v: clean_max_marks(v, "Exam maximum marks"),
                                fmt_num(e.max_marks))
        self.exams.update(e)
        print("  Exam updated (new maximum applies to subjects assigned from now on).")

    def delete_exam(self):
        e = self.pick_exam()
        if confirm(f"Delete exam '{e.name}' with all its marks?"):
            self.exams.delete(e.exam_id)
            print("  Exam deleted.")

    def assign_subject(self):
        e = self.pick_exam()
        self.list_subjects()
        s = self.pick_subject()
        paper = self.exams.assign_subject(e, s)
        print(f"  {s.code} assigned to '{e.name}' with maximum {fmt_num(paper)} marks.")

    def remove_subject(self):
        e = self.pick_exam()
        s = self.pick_subject()
        if not e.has_subject(s.subject_id):
            raise ValidationError("That subject is not assigned to this exam.")
        if confirm("Removing it also deletes marks entered for it. Continue?"):
            self.exams.remove_subject(e, s.subject_id)
            print("  Subject removed from exam.")

    # ================================================================== marks
    def marks_menu(self):
        run_menu("MARKS & RESULTS", [
            ("Enter marks (one student, one subject)", lambda: self.enter_marks(False)),
            ("Update marks", lambda: self.enter_marks(True)),
            ("Bulk entry for a subject (all students)", self.bulk_entry),
            ("Delete a mark", self.delete_mark),
            ("View a student's result in an exam", self.view_result),
            ("View all results of an exam", self.exam_results)])

    def _result_for(self, student, exam):
        if not exam.subjects:
            raise ValidationError("This exam has no subjects yet. Assign subjects first.")
        return self.results.load_result(student, exam, self.calc)

    def _show_marks_table(self, result):
        print_table(["Subject ID", "Code", "Subject", "Max", "Obtained"],
                    [(m.subject.subject_id, m.subject.code, m.subject.name, fmt_num(m.max_marks),
                      fmt_num(m.obtained) if m.is_entered else "-") for m in result.marks])

    def enter_marks(self, update: bool):
        exam = self.pick_exam()
        student = self.pick_student()
        result = self._result_for(student, exam)
        self._show_marks_table(result)
        subject_id = ask_int("Subject ID")
        mark = result.mark_for(subject_id)
        if update and not mark.is_entered:
            raise ValidationError("No marks recorded yet for this subject; use 'Enter marks'.")
        if not update and mark.is_entered:
            print(f"  Marks already recorded ({fmt_num(mark.obtained)}); they will be overwritten.")
        default = fmt_num(mark.obtained) if mark.is_entered else None
        ask_field(f"Marks for {mark.subject.name} (0-{fmt_num(mark.max_marks)})",
                  lambda v: result.set_marks(subject_id, v), default)
        self.results.save_marks(result, subject_id)
        print(f"  Saved. Current standing: {result.summary()}")

    def bulk_entry(self):
        exam = self.pick_exam()
        if not exam.subjects:
            raise ValidationError("This exam has no subjects yet.")
        print_table(["Subject ID", "Code", "Subject"], [(s.subject_id, s.code, s.name) for s in exam.subjects])
        subject_id = ask_int("Subject ID")
        if not exam.has_subject(subject_id):
            raise ValidationError("That subject is not part of this exam.")
        print("Enter marks per student. Blank = skip, q = stop.")
        for student in self.students.all():
            result = self.results.load_result(student, exam, self.calc)
            mark = result.mark_for(subject_id)
            current = f" (current {fmt_num(mark.obtained)})" if mark.is_entered else ""
            while True:
                raw = input(f"  [{student.student_id}] {student.name}{current} /{fmt_num(mark.max_marks)}: ").strip()
                if raw.lower() == "q":
                    return
                if raw == "":
                    break
                try:
                    result.set_marks(subject_id, raw)
                    self.results.save_marks(result, subject_id)
                    break
                except ValidationError as exc:
                    print(f"    [!] {exc}")

    def delete_mark(self):
        exam = self.pick_exam()
        student = self.pick_student()
        result = self._result_for(student, exam)
        self._show_marks_table(result)
        subject_id = ask_int("Subject ID")
        result.mark_for(subject_id)
        if self.results.delete_marks(student.student_id, exam.exam_id, subject_id):
            print("  Mark deleted.")
        else:
            print("  No mark was recorded for that subject.")

    def view_result(self):
        exam = self.pick_exam()
        student = self.pick_student()
        result = self._result_for(student, exam)
        print("\n" + self._card(result, exam).render())

    def _rank_lookup(self, exam, calc=None):
        calc = calc or self.calc
        ranked = calc.rank(self.results.results_for_exam(exam, calc))
        return {e.result.student.student_id: e.rank for e in ranked}, len(ranked)

    def _card(self, result, exam, fmt=TextReportCard):
        ranks, total = self._rank_lookup(exam, result.calculator)
        return fmt(result, ranks.get(result.student.student_id), total)

    def exam_results(self):
        exam = self.pick_exam()
        results = self.results.results_for_exam(exam, self.calc)
        print_table(["ID", "Name", "Total", "%", "Grade", "Status", "Failed subjects"],
                    [(r.student.student_id, r.student.name,
                      f"{fmt_num(r.total_obtained)}/{fmt_num(r.total_max)}", f"{r.percentage:.2f}",
                      r.grade, r.status, ", ".join(m.subject.code for m in r.failed_subjects) or "-")
                     for r in results])

    # ================================================================ ranking
    def merit_list(self):
        exam = self.pick_exam()
        calc = self.calc
        include_failed = confirm("Include students who failed?")
        ranked = calc.rank(self.results.results_for_exam(exam, calc), include_failed)
        report = MeritListReport(exam, ranked)
        print("\n" + report.render())
        if ranked and confirm("Export merit list to CSV?"):
            os.makedirs(self.report_dir, exist_ok=True)
            path = os.path.join(self.report_dir, f"merit_list_E{exam.exam_id}.csv")
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(report.to_csv())
            print(f"  Saved to {path}")

    # ================================================================ reports
    def report_menu(self):
        run_menu("REPORT CARDS", [
            ("Generate report card for one student", self.report_one),
            ("Generate report cards for all students in an exam", self.report_all)])

    def report_one(self):
        exam = self.pick_exam()
        student = self.pick_student()
        card = self._card(self._result_for(student, exam), exam)
        print("\n" + card.render())
        if confirm("Save to a file?"):
            kind = input("Format - 1) text  2) csv [1]: ").strip()
            if kind == "2":
                card = self._card(self._result_for(student, exam), exam, CsvReportCard)
            print(f"  Saved to {card.save(self.report_dir)}")

    def report_all(self):
        exam = self.pick_exam()
        calc = self.calc
        results = self.results.results_for_exam(exam, calc)
        if not results:
            raise ValidationError("No marks have been entered for this exam.")
        ranks, total = self._rank_lookup(exam, calc)
        for r in results:
            path = TextReportCard(r, ranks.get(r.student.student_id), total).save(self.report_dir)
            print(f"  {r.student.name}: {path}")
        print(f"  {len(results)} report card(s) generated.")

    # ================================================================ grading
    def grading_menu(self):
        run_menu("GRADING SETTINGS", [
            ("View grading scale", self.show_scale), ("Edit grading scale", self.edit_scale),
            ("Set pass percentage per subject", self.set_pass), ("Reset to defaults", self.reset_scale)])

    def show_scale(self):
        calc = self.calc
        print("\nGrade bands (percentage):")
        for line in calc.scheme.describe():
            print("  " + line)
        print(f"Pass requirement: at least {calc.pass_percentage:g}% in every subject.")

    def edit_scale(self):
        print("Enter bands as 'minimum:grade' pairs separated by commas, e.g. 90:A+,80:A,60:B,0:F")
        raw = input("Bands: ").strip()
        bands = []
        for part in raw.split(","):
            try:
                minimum, grade = part.split(":")
                bands.append((float(minimum), grade.strip()))
            except ValueError:
                raise ValidationError(f"Could not read '{part.strip()}'. Use minimum:grade.") from None
        self.grading.set_bands(bands)
        print("  Grading scale updated.")
        self.show_scale()

    def set_pass(self):
        value = ask_field("Pass percentage", lambda v: self._pass_value(v), fmt_num(self.grading.get_pass_percentage()))
        self.grading.set_pass_percentage(value)
        print(f"  Pass percentage set to {value:g}%.")

    @staticmethod
    def _pass_value(v):
        n = to_number(v, "Pass percentage")
        if not 0 <= n <= 100:
            raise ValidationError("Pass percentage must be between 0 and 100.")
        return n

    def reset_scale(self):
        if confirm("Restore the default grading scale and 40% pass mark?"):
            self.grading.reset_default()
            print("  Defaults restored.")
