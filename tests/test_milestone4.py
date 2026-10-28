import tempfile
from pathlib import Path
from database import init_db, add_feedback, get_feedback_summary
from voice_screening import communication_score


def test_satisfaction_target_calculation():
    with tempfile.TemporaryDirectory() as d:
        db=Path(d)/"test.db"
        init_db(db)
        for rating in [5,5,4,5,4]: add_feedback(db,"tester",rating,"good")
        s=get_feedback_summary(db)
        assert s["responses"] == 5
        assert s["score"] == 92.0
        assert s["met"] is True


def test_voice_score():
    assert communication_score("I built a data pipeline and explained the results to stakeholders clearly.") > 0
