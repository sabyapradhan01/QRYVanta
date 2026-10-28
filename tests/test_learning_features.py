import csv
import tempfile
import unittest
from pathlib import Path

from learning_content import QUESTION_BANK, SQL_RULES, PERFORMANCE_RULES
from quiz_engine import build_attempt, validate_answer, summarize_attempt, available_questions
from export_utils import export_table_csv, format_command_history, build_processing_report, save_report_txt, save_report_pdf, save_report_docx


class QuizEngineTests(unittest.TestCase):
    def test_complete_rule_coverage_and_canonical_question_bank(self):
        self.assertEqual([r[0] for r in SQL_RULES], [f"SQL{i:03d}" for i in range(1, 16)])
        self.assertEqual([r[0] for r in PERFORMANCE_RULES], [f"P{i:03d}" for i in range(1, 23)])
        self.assertGreaterEqual(len(QUESTION_BANK), 50)
        ids = [q["id"] for q in QUESTION_BANK]
        self.assertEqual(len(ids), len(set(ids)))
        for question in QUESTION_BANK:
            self.assertIn(question["answer"], question["options"])
            self.assertEqual(len(question["options"]), 4)
            self.assertTrue(question["explanation"].strip())

    def test_build_attempt_unique_questions_and_valid_answers(self):
        for difficulty in ("Easy", "Medium", "Hard"):
            pool = available_questions(QUESTION_BANK, difficulty)
            attempt = build_attempt(QUESTION_BANK, min(7, len(pool)), difficulty)
            self.assertEqual(len(attempt), min(7, len(pool)))
            self.assertEqual(len({q["id"] for q in attempt}), len(attempt))
            for q in attempt:
                self.assertIn(q["answer"], q["options"])
                self.assertEqual(len(q["options"]), 4)
                self.assertEqual(len(set(q["options"])), 4)

    def test_answer_feedback_exact_and_summary(self):
        question = QUESTION_BANK[0]
        self.assertEqual(validate_answer(question, question["answer"])[1], "Yes, you have correctly answered the question.")
        self.assertEqual(validate_answer(question, "not an answer")[1], "Yet to answer correctly.")
        self.assertEqual(validate_answer(question, None)[1], "Yet to answer correctly.")
        summary = summarize_attempt([question], {question["id"]: question["answer"]})
        self.assertEqual(summary["correct"], 1)
        self.assertEqual(summary["percentage"], 100.0)

    def test_bad_count_and_empty_difficulty_validation(self):
        with self.assertRaises(ValueError):
            build_attempt(QUESTION_BANK, 0, "Easy")
        with self.assertRaises(ValueError):
            build_attempt([], 1, "All")


class ExportTests(unittest.TestCase):
    def test_csv_has_headers_and_quotes_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "table.csv"
            export_table_csv(path, ["id", "note"], [[1, 'hello, "world"'], [2, None]])
            with path.open(encoding="utf-8-sig", newline="") as f:
                rows = list(csv.reader(f))
            self.assertEqual(rows[0], ["id", "note"])
            self.assertEqual(rows[1], ["1", 'hello, "world"'])
            self.assertEqual(rows[2], ["2", ""])

    def test_history_is_numbered_and_empty_state_is_clear(self):
        content = format_command_history(["SELECT 1;", "UPDATE t SET v=2 WHERE id=1;"])
        self.assertIn("Command 001", content)
        self.assertIn("SELECT 1;", content)
        self.assertIn("Command 002", content)
        self.assertIn("UPDATE t", content)
        self.assertIn("No SQL statements", format_command_history([]))

    def test_report_transparently_uses_only_available_fields(self):
        report = {
            "status": "Analysis complete", "database_type": "postgresql", "query": "SELECT id FROM t;",
            "lint_findings": [{"rule_id": "SQL001", "severity": "Medium", "message": "Sample lint", "explanation": "Why", "recommendation": "Fix"}],
            "analysis": {"query_score": 88, "query_info": {"tables": ["t"], "table_count": 1, "join_count": 0},
                         "findings": [{"rule_id": "P001", "severity": "High", "message": "Scan", "explanation": "Plan evidence", "recommendation": "Inspect"}],
                         "execution_plan": "TABLE SCAN | table=t | rows=20"},
        }
        text = build_processing_report(report)
        self.assertIn("Query health score: 88 / 100", text)
        self.assertIn("[SQL001] Medium: Sample lint", text)
        self.assertIn("[P001] High: Scan", text)
        self.assertIn("TABLE SCAN", text)
        self.assertIn("is inferred", text)
        self.assertNotIn("Execution time: 0", text)

    def test_text_pdf_and_docx_report_exports(self):
        report = {"status": "No analysis", "query": "", "analysis": None, "lint_findings": []}
        with tempfile.TemporaryDirectory() as tmp:
            p_txt = save_report_txt(Path(tmp) / "r.txt", report)
            p_pdf = save_report_pdf(Path(tmp) / "r.pdf", report)
            p_docx = save_report_docx(Path(tmp) / "r.docx", report)
            self.assertIn(b"QRYVANTA", p_txt.read_bytes())
            self.assertTrue(p_pdf.read_bytes().startswith(b"%PDF"))
            self.assertTrue(p_docx.read_bytes().startswith(b"PK"))
            self.assertGreater(p_pdf.stat().st_size, 1000)
            self.assertGreater(p_docx.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
