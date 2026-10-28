
import re
from typing import Dict, List, Tuple

# Canonical skill aliases make matching more robust than exact case-sensitive matching.
SKILL_ALIASES = {
    "python": "Python",
    "py": "Python",
    "machine learning": "Machine Learning",
    "ml": "Machine Learning",
    "deep learning": "Deep Learning",
    "dl": "Deep Learning",
    "sql": "SQL",
    "mysql": "MySQL",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "scikit-learn": "Scikit-learn",
    "sklearn": "Scikit-learn",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "aws": "AWS",
    "amazon web services": "AWS",
    "aws sagemaker": "AWS SageMaker",
    "sagemaker": "AWS SageMaker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "docker": "Docker",
    "java": "Java",
    "spring": "Spring",
    "spring boot": "Spring",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "react": "React",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "flask": "Flask",
    "django": "Django",
    "html": "HTML",
    "css": "CSS",
    "excel": "Excel",
    "power bi": "Power BI",
    "tableau": "Tableau",
    "data analysis": "Data Analysis",
    "data science": "Data Science",
    "statistics": "Statistics",
    "nlp": "NLP",
    "natural language processing": "NLP",
    "computer vision": "Computer Vision",
    "llm": "LLM",
    "generative ai": "Generative AI",
    "git": "Git",
    "github": "GitHub",
    "rest api": "REST API",
    "mongodb": "MongoDB",
    "linux": "Linux",
    "c++": "C++",
    "c#": "C#",
}

def normalize_skill(skill: str) -> str:
    s = re.sub(r"\s+", " ", str(skill).strip().lower())
    return SKILL_ALIASES.get(s, str(skill).strip())

def normalize_skills(skills: List[str]) -> List[str]:
    return sorted(set(normalize_skill(s) for s in (skills or []) if str(s).strip()), key=str.lower)

def _education_match(candidate_education, required_education) -> float:
    if not required_education:
        return 1.0
    required = str(required_education).lower().strip()
    values = candidate_education if isinstance(candidate_education, list) else [candidate_education]
    text = " ".join(str(x).lower() for x in values if x)
    return 1.0 if required in text or text in required else 0.0

def calculate_match(candidate: Dict, job: Dict) -> Dict:
    candidate_skills = set(normalize_skills(candidate.get("skills", [])))
    required_skills = set(normalize_skills(job.get("required_skills", [])))

    matched = sorted(required_skills & candidate_skills, key=str.lower)
    missing = sorted(required_skills - candidate_skills, key=str.lower)

    skill_score = (len(matched) / len(required_skills)) if required_skills else 1.0

    candidate_exp = float(candidate.get("experience_years", candidate.get("experience", 0)) or 0)
    required_exp = float(job.get("experience_required", 0) or 0)
    exp_score = min(candidate_exp / required_exp, 1.0) if required_exp > 0 else 1.0

    education_score = _education_match(
        candidate.get("education", []),
        job.get("education_required", "")
    )

    # Same weights as the supplied  specification:
    # skills 60%, experience 25%, education 15%.
    hiring_score = round(
        (skill_score * 0.60 + exp_score * 0.25 + education_score * 0.15) * 100,
        2
    )

    return {
        "hiring_score": hiring_score,
        "skill_score": round(skill_score * 100, 2),
        "experience_score": round(exp_score * 100, 2),
        "education_score": round(education_score * 100, 2),
        "matched_skills": matched,
        "missing_skills": missing,
        "match_ratio": round(skill_score * 100, 2),
        "recommendations": [f"Consider training in {skill}" for skill in missing],
    }

def rank_candidates(candidates: List[Dict], job: Dict) -> List[Dict]:
    rows = []
    for candidate in candidates:
        result = calculate_match(candidate, job)
        rows.append({
            "Candidate": candidate.get("name") or "Unknown candidate",
            "Job Title": job.get("title", "Untitled job"),
            "Hiring Score (%)": result["hiring_score"],
            "Skill Score (%)": result["skill_score"],
            "Experience Score (%)": result["experience_score"],
            "Education Score (%)": result["education_score"],
            "Matched Skills": ", ".join(result["matched_skills"]),
            "Missing Skills": ", ".join(result["missing_skills"]),
            "Recommendations": "; ".join(result["recommendations"]),
        })
    return sorted(rows, key=lambda x: x["Hiring Score (%)"], reverse=True)

def build_matching_matrix(candidates: List[Dict], jobs: List[Dict]):
    rows = []
    for job in jobs:
        rows.extend(rank_candidates(candidates, job))
    return rows
