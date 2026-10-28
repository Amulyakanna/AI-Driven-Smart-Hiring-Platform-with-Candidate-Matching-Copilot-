
import os
import re
import csv
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from resume_parser import process_resume, ALLOWED_EXTENSIONS
from database import (
    init_db, add_candidate, get_candidates, get_candidate,
    get_analytics, delete_candidate, get_users, add_user, update_user_password, update_candidate_status,
    add_feedback, get_feedback_summary, get_feedback, record_user_login
)
from job_store import init_job_tables, add_job, get_jobs, get_job, delete_job, seed_demo_jobs, update_job, set_job_status
from matching_engine import calculate_match, rank_candidates, build_matching_matrix, normalize_skills
from interview_assistant import (
    available_roles, build_interview_questions, init_ats_tables, add_ats_candidate,
    list_ats_candidates, update_ats_status, create_interview_session, get_interview_session,
    add_response, complete_interview
)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
DATABASE = BASE_DIR / "instance" / "recruitment.db"
EXPORT_FOLDER = BASE_DIR / "exports"

app = Flask(__name__)
app.secret_key = "ai-recruitment-copilot-demo-change-this"
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

UPLOAD_FOLDER.mkdir(exist_ok=True)
EXPORT_FOLDER.mkdir(exist_ok=True)
DATABASE.parent.mkdir(exist_ok=True)

init_db(DATABASE)
init_job_tables(DATABASE)
# Keep the three demo logins available even when an older database already exists.
# Passwords are always stored as Werkzeug hashes.
for demo_username, demo_password, demo_role in [
    ("admin", "admin123", "admin"),
    ("recruiter", "recruiter123", "recruiter"),
    ("user", "user123", "user"),
]:
    existing = next((u for u in get_users(DATABASE) if u["username"].lower() == demo_username), None)
    if existing is None:
        add_user(DATABASE, demo_username, generate_password_hash(demo_password), demo_role)
    else:
        try:
            is_valid_hash = check_password_hash(existing["password"], demo_password)
        except (ValueError, TypeError):
            is_valid_hash = False
        if not is_valid_hash:
            update_user_password(DATABASE, existing["username"], generate_password_hash(demo_password))
        # Ensure the built-in demo accounts keep their intended role.
        import sqlite3
        with sqlite3.connect(DATABASE) as _conn:
            _conn.execute("UPDATE users SET role=? WHERE username=?", (demo_role, existing["username"]))
seed_demo_jobs(DATABASE)
init_ats_tables(DATABASE)

