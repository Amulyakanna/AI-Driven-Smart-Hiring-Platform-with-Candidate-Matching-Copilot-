
import json
import sqlite3
from pathlib import Path
from datetime import datetime

def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_job_tables(db_path):
    conn = connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            required_skills TEXT NOT NULL,
            experience_required REAL DEFAULT 0,
            education_required TEXT DEFAULT '',
            description TEXT DEFAULT '',
            created_by TEXT,
            created_at TEXT
        )
    """)
    # Safe migration for databases created by earlier project versions.
    columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
    if "status" not in columns:
        conn.execute("ALTER TABLE jobs ADD COLUMN status TEXT NOT NULL DEFAULT 'Published'")
    conn.commit()
    conn.close()

def update_job(db_path, job_id, job):
    conn = connect(db_path)
    conn.execute("""UPDATE jobs SET title=?, required_skills=?, experience_required=?,
        education_required=?, description=? WHERE id=?""", (
        job["title"], json.dumps(job.get("required_skills", [])),
        float(job.get("experience_required", 0) or 0), job.get("education_required", ""),
        job.get("description", ""), job_id))
    conn.commit()
    changed = conn.total_changes > 0
    conn.close()
    return changed

def set_job_status(db_path, job_id, status):
    conn = connect(db_path)
    cur = conn.execute("UPDATE jobs SET status=? WHERE id=?", (status, job_id))
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed

def add_job(db_path, job):
    conn = connect(db_path)
    cur = conn.execute("""
        INSERT INTO jobs
        (title, required_skills, experience_required, education_required,
         description, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        job["title"],
        json.dumps(job.get("required_skills", [])),
        float(job.get("experience_required", 0) or 0),
        job.get("education_required", ""),
        job.get("description", ""),
        job.get("created_by", ""),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    conn.commit()
    job_id = cur.lastrowid
    conn.close()
    return job_id

def get_jobs(db_path):
    conn = connect(db_path)
    rows = conn.execute("SELECT * FROM jobs ORDER BY id DESC").fetchall()
    conn.close()
    result = []
    for row in rows:
        item = dict(row)
        try:
            item["required_skills"] = json.loads(item["required_skills"])
        except Exception:
            item["required_skills"] = []
        result.append(item)
    return result

def get_job(db_path, job_id):
    conn = connect(db_path)
    row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    conn.close()
    if not row:
        return None
    item = dict(row)
    try:
        item["required_skills"] = json.loads(item["required_skills"])
    except Exception:
        item["required_skills"] = []
    return item

def delete_job(db_path, job_id):
    conn = connect(db_path)
    conn.execute("DELETE FROM jobs WHERE id=?", (job_id,))
    conn.commit()
    conn.close()

def seed_demo_jobs(db_path):
    existing={j["title"] for j in get_jobs(db_path)}
    demo_jobs=[
{"title":"Senior Machine Learning Engineer","required_skills":["Python","TensorFlow","Kubernetes","AWS SageMaker","SQL"],"experience_required":4,"education_required":"Computer Science","description":"Build and deploy production machine learning systems."},
{"title":"Data Scientist","required_skills":["Python","SQL","Pandas","Scikit-learn","Statistics"],"experience_required":2,"education_required":"Data Science","description":"Build predictive models and translate data into business insights."},
{"title":"Data Analyst","required_skills":["Python","SQL","Excel","Power BI","Data Analysis"],"experience_required":1,"education_required":"Computer Science","description":"Analyze business data and create decision-ready dashboards."},
{"title":"Software Engineer","required_skills":["Python","Java","SQL","Git","REST API"],"experience_required":2,"education_required":"Computer Science","description":"Develop maintainable software products and APIs."},
{"title":"Python Developer","required_skills":["Python","Flask","SQL","Git","REST API"],"experience_required":1,"education_required":"Computer Science","description":"Build Python services, automation and backend applications."},
{"title":"AI Engineer","required_skills":["Python","LLM","Generative AI","RAG","Machine Learning"],"experience_required":2,"education_required":"Artificial Intelligence","description":"Build and evaluate AI-powered applications."},
{"title":"Frontend Developer","required_skills":["JavaScript","React","HTML","CSS","Git"],"experience_required":1,"education_required":"Computer Science","description":"Build responsive, accessible web interfaces."},
{"title":"Backend Developer","required_skills":["Java","Spring","SQL","AWS","REST API"],"experience_required":3,"education_required":"Computer Science","description":"Develop scalable backend services and APIs."},
{"title":"Cloud Engineer","required_skills":["AWS","Docker","Kubernetes","Linux","Git"],"experience_required":2,"education_required":"Computer Science","description":"Design cloud infrastructure, deployment and observability."},
{"title":"DevOps Engineer","required_skills":["Docker","Kubernetes","Linux","Git","AWS"],"experience_required":2,"education_required":"Computer Science","description":"Automate delivery, reliability and infrastructure operations."},
{"title":"Data Engineer","required_skills":["Python","SQL","Pandas","Spark","Airflow"],"experience_required":2,"education_required":"Data Engineering","description":"Build reliable data pipelines and analytical platforms."},
{"title":"Cybersecurity Analyst","required_skills":["Linux","Python","SQL","Security","SIEM"],"experience_required":1,"education_required":"Cybersecurity","description":"Monitor threats, investigate incidents and improve security posture."},
{"title":"Product Manager","required_skills":["Analytics","SQL","Product Management","Agile","Communication"],"experience_required":3,"education_required":"Business","description":"Own product strategy, discovery, prioritization and outcomes."},
{"title":"UI/UX Designer","required_skills":["Figma","UI/UX","User Research","Prototyping","Accessibility"],"experience_required":2,"education_required":"Design","description":"Design intuitive user experiences backed by research and testing."}]
    for job in demo_jobs:
        if job["title"] not in existing: add_job(db_path,job)
