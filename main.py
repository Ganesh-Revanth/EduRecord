import argparse

from cli import ExamManagementApp

# main entry
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Student Examination and Grade Management System")
    parser.add_argument("--db", default="exam_system.db", help="SQLite database file")
    parser.add_argument("--reports", default="reports", help="folder for generated reports")
    args = parser.parse_args()
    # run app
    ExamManagementApp(args.db, args.reports).run()
