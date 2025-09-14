import os
import json
import uuid
import re
import tempfile
from datetime import datetime
from typing import List, Optional, Dict, Any

# FastAPI & related
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# DB (SQLAlchemy)
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float
from sqlalchemy.orm import sessionmaker, Session, declarative_base

# AI (Gemini) - optional
import google.generativeai as genai

# Speech & audio
import speech_recognition as sr
import pydub
from gtts import gTTS
import shutil

# ------------------------------------------------------------------------
# 1. Configuration
# ------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./excel_interviewer.db")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # optional

# Ensure static directory exists for TTS audio
STATIC_DIR = "static"
TTS_DIR = os.path.join(STATIC_DIR, "tts")
os.makedirs(TTS_DIR, exist_ok=True)

app = FastAPI(title="Conversational Excel Interviewer API (Spoken)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (TTS audio)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ------------------------------------------------------------------------
# 2. Database setup
# ------------------------------------------------------------------------
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ------------------------------------------------------------------------
# 3. Models
# ------------------------------------------------------------------------
class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, nullable=False)
    difficulty = Column(String, nullable=False)
    question_text = Column(Text, nullable=False)
    question_type = Column(String, nullable=False)  # e.g., "conceptual", "formula", "coding", ...
    canonical_answer = Column(Text, nullable=True)
    alternatives = Column(Text, default="[]")  # JSON list
    explanation = Column(Text, nullable=True)
    hints = Column(Text, default="[]")
    tags = Column(String, nullable=True)


class InterviewSession(Base):
    __tablename__ = "interview_sessions"
    id = Column(String, primary_key=True, index=True)
    role_level = Column(String, nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    overall_score = Column(Float, nullable=True)
    status = Column(String, default="in_progress")
    # We'll store any pending followup question text here (if AI asks followup)
    pending_followup = Column(Text, nullable=True)


class Answer(Base):
    __tablename__ = "answers"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, nullable=False)
    question_id = Column(Integer, nullable=True)  # None for followups created on the fly
    user_answer = Column(Text, nullable=False)
    score = Column(Float, nullable=False)
    time_spent = Column(Float, nullable=False)
    feedback = Column(Text, nullable=True)
    is_followup = Column(Integer, default=0)  # 1 if this answer was to a followup


Base.metadata.create_all(bind=engine)

# ------------------------------------------------------------------------
# 4. Pydantic Schemas
# ------------------------------------------------------------------------
class SessionCreate(BaseModel):
    role_level: str = "intermediate"


class AnswerSubmitSchema(BaseModel):
    question_id: Optional[int] = None
    user_answer: Optional[str] = None
    time_spent: float = 0.0
    # formula field not included here because for multipart/form-data we accept 'formula' via Form


# ------------------------------------------------------------------------
# 5. AI / TTS / STT Services
# ------------------------------------------------------------------------
# Gemini setup (optional)
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-1.5-flash-latest")
else:
    gemini_model = None
    print("WARNING: GEMINI_API_KEY not set. Gemini evaluations disabled.")


async def evaluate_answer_with_ai(question: Question, user_answer: str) -> Dict[str, Any]:
    """
    Evaluate free-text answer using Gemini (if available).
    Expected AI JSON: {"score": <0-100>, "feedback": "<...>", "followup": "<optional followup or empty>"}
    """
    if not gemini_model:
        # fallback: simple heuristic
        return {"score": 60, "feedback": "AI evaluator unavailable; basic fallback used.", "followup": ""}

    prompt = f"""
    You are an Excel interviewer. Evaluate the user's answer concisely.

    Question: "{question.question_text}"
    Expected Answer: "{question.canonical_answer or ''}"
    User's Answer: "{user_answer}"

    Provide output STRICTLY as JSON only, with these keys:
    {{
      "score": <int 0-100>,
      "feedback": "<concise constructive feedback>",
      "followup": "<a short clarifying follow-up question for the user if needed, or empty string>"
    }}
    """
    try:
        response = await gemini_model.generate_content_async(prompt)
        cleaned = response.text.strip().replace("```json", "").replace("```", "")
        parsed = json.loads(cleaned)
        # ensure keys exist
        return {
            "score": int(parsed.get("score", 0)),
            "feedback": parsed.get("feedback", ""),
            "followup": parsed.get("followup", "") or ""
        }
    except Exception as e:
        print("Gemini error:", e)
        return {"score": 0, "feedback": "Error evaluating your answer.", "followup": ""}