def log_activity(action, details="", actor=None):
    """Write a small audit trail for consequential workflow actions."""
    try:
        with sqlite3.connect(DATABASE) as conn:
            conn.execute("INSERT INTO activity_logs(actor, role, action, details, created_at) VALUES(?,?,?,?,?)",
                         (actor or session.get("username", "system"), session.get("role", "system"),
                          action[:100], details[:1000], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    except sqlite3.Error:
        app.logger.exception("Could not write activity log")

def notify(role, title, message, recipient=None):
    try:
        with sqlite3.connect(DATABASE) as conn:
            conn.execute("INSERT INTO notifications(recipient, role, title, message, created_at, is_read) VALUES(?,?,?,?,?,0)",
                         (recipient, role, title[:160], message[:1000], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    except sqlite3.Error:
        app.logger.exception("Could not create notification")

def init_feature_tables():
    with sqlite3.connect(DATABASE) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, recipient TEXT, role TEXT NOT NULL, title TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL, is_read INTEGER DEFAULT 0)")
        conn.execute("CREATE TABLE IF NOT EXISTS activity_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT, role TEXT, action TEXT NOT NULL, details TEXT DEFAULT '', created_at TEXT NOT NULL)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_notifications_role ON notifications(role, recipient, id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_logs(id)")

init_feature_tables()

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required():
    return "username" in session

@app.context_processor
def inject_globals():
    return {"now": datetime.now()}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = next((u for u in get_users(DATABASE) if u["username"].strip().casefold() == username.casefold()), None)
        if user:
            stored = user["password"]
            try:
                valid = check_password_hash(stored, password)
            except (ValueError, TypeError):
                valid = stored == password
            if valid:
                session["username"] = user["username"]
                session["role"] = user["role"]
                record_user_login(DATABASE, user["username"])
                return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        role = "user"  # public self-registration is candidate-only
        if not username or not password:
            flash("Username and password are required.", "warning")
            return redirect(url_for("signup"))
        if len(username) < 3 or len(password) < 6:
            flash("Username must have 3+ characters and password 6+ characters.", "warning")
            return redirect(url_for("signup"))
        if password != confirm:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("signup"))
        if any(u["username"].lower() == username.lower() for u in get_users(DATABASE)):
            flash("Username already exists.", "danger")
            return redirect(url_for("signup"))
        add_user(DATABASE, username, generate_password_hash(password), role)
        flash("Account created successfully. Please sign in.", "success")
        return redirect(url_for("login"))
    return render_template("signup.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if not login_required():
        return redirect(url_for("login"))
    role = session.get("role", "user")
    users = get_users(DATABASE)
    all_candidates = get_candidates(DATABASE)
    jobs = get_jobs(DATABASE)

    # Admin-only account creation: public signup never grants staff privileges.
    if request.method == "POST":
        if role != "admin":
            flash("Only administrators can create recruiter accounts.", "danger")
            return redirect(url_for("dashboard"))
        username = request.form.get("new_username", "").strip()
        password = request.form.get("new_password", "")
        if len(username) < 3 or len(password) < 6:
            flash("Recruiter username must be 3+ characters and password 6+ characters.", "warning")
        elif any(u["username"].lower() == username.lower() for u in users):
            flash("That username already exists.", "danger")
        else:
            add_user(DATABASE, username, generate_password_hash(password), "recruiter")
            log_activity("Recruiter account created", f"Recruiter account {username} created by admin")
            flash(f"Recruiter account '{username}' created successfully.", "success")
        return redirect(url_for("dashboard"))

    # Candidate users only see their own profiles and their own upload statistics.
    candidates = [c for c in all_candidates if c.get("uploaded_by") == session["username"]] if role == "user" else all_candidates
    analytics = get_analytics(DATABASE)
    if role == "user":
        analytics = dict(analytics)
        analytics["total_candidates"] = len(candidates)
    user_performance = []
    for account in users:
        if account.get("role") == "user":
            owned = [c for c in all_candidates if c.get("uploaded_by") == account.get("username")]
            user_performance.append({
                "username": account.get("username"),
                "profiles": len(owned),
                "login_count": int(account.get("login_count") or 0),
                "last_login": account.get("last_login") or "Never",
                "avg_completeness": round(sum(float(c.get("completeness", 0) or 0) for c in owned) / len(owned), 1) if owned else 0,
                "shortlisted": sum(1 for c in owned if c.get("status") == "Shortlisted"),
                "interviews": sum(1 for c in owned if c.get("status") == "Interview"),
                "hired": sum(1 for c in owned if c.get("status") == "Hired"),
            })
    stats = {
        "users": len(users),
        "admins": sum(1 for u in users if u.get("role") == "admin"),
        "recruiters": sum(1 for u in users if u.get("role") == "recruiter"),
        "candidate_users": sum(1 for u in users if u.get("role") == "user"),
        "jobs": len(jobs),
        "open_jobs": sum(1 for j in jobs if str(j.get("status", "Published")).lower() == "published"),
        "closed_jobs": sum(1 for j in jobs if str(j.get("status", "Published")).lower() == "closed"),
        "candidates": len(all_candidates),
        "pending_reviews": sum(1 for c in all_candidates if (c.get("status") or "New") in {"New", "Screened"}),
        "shortlisted": sum(1 for c in all_candidates if c.get("status") == "Shortlisted"),
        "interviews": sum(1 for c in all_candidates if c.get("status") == "Interview"),
        "hired": sum(1 for c in all_candidates if c.get("status") == "Hired"),
        "my_candidates": len(candidates),
        "my_jobs": len(jobs),
    }
    template = {"admin": "admin_dashboard.html", "recruiter": "recruiter_dashboard.html", "user": "user_dashboard.html"}.get(role, "user_dashboard.html")
    return render_template(template, analytics=analytics, candidates=candidates,
                           jobs=jobs, users=users, stats=stats,
                           username=session["username"], role=role,
                           user_performance=user_performance,
                           feedback_summary=get_feedback_summary(DATABASE))

@app.route("/analytics")
def analytics_dashboard():
    """Advanced visual analytics and transparent milestone gap tracker."""
    if not login_required():
        return redirect(url_for("login"))
    if session.get("role") == "user":
        flash("Advanced recruitment analytics are available to recruiters and administrators.", "warning")
        return redirect(url_for("dashboard"))

    candidates = get_candidates(DATABASE)
    jobs = get_jobs(DATABASE)
    feedback_summary = get_feedback_summary(DATABASE)
    statuses = ["New", "Screened", "Shortlisted", "Interview", "Offered", "Hired", "Rejected"]
    status_counts = {stage: sum(1 for c in candidates if (c.get("status") or "New") == stage) for stage in statuses}

    # Daily intake trend from real uploaded_at timestamps; no synthetic historical data.
    from collections import Counter
    intake = Counter()
    for candidate in candidates:
        raw_date = str(candidate.get("uploaded_at") or "")[:10]
        if raw_date:
            intake[raw_date] += 1
    intake_labels = sorted(intake)[-14:]
    intake_values = [intake[d] for d in intake_labels]

    skill_counts = Counter()
    for c in candidates:
        for skill in c.get("skills", []) or []:
            if str(skill).strip():
                skill_counts[str(skill).strip().title()] += 1
    top_skills = skill_counts.most_common(10)
    required_counts = Counter()
    for job in jobs:
        for skill in job.get("required_skills", []) or []:
            if str(skill).strip():
                required_counts[str(skill).strip().title()] += 1
    demand_labels = [skill for skill, _ in (required_counts + Counter(dict(top_skills))).most_common(10)]
    demand_values = [required_counts.get(skill, 0) for skill in demand_labels]
    supply_values = [skill_counts.get(skill, 0) for skill in demand_labels]

    # Score distribution is derived from the existing matching engine, not guessed.
    match_scores = []
    score_rows = []
    for job in jobs:
        for c in candidates:
            try:
                result = calculate_match(c, job)
                score = float(result.get("hiring_score", 0) or 0)
                match_scores.append(score)
                score_rows.append({"candidate": c.get("name") or f"Candidate {c.get('id', '')}",
                                   "job": job.get("title", "Untitled job"), "score": round(score, 1)})
            except (TypeError, ValueError, ZeroDivisionError):
                continue
    score_bins = {"0–19": 0, "20–39": 0, "40–59": 0, "60–79": 0, "80–100": 0}
    for score in match_scores:
        key = "0–19" if score < 20 else "20–39" if score < 40 else "40–59" if score < 60 else "60–79" if score < 80 else "80–100"
        score_bins[key] += 1

    scatter_points = [{"x": round(float(c.get("experience_years", 0) or 0), 2),
                       "y": round(float(c.get("completeness", 0) or 0), 1),
                       "label": c.get("name") or "Unknown candidate",
                       "status": c.get("status") or "New"} for c in candidates]

    objectives = [
        {"milestone":"1 · Resume parsing", "objective":"PDF/DOCX extraction with field-level validation", "status":"Implemented — validate", "evidence":"Run a labelled resume test set and report field-wise precision/recall or extraction accuracy."},
        {"milestone":"1 · Resume parsing", "objective":"Demonstrate ≥95% extraction accuracy", "status":"Evidence required", "evidence":"Compare extracted fields with manually verified ground truth; do not claim the target without measured results."},
        {"milestone":"2 · Matching", "objective":"Demonstrate ≥85% matching accuracy", "status":"Evidence required", "evidence":"Define the evaluation metric and test on labelled candidate-job pairs; record results and limitations."},
        {"milestone":"2 · Matching", "objective":"Edge cases and explainable score breakdown", "status":"Validate / extend", "evidence":"Test missing skills, empty job requirements, unknown experience and explain score components."},
        {"milestone":"3 · Interview & ATS", "objective":"Interactive interview answers stored and reviewed", "status":"Validate / extend", "evidence":"Run an actual session, persist answers, generate a summary and verify status updates."},
        {"milestone":"3 · Interview & ATS", "objective":"External ATS API integration", "status":"Optional / not demonstrated", "evidence":"Use a supported provider API with authorization, error handling and synchronization if required by the specification."},
        {"milestone":"4 · Dashboard", "objective":"Live visual analytics and end-to-end workflow", "status":"Added — validate", "evidence":"Charts use stored candidate/job/feedback data; execute a full workflow test."},
        {"milestone":"4 · Voice & quality", "objective":"Voice screening fallback and transcript review", "status":"Validate / extend", "evidence":"Test browser microphone, transcription failures and typed fallback."},
        {"milestone":"4 · User satisfaction", "objective":"Measure user satisfaction ≥85%", "status":"Evidence required", "evidence":"Collect genuine user ratings and calculate the score from submitted responses."},
        {"milestone":"Overall · Database", "objective":"Confirm SQLite vs MongoDB requirement", "status":"Decision required", "evidence":"Current bundle uses SQLite. Migrate only if MongoDB is a mandatory project requirement."},
        {"milestone":"Overall · Security", "objective":"Production secrets, access control and candidate privacy", "status":"Review required", "evidence":"Change demo credentials/secret key and review upload validation, role permissions and personal-data handling."},
        {"milestone":"Overall · QA & deployment", "objective":"Automated regression tests and clean deployment", "status":"Validate", "evidence":"Run tests from a fresh environment and retain test logs and deployment evidence."},
    ]
    return render_template("analytics.html", candidates=candidates, jobs=jobs,
        statuses=statuses, status_counts=status_counts, status_values=[status_counts[s] for s in statuses], intake_labels=intake_labels,
        intake_values=intake_values, top_skills=top_skills, demand_labels=demand_labels,
        demand_values=demand_values, supply_values=supply_values, score_bins=score_bins,
        score_rows=sorted(score_rows, key=lambda x: x["score"], reverse=True)[:12],
        scatter_points=scatter_points, feedback_summary=feedback_summary, objectives=objectives)

@app.route("/upload", methods=["GET", "POST"])
def upload():
    if not login_required():
        return redirect(url_for("login"))
    if request.method == "POST":
        file = request.files.get("resume")
        if not file or not file.filename:
            flash("Please choose a PDF or DOCX resume.", "warning")
            return redirect(url_for("upload"))
        if not allowed_file(file.filename):
            flash("Unsupported format. Please upload PDF or DOCX only.", "danger")
            return redirect(url_for("upload"))
        filename = secure_filename(file.filename)
        saved_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{filename}"
        path = UPLOAD_FOLDER / saved_name
        file.save(path)
        try:
            candidate = process_resume(str(path))
            candidate["source_file"] = filename
            candidate["stored_file"] = saved_name
            candidate["uploaded_by"] = session["username"]
            candidate_id = add_candidate(DATABASE, candidate)
            log_activity("Resume uploaded", f"Candidate #{candidate_id} profile created")
            notify("recruiter", "New candidate profile", f"A resume was uploaded by {session['username']}.")
            notify("admin", "New candidate profile", f"A resume was uploaded by {session['username']}.")
            flash(f"Resume processed successfully. Candidate #{candidate_id} created.", "success")
            return redirect(url_for("candidate_detail", candidate_id=candidate_id))
        except Exception as exc:
            if path.exists():
                path.unlink()
            flash(f"Could not process the resume: {exc}", "danger")
    return render_template("upload.html")

def build_ai_analysis(candidate):
    raw = str(candidate.get("raw_text", ""))
    lower = raw.lower()
    skills = [str(s) for s in candidate.get("skills", [])]
    education = candidate.get("education", []) or []
    projects = candidate.get("projects", []) or []
    certs = candidate.get("certifications", []) or []
    years = float(candidate.get("experience_years", 0) or 0)
    completeness = float(candidate.get("completeness", 0) or 0)

    score = min(100, round(
        min(len(skills) * 4, 32) + min(len(projects) * 5, 20) +
        min(len(certs) * 4, 12) + min(len(education) * 8, 16) +
        min(years * 3, 15) + min(completeness * .05, 5), 1))

    if score >= 80: level, cls = "Strong profile", "strong"
    elif score >= 60: level, cls = "Promising profile", "good"
    elif score >= 40: level, cls = "Developing profile", "medium"
    else: level, cls = "Needs improvement", "low"

    strengths, recommendations = [], []
    if len(skills) >= 6: strengths.append(f"Good technical coverage with {len(skills)} detected skills.")
    elif skills: strengths.append(f"{len(skills)} technical skill(s) were detected.")
    if years >= 2: strengths.append(f"Experience signal indicates approximately {years:g} years.")
    if len(projects) >= 2: strengths.append(f"{len(projects)} projects provide useful hands-on evidence.")
    if certs: strengths.append(f"{len(certs)} certification signal(s) were detected.")
    if completeness >= 75: strengths.append("Most core profile fields contain extractable information.")
    if not strengths: strengths.append("Add more structured resume information to create stronger evidence.")

    if not candidate.get("email") or not candidate.get("phone"):
        recommendations.append("Add both a professional email and phone number in the resume header.")
    if len(skills) < 5:
        recommendations.append("Create a dedicated Skills section and list relevant skills you genuinely know.")
    if len(projects) < 2:
        recommendations.append("Add 2–3 relevant projects with technologies, contribution and measurable outcomes.")
    if not education:
        recommendations.append("Add a clear Education section with degree, institution and graduation year.")
    if not certs:
        recommendations.append("If applicable, add relevant certifications with issuer and year.")
    if not re.search(r"\b\d+(?:\.\d+)?\s*(?:%|percent|years?|months?|users?|records?|projects?|clients?|days?)\b", lower):
        recommendations.append("Add truthful measurable achievements such as accuracy, records processed or time saved.")
    if not recommendations:
        recommendations.append("No major gaps detected. Keep achievements specific and measurable.")

    checks = [
        ("Contact information", bool(candidate.get("email") and candidate.get("phone")), "Email and phone are available.", "Add both a professional email and phone number."),
        ("Skills section", len(skills) >= 5, f"{len(skills)} skills detected.", "Add a dedicated Skills section with role-relevant skills."),
        ("Projects evidence", len(projects) >= 2, f"{len(projects)} project(s) detected.", "Add 2–3 projects with technology, contribution and outcomes."),
        ("Education details", bool(education), f"{len(education)} education item(s) detected.", "Add degree, institution and graduation year."),
        ("Certifications", bool(certs), f"{len(certs)} certification(s) detected.", "Add relevant certifications if applicable."),
        ("Quantified impact", bool(re.search(r"\b\d+(?:\.\d+)?\s*(?:%|percent|years?|months?|users?|records?|projects?|clients?|days?)\b", lower)), "Measurable language detected.", "Add truthful numbers to achievements."),
    ]
    health = round(sum(ok for _, ok, _, _ in checks) / len(checks) * 100)

    if years >= 8: seniority = "Senior"
    elif years >= 4: seniority = "Mid-level"
    elif years > 0: seniority = "Early-career"
    else: seniority = "Fresher / not detected"

    groups = {
        "Programming": ["Python","Java","C","C++","C#","JavaScript","TypeScript"],
        "Data & Analytics": ["SQL","Pandas","NumPy","Power BI","Tableau","Excel","Data Analysis","Statistics"],
        "AI / ML": ["Machine Learning","Deep Learning","NLP","TensorFlow","PyTorch","LLM","Generative AI","Computer Vision"],
        "Web / Cloud": ["HTML","CSS","React","Angular","Node.js","Flask","Django","AWS","Azure","GCP","Docker"],
        "Tools": ["Git","GitHub","Linux","REST API","MongoDB","MySQL","PostgreSQL","Oracle"]
    }
    skill_groups = []
    for name, options in groups.items():
        found = [s for s in skills if any(s.lower() == x.lower() for x in options)]
        if found: skill_groups.append((name, found))
    tracked = ["Python","SQL","Machine Learning","Data Analysis","Power BI","Tableau","Java","JavaScript","Pandas","NumPy","Scikit-learn"]
    keyword_map = [(k, k.lower() in lower) for k in tracked]
    sections = [
        ("Contact", bool(candidate.get("email") or candidate.get("phone"))),
        ("Skills", bool(skills)), ("Education", bool(education)),
        ("Projects", bool(projects)), ("Certifications", bool(certs)), ("Experience", years > 0)
    ]
    return dict(score=score, level=level, level_class=cls, strengths=strengths[:5],
                recommendations=recommendations[:6], checks=checks, health=health,
                seniority=seniority, skill_groups=skill_groups, keyword_map=keyword_map,
                keyword_found=sum(x[1] for x in keyword_map), sections=sections,
                section_percent=round(sum(x[1] for x in sections)/len(sections)*100),
                skill_count=len(skills), project_count=len(projects), cert_count=len(certs),
                education_count=len(education), experience_years=years, completeness=completeness)

@app.route("/candidate/<int:candidate_id>")
def candidate_detail(candidate_id):
    if not login_required(): return redirect(url_for("login"))
    candidate = get_candidate(DATABASE, candidate_id)
    if not candidate or (session.get("role") == "user" and candidate.get("uploaded_by") != session.get("username")):
        flash("Candidate profile not found or you do not have access to it.", "danger")
        return redirect(url_for("dashboard"))
    return render_template("candidate.html", candidate=candidate)

@app.route("/candidate/<int:candidate_id>/analysis")
def candidate_analysis(candidate_id):
    if not login_required(): return redirect(url_for("login"))
    candidate = get_candidate(DATABASE, candidate_id)
    if not candidate or (session.get("role") == "user" and candidate.get("uploaded_by") != session.get("username")):
        flash("Candidate profile not found or you do not have access to it.", "danger")
        return redirect(url_for("dashboard"))
    return render_template("analysis.html", candidate=candidate, analysis=build_ai_analysis(candidate))

@app.route("/candidate/<int:candidate_id>/delete", methods=["POST"])
def candidate_delete(candidate_id):
    if not login_required(): return redirect(url_for("login"))
    if session.get("role") not in {"admin", "recruiter"}:
        flash("Only Admin or Recruiter can delete candidate records.", "danger")
        return redirect(url_for("dashboard"))
    candidate = get_candidate(DATABASE, candidate_id)
    if candidate and candidate.get("stored_file"):
        path = UPLOAD_FOLDER / candidate["stored_file"]
        if path.exists(): path.unlink()
    delete_candidate(DATABASE, candidate_id)
    flash("Candidate deleted.", "success")
    return redirect(url_for("dashboard"))

# -------------------- CANDIDATE MATCHING --------------------

@app.route("/jobs")
def jobs():
    if not login_required(): return redirect(url_for("login"))
    return render_template("jobs.html", jobs=get_jobs(DATABASE))

@app.route("/jobs/new", methods=["GET", "POST"])
def new_job():
    if not login_required(): return redirect(url_for("login"))
    if session.get("role") not in {"admin", "recruiter"}:
        flash("Job creation is available to Admin and Recruiter accounts.", "warning")
        return redirect(url_for("jobs"))
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        required = [x.strip() for x in request.form.get("required_skills", "").split(",") if x.strip()]
        experience = request.form.get("experience_required", "0").strip()
        education = request.form.get("education_required", "").strip()
        description = request.form.get("description", "").strip()
        if not title or not required:
            flash("Job title and at least one required skill are required.", "warning")
            return redirect(url_for("new_job"))
        try:
            exp = float(experience or 0)
        except ValueError:
            exp = 0
        job_id = add_job(DATABASE, {
            "title": title, "required_skills": normalize_skills(required),
            "experience_required": exp, "education_required": education,
            "description": description, "created_by": session["username"]
        })
        log_activity("Job created", f"Job #{job_id}: {title}")
        notify("user", "New job posted", f"A new opportunity is available: {title}.")
        notify("admin", "Job created", f"{session['username']} created job #{job_id}: {title}.")
        flash(f"Job #{job_id} created successfully.", "success")
        return redirect(url_for("jobs"))
    return render_template("job_form.html")

@app.route("/jobs/<int:job_id>/edit", methods=["GET", "POST"])
def job_edit(job_id):
    if not login_required(): return redirect(url_for("login"))
    if session.get("role") not in {"admin", "recruiter"}:
        flash("Only recruitment staff can edit job postings.", "danger")
        return redirect(url_for("jobs"))
    job = get_job(DATABASE, job_id)
    if not job:
        flash("Job posting not found.", "warning")
        return redirect(url_for("jobs"))
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        required = [x.strip() for x in request.form.get("required_skills", "").split(",") if x.strip()]
        try: experience = max(0.0, float(request.form.get("experience_required", "0") or 0))
        except ValueError: experience = 0.0
        if not title or not required:
            flash("Job title and at least one required skill are required.", "warning")
            return redirect(url_for("job_edit", job_id=job_id))
        update_job(DATABASE, job_id, {"title": title, "required_skills": normalize_skills(required),
            "experience_required": experience, "education_required": request.form.get("education_required", "").strip(),
            "description": request.form.get("description", "").strip()})
        log_activity("Job updated", f"Job #{job_id}: {title}")
        flash("Job posting updated.", "success")
        return redirect(url_for("jobs"))
    return render_template("job_form.html", job=job, editing=True)

@app.route("/jobs/<int:job_id>/status", methods=["POST"])
def job_status(job_id):
    if not login_required(): return redirect(url_for("login"))
    if session.get("role") not in {"admin", "recruiter"}:
        flash("Only recruitment staff can change job status.", "danger")
        return redirect(url_for("jobs"))
    status = request.form.get("status", "")
    if status not in {"Published", "Closed"}:
        flash("Invalid job status.", "danger")
    elif set_job_status(DATABASE, job_id, status):
        job = get_job(DATABASE, job_id)
        log_activity("Job status changed", f"Job #{job_id} set to {status}")
        if status == "Published" and job:
            notify("user", "Job opportunity available", f"{job['title']} is now published.")
        flash(f"Job marked {status.lower()}.", "success")
    else:
        flash("Job posting not found.", "warning")
    return redirect(url_for("jobs"))

@app.route("/jobs/<int:job_id>/delete", methods=["POST"])
def job_delete(job_id):
    if not login_required(): return redirect(url_for("login"))
    if session.get("role") not in {"admin", "recruiter"}:
        flash("Only Admin or Recruiter can delete job postings.", "danger")
        return redirect(url_for("jobs"))
    deleted = get_job(DATABASE, job_id)
    delete_job(DATABASE, job_id)
    log_activity("Job deleted", f"Job #{job_id}: {(deleted or {}).get('title', 'unknown')}")
    flash("Job deleted.", "success")
    return redirect(url_for("jobs"))

@app.route("/matching")
def matching():
    if not login_required(): return redirect(url_for("login"))
    candidates = get_candidates(DATABASE)
    if session.get("role") == "user":
        candidates = [c for c in candidates if c.get("uploaded_by") == session.get("username")]
    jobs_list = get_jobs(DATABASE)
    job_id = request.args.get("job_id", type=int)
    selected = get_job(DATABASE, job_id) if job_id else (jobs_list[0] if jobs_list else None)
    rows = rank_candidates(candidates, selected) if selected else []
    return render_template("matching.html", candidates=candidates, jobs=jobs_list,
                           selected_job=selected, rows=rows)

@app.route("/matching/all")
def matching_all():
    if not login_required(): return redirect(url_for("login"))
    candidates = get_candidates(DATABASE)
    if session.get("role") == "user": candidates = [c for c in candidates if c.get("uploaded_by") == session.get("username")]
    rows = build_matching_matrix(candidates, get_jobs(DATABASE))
    return render_template("matching_all.html", rows=rows, jobs=get_jobs(DATABASE))

@app.route("/matching/export")
def matching_export():
    if not login_required(): return redirect(url_for("login"))
    job_id = request.args.get("job_id", type=int)
    selected = get_job(DATABASE, job_id) if job_id else None
    if selected:
        export_candidates = get_candidates(DATABASE)
        if session.get("role") == "user": export_candidates = [c for c in export_candidates if c.get("uploaded_by") == session.get("username")]
        rows = rank_candidates(export_candidates, selected)
        filename = f"matching_{selected['id']}.csv"
    else:
        export_candidates = get_candidates(DATABASE)
        if session.get("role") == "user": export_candidates = [c for c in export_candidates if c.get("uploaded_by") == session.get("username")]
        rows = build_matching_matrix(export_candidates, get_jobs(DATABASE))
        filename = "matching_all_jobs.csv"
    df = pd.DataFrame(rows)
    path = EXPORT_FOLDER / filename
    df.to_csv(path, index=False)
    return send_file(path, as_attachment=True, download_name=filename)

@app.route("/matching/export_excel")
def matching_export_excel():
    if not login_required(): return redirect(url_for("login"))
    export_candidates = get_candidates(DATABASE)
    if session.get("role") == "user": export_candidates = [c for c in export_candidates if c.get("uploaded_by") == session.get("username")]
    rows = build_matching_matrix(export_candidates, get_jobs(DATABASE))
    filename = "matching_results.xlsx"
    path = EXPORT_FOLDER / filename
    pd.DataFrame(rows).to_excel(path, index=False)
    return send_file(path, as_attachment=True, download_name=filename)

# --------------------  3: INTERVIEW ASSISTANCE & ATS --------------------

@app.route("/interview-assistant", methods=["GET", "POST"])
def interview_assistant():
    if not login_required():
        return redirect(url_for("login"))
    candidates = get_candidates(DATABASE)
    ats_candidates = list_ats_candidates(DATABASE)
    roles = available_roles()
    role = request.values.get("job_role", roles[0] if roles else "Data Scientist")
    qtype = request.values.get("question_type", "technical")
    count = request.values.get("num_questions", 3, type=int) or 3
    questions = build_interview_questions(role, qtype, max(1, min(count, 1000)))

    active_session = None
    session_id = request.args.get("session_id", type=int)
    if session_id:
        active_session = get_interview_session(DATABASE, session_id)

    if request.method == "POST" and request.form.get("action") == "start_interview":
        candidate_name = request.form.get("candidate_name", "Candidate").strip() or "Candidate"
        candidate_email = request.form.get("candidate_email", "").strip()
        role = request.form.get("job_role", roles[0])
        qtype = request.form.get("question_type", "mixed")
        count = max(1, min(request.form.get("num_questions", 10, type=int) or 10, 1000))
        questions = build_interview_questions(role, qtype, count)
        active_session_id = create_interview_session(DATABASE, candidate_name, candidate_email, role, questions)
        log_activity("Interview scheduled", f"Interview for {candidate_name} ({role})")
        notify("admin", "Interview scheduled", f"Interview scheduled for {candidate_name} ({role}).")
        notify("recruiter", "Interview scheduled", f"Interview scheduled for {candidate_name} ({role}).")
        if candidate_email and session.get("role") in {"admin", "recruiter"}:
            add_ats_candidate(DATABASE, candidate_name, candidate_email, role, "Interview Scheduled")
        return redirect(url_for("interview_assistant", session_id=active_session_id))

    return render_template("interview_assistant.html", roles=roles, role=role, question_type=qtype,
                           questions=questions, candidates=candidates, ats_candidates=ats_candidates,
                           active_session=active_session)

@app.route("/interview-assistant/respond", methods=["POST"])
def interview_respond():
    if not login_required():
        return redirect(url_for("login"))
    session_id = request.form.get("session_id", type=int)
    question = request.form.get("question", "").strip()
    response = request.form.get("response", "").strip()
    if session_id and question and response:
        add_response(DATABASE, session_id, question, response)
    return redirect(url_for("interview_assistant", session_id=session_id))

@app.route("/interview-assistant/complete/<int:session_id>", methods=["POST"])
def interview_complete(session_id):
    if not login_required():
        return redirect(url_for("login"))
    interview = get_interview_session(DATABASE, session_id)
    if interview:
        complete_interview(DATABASE, session_id)
        log_activity("Interview completed", f"Interview #{session_id} for {interview.get('candidate_name', 'Candidate')}")
        notify("recruiter", "Interview completed", f"Interview #{session_id} has been completed.")
        notify("admin", "Interview completed", f"Interview #{session_id} has been completed.")
        if interview.get("candidate_email"):
            update_ats_status(DATABASE, interview["candidate_email"], "Interview Completed")
        flash("Interview completed and ATS status updated.", "success")
    return redirect(url_for("interview_assistant", session_id=session_id))


@app.route("/pipeline")
def pipeline():
    if not login_required(): return redirect(url_for("login"))
    role = session.get("role")
    if role not in {"admin", "recruiter"}:
        flash("Recruitment pipeline is available to recruitment staff.", "warning")
        return redirect(url_for("dashboard"))
    candidates = get_candidates(DATABASE)
    if role == "user":
        candidates = [c for c in candidates if c.get("uploaded_by") == session.get("username")]
    stages=["New","Shortlisted","Interview","Offered","Hired","Rejected"]
    grouped={s:[c for c in candidates if c.get("status","New")==s] for s in stages}
    return render_template("pipeline.html",grouped=grouped,stages=stages,role=role)

@app.route("/candidate/<int:candidate_id>/status",methods=["POST"])
def candidate_status(candidate_id):
    if not login_required(): return redirect(url_for("login"))
    if session.get("role") not in {"admin", "recruiter"}:
        flash("Only Admin or Recruiter can change pipeline stages.", "danger")
        return redirect(url_for("dashboard"))
    status=request.form.get("status","New")
    candidate_record=get_candidate(DATABASE,candidate_id)
    if update_candidate_status(DATABASE,candidate_id,status):
        log_activity("Candidate status changed", f"Candidate #{candidate_id} moved to {status}")
        if candidate_record and candidate_record.get("uploaded_by"):
            notify("user", "Application status updated", f"Your profile status is now {status}.", recipient=candidate_record.get("uploaded_by"))
        notify("admin", "Candidate status updated", f"Candidate #{candidate_id} moved to {status} by {session['username']}.")
        flash("Candidate pipeline updated.","success")
    else: flash("Invalid candidate status.","danger")
    return redirect(request.referrer or url_for("pipeline"))

@app.route("/screening", methods=["GET", "POST"])
def screening():
    if not login_required(): return redirect(url_for("login"))
    roles = available_roles()
    role = request.values.get("job_role", roles[0] if roles else "Data Analyst")
    try: count = max(1, min(int(request.values.get("num_questions", 10)), 1000))
    except (TypeError, ValueError): count = 10
    questions = build_interview_questions(role, request.values.get("question_type", "mixed"), count)
    if request.method == "POST" and request.form.get("transcript"):
        flash("Voice interview transcript captured for this session. Review it below before making a hiring decision.", "success")
    return render_template("screening.html", candidates=get_candidates(DATABASE), roles=roles,
                           selected_role=role, num_questions=count, questions=questions)

@app.route("/chatbot",methods=["POST"])
def chatbot():
    if not login_required(): return jsonify({"error":"Unauthorized"}),401
    data=request.get_json(silent=True) or {}; original=str(data.get("message", "")).strip(); msg=original.lower()
    if not original:
        return jsonify({"answer":"Please enter a question about resumes, jobs, matching, interviews, analytics or recruitment."}), 400
    # Optional LLM mode: configure OPENAI_API_KEY and optionally OPENAI_MODEL.
    # The app remains fully usable in offline/demo mode without an API key.
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if api_key:
        try:
            import json as _json
            import urllib.request
            prompt = ("You are Recruitment Copilot, an assistant for a hiring platform. "
                      "Give concise, responsible guidance on resume parsing, job descriptions, "
                      "candidate-job matching, skill gaps, ATS, interview practice, voice screening, "
                      "and dashboard analytics. Do not make hiring decisions based on protected traits. "
                      "User question: " + original)
            payload = _json.dumps({"model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                                   "messages": [{"role": "system", "content": "You are a helpful recruitment workflow copilot."},
                                               {"role": "user", "content": prompt}], "temperature": 0.3}).encode("utf-8")
            req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=payload,
                    headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=18) as response:
                llm_data = _json.loads(response.read().decode("utf-8"))
            answer = llm_data["choices"][0]["message"]["content"].strip()
            if answer:
                return jsonify({"answer": answer, "mode": "llm"})
        except Exception:
            pass  # use local assistant fallback if the API is unavailable

    candidates=get_candidates(DATABASE); jobs=get_jobs(DATABASE)
    if any(k in msg for k in ["candidate","resume","applicant"]):
        answer=f"There are {len(candidates)} candidate profiles. Open Candidate Matching to rank them against a job."
    elif "job" in msg or "role" in msg:
        answer=f"There are {len(jobs)} job postings. You can create additional roles from Job Postings."
    elif "match" in msg or "skill gap" in msg:
        answer="Use Candidate Matching to see compatibility, matched skills, missing skills and recommendations."
    elif "question" in msg or "interview" in msg:
        answer="Interview Assistant supports any number from 1 to 1000 questions, with technical, behavioral or mixed modes."
    elif "voice" in msg or "screen" in msg:
        answer="Voice Screening uses browser speech recognition when supported. Open Voice Screening and press Start Screening."
    elif "pipeline" in msg:
        answer="Pipeline stages are New, Shortlisted, Interview, Offered, Hired and Rejected."
    else:
        answer="I can help with resumes, jobs, matching, skill gaps, interviews, ATS, voice screening and pipeline. Try asking about one of these."
    return jsonify({"answer":answer})

@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    if not login_required():
        return redirect(url_for("login"))
    role = session.get("role", "user")
    all_candidates = get_candidates(DATABASE)
    candidates = all_candidates if role in ("admin", "recruiter") else [c for c in all_candidates if c.get("uploaded_by") == session.get("username")]
    if request.method == "POST":
        if role != "user":
            flash("Recruiters and administrators can monitor feedback but cannot submit it.", "danger")
            return redirect(url_for("feedback"))
        rating = request.form.get("rating", type=int)
        comment = request.form.get("comment", "")
        candidate_id = request.form.get("candidate_id", type=int)
        selected = next((c for c in candidates if c.get("id") == candidate_id), None) if candidate_id else None
        if not rating or not 1 <= rating <= 5:
            flash("Please select a satisfaction rating from 1 to 5.", "warning")
        elif candidate_id and not selected:
            flash("Please select a valid candidate from your permitted list.", "danger")
        else:
            add_feedback(DATABASE, session.get("username", "anonymous"), rating, comment, candidate_id, selected.get("name", "") if selected else "")
            log_activity("Feedback submitted", f"Rating {rating}/5")
            notify("recruiter", "New user feedback", f"A user submitted a {rating}/5 rating.")
            notify("admin", "New user feedback", f"A user submitted a {rating}/5 rating.")
            flash("Thank you. Your feedback has been recorded.", "success")
            return redirect(url_for("feedback"))
    feedback_rows = get_feedback(DATABASE)
    if role == "user":
        feedback_rows = [r for r in feedback_rows if r.get("username") == session.get("username")]
    return render_template("feedback.html", summary=get_feedback_summary(DATABASE), feedback=feedback_rows, candidates=candidates, role=role)


@app.route("/workflow/<int:candidate_id>")
def workflow(candidate_id):
    if not login_required():
        return redirect(url_for("login"))
    candidate = get_candidate(DATABASE, candidate_id)
    if not candidate:
        flash("Candidate not found.", "danger")
        return redirect(url_for("dashboard"))
    status = candidate.get("status", "New")
    stage_map = {"New": 1, "Shortlisted": 2, "Interview": 3, "Offered": 4, "Hired": 5, "Rejected": 0}
    return render_template("workflow.html", candidate=candidate, current_stage=stage_map.get(status, 1), stages=["Profiled", "Matched", "Interviewed", "Offered", "Hired"], status=status)


# -------------------- PRODUCTIVITY FEATURES --------------------
def _visible_candidates():
    items = get_candidates(DATABASE)
    if session.get("role") == "user":
        items = [c for c in items if c.get("uploaded_by") == session.get("username")]
    return items

@app.route("/notifications")
def notifications():
    if not login_required(): return redirect(url_for("login"))
    role, username = session.get("role"), session.get("username")
    with sqlite3.connect(DATABASE) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM notifications WHERE (role=? OR recipient=?) AND (recipient IS NULL OR recipient=? OR role=?) ORDER BY id DESC LIMIT 100",
                            (role, username, username, role)).fetchall()
    return render_template("feature_hub.html", feature="notifications", items=[dict(r) for r in rows])

