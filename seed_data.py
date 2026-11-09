import argparse

from database import (Database, ExamRepository, ResultRepository, StudentRepository,
                      SubjectRepository, GradingRepository)
from models import Exam, Student, Subject


# load sample data
def seed(db: Database) -> None:
    students, subjects = StudentRepository(db), SubjectRepository(db)
    exams, grading = ExamRepository(db), GradingRepository(db)
    results = ResultRepository(db, students, exams)

    # add students
    people = [("Aarav Sharma", "Computer Science"), ("Priya Nair", "Computer Science"),
              ("Karthik Raman", "Computer Science"), ("Meera Iyer", "Computer Science"),
              ("Rohan Das", "Computer Science"), ("Sneha Reddy", "Computer Science")]
    for i, (name, dept) in enumerate(people, 1):
        students.add(Student(name, dept, 3, f"student{i}@college.edu", "9840012345", "Chennai", 2024))

    # add subjects
    subs = [Subject("Data Structures", "CS201", 100), Subject("Database Systems", "CS202", 100),
            Subject("Operating Systems", "CS203", 100), Subject("Mathematics III", "MA201", 100),
            Subject("Programming Lab", "CS204L", 50)]
    for s in subs:
        subjects.add(s)

    # create exam
    exam = exams.add(Exam("Semester 3 Final Examination", "Final", "2026-12-10", 100))
    for s in subs:
        exams.assign_subject(exam, s)

    calc = grading.build_calculator()
    # insert marks
    marks = {
        1: (92, 88, 95, 90, 47), 2: (85, 90, 80, 78, 44), 3: (85, 90, 80, 78, 44),
        4: (70, 65, 72, 60, 35), 5: (95, 92, 35, 90, 45),
        6: (55, 48, 52, 45, 30)}
    for sid, values in marks.items():
        result = results.load_result(students.get(sid), exam, calc)
        for subject, value in zip(subs, values):
            result.set_marks(subject.subject_id, value)
            results.save_marks(result, subject.subject_id)


# run seed
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="exam_system.db")
    args = parser.parse_args()
    database = Database(args.db)
    if database.query("SELECT 1 FROM students LIMIT 1"):
        print("Database already has data; seed skipped.")
    else:
        seed(database)
        print(f"Sample data loaded into {args.db}.")
