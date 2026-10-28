
"""
Optional HuggingFace integration for dynamic skill extraction.

The main application remains fully runnable without downloading an LLM.
If transformers + torch are installed and a compatible local/downloadable
text2text model is available, the extractor can be enabled from the matching
page. Otherwise it automatically falls back to the deterministic skill
vocabulary used by the resume parser.
"""
import re

DEFAULT_SKILLS = [
    "Python","Java","SQL","Machine Learning","TensorFlow","PyTorch",
    "Kubernetes","AWS SageMaker","AWS","Docker","Spring","JavaScript",
    "React","Node.js","Pandas","NumPy","Power BI","Excel","Tableau",
    "Data Analysis","Data Science","Statistics","NLP","Deep Learning",
    "Computer Vision","LLM","Generative AI","Git","GitHub","Linux",
    "REST API","MongoDB","MySQL","PostgreSQL","Flask","Django"
]

def keyword_extract(text, vocabulary=None):
    vocabulary = vocabulary or DEFAULT_SKILLS
    lower = (text or "").lower()
    return sorted(
        {skill for skill in vocabulary if skill.lower() in lower},
        key=str.lower
    )

def extract_skills_with_huggingface(text, model_name="google/flan-t5-small"):
    """
    Returns a list of skills using an optional HuggingFace text2text model.
    This is intentionally optional because the model download can be large.
    """
    try:
        from transformers import pipeline
    except Exception as exc:
        raise RuntimeError(
            "HuggingFace is not installed. Run: pip install -r requirements-llm.txt"
        ) from exc

    generator = pipeline("text2text-generation", model=model_name)
    prompt = (
        "Extract only technical and professional skills from this resume/job text. "
        "Return a comma-separated list and nothing else.\n\n" + text[:8000]
    )
    result = generator(prompt, max_new_tokens=128, do_sample=False)[0]["generated_text"]
    raw = [x.strip() for x in re.split(r",|\n", result) if x.strip()]
    if not raw:
        return keyword_extract(text)
    return sorted(set(raw), key=str.lower)
