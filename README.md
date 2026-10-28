# AI Recruitment Copilot — Complete Runnable System

A professional Flask recruitment platform combining resume parsing, candidate profiling, job matching, skill-gap analysis, ATS, interactive interviews, voice screening, recruitment pipeline and an in-app chatbot.

## Core capabilities

### Resume & Candidate Profiling
- PDF/DOCX upload
- Text extraction with PyMuPDF and python-docx
- Contact, education, experience, skills, certifications and project extraction
- Skill normalization and profile completeness
- Candidate detail and analysis pages

### Matching & Skill Analysis
- 14+ built-in job roles
- Custom job postings
- 60% skills + 25% experience + 15% education weighted score
- Candidate ranking
- Matched skills
- Missing skills
- Training recommendations
- CSV/Excel exports

### Interview & ATS
- 14+ interview roles
- Technical, behavioral and mixed question modes
- Enter any N from 1 to 1000
- Exact N-question generation
- Interactive question-by-question simulation
- ATS candidate records and status updates
- Interview completion tracking

### Voice Screening
- Browser Speech Recognition where supported
- Start/stop screening
- Live transcript
- Preliminary communication signal
- Candidate selection
- Screening guide

### Advanced Analytics & Missing-Objective Tracker
- Interactive recruitment funnel and polar-area stage composition
- Resume intake line chart based on real upload dates
- Matching score distribution across current candidate-job pairs (not a claimed accuracy metric)
- Skill supply vs. job demand comparison
- Bubble plot of experience vs. profile completeness
- Evidence-based milestone gap tracker covering extraction accuracy, matching evaluation, ATS, interviews, voice, user satisfaction, database decision, security and deployment
- Open **Advanced Analytics** from the recruiter/admin navigation or visit `/analytics`

### Dashboard & Workflow
- Professional recruitment dashboard
- Candidate KPIs
- Recruitment pipeline
- New → Shortlisted → Interview → Offered → Hired / Rejected
- Quick access cards
- Responsive design

### Copilot Chatbot
Use the floating chat button to ask about candidates, jobs, matching, interviews, voice screening and pipeline navigation.

## Login accounts

Admin:
- username: admin
- password: admin123

Recruiter:
- username: recruiter
- password: recruiter123

User/Candidate:
- username: user
- password: user123

## Windows setup

