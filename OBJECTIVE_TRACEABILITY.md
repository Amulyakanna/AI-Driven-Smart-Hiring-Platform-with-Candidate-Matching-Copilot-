# Project objective traceability and acceptance test plan

This document maps the six modules and four milestone checkpoints in the supplied project statement to the application. Feature availability is not proof of an accuracy target; benchmark targets must be verified using a labelled test set and recorded results.

## Six modules

| Module | Implemented area | Manual acceptance test |
|---|---|---|
| Resume Parsing & Candidate Profiling | Resume Upload / `resume_parser.py` | Upload valid PDF and DOCX files; compare extracted name, email, phone, education, skills, and experience with manually labelled values. |
| Job Description Analysis | Job Postings / job form | Create jobs with title, required skills, education, and experience; confirm saved fields are reflected in matching. |
| Candidate Matching & Ranking Engine | Matching & Skills / `matching_engine.py` | Match candidates to a job; confirm score, matched skills, and missing skills. Evaluate ≥85% only against a labelled benchmark and a pre-defined metric. |
| Skill Gap Analysis | Matching & Skills | Check missing competencies and training recommendations for each evaluated candidate. |
| Interview Assistance & Screening | Interview Assistant / Voice Screening / `interview_assistant.py` | Generate questions for multiple roles, answer a practice session, complete it, and verify the ATS status update. Test browser microphone/speech support separately. |
| Dashboard & Recruitment Analytics | Role-specific dashboards / feedback analytics | Test admin-wide totals, recruiter activity/performance views, candidate's personal dashboard, chart data, and feedback submission. |

## Added analytics and missing-objective tracker

The recruiter/admin **Advanced Analytics** page (`/analytics`) adds:
- Recruitment funnel horizontal bar chart and polar-area stage composition.
- Resume intake trend using recorded upload dates (no fabricated historical values).
- Matching score distribution across current candidate-job pairs; this distribution is not a substitute for a labelled accuracy benchmark.
- Candidate skill supply vs. job requirement demand chart.
- Bubble plot of candidate experience vs. profile completeness.
- Top computed candidate-job matches.
- A milestone evidence tracker for the 95% extraction target, 85% matching target, ATS integration, interview storage/evaluation, voice fallback, genuine satisfaction measurements, database choice, security and deployment.

## Four milestone checkpoints

- **Milestone 1 — Week 2:** PDF and DOCX are accepted. Target ≥95% extraction must be calculated over manually labelled resumes; do not report this target as achieved until measured.
- **Milestone 2 — Week 4:** Matching scores and skill gaps are produced. Target ≥85% matching accuracy requires a labelled evaluation set and documented precision/recall/accuracy or an agreed ranking metric.
- **Milestone 3 — Week 6:** Questions work for multiple roles; ATS create/list/update routes work; interview simulation can be completed.
- **Milestone 4 — Week 8:** Dashboards, voice screening, and feedback form work end-to-end. Target ≥85% satisfaction requires collected ratings and a stated calculation (for example, share of ratings 4 or 5).

## Role-based manual smoke test

1. Admin: sign in with `admin` / `admin123`; verify platform totals and recruiter account creation.
2. Recruiter: sign in with `recruiter` / `recruiter123`; create a job, inspect candidates and matching, and update a pipeline stage.
3. User: sign in with `user` / `user123`; upload a test resume, inspect personal matching/interview tools, and submit a 1–5 feedback rating.
4. Re-open Feedback Analytics as admin and confirm the new response appears in overall analytics. Candidate accounts should only see their own submitted feedback rows.
5. If using LLM mode, set `OPENAI_API_KEY` and optional `OPENAI_MODEL` in the shell before starting. Without a key, the chatbot uses a rule-based local fallback.

## Important limitations

- Demo credentials are for local demonstration only; change them before deployment.
- Candidate matching scores are decision-support signals, not proof of hiring suitability. Human review is required.
- LLM responses require a configured API key, network access, and a valid provider account. The fallback is not an LLM.
- Voice screening depends on browser/device speech capabilities and microphone permissions.
- Accuracy targets are project acceptance criteria, not automatically guaranteed by feature presence.