class FormulaEvaluator:
    @staticmethod
    def normalize(formula: str) -> str:
        if not formula:
            return ""
        return re.sub(r'\s+', '', formula).upper().lstrip('=')

    @staticmethod
    def evaluate(user_formula: str, correct_formula: str, alternatives: List[str]) -> Dict[str, Any]:
        user_norm = FormulaEvaluator.normalize(user_formula)
        if user_norm == FormulaEvaluator.normalize(correct_formula):
            return {"score": 100, "feedback": "Perfect! That's the exact formula.", "followup": ""}
        alt_norms = [FormulaEvaluator.normalize(a) for a in alternatives]
        if user_norm in alt_norms:
            return {"score": 95, "feedback": "Great! That's a valid alternative formula.", "followup": ""}
        return {"score": 20, "feedback": "That formula doesn't seem to be correct.", "followup": ""}


# Speech recognition (transcription)
class FreeSpeechRecognition:
    def __init__(self):
        self.recognizer = sr.Recognizer()

    async def transcribe_audio(self, audio_file_path: str) -> str:
        wav_path = None
        try:
            # pydub handles many formats
            audio = pydub.AudioSegment.from_file(audio_file_path)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as wav_file:
                audio.export(wav_file.name, format="wav")
                wav_path = wav_file.name

            with sr.AudioFile(wav_path) as source:
                audio_data = self.recognizer.record(source)
                # Using Google's free API - has limitations
                text = self.recognizer.recognize_google(audio_data)
                return text
        except sr.UnknownValueError:
            return "Could not understand audio"
        except sr.RequestError as e:
            return f"API unavailable: {e}"
        except Exception as e:
            print("Transcription error:", e)
            return "Failed to transcribe audio."
        finally:
            if wav_path and os.path.exists(wav_path):
                os.unlink(wav_path)


speech_service = FreeSpeechRecognition()


# Text-to-speech (gTTS)
class SpeechSynthesis:
    @staticmethod
    def synthesize_text_to_file(text: str, session_id: str = None) -> str:
        """
        Synthesize text to a TTS file and return a publicly accessible URL path under /static/.
        """
        try:
            filename = f"tts_{session_id or 'anon'}_{uuid.uuid4().hex[:8]}.mp3"
            filepath = os.path.join(TTS_DIR, filename)
            # gTTS will save file
            tts = gTTS(text=text, lang="en")
            tts.save(filepath)
            # return path accessible under /static/
            return f"/static/tts/{filename}"
        except Exception as e:
            print("TTS error:", e)
            return ""


# ------------------------------------------------------------------------
# 6. Helper: get next question, prefer followup
# ------------------------------------------------------------------------
def generate_question_audio_and_payload(db_question: Optional[Question], followup_text: Optional[str], session_id: str):
    """
    Returns a dict to send to the client: question_id (maybe None if followup),
    question_text, question_type, audio_url
    """
    if followup_text:
        audio_url = SpeechSynthesis.synthesize_text_to_file(followup_text, session_id=session_id)
        return {
            "question_id": None,
            "is_followup": True,
            "question_text": followup_text,
            "question_type": "followup",
            "audio_url": audio_url,
            "hints": []
        }
    if db_question:
        audio_url = SpeechSynthesis.synthesize_text_to_file(db_question.question_text, session_id=session_id)
        return {
            "question_id": db_question.id,
            "is_followup": False,
            "question_text": db_question.question_text,
            "question_type": db_question.question_type,
            "audio_url": audio_url,
            "hints": json.loads(db_question.hints or "[]")
        }
    return None


# ------------------------------------------------------------------------
# 7. API Endpoints
# ------------------------------------------------------------------------
@app.post("/api/sessions", status_code=201)
def create_session(session_data: SessionCreate, db: Session = Depends(get_db)):
    session = InterviewSession(id=str(uuid.uuid4()), role_level=session_data.role_level)
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"session_id": session.id}


@app.get("/api/sessions/{session_id}/question")
def get_next_question(session_id: str, db: Session = Depends(get_db)):
    """
    Returns the next question for the session.
    If there's a pending followup in session.pending_followup, return that (spoken).
    Otherwise find the next question matching session.role_level not yet answered.
    """
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    # If there's a followup queued, return it (and don't remove it yet; remove when answered)
    if session.pending_followup:
        payload = generate_question_audio_and_payload(None, session.pending_followup, session_id)
        return payload

    # find answered question IDs
    answered_ids = [q_id for (q_id,) in db.query(Answer.question_id).filter(Answer.session_id == session_id).all() if q_id]
    next_question = db.query(Question).filter(
        Question.difficulty == session.role_level,
        ~Question.id.in_(answered_ids)
    ).first()

    if not next_question:
        raise HTTPException(status_code=404, detail="Interview complete!")

    payload = generate_question_audio_and_payload(next_question, None, session_id)
    return payload


