"""Voice screening utilities required for the recruitment workflow.
SpeechRecognition converts recorded WAV audio to text; pyttsx3 provides optional spoken prompts.
"""
from pathlib import Path
import tempfile


def recognize_wav_bytes(wav_bytes: bytes, language="en-US"):
    import speech_recognition as sr
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(wav_bytes)
        path = f.name
    try:
        r = sr.Recognizer()
        with sr.AudioFile(path) as source:
            audio = r.record(source)
        try:
            text = r.recognize_google(audio, language=language)
            return {"text": text, "provider": "Google Speech Recognition", "error": None}
        except sr.UnknownValueError:
            return {"text": "", "provider": "Google Speech Recognition", "error": "Speech could not be understood."}
        except sr.RequestError as e:
            return {"text": "", "provider": "Google Speech Recognition", "error": f"Recognition service unavailable: {e}"}
    finally:
        Path(path).unlink(missing_ok=True)


def communication_score(text: str):
    words = [w for w in text.split() if w.strip()]
    if not words:
        return 0
    sentences = max(1, sum(text.count(p) for p in ".!?"))
    avg_sentence = len(words) / sentences
    length_score = min(45, len(words) * 1.5)
    structure_score = 25 if 8 <= avg_sentence <= 28 else 15
    vocabulary_score = min(30, len(set(w.lower() for w in words)) / len(words) * 40)
    return round(min(100, length_score + structure_score + vocabulary_score), 1)


def speak_prompt(text: str):
    """Speak a prompt when pyttsx3 is available; returns False instead of breaking the app."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
        return True
    except Exception:
        return False
