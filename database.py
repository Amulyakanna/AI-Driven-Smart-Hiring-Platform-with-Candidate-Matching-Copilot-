import json
import sqlite3
from collections import Counter

def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path):
    conn = connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """)
    user_columns = {r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "last_login" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN last_login TEXT")
    if "login_count" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN login_count INTEGER DEFAULT 0")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            phone TEXT,
            education TEXT,
            skills TEXT,
            experience_years REAL DEFAULT 0,
            experience_entries TEXT,
            certifications TEXT,
            projects TEXT,
            organizations TEXT,
            completeness REAL DEFAULT 0,
            source_file TEXT,
            stored_file TEXT,
            uploaded_by TEXT,
            uploaded_at TEXT,
            status TEXT DEFAULT 'New',
            notes TEXT DEFAULT '',
            updated_at TEXT
        )
    """)
    columns={r[1] for r in conn.execute("PRAGMA table_info(candidates)").fetchall()}
    for name, definition in [("status","TEXT DEFAULT 'New'"),("notes","TEXT DEFAULT ''"),("updated_at","TEXT")]:
        if name not in columns: conn.execute(f"ALTER TABLE candidates ADD COLUMN {name} {definition}")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidates(status)")
    conn.execute("""CREATE TABLE IF NOT EXISTS user_feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
        comment TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        candidate_id INTEGER,
        candidate_name TEXT DEFAULT ''
    )""")
    # Migrate databases created by earlier versions. Without this migration, the
    # feedback POST fails on older local SQLite files that lack candidate columns.
    feedback_columns = {r[1] for r in conn.execute("PRAGMA table_info(user_feedback)").fetchall()}
    if "candidate_id" not in feedback_columns:
        conn.execute("ALTER TABLE user_feedback ADD COLUMN candidate_id INTEGER")
    if "candidate_name" not in feedback_columns:
        conn.execute("ALTER TABLE user_feedback ADD COLUMN candidate_name TEXT DEFAULT ''")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_username ON user_feedback(username)")
    conn.commit()
    conn.close()


def add_user(db_path, username, password, role):
    conn = connect(db_path)
    try:
        conn.execute(
            "INSERT INTO users(username,password,role) VALUES(?,?,?)",
            (username, password, role)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()


def record_user_login(db_path, username):
    from datetime import datetime
    conn = connect(db_path)
    conn.execute("UPDATE users SET last_login=?, login_count=COALESCE(login_count,0)+1 WHERE username=?",
                 (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), username))
    conn.commit()
    conn.close()


def update_user_password(db_path, username, password):
    conn = connect(db_path)
    conn.execute("UPDATE users SET password=? WHERE username=?", (password, username))
    conn.commit()
    conn.close()