@app.post("/api/sessions/{session_id}/answer")
async def submit_answer(
    session_id: str,
    question_id: Optional[int] = Form(None),
    time_spent: float = Form(0.0),
    # text answer (transcribed or typed) can be provided directly
    text_answer: Optional[str] = Form(None),
    # formula field for formula questions
    formula: Optional[str] = Form(None),
    # or an audio file (multipart)
    audio: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    """
    Accepts either:
     - For formula questions: provide 'question_id' (int) and 'formula' (str) as form fields.
     - For spoken answers: upload 'audio' (file), optionally with 'question_id'.
       If the question is a followup (question_id=None but session.pending_followup present), it uses that followup text.
     - Alternatively: send 'text_answer' (string) directly (useful for debugging or when frontend sends transcription).
    """

    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    # If it's a followup response, question_id will be None and pending_followup has text
    is_followup = 0
    question_obj = None
    followup_text = None
    if question_id:
        question_obj = db.query(Question).filter(Question.id == question_id).first()
        if not question_obj:
            raise HTTPException(status_code=404, detail="Question not found.")
    else:
        # no question_id -> treat as followup if present
        if session.pending_followup:
            is_followup = 1
            followup_text = session.pending_followup
        else:
            raise HTTPException(status_code=400, detail="No question_id provided and no followup pending.")

    # Acquire the user's answer text
    user_answer_text = None
    # For formula-type questions: prefer 'formula' field
    if question_obj and question_obj.question_type == "formula":
        if not formula:
            raise HTTPException(status_code=400, detail="Formula-type question requires 'formula' field.")
        user_answer_text = formula
    else:
        # If text_answer provided directly, use it
        if text_answer:
            user_answer_text = text_answer
        elif audio:
            # Save uploaded audio to temp file and transcribe
            try:
                suffix = os.path.splitext(audio.filename or "")[-1] or ".tmp"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    content = await audio.read()
                    tmp.write(content)
                    tmp_path = tmp.name
                transcription = await speech_service.transcribe_audio(tmp_path)
                user_answer_text = transcription
            finally:
                if 'tmp_path' in locals() and os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        else:
            raise HTTPException(status_code=400, detail="No answer provided; include audio or text_answer (or formula for formula questions).")

    # Evaluate
    if question_obj and question_obj.question_type == "formula":
        alternatives = json.loads(question_obj.alternatives or "[]")
        result = FormulaEvaluator.evaluate(user_answer_text, question_obj.canonical_answer or "", alternatives)
    else:
        # Build a synthetic Question object for followups if needed
        if is_followup:
            # create a temporary simple object to pass the followup prompt context
            temp_q = Question(id=None, question_text=followup_text, canonical_answer=None)
            result = await evaluate_answer_with_ai(temp_q, user_answer_text)
        else:
            result = await evaluate_answer_with_ai(question_obj, user_answer_text)

    # Save the answer record
    db_answer = Answer(
        session_id=session_id,
        question_id=question_id if question_id else None,
        user_answer=user_answer_text,
        score=float(result.get("score", 0)),
        time_spent=float(time_spent),
        feedback=result.get("feedback", ""),
        is_followup=is_followup
    )
    db.add(db_answer)

    # If AI provided followup, queue it in session.pending_followup
    followup_text_from_ai = result.get("followup", "").strip() if isinstance(result.get("followup", ""), str) else ""
    if followup_text_from_ai:
        session.pending_followup = followup_text_from_ai
    else:
        # If this was a followup answer, clear it
        if is_followup:
            session.pending_followup = None

    db.commit()
    db.refresh(db_answer)
    db.refresh(session)

    return {
        "score": result.get("score"),
        "feedback": result.get("feedback"),
        "followup_queued": bool(session.pending_followup),
        "pending_followup_text": session.pending_followup or ""
    }


@app.post("/api/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """
    Upload an audio file and get a transcription (useful for client-side verification).
    """
    try:
        suffix = os.path.splitext(audio.filename or "")[-1] or ".tmp"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await audio.read()
            tmp.write(content)
            tmp_path = tmp.name

        transcription = await speech_service.transcribe_audio(tmp_path)
        return {"transcription": transcription}
    except Exception as e:
        print("Error during transcription:", e)
        raise HTTPException(status_code=500, detail="Transcription failed.")
    finally:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
