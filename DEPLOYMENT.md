# Deployment and Quality Guide

## Flask
python -m venv venv
venv\\Scripts\\activate  # Windows
pip install -r requirements.txt
python app.py

Health check: http://127.0.0.1:5000/health

## Streamlit
streamlit run streamlit_app.py

## Tests
pytest -q tests

## Docker
docker build -t recruitment-copilot .
docker run -p 5000:5000 recruitment-copilot

## Voice
The web interface uses browser SpeechRecognition. The Streamlit console accepts WAV audio and sends it through SpeechRecognition. pyttsx3 is available for spoken interviewer prompts and is intentionally optional so unsupported audio drivers do not crash the application.

## Satisfaction
The web application collects 1–5 ratings and calculates score = average rating / 5 × 100. The acceptance target is ≥85%. No score is fabricated; the dashboard shows "Not measured" until feedback exists.


## Render deployment
This project includes `render.yaml` for a Render Blueprint deployment. If configuring a Web Service manually, set:
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT`

The `gunicorn` dependency is included in `requirements.txt`. Do not use Flask's development server for the hosted service.