@app.route("/notifications/<int:notification_id>/read", methods=["POST"])
def notification_read(notification_id):
    if not login_required(): return redirect(url_for("login"))
    with sqlite3.connect(DATABASE) as conn:
        conn.execute("UPDATE notifications SET is_read=1 WHERE id=? AND (role=? OR recipient=?)",
                     (notification_id, session.get("role"), session.get("username")))
    return redirect(url_for("notifications"))

@app.route("/candidates/search")
def candidate_search():
    if not login_required(): return redirect(url_for("login"))
    q=request.args.get("q", "").strip().lower(); skill=request.args.get("skill", "").strip().lower()
    status=request.args.get("status", "").strip(); role_filter=request.args.get("role", "").strip().lower()
    selected_job_id=request.args.get("job_id",type=int); selected_job=get_job(DATABASE,selected_job_id) if selected_job_id else None
    try: min_match=float(request.args.get("min_match", "0") or 0)
    except ValueError: min_match=0
    jobs_for_filter=get_jobs(DATABASE)
    try: min_exp=float(request.args.get("min_exp", "0") or 0)
    except ValueError: min_exp=0
    # Candidate accounts use Advanced Search to discover jobs, not to browse other candidates.
    if session.get("role") == "user":
        filtered_jobs=[]
        for j in jobs_for_filter:
            jskills=j.get("required_skills", [])
            if isinstance(jskills, str):
                try: jskills=json.loads(jskills)
                except Exception: jskills=[jskills]
            jhay=" ".join([str(j.get("title", "")), str(j.get("description", "")), " ".join(map(str, jskills))]).lower()
            if q and q not in jhay: continue
            if skill and not any(skill in str(x).lower() for x in jskills): continue
            if role_filter and role_filter not in str(j.get("title", "")).lower() and role_filter not in jhay: continue
            if float(j.get("experience_required", 0) or 0) < min_exp: continue
            if str(j.get("status", "Published")).lower() not in {"published", "open", "active"}: continue
            filtered_jobs.append(j)
        return render_template("feature_hub.html", feature="search", candidates=[], jobs=filtered_jobs,
            jobs_for_filter=[], selected_job_id=None,
            filters={"q":q,"skill":skill,"status":"","min_exp":min_exp,"role":role_filter,"min_match":0},
            is_candidate_search=True)
    candidates=_visible_candidates()
    filtered=[]
    for c in candidates:
        hay=" ".join([str(c.get("name", "")),str(c.get("email", "")),str(c.get("education", ""))," ".join(c.get("skills", []))]).lower()
        if q and q not in hay: continue
        if skill and not any(skill in str(x).lower() for x in c.get("skills", [])): continue
        if status and c.get("status", "New") != status: continue
        if float(c.get("experience_years",0) or 0) < min_exp: continue
        if role_filter and role_filter not in str(c.get("target_role", c.get("job_role", ""))).lower() and role_filter not in hay: continue
        if selected_job and calculate_match(c, selected_job).get("hiring_score",0) < min_match: continue
        filtered.append(c)
    job_rows=get_jobs(DATABASE)
    filtered_jobs=[]
    for j in job_rows:
        jskills=j.get("required_skills", [])
        if isinstance(jskills,str):
            try: jskills=json.loads(jskills)
            except Exception: jskills=[jskills]
        jhay=" ".join([str(j.get("title", "")),str(j.get("description", ""))," ".join(map(str,jskills))]).lower()
        if q and q not in jhay: continue
        if skill and not any(skill in str(x).lower() for x in jskills): continue
        if role_filter and role_filter not in str(j.get("title", "")).lower() and role_filter not in jhay: continue
        filtered_jobs.append(j)
    return render_template("feature_hub.html", feature="search", candidates=filtered, jobs=filtered_jobs, jobs_for_filter=jobs_for_filter, selected_job_id=selected_job_id, filters={"q":q,"skill":skill,"status":status,"min_exp":min_exp,"role":role_filter,"min_match":min_match})

