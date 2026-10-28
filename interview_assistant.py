
import json, sqlite3
from datetime import datetime

ROLE_BANK = {
"Senior ML Engineer": ["machine learning system design","model optimization","production deployment","model monitoring","MLOps","deep learning","inference scaling"],
"Data Scientist": ["feature engineering","model evaluation","imbalanced data","A/B testing","statistics","experimentation","business impact"],
"Data Analyst": ["SQL","data cleaning","KPI analysis","dashboard design","Excel","Power BI","statistics","root-cause analysis"],
"Software Engineer": ["REST APIs","system design","debugging","testing","authentication","database design","performance","CI/CD"],
"Python Developer": ["Python","Flask","OOP","exception handling","testing","performance","APIs","data pipelines"],
"AI Engineer": ["LLM evaluation","RAG","prompt engineering","hallucination reduction","embeddings","vector databases","AI monitoring","agents"],
"Frontend Developer": ["React","JavaScript","state management","responsive design","accessibility","performance","API integration","testing"],
"Backend Developer": ["API architecture","database transactions","authentication","caching","security","scalability","logging","testing"],
"Cloud Engineer": ["AWS","Docker","Kubernetes","CI/CD","IAM","observability","autoscaling","cost optimization"],
"DevOps Engineer": ["CI/CD","Docker","Kubernetes","Linux","monitoring","deployment strategies","infrastructure as code","incident response"],
"Data Engineer": ["ETL","SQL optimization","data modeling","Spark","Airflow","data quality","stream processing","warehousing"],
"Cybersecurity Analyst": ["threat detection","SIEM","incident response","vulnerability management","authentication","security logs","phishing","risk assessment"],
"Product Manager": ["product metrics","roadmaps","experimentation","user research","prioritization","product strategy","analytics","release planning"],
"UI/UX Designer": ["user research","wireframing","prototyping","usability testing","design systems","accessibility","interaction design","Figma"]
}
BEHAVIORAL = ["Tell me about a time you handled {topic}. What was the situation, action and result?",
"How would you handle {topic} when priorities change?",
"Describe a challenging {topic} situation and what you learned.",
"Give an example of how you communicated {topic} to a stakeholder.",
"How do you make decisions when dealing with {topic} and incomplete information?"]
TECHNICAL = ["For {role}, explain how you would solve a real-world problem involving {topic}.",
"How would you design, implement and validate a solution for {topic}?",
"Suppose a production system has a problem involving {topic}. Walk through your debugging process.",
"What trade-offs should an engineer consider when working with {topic}?",
"How would you improve an existing solution involving {topic}? Give a practical example."]

def available_roles(): return list(ROLE_BANK)

