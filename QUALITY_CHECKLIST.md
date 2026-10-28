# Quality Checklist — Acceptance Criteria

This project explicitly implements the Week 8 acceptance objectives from the supplied project specification.

| Objective | Implementation | Verification |
|---|---|---|
| Dashboard fully functional | Flask dashboard + `streamlit_app.py` with KPIs, pipeline, candidate intelligence, quality/deployment panel | Run `python app.py` or `streamlit run streamlit_app.py` |
| Voice screening operational | Browser SpeechRecognition UI + `voice_screening.py` using SpeechRecognition for WAV transcription and pyttsx3 for optional spoken prompts | Open Voice Screening; or use Streamlit audio input |
| End-to-end workflow completed | Candidate workflow page tracks Profiled → Matched → Interviewed → Offered → Hired, with links to matching, interview, voice screening and pipeline | Open `/workflow/<candidate_id>` |
| User satisfaction ≥85% | 1–5 feedback collection stored in SQLite; score = average/5×100; target status displayed on dashboard | Submit five demo ratings [5,5,4,5,4] to obtain 92% in test |
| Testing | Automated acceptance tests in `tests/test_milestone4.py` | `pytest -q tests` |
| Optimization/readiness | Database indexes, bounded question generation, health endpoint, production-style error handling, Docker/Streamlit run instructions | `/health`, `DEPLOYMENT.md` |
| Deployment | Dockerfile and Streamlit deployment command | `docker build ...` or `streamlit run ...` |