```powershell
cd AI_Recruitment_Copilot_Complete
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open:
http://127.0.0.1:5000

If you already have an old database from an earlier copy and see schema errors, delete:
`instance/recruitment.db`
and restart the application. The database will be recreated automatically.

## Notes
- Voice recognition is browser-dependent; Chrome/Edge generally provide the best support.
- The chatbot is an offline rule-based assistant and does not require an external API key.
- LLM integration can be added later without changing the core workflow.

## Updated voice interview and access control
- Voice Screening now acts as a spoken interviewer: it reads each role-specific question aloud using browser text-to-speech, accepts answers through browser speech recognition or typed text, tracks N questions (1–1000), and supports transcript review/export.
- Speech features require a modern browser (Chrome/Edge recommended) and microphone permission. Typed answers remain available when speech recognition is unsupported.
- The Recruitment Pipeline link and route are restricted to Admin and Recruiter accounts; User/Candidate accounts are redirected away from the pipeline.
- The User Satisfaction form has an upgraded responsive visual design with selectable ratings and a satisfaction target indicator.

Default demo accounts (change passwords before deployment):
- Admin: `admin` / `admin123`
- Recruiter: `recruiter` / `recruiter123`
- User/Candidate: `user` / `user123`

## Role-specific dashboards (updated)

The dashboard route now loads a different workspace for each role:
- **Admin:** platform-wide account/job/candidate statistics, role distribution charts, hiring status charts, and an admin-only form to add recruiter accounts.
- **Recruiter:** hiring statistics, candidate status/funnel charts, candidate list, job management, matching, interviews, voice screening, and the Recruitment Pipeline. The pipeline is not displayed on the Admin or Candidate home dashboards.
- **Candidate/User:** personal resume profiles only, available jobs, resume readiness chart, matching and skill analysis, interview practice, and voice practice.

Public signup creates Candidate/User accounts only. Admin creates recruiter accounts. Built-in demo credentials are initialized and password hashes repaired at startup:
- `admin` / `admin123`
- `recruiter` / `recruiter123`
- `user` / `user123`

The charts use database-derived counts where available. Any example/demo statistics shown by other existing pages should not be interpreted as validated hiring outcomes.


## Demo logins (local demonstration)

- **Admin:** `admin` / `admin123` — full platform oversight and recruiter account creation.
- **Recruiter:** `recruiter` / `recruiter123` — candidate evaluation, job postings, pipeline and recruitment analytics.
- **Candidate/User:** `user` / `user123` — personal resume workspace, job matching, interview practice and feedback.

Usernames are matched without case sensitivity. Passwords are case-sensitive. If an old local SQLite database is present, the application migrates the feedback table automatically at startup. Do not use these demo passwords in a public deployment.

## Optional LLM chatbot

The assistant works in local rule-based demo mode without an API key. To enable generated LLM answers, set an OpenAI-compatible API key in the environment before starting the app:

**Windows Command Prompt**
```bat
set OPENAI_API_KEY=your_api_key_here
set OPENAI_MODEL=gpt-4o-mini
python app.py
```

**PowerShell**
```powershell
$env:OPENAI_API_KEY="your_api_key_here"
$env:OPENAI_MODEL="gpt-4o-mini"
python app.py
```

LLM mode requires internet access and a valid provider key and may incur provider charges. Never put a real key in source code or share it in screenshots. The app falls back to its local assistant if the provider is unavailable.

## Validation note

The package includes automated syntax, template, and SQLite migration checks. Browser speech features depend on browser support and microphone permission. Chart.js and web fonts are loaded from CDNs, so visualizations use full styling when internet access is available.

## Requirements traceability and validation
See `OBJECTIVE_TRACEABILITY.md` for the six module mapping, four milestone acceptance checklist, role-based manual smoke tests, and a clear distinction between available features and accuracy targets that still need benchmark evidence. Run the local smoke tests after installing requirements:

```bash
python -m unittest discover -s tests -p "test_objectives_smoke.py"
```

Optional LLM chatbot mode: set `OPENAI_API_KEY` and optionally `OPENAI_MODEL` in the environment before starting the app. `.env.example` documents the variable names. No API key is required for the local fallback; the fallback is rule-based and is not an LLM.

## Productivity features added

- **Notifications Center:** role-scoped alerts for newly posted jobs, interview scheduling/completion, candidate status changes, and user feedback. Users can mark alerts as read.
- **Candidate Comparison:** compare up to four permitted profiles side by side, including extracted skills, education, experience, completeness, and pipeline status. For hiring-score comparisons, select a job in Candidate Matching.
- **Report Exports:** candidate reports in CSV/Excel; matching results remain exportable in CSV/Excel; administrator-only platform analytics and audit-log exports.
- **Personalized Learning Roadmap:** suggests learning resources and practical tasks based on skills found in the selected candidate profile. Recommendations are guidance and should be checked for relevance.
- **Activity Timeline & Audit Log:** records key events such as resume intake, job creation/deletion, candidate status changes, interview scheduling/completion, scorecard saves, recruiter-account creation, and report exports.
- **Advanced Search:** search candidate profiles and job postings by keyword and skill; filter candidates by experience, pipeline status, role keywords, and a minimum hiring score for a selected job.
- **Interview Scorecards:** recruiters and administrators can rate completed interviews across technical skills, communication, problem solving, and role-specific competencies, with evidence-based notes.
- **Access controls:** public registration remains candidate-only; candidate accounts can only search/compare their own profiles; scorecards and recruitment pipeline are staff-only; platform analytics/audit exports are admin-only; ATS write/list endpoints are staff-only. User-submitted feedback remains read-only for recruiters and admins.

The first run creates the notification, activity-log, and scorecard tables in the local SQLite database. Notifications are event-based; they do not retroactively create alerts for older activity. Skill roadmaps are rule-based suggestions rather than an external course API integration.

### Validation note

The updated Python files pass `py_compile`, and all Jinja templates parse successfully. The current build environment does not have Flask installed, so the Flask app could not be imported for live route/browser testing here. Install dependencies from `requirements.txt`, then run `run.bat` on Windows to verify the complete workflow locally.
