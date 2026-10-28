"""Lightweight smoke tests for core scoring and SQLite objectives.
Run with: python -m unittest discover -s tests -p 'test_objectives_smoke.py'
"""
import os
import tempfile
import unittest

from database import init_db, add_feedback, get_feedback_summary, get_feedback, add_user, record_user_login, get_users
from matching_engine import calculate_match, rank_candidates


class MatchingObjectiveTests(unittest.TestCase):
    def test_matching_reports_missing_skills_and_score(self):
        candidate = {"name": "Demo Candidate", "skills": ["Python", "SQL"], "experience_years": 2,
                     "education": ["B.Tech Computer Science"]}
        job = {"title": "Data Analyst", "required_skills": ["Python", "SQL", "Power BI"],
               "experience_required": 2, "education_required": "Computer Science"}
        result = calculate_match(candidate, job)
        self.assertGreaterEqual(result["hiring_score"], 0)
        self.assertLessEqual(result["hiring_score"], 100)
        self.assertIn("Power BI", result["missing_skills"])
        self.assertEqual(set(result["matched_skills"]), {"Python", "SQL"})
        self.assertEqual(len(rank_candidates([candidate], job)), 1)


class DatabaseObjectiveTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tempdir.name, "test.db")
        init_db(self.db)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_feedback_submission_and_summary(self):
        add_feedback(self.db, "demo-user", 5, "Easy to use", None, "")
        rows = get_feedback(self.db)
        summary = get_feedback_summary(self.db)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["rating"], 5)
        self.assertGreaterEqual(summary.get("responses", 0), 1)

    def test_login_activity_tracking(self):
        add_user(self.db, "demo-user", "hashed-demo-password", "user")
        record_user_login(self.db, "demo-user")
        account = next(u for u in get_users(self.db) if u["username"] == "demo-user")
        self.assertEqual(account["login_count"], 1)
        self.assertTrue(account["last_login"])


if __name__ == "__main__":
    unittest.main()