@app.route("/candidates/compare")
def candidate_compare():
    if not login_required(): return redirect(url_for("login"))
    candidates=_visible_candidates(); ids=request.args.getlist("candidate_id", type=int)
    selected=[c for c in candidates if c.get("id") in ids][:4]
    return render_template("feature_hub.html", feature="compare", candidates=candidates, selected=selected)

@app.route("/learning-roadmap")
def learning_roadmap():
    if not login_required(): return redirect(url_for("login"))
    candidates=_visible_candidates(); candidate_id=request.args.get("candidate_id",type=int)
    chosen=next((c for c in candidates if c.get("id")==candidate_id), candidates[0] if candidates else None)
    skills=[str(x).strip() for x in (chosen or {}).get("skills",[]) if str(x).strip()]
    known={x.lower() for x in skills}
    suggestions=[("SQL", "SQLBolt interactive lessons", "Practice SELECT, JOIN, GROUP BY and window functions"),("Python", "Python official tutorial", "Work through functions, collections, files and error handling"),("Statistics", "Khan Academy statistics", "Review distributions, probability, confidence intervals and hypothesis tests"),("Power BI", "Microsoft Learn: Power BI", "Build a data model, measures and an interactive report"),("Machine Learning", "Google Machine Learning Crash Course", "Practice train/test split, evaluation metrics and overfitting"),("Communication", "Project presentation practice", "Explain one project in 2 minutes and defend design decisions")]
    roadmap=[{"skill":sk,"resource":res,"task":task} for sk,res,task in suggestions if sk.lower() not in known]
    if not roadmap: roadmap=[{"skill":"Advanced practice","resource":"Portfolio project","task":"Build a small end-to-end project and document the decisions, metrics and limitations."}]
    return render_template("feature_hub.html", feature="roadmap", candidates=candidates, chosen=chosen, roadmap=roadmap,
                           needs_resume=(session.get("role") == "user" and chosen is None))