def get_users(db_path):
    conn = connect(db_path)
    rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_candidate(db_path, c):
    conn = connect(db_path)
    cur = conn.execute("""
        INSERT INTO candidates
        (name,email,phone,education,skills,experience_years,experience_entries,
         certifications,projects,organizations,completeness,source_file,stored_file,
         uploaded_by,uploaded_at,status,notes,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        c.get("name"),
        c.get("email"),
        c.get("phone"),
        json.dumps(c.get("education", [])),
        json.dumps(c.get("skills", [])),
        c.get("experience_years", 0),
        json.dumps(c.get("experience_entries", [])),
        json.dumps(c.get("certifications", [])),
        json.dumps(c.get("projects", [])),
        json.dumps(c.get("organizations", [])),
        c.get("completeness", 0),
        c.get("source_file"),
        c.get("stored_file"),
        c.get("uploaded_by"),
        c.get("uploaded_at") or __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        c.get("status","New"), c.get("notes",""), c.get("updated_at")
    ))
    conn.commit()
    candidate_id = cur.lastrowid
    conn.close()
    return candidate_id


def deserialize(row):
    d = dict(row)
    for key in [
        "education", "skills", "experience_entries",
        "certifications", "projects", "organizations"
    ]:
        try:
            d[key] = json.loads(d[key]) if d[key] else []
        except Exception:
            d[key] = []
    return d


def get_candidates(db_path):
    conn = connect(db_path)
    rows = conn.execute(
        "SELECT * FROM candidates ORDER BY uploaded_at DESC, id DESC"
    ).fetchall()
    conn.close()
    return [deserialize(r) for r in rows]


def get_candidate(db_path, candidate_id):
    conn = connect(db_path)
    row = conn.execute(
        "SELECT * FROM candidates WHERE id=?", (candidate_id,)
    ).fetchone()
    conn.close()
    return deserialize(row) if row else None


def delete_candidate(db_path, candidate_id):
    conn = connect(db_path)
    conn.execute("DELETE FROM candidates WHERE id=?", (candidate_id,))
    conn.commit()
    conn.close()


def get_analytics(db_path):
    candidates = get_candidates(db_path)

    total = len(candidates)
    avg_completeness = round(
        sum(float(c.get("completeness", 0)) for c in candidates) / total, 1
    ) if total else 0

    avg_experience = round(
        sum(float(c.get("experience_years", 0)) for c in candidates) / total, 1
    ) if total else 0

    skill_counter = Counter()
    education_counter = Counter()
    experience_buckets = Counter()
    certification_count = 0
    project_count = 0
    complete_profiles = 0

    for c in candidates:
        skill_counter.update(c.get("skills", []))

        for edu in c.get("education", []):
            education_counter[edu[:50]] += 1

        years = float(c.get("experience_years", 0))
        if years == 0:
            bucket = "0 years"
        elif years < 2:
            bucket = "0–2 years"
        elif years < 5:
            bucket = "2–5 years"
        elif years < 10:
            bucket = "5–10 years"
        else:
            bucket = "10+ years"
        experience_buckets[bucket] += 1

        certification_count += len(c.get("certifications", []))
        project_count += len(c.get("projects", []))

        if float(c.get("completeness", 0)) >= 75:
            complete_profiles += 1

    top_skills = [
        {"skill": k, "count": v}
        for k, v in skill_counter.most_common(10)
    ]

    top_education = [
        {"education": k, "count": v}
        for k, v in education_counter.most_common(8)
    ]

    experience_order = ["0 years", "0–2 years", "2–5 years", "5–10 years", "10+ years"]
    experience_distribution = [
        {"range": k, "count": experience_buckets.get(k, 0)}
        for k in experience_order
    ]

    format_counter = Counter(
        "PDF" if str(c.get("source_file", "")).lower().endswith(".pdf") else "DOCX"
        for c in candidates
    )

    return {
        "total_candidates": total,
        "avg_completeness": avg_completeness,
        "avg_experience": avg_experience,
        "complete_profiles": complete_profiles,
        "certifications": certification_count,
        "projects": project_count,
        "top_skills": top_skills,
        "top_education": top_education,
        "experience_distribution": experience_distribution,
        "format_distribution": [
            {"format": k, "count": v} for k, v in format_counter.items()
        ],
        "satisfaction": get_feedback_summary(db_path)
    }

def add_feedback(db_path, username, rating, comment="", candidate_id=None, candidate_name=""):
    from datetime import datetime
    rating = max(1, min(int(rating), 5))
    conn = connect(db_path)
    conn.execute("INSERT INTO user_feedback(username,rating,comment,created_at,candidate_id,candidate_name) VALUES(?,?,?,?,?,?)",
                 (username, rating, comment.strip(), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), candidate_id, candidate_name))
    conn.commit()
    conn.close()


def get_feedback_summary(db_path):
    conn = connect(db_path)
    rows = conn.execute("SELECT rating FROM user_feedback").fetchall()
    conn.close()
    ratings = [int(r[0]) for r in rows]
    score = round(sum(ratings) / len(ratings) * 20, 1) if ratings else 0
    return {"responses": len(ratings), "score": score, "target": 85, "met": bool(ratings) and score >= 85, "average_rating": round(sum(ratings)/len(ratings),2) if ratings else 0, "rating_distribution": [{"rating": i, "count": ratings.count(i)} for i in range(1,6)]}


def get_feedback(db_path, limit=20):
    conn = connect(db_path)
    rows = conn.execute("SELECT * FROM user_feedback ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_candidate_status(db_path,candidate_id,status):
    allowed={"New","Shortlisted","Interview","Offered","Hired","Rejected"}
    if status not in allowed:return False
    conn=connect(db_path)
    cur=conn.execute("UPDATE candidates SET status=?,updated_at=? WHERE id=?",
        (status,__import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),candidate_id))
    conn.commit();conn.close();return cur.rowcount>0
