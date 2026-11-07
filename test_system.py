import unittest

from database import (Database, ExamRepository, GradingRepository, ResultRepository,
                      StudentRepository, SubjectRepository)
from errors import ValidationError
from grading import BandGradingScheme, GradeCalculator, PassFailGradingScheme
from models import Exam, Person, Result, Student, Subject
from reports import MeritListReport, TextReportCard
from seed_data import seed


class ModelTests(unittest.TestCase):
    def test_inheritance_and_override(self):
        p, s = Person("Asha Rao"), Student("Asha Rao", "CSE", 2, student_id=1)
        self.assertIsInstance(s, Person)
        self.assertEqual(p.get_role(), "Person")
        self.assertEqual(s.get_role(), "Student")
        self.assertNotEqual(p.describe(), s.describe())

    def test_encapsulation_validation(self):
        s = Student("Asha Rao", "CSE", 2, student_id=1)
        for bad in (lambda: setattr(s, "semester", 13), lambda: setattr(s, "email", "nope"),
                    lambda: setattr(s, "name", "1"), lambda: setattr(s, "student_id", 9)):
            with self.assertRaises(ValidationError):
                bad()

    def test_grade_boundaries(self):
        g = GradeCalculator()
        cases = {100: "A+", 90: "A+", 89.99: "A", 80: "A", 70: "B", 60: "C", 50: "D", 40: "E",
                 39.99: "F", 0: "F"}
        for pct, grade in cases.items():
            self.assertEqual(g.grade(pct), grade, pct)

    def test_polymorphic_schemes(self):
        self.assertEqual(PassFailGradingScheme().grade_for(55), "PASS")
        self.assertEqual(BandGradingScheme().grade_for(55), "D")

    def test_bad_bands(self):
        with self.assertRaises(ValidationError):
            BandGradingScheme([(90, "A"), (50, "B")])        # no zero band
        with self.assertRaises(ValidationError):
            BandGradingScheme([(0, "F"), (0, "G")])


class SystemTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        seed(self.db)
        self.students, self.subjects = StudentRepository(self.db), SubjectRepository(self.db)
        self.exams, self.grading = ExamRepository(self.db), GradingRepository(self.db)
        self.results = ResultRepository(self.db, self.students, self.exams)
        self.exam = self.exams.get(1)
        self.calc = self.grading.build_calculator()

    def result(self, sid):
        return self.results.load_result(self.students.get(sid), self.exam, self.calc)

    def test_marks_validation(self):
        r = self.result(1)
        sid = self.subjects.all()[0].subject_id
        for bad in (-1, 101, "abc", "nan"):
            with self.assertRaises(ValidationError):
                r.set_marks(sid, bad)
        lab = [s for s in self.subjects.all() if s.code == "CS204L"][0]
        with self.assertRaises(ValidationError):
            r.set_marks(lab.subject_id, 51)                  # lab paper max is 50

    def test_totals_and_status(self):
        r = self.result(1)
        self.assertEqual(r.total_obtained, 412)
        self.assertEqual(r.total_max, 450)
        self.assertEqual(r.percentage, 91.56)
        self.assertEqual((r.grade, r.status), ("A+", "PASS"))

    def test_fail_in_one_subject_fails_overall(self):
        r = self.result(5)
        self.assertEqual([m.subject.code for m in r.failed_subjects], ["CS203"])
        self.assertEqual(r.status, "FAIL")

    def test_ranking_with_ties(self):
        ranked = self.calc.rank(self.results.results_for_exam(self.exam, self.calc))
        ids = [(e.rank, e.result.student.student_id) for e in ranked]
        self.assertEqual([r for r, _ in ids], [1, 2, 2, 4, 5, 6])
        by_id = {sid: rank for rank, sid in ids}
        self.assertEqual(by_id[2], by_id[3])                 # tie shares a rank
        self.assertEqual(by_id[1], 1)
        passed_only = self.calc.rank(self.results.results_for_exam(self.exam, self.calc), False)
        self.assertNotIn(5, [e.result.student.student_id for e in passed_only])

    def test_incomplete_not_ranked(self):
        self.results.delete_marks(1, 1, 1)
        ranked = self.calc.rank(self.results.results_for_exam(self.exam, self.calc))
        self.assertNotIn(1, [e.result.student.student_id for e in ranked])
        self.assertEqual(self.result(1).status, "INCOMPLETE")

    def test_update_marks_persists(self):
        r = self.result(6)
        sid = r.marks[0].subject.subject_id
        r.set_marks(sid, 99)
        self.results.save_marks(r, sid)
        self.assertEqual(self.result(6).mark_for(sid).obtained, 99)

    def test_configurable_grading(self):
        self.grading.set_bands([(75, "Distinction"), (50, "Pass"), (0, "Fail")])
        self.grading.set_pass_percentage(50)
        calc = self.grading.build_calculator()
        r = self.results.load_result(self.students.get(1), self.exam, calc)
        self.assertEqual(r.grade, "Distinction")
        self.assertEqual(self.results.load_result(self.students.get(6), self.exam, calc).status, "FAIL")

    def test_crud_and_cascades(self):
        self.assertEqual(len(self.students.search("priya")), 1)
        self.assertEqual(self.students.search("3")[0].name, "Karthik Raman")
        with self.assertRaises(ValidationError):
            self.students.add(Student("Dup", "CSE", 1, "student1@college.edu"))
        self.students.delete(1)
        self.assertEqual(len(self.results.results_for_exam(self.exam, self.calc)), 5)
        self.subjects.delete(1)
        self.assertEqual(len(self.exams.get(1).subjects), 4)
        with self.assertRaises(ValidationError):
            self.subjects.add(Subject("X", "cs202", 50))     # duplicate code

    def test_report_and_merit(self):
        r = self.result(2)
        text = TextReportCard(r, 2, 6).render()
        self.assertIn("Priya Nair", text)
        ranked = self.calc.rank(self.results.results_for_exam(self.exam, self.calc))
        self.assertIn("MERIT LIST", MeritListReport(self.exam, ranked).render())


if __name__ == "__main__":
    unittest.main()