@app.route("/interview-scorecards", methods=["GET","POST"])
def interview_scorecards():
    if not login_required(): return redirect(url_for("login"))
    role=session.get("role")
    if role not in {"admin","recruiter"}:
        flash("Interview scorecards are available to recruiters and administrators.","warning")
        return redirect(url_for("dashboard"))
    with sqlite3.connect(DATABASE) as conn:
        conn.row_factory=sqlite3.Row
        conn.execute("CREATE TABLE IF NOT EXISTS interview_scorecards (id INTEGER PRIMARY KEY AUTOINCREMENT, interview_id INTEGER NOT NULL, reviewer TEXT NOT NULL, technical INTEGER NOT NULL, communication INTEGER NOT NULL, problem_solving INTEGER NOT NULL, role_fit INTEGER NOT NULL, notes TEXT DEFAULT '', created_at TEXT NOT NULL, UNIQUE(interview_id, reviewer))")
        if request.method=="POST":
            iid=request.form.get("interview_id",type=int)
            interview=get_interview_session(DATABASE,iid) if iid else None
            if not interview or interview.get("status")!="Interview Completed":
                flash("Select a completed interview before scoring it.","warning")
            else:
                vals=[request.form.get(k,type=int) for k in ("technical","communication","problem_solving","role_fit")]
                if any(v is None or v<1 or v>5 for v in vals): flash("All competency ratings must be between 1 and 5.","warning")
                else:
                    conn.execute("INSERT INTO interview_scorecards(interview_id,reviewer,technical,communication,problem_solving,role_fit,notes,created_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(interview_id,reviewer) DO UPDATE SET technical=excluded.technical,communication=excluded.communication,problem_solving=excluded.problem_solving,role_fit=excluded.role_fit,notes=excluded.notes,created_at=excluded.created_at",(iid,session["username"],*vals,request.form.get("notes","")[:2000],datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    log_activity("Interview scorecard saved",f"Interview #{iid}")
                    flash("Interview scorecard saved.","success")
        rows=conn.execute("SELECT * FROM interview_scorecards ORDER BY id DESC LIMIT 100").fetchall()
    with sqlite3.connect(DATABASE) as conn:
        conn.row_factory=sqlite3.Row
        completed=conn.execute("SELECT id,candidate_name,candidate_email,job_role,status,created_at,completed_at FROM interview_sessions WHERE status='Interview Completed' ORDER BY id DESC").fetchall()
    return render_template("feature_hub.html",feature="scorecards",scorecards=[dict(r) for r in rows], completed=[dict(r) for r in completed])

@app.route("/activity")
def activity_timeline():
    if not login_required(): return redirect(url_for("login"))
    if session.get("role") not in {"admin","recruiter"}:
        flash("Activity timeline is available to recruitment staff.","warning"); return redirect(url_for("dashboard"))
    with sqlite3.connect(DATABASE) as conn:
        conn.row_factory=sqlite3.Row
        rows=conn.execute("SELECT * FROM activity_logs ORDER BY id DESC LIMIT 200").fetchall()
    return render_template("feature_hub.html",feature="activity",items=[dict(r) for r in rows])

@app.route("/reports/export/<report_type>")
def report_export(report_type):
    if not login_required(): return redirect(url_for("login"))
    if report_type not in {"candidates","analytics","activity"}:
        flash("Unknown report type.","warning"); return redirect(url_for("dashboard"))
    if report_type in {"activity", "analytics"} and session.get("role")!="admin":
        flash("Only administrators can export platform analytics or the audit log.","danger"); return redirect(url_for("dashboard"))
    if report_type=="candidates":
        rows=[]
        for c in _visible_candidates():
            rows.append({"id":c.get("id"),"name":c.get("name"),"email":c.get("email"),"experience_years":c.get("experience_years"),"skills":", ".join(c.get("skills",[])),"status":c.get("status"),"uploaded_by":c.get("uploaded_by"),"completeness":c.get("completeness")})
    elif report_type=="analytics":
        a=get_analytics(DATABASE); rows=[{"metric":k,"value":json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v} for k,v in a.items()]
    else:
        with sqlite3.connect(DATABASE) as conn:
            conn.row_factory=sqlite3.Row; rows=[dict(r) for r in conn.execute("SELECT * FROM activity_logs ORDER BY id DESC").fetchall()]
    df=pd.DataFrame(rows); base=EXPORT_FOLDER/f"{report_type}_report"
    if request.args.get("format","csv").lower()=="xlsx":
        path=base.with_suffix(".xlsx"); df.to_excel(path,index=False); mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        path=base.with_suffix(".csv"); df.to_csv(path,index=False); mime="text/csv"
    log_activity("Report exported",f"{report_type} report ({path.suffix})")
    return send_file(path,as_attachment=True,download_name=path.name,mimetype=mime)

@app.route("/health")
def health():
    return jsonify({"status": "healthy", "service": "AI Recruitment Copilot", "time": datetime.utcnow().isoformat() + "Z"})


@app.route("/api/feedback/summary")
def feedback_summary_api():
    if not login_required():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(get_feedback_summary(DATABASE))


@app.route("/api/ats/add_candidate", methods=["POST"])
def api_ats_add_candidate():
    if not login_required():
        return jsonify({"error": "Unauthorized"}), 401
    if session.get("role") not in {"admin", "recruiter"}: return jsonify({"error":"Recruiter or administrator access required"}),403
    data = request.get_json(silent=True) or request.form
    required = [data.get("name"), data.get("email"), data.get("job_applied")]
    if not all(required):
        return jsonify({"error": "name, email and job_applied are required"}), 400
    candidate = add_ats_candidate(DATABASE, data.get("name"), data.get("email"), data.get("job_applied"), data.get("status", "Interview Scheduled"))
    log_activity("ATS candidate added", f"{data.get('name')} applied for {data.get('job_applied')}")
    return jsonify({"message": "Candidate added successfully", "candidate": candidate}), 201

@app.route("/api/ats/list_candidates", methods=["GET"])
def api_ats_list_candidates():
    if not login_required():
        return jsonify({"error": "Unauthorized"}), 401
    if session.get("role") not in {"admin", "recruiter"}: return jsonify({"error":"Recruiter or administrator access required"}),403
    return jsonify(list_ats_candidates(DATABASE))

@app.route("/api/ats/update_status/<path:email>", methods=["PUT"])
def api_ats_update_status(email):
    if not login_required():
        return jsonify({"error": "Unauthorized"}), 401
    if session.get("role") not in {"admin", "recruiter"}: return jsonify({"error":"Recruiter or administrator access required"}),403
    data = request.get_json(silent=True) or request.form
    status = data.get("status")
    if not status:
        return jsonify({"error": "status is required"}), 400
    if not update_ats_status(DATABASE, email, status):
        return jsonify({"error": "Candidate not found"}), 404
    return jsonify({"message": f"Status updated for {email}", "status": status})


@app.route("/api/match/<int:candidate_id>/<int:job_id>")
def api_match(candidate_id, job_id):
    if not login_required(): return jsonify({"error": "Unauthorized"}), 401
    candidate = get_candidate(DATABASE, candidate_id)
    job = get_job(DATABASE, job_id)
    if not candidate or not job:
        return jsonify({"error": "Candidate or job not found"}), 404
    return jsonify(calculate_match(candidate, job))

@app.route("/api/matching")
def api_matching():
    if not login_required(): return jsonify({"error": "Unauthorized"}), 401
    job_id = request.args.get("job_id", type=int)
    job = get_job(DATABASE, job_id) if job_id else None
    if job:
        rows = rank_candidates(get_candidates(DATABASE), job)
    else:
        rows = build_matching_matrix(get_candidates(DATABASE), get_jobs(DATABASE))
    return jsonify(rows)

@app.route("/api/analytics")
def api_analytics():
    if not login_required(): return jsonify({"error": "Unauthorized"}), 401
    return jsonify(get_analytics(DATABASE))

@app.route("/api/candidates")
def api_candidates():
    if not login_required(): return jsonify({"error": "Unauthorized"}), 401
    return jsonify(get_candidates(DATABASE))

if __name__ == "__main__":
    # Local development and container fallback. Render uses Gunicorn via render.yaml.
    port = int(os.environ.get("PORT", "5000"))
    app.run(debug=False, host="0.0.0.0", port=port)