def build_interview_questions(job_role, question_type="technical", num_questions=10):
    """Build a deterministic, role-relevant set of distinct questions (up to 1,000)."""
    try:
        n = max(1, min(int(num_questions), 1000))
    except (TypeError, ValueError):
        n = 10

    role = job_role if job_role in ROLE_BANK else available_roles()[0]
    topics = ROLE_BANK[role]
    qtype = (question_type or "technical").lower()
    if qtype not in {"technical", "behavioral", "mixed"}:
        qtype = "technical"

    technical_prompts = [
        "For {role}, explain a practical solution to a real-world problem involving {topic}.",
        "How would you design, implement, and validate a solution involving {topic} for a {role} team?",
        "A production system has an issue related to {topic}. Describe your investigation and debugging steps.",
        "What trade-offs would you evaluate when choosing an approach to {topic}?",
        "How would you improve an existing {topic} workflow, and which metrics would prove the improvement?",
        "Describe the architecture you would choose for a {topic} task, including reliability and security concerns.",
        "How would you test edge cases and failure modes in a solution involving {topic}?",
        "Explain how you would communicate a technical decision about {topic} to a non-technical stakeholder.",
        "What common mistakes do teams make with {topic}, and how would you prevent them?",
        "You have limited time and resources for a {topic} task. How would you prioritize the work?",
    ]
    behavioral_prompts = [
        "Tell me about a time you handled {topic}. What was the situation, action, and result?",
        "Describe a challenging situation involving {topic} and what you learned from it.",
        "How would you handle competing priorities related to {topic} when a deadline changes?",
        "Give an example of explaining {topic} to a stakeholder with a different background.",
        "Describe a decision you made with incomplete information about {topic}. What happened?",
        "Tell me about feedback you received while working on {topic} and how you used it.",
        "Describe a disagreement with a teammate about {topic} and how you resolved it.",
        "What would you do if a project involving {topic} fell behind schedule?",
        "Give an example of taking ownership of a problem related to {topic}.",
        "How have you helped a team improve its process for {topic}?",
    ]
    # Distinct scenario prompts extend the bank without simply repeating the same question.
    scenarios = [
        "Consider a small startup with a limited budget.",
        "Consider a large organization with strict compliance requirements.",
        "Assume the system serves millions of users.",
        "Assume the available data is incomplete or noisy.",
        "Assume the first implementation failed in production.",
        "Assume a stakeholder requests a delivery date that seems unrealistic.",
        "Assume the team must support a legacy system.",
        "Assume performance has degraded after a recent release.",
        "Assume you must explain the decision during a design review.",
        "Assume the solution must be accessible and inclusive.",
        "Assume the requirements change halfway through the project.",
        "Assume the team is distributed across several time zones.",
        "Assume there is a strict privacy constraint.",
        "Assume the first approach increases costs unexpectedly.",
        "Assume a new team member must maintain your solution.",
        "Assume monitoring reveals an issue only under peak load.",
        "Assume you have one day to prepare a safe workaround.",
        "Assume the results conflict with the team's initial hypothesis.",
        "Assume the client cannot clearly define success criteria.",
        "Assume you need to compare two competing approaches.",
    ]

    questions = []
    seen = set()
    for i in range(n):
        if qtype == "mixed":
            kind = "technical" if i % 2 == 0 else "behavioral"
        else:
            kind = qtype
        topic_index = i % len(topics)
        topic = topics[topic_index]
        bank = technical_prompts if kind == "technical" else behavioral_prompts
        prompt_index = (i // len(topics)) % len(bank)
        q = bank[prompt_index].format(role=role, topic=topic)
        cycle = i // (len(topics) * len(bank))
        if cycle:
            scenario = scenarios[(cycle - 1) % len(scenarios)]
            q = f"{q} {scenario}"
            if cycle > len(scenarios):
                q += f" In this interview, focus on approach {cycle + 1} and explain the trade-offs."
        # Guard against accidental duplicates while keeping wording meaningful.
        if q in seen:
            q = f"{q} Explain your reasoning step by step, including a measurable success criterion for case {i + 1}."
        seen.add(q)
        questions.append(q)
    return questions

def init_ats_tables(db_path):
    conn=sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE IF NOT EXISTS ats_candidates(
        id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,email TEXT NOT NULL UNIQUE,
        job_applied TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'Interview Scheduled',created_at TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS interview_sessions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,candidate_name TEXT NOT NULL,candidate_email TEXT,
        job_role TEXT NOT NULL,questions TEXT NOT NULL,responses TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Active Session',created_at TEXT NOT NULL,completed_at TEXT)""")
    conn.commit();conn.close()

def add_ats_candidate(db_path,name,email,job_applied,status="Interview Scheduled"):
    conn=sqlite3.connect(db_path);now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("""INSERT INTO ats_candidates(name,email,job_applied,status,created_at) VALUES(?,?,?,?,?)
    ON CONFLICT(email) DO UPDATE SET name=excluded.name,job_applied=excluded.job_applied,status=excluded.status""",
    (name,email,job_applied,status,now));conn.commit()
    row=conn.execute("SELECT * FROM ats_candidates WHERE email=?",(email,)).fetchone();conn.close()
    return dict(zip(["id","name","email","job_applied","status","created_at"],row))

def list_ats_candidates(db_path):
    conn=sqlite3.connect(db_path);rows=conn.execute("SELECT * FROM ats_candidates ORDER BY id DESC").fetchall();conn.close()
    return [dict(zip(["id","name","email","job_applied","status","created_at"],r)) for r in rows]

def update_ats_status(db_path,email,status):
    conn=sqlite3.connect(db_path);cur=conn.execute("UPDATE ats_candidates SET status=? WHERE email=?",(status,email));conn.commit();conn.close();return cur.rowcount>0

def create_interview_session(db_path,name,email,role,questions):
    conn=sqlite3.connect(db_path);now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur=conn.execute("INSERT INTO interview_sessions(candidate_name,candidate_email,job_role,questions,responses,status,created_at) VALUES(?,?,?,?,?,?,?)",
    (name,email,role,json.dumps(questions),json.dumps([]),"Active Session",now));conn.commit();sid=cur.lastrowid;conn.close();return sid

def get_interview_session(db_path,sid):
    conn=sqlite3.connect(db_path);row=conn.execute("SELECT * FROM interview_sessions WHERE id=?",(sid,)).fetchone();conn.close()
    if not row:return None
    cols=["id","candidate_name","candidate_email","job_role","questions","responses","status","created_at","completed_at"]
    d=dict(zip(cols,row));d["questions"]=json.loads(d["questions"] or "[]");d["responses"]=json.loads(d["responses"] or "[]");return d

def add_response(db_path,sid,question,response):
    s=get_interview_session(db_path,sid)
    if not s:return None
    a=s["responses"];a.append({"question":question,"response":response,"time":datetime.now().strftime("%H:%M:%S")})
    conn=sqlite3.connect(db_path);conn.execute("UPDATE interview_sessions SET responses=? WHERE id=?",(json.dumps(a),sid));conn.commit();conn.close();return a

def complete_interview(db_path,sid):
    conn=sqlite3.connect(db_path);conn.execute("UPDATE interview_sessions SET status='Interview Completed',completed_at=? WHERE id=?",(datetime.now().strftime("%Y-%m-%d %H:%M:%S"),sid));conn.commit();conn.close()
