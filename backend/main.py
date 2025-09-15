# main.py
import os
import json
import uuid
import tempfile
import traceback
import logging
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
load_dotenv(dot_env_path="./.env")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI & related
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Database (SQLAlchemy)
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float
from sqlalchemy.orm import sessionmaker, Session, declarative_base

# External AI / speech / TTS
import google.generativeai as genai
import speech_recognition as sr
import pydub
from gtts import gTTS

# PDF generation
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT

# ------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./excel_interviewer.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
if "railway.internal" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("railway.internal", "localhost")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MAX_QUESTIONS = int(os.getenv("MAX_QUESTIONS", "10"))
MAX_FOLLOWUPS = int(os.getenv("MAX_FOLLOWUPS", "1"))

STATIC_DIR = "static"
TTS_DIR = os.path.join(STATIC_DIR, "tts")
REPORTS_DIR = os.path.join(STATIC_DIR, "reports")
os.makedirs(TTS_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Excel Interview Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ------------------------------------------------------------------------
# Database Setup
# ------------------------------------------------------------------------
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ------------------------------------------------------------------------
# Gemini AI Setup (optional)
# ------------------------------------------------------------------------
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-1.5-flash-latest")
else:
    gemini_model = None
    print("WARNING: GEMINI_API_KEY not set. Using fallback analysis/summaries.")

# ------------------------------------------------------------------------
# Models & Schemas
# ------------------------------------------------------------------------
class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, nullable=False)
    difficulty = Column(String, nullable=False)
    question_text = Column(Text, nullable=False)
    question_type = Column(String, nullable=False)
    canonical_answer = Column(Text, nullable=True)
    alternatives = Column(Text, default="[]")
    explanation = Column(Text, nullable=True)
    tags = Column(String, nullable=True)

class InterviewSession(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True, index=True)
    candidate_name = Column(String, nullable=False)
    candidate_email = Column(String, nullable=False)
    candidate_phone = Column(String, nullable=True)
    college_name = Column(String, nullable=True)
    roll_number = Column(String, nullable=True)
    role_level = Column(String, default="intermediate")
    status = Column(String, default="in_progress")
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    overall_score = Column(Float, nullable=True)
    pending_followup = Column(Text, nullable=True)

class Answer(Base):
    __tablename__ = "answers"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, nullable=False)
    question_id = Column(Integer, nullable=True)
    user_answer = Column(Text, nullable=True)
    score = Column(Float, nullable=True)
    time_spent = Column(Float, nullable=True)
    feedback = Column(Text, nullable=True)
    is_followup = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# ------------------------------------------------------------------------
# Request Schemas
# ------------------------------------------------------------------------
class SessionCreate(BaseModel):
    candidate_name: str
    candidate_email: str
    candidate_phone: Optional[str] = None
    college_name: Optional[str] = None
    roll_number: Optional[str] = None
    role_level: str = "intermediate"

# ------------------------------------------------------------------------
# Speech Service (using speech_recognition)
# ------------------------------------------------------------------------
class SpeechService:
    def __init__(self):
        self.recognizer = sr.Recognizer()

    async def transcribe_audio(self, audio_path: str) -> str:
        try:
            with sr.AudioFile(audio_path) as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.2)
                audio_data = self.recognizer.record(source)
                text = self.recognizer.recognize_google(audio_data)
                return text.strip()
        except sr.UnknownValueError:
            return "I'm sorry, I couldn't understand that."
        except Exception as e:
            print("SpeechService error:", e)
            return "There was an issue processing your audio."

speech_service = SpeechService()

# ------------------------------------------------------------------------
# AI evaluation helper (single question evaluation)
# ------------------------------------------------------------------------
async def evaluate_answer_with_ai(question_text: str, answer_text: str, candidate_name: str) -> Dict[str, Any]:
    prompt = f"""
You are Sarah, a friendly professional Excel interviewer speaking with {candidate_name}.
Question asked: "{question_text}"
Candidate's Answer: "{answer_text}"

As Sarah, do the following:
1) Provide a short conversational acknowledgment.
2) Give a numeric score between 0 and 100 (integer).
3) Provide concise feedback highlighting strengths and weaknesses in one sentence.
4) If the answer is strong, provide a single natural follow-up question (or empty string).
Respond ONLY with valid JSON:

{{
  "score": <number>,
  "feedback": "<short feedback>",
  "followup": "<follow-up or empty>"
}}
"""
    if not gemini_model:
        return {"score": 65, "feedback": f"Thanks {candidate_name}, noted.", "followup": ""}
    try:
        resp = await gemini_model.generate_content_async(prompt)
        text = resp.text.strip().replace("```json", "").replace("```", "")
        parsed = json.loads(text)
        return {"score": int(parsed.get("score", 0)), "feedback": parsed.get("feedback", "") or "", "followup": parsed.get("followup", "") or ""}
    except Exception as e:
        print("AI evaluation error:", e)
        return {"score": 65, "feedback": f"Thanks {candidate_name}, noted.", "followup": ""}

# ------------------------------------------------------------------------
# Analysis: use Gemini to analyze all answers and return structured metrics
# ------------------------------------------------------------------------
async def generate_analysis_with_gemini(answers: List[Dict[str, Any]], overall_score: float, candidate_name: str) -> Dict[str, Any]:
    """
    Calls Gemini with a prompt that returns JSON with:
    - communication_score (0-100)
    - presentation_score (0-100)
    - clarity_score (0-100)
    - confidence_score (0-100)
    - problem_solving_score (0-100)
    - overall_score (0-100)
    - summary (short text)
    - suggestions (array of 2 short strings)
    """
    prompt = {
        "instructions": f"You are an expert interview evaluator. Given candidate '{candidate_name}' answers below, produce a JSON object with numeric scores (0-100) for communication, presentation, clarity, confidence, problem_solving and a short 2-3 sentence summary and two improvement suggestions. Return only JSON with these keys: communication_score, presentation_score, clarity_score, confidence_score, problem_solving_score, overall_score, summary, suggestions (array of two short strings).",
        "answers": answers,
        "overall_score": overall_score
    }

    text_prompt = f"""
You are an expert interview evaluator.

Candidate: {candidate_name}

The "answers" field below contains raw speech-to-text transcripts from an interview. These transcripts may include spelling mistakes, repeated words, filler ("um", "uh"), partial words, or other transcription artifacts. When you analyze them you should:

- Automatically correct obvious spelling mistakes and minor transcription errors before evaluating (do not invent new content).
- Normalize filler words and repeated fragments (treat "um", "uh", "you know", repeated words, and trailing partial words as noise).
- If an answer is ambiguous because of transcription errors, infer the most likely intended meaning in a conservative way; reflect any important assumptions in the summary (the summary may note that the model made small assumptions).
- Be robust: evaluate intent, clarity, and knowledge even when the wording is imperfect.

Answers JSON:
{json.dumps(answers, indent=2)}

Current overall_score: {overall_score}

Produce ONLY a JSON object with the following keys (no extra keys, no commentary):

- communication_score (number 0-100)
- presentation_score (number 0-100)
- clarity_score (number 0-100)
- confidence_score (number 0-100)
- problem_solving_score (number 0-100)
- overall_score (number 0-100)   # you may adjust this slightly if your analysis warrants it
- summary (string, 1-3 sentences). In the summary, briefly mention if you corrected obvious transcription errors or made assumptions.
- suggestions (array of exactly 2 short strings)

Return only the JSON object and nothing else.
"""

    if not gemini_model:
        return {
            "communication_score": round(overall_score * 0.9, 1),
            "presentation_score": round(overall_score * 0.85, 1),
            "clarity_score": round(overall_score * 0.9, 1),
            "confidence_score": round(overall_score * 0.8, 1),
            "problem_solving_score": round(overall_score, 1),
            "overall_score": round(overall_score, 1),
            "summary": "Overall solid performance. Focus on structuring responses and practicing clarity.",
            "suggestions": ["Structure answers with 3 steps (what/why/how).", "Practice concise explanations out loud."]
        }

    try:
        resp = await gemini_model.generate_content_async(text_prompt)
        text = resp.text.strip().replace("```json", "").replace("```", "")
        parsed = json.loads(text)
        # sanitize/limit values
        numeric_keys = ["communication_score", "presentation_score", "clarity_score", "confidence_score", "problem_solving_score", "overall_score"]
        for k in numeric_keys:
            if k in parsed:
                try:
                    parsed[k] = round(float(parsed[k]), 1)
                except:
                    parsed[k] = 0.0
            else:
                parsed[k] = 0.0
        if "suggestions" not in parsed:
            parsed["suggestions"] = []
        if "summary" not in parsed:
            parsed["summary"] = ""
        return parsed
    except Exception as e:
        print("generate_analysis_with_gemini error:", e)
        return {
            "communication_score": round(overall_score * 0.9, 1),
            "presentation_score": round(overall_score * 0.85, 1),
            "clarity_score": round(overall_score * 0.9, 1),
            "confidence_score": round(overall_score * 0.8, 1),
            "problem_solving_score": round(overall_score, 1),
            "overall_score": round(overall_score, 1),
            "summary": "Overall solid performance. Focus on structuring responses and practicing clarity.",
            "suggestions": ["Structure answers with 3 steps (what/why/how).", "Practice concise explanations out loud."]
        }

# ------------------------------------------------------------------------
# Helpers (TTS, DB helpers, PDF)
# ------------------------------------------------------------------------
def text_to_speech_file(text: str, session_id: str) -> str:
    try:
        filename = f"tts_{session_id}_{uuid.uuid4().hex[:6]}.mp3"
        filepath = os.path.join(TTS_DIR, filename)
        tts = gTTS(text=text, lang="en", slow=False)
        tts.save(filepath)
        return f"/static/tts/{filename}"
    except Exception as e:
        print("TTS error:", e)
        return ""

def get_interview_question(session: InterviewSession, db: Session) -> Optional[Question]:
    answered_ids = [
        q_id for (q_id,) in db.query(Answer.question_id)
        .filter(Answer.session_id == session.id, Answer.question_id.isnot(None))
    ]
    return db.query(Question).filter(
        Question.difficulty == session.role_level,
        ~Question.id.in_(answered_ids)
    ).first()

def count_main_answers(session_id: str, db: Session) -> int:
    return db.query(Answer).filter(Answer.session_id == session_id, Answer.is_followup == 0).count()

def count_followup_answers(session_id: str, db: Session) -> int:
    return db.query(Answer).filter(Answer.session_id == session_id, Answer.is_followup == 1).count()

def create_pdf_report(result: dict, session_id: str) -> Optional[str]:
    filename = f"report_{session_id}.pdf"
    filepath = os.path.join(REPORTS_DIR, filename)
    try:
        doc = SimpleDocTemplate(filepath, pagesize=letter, rightMargin=36,leftMargin=36, topMargin=36,bottomMargin=36)
        styles = getSampleStyleSheet()
        # small paragraph style for table cells
        styles.add(ParagraphStyle(name="TableCell", parent=styles["BodyText"], fontSize=8, leading=10))
        styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], fontSize=20, leading=22))
        styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=9))

        story = []

        # Header
        story.append(Paragraph(f"Interview Report — {result.get('candidate_name','')}", styles['ReportTitle']))
        story.append(Spacer(1, 8))

        # Meta info
        candidate = result.get("candidate_name","")
        email = result.get("candidate_email","")
        started_at = result.get("started_at","")
        completed_at = result.get("completed_at","")
        overall_score = result.get("overall_score","")

        total_time_minutes = result.get("total_time_minutes")
        if total_time_minutes is None:
            try:
                total_time_minutes = round(sum(a.get("time_spent") or 0 for a in result.get("answers", [])) / 60.0, 1)
            except:
                total_time_minutes = 0.0

        meta_table_data = [
            ["Candidate:", candidate, "Overall Score:", str(overall_score)],
            ["Email:", email, "Total Time (min):", f"{total_time_minutes:.1f}"],
            ["Started At:", started_at or "-", "Completed At:", completed_at or "-"],
        ]
        meta_table = Table(meta_table_data, colWidths=[70, 220, 90, 120])
        meta_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), colors.whitesmoke),
            ("BOX", (0,0), (-1,-1), 0.5, colors.gray),
            ("INNERGRID", (0,0), (-1,-1), 0.25, colors.lightgrey),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("LEFTPADDING", (0,0), (-1,-1), 6),
            ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 10))

        # Metrics block
        metrics_keys = [
            ("Communication", result.get("communication_score")),
            ("Presentation", result.get("presentation_score")),
            ("Clarity", result.get("clarity_score")),
            ("Confidence", result.get("confidence_score")),
            ("Problem Solving", result.get("problem_solving_score")),
        ]
        metrics_rows = [[k for k,_ in metrics_keys], [str(v) if v is not None else "-" for _,v in metrics_keys]]
        metrics_tbl = Table(metrics_rows, colWidths=[100]*len(metrics_keys))
        metrics_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#f0f4ff")),
            ("INNERGRID", (0,0), (-1,-1), 0.25, colors.grey),
            ("BOX", (0,0), (-1,-1), 0.25, colors.grey),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ]))
        story.append(Paragraph("Detailed Metrics", styles['Heading2']))
        story.append(metrics_tbl)
        story.append(Spacer(1, 10))

        # Summary & Suggestions
        story.append(Paragraph("Summary", styles['Heading2']))
        story.append(Paragraph(result.get("summary",""), styles['Small']))
        story.append(Spacer(1, 8))
        story.append(Paragraph("Improvement Suggestions", styles['Heading2']))
        for s in result.get("suggestions", [])[:2]:
            story.append(Paragraph(f"• {s}", styles['Small']))
        story.append(Spacer(1, 12))

        # Answers table with wrapped paragraphs
        story.append(Paragraph("Answers", styles['Heading2']))
        col_widths = [40, 260, 50, 60, 120]  # QID, Answer, Score, Followup, Feedback
        header = ["QID", "Answer (truncated)", "Score", "Followup", "Feedback (truncated)"]
        table_data = [header]
        for a in result.get("answers", []):
            qid = a.get("question_id") if a.get("question_id") is not None else "None"
            ans_text = (a.get("user_answer") or "")
            feedback = (a.get("feedback") or "")
            score = a.get("score") if a.get("score") is not None else "-"
            is_followup = "Yes" if a.get("is_followup") else "No"
            ans_para = Paragraph(ans_text.replace("\n","<br/>")[:800], styles["TableCell"])
            fb_para = Paragraph(feedback.replace("\n","<br/>")[:800], styles["TableCell"])
            table_data.append([str(qid), ans_para, str(score), is_followup, fb_para])
        answers_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        answers_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#e6e6e6")),
            ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(answers_table)
        story.append(Spacer(1, 12))

        # Footer note
        gen_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        story.append(Paragraph(f"Generated: {gen_time}", styles['Small']))

        doc.build(story)
        return f"/static/reports/{filename}"
    except Exception as e:
        print("create_pdf_report error:", e)
        traceback.print_exc()
        return None


# ------------------------------------------------------------------------
# API Endpoints
# ------------------------------------------------------------------------
@app.post("/api/sessions", status_code=201)
def create_session(session_data: SessionCreate, db: Session = Depends(get_db)):
    session = InterviewSession(id=str(uuid.uuid4()), **session_data.dict())
    session.pending_followup = (
        f"Hi {session.candidate_name}, welcome to your interview! "
        "Before we dive into Excel, could you please introduce yourself?"
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    print(f"[create_session] created session_id={session.id}")
    return {"session_id": session.id}

@app.get("/api/sessions/{session_id}/question")
def get_question_endpoint(session_id: str, db: Session = Depends(get_db)):
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # if completed already -> respond done
    if session.status == "completed":
        closing_text = f"Thank you {session.candidate_name}! You've completed the interview."
        return {"question_id": None, "is_complete": True, "question_text": closing_text, "audio_url": text_to_speech_file(closing_text, session_id)}

    main_count = count_main_answers(session.id, db)
    if main_count >= MAX_QUESTIONS:
        # finalize
        session.status = "completed"
        session.completed_at = datetime.utcnow()
        session.pending_followup = None
        db.commit()
        closing_text = f"Thank you {session.candidate_name}! You've completed the interview (max questions reached)."
        return {"question_id": None, "is_complete": True, "question_text": closing_text, "audio_url": text_to_speech_file(closing_text, session_id)}

    # pending followup first
    if session.pending_followup:
        has_answers = db.query(Answer).filter(Answer.session_id == session.id).first() is not None
        is_intro = (not has_answers) and session.status == "in_progress"
        return {"question_id": None, "is_followup": True, "question_text": session.pending_followup, "audio_url": text_to_speech_file(session.pending_followup, session_id)}

    # next DB question
    next_question = get_interview_question(session, db)
    if next_question:
        return {"question_id": next_question.id, "is_followup": False, "question_text": next_question.question_text, "audio_url": text_to_speech_file(next_question.question_text, session_id)}

    # no more questions -> finalize
    session.status = "completed"
    session.completed_at = datetime.utcnow()
    db.commit()
    closing_text = f"Thank you {session.candidate_name}! You've completed all the questions. You'll see the results now."
    return {"question_id": None, "is_complete": True, "question_text": closing_text, "audio_url": text_to_speech_file(closing_text, session_id)}

@app.post("/api/sessions/{session_id}/answer")
async def submit_answer(
    session_id: str,
    question_id: Optional[int] = Form(None),
    time_spent: float = Form(0.0),
    text_answer: Optional[str] = Form(None),
    audio: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    try:
        session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if session.status == "completed":
            raise HTTPException(status_code=400, detail="Session already completed")

        is_followup = 0
        question_text = ""

        if question_id is None:
            if session.pending_followup:
                is_followup = 1
                question_text = session.pending_followup
            else:
                next_q = get_interview_question(session, db)
                if not next_q:
                    raise HTTPException(status_code=400, detail="No question_id provided and no available question.")
                question_id = next_q.id
                question_text = next_q.question_text
        else:
            qobj = db.query(Question).filter(Question.id == question_id).first()
            if not qobj:
                raise HTTPException(status_code=404, detail="Question not found")
            question_text = qobj.question_text

        # obtain user answer text
        user_answer_text = None
        if text_answer:
            user_answer_text = text_answer
        elif audio:
            tmp_path = None
            wav_path = None
            try:
                suffix = os.path.splitext(audio.filename or "")[-1] or ".webm"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    content = await audio.read()
                    tmp.write(content)
                    tmp_path = tmp.name
                try:
                    audio_seg = pydub.AudioSegment.from_file(tmp_path)
                    wav_path = tmp_path + ".wav"
                    audio_seg.export(wav_path, format="wav")
                    user_answer_text = await speech_service.transcribe_audio(wav_path)
                except Exception as e:
                    print("pydub conversion/transcription failed:", e)
                    user_answer_text = await speech_service.transcribe_audio(tmp_path)
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except:
                        pass
                if wav_path and os.path.exists(wav_path):
                    try:
                        os.remove(wav_path)
                    except:
                        pass
        else:
            raise HTTPException(status_code=400, detail="No answer provided")

        # Evaluate via Gemini (or fallback)
        evaluation = await evaluate_answer_with_ai(question_text, user_answer_text, session.candidate_name)

        db_answer = Answer(
            session_id=session_id,
            question_id=question_id,
            user_answer=user_answer_text,
            score=float(evaluation.get("score", 0)),
            time_spent=float(time_spent),
            feedback=evaluation.get("feedback", ""),
            is_followup=is_followup,
        )
        db.add(db_answer)

        # followup management: only allow at most MAX_FOLLOWUPS
        followup_text = (evaluation.get("followup") or "").strip()
        existing_followups = count_followup_answers(session_id, db)
        if followup_text and existing_followups < MAX_FOLLOWUPS:
            session.pending_followup = followup_text
        else:
            session.pending_followup = None

        db.commit()
        db.refresh(session)

        # if reached max questions -> finalize
        main_count = count_main_answers(session_id, db)
        if main_count >= MAX_QUESTIONS:
            session.status = "completed"
            session.completed_at = datetime.utcnow()
            session.pending_followup = None
            db.commit()
            return {"score": evaluation.get("score"), "feedback": evaluation.get("feedback"), "user_transcript": user_answer_text, "next_step": None, "is_complete": True, "message": "Max questions reached; interview completed."}

        return {"score": evaluation.get("score"), "feedback": evaluation.get("feedback"), "user_transcript": user_answer_text, "next_step": session.pending_followup, "is_complete": False}

    except HTTPException:
        raise
    except Exception as e:
        print("[submit_answer] unexpected error:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/sessions/{session_id}/report")
async def get_session_report(session_id: str, db: Session = Depends(get_db)):
    """
    Build a detailed report using Gemini for analysis (structured JSON),
    save a PDF under static/reports and return the report JSON (and pdf url).
    """
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    answers_objs = db.query(Answer).filter(Answer.session_id == session_id).all()
    if not answers_objs:
        raise HTTPException(status_code=404, detail="No answers found for session")

    answers = []
    for a in answers_objs:
        answers.append({
            "question_id": a.question_id,
            "user_answer": a.user_answer,
            "score": a.score,
            "feedback": a.feedback,
            "time_spent": a.time_spent,
            "is_followup": bool(a.is_followup),
        })

    total_score = sum((a["score"] or 0) for a in answers)
    average_score = total_score / len(answers) if answers else 0.0
    total_time = sum((a["time_spent"] or 0) for a in answers)

    # update session fields
    session.overall_score = average_score
    session.completed_at = session.completed_at or datetime.utcnow()
    session.status = "completed"
    db.commit()

    try:
        analysis = await generate_analysis_with_gemini(answers, average_score, session.candidate_name)
    except Exception as e:
        print("Analysis generation failed:", e)
        analysis = {
            "communication_score": round(average_score * 0.9, 1),
            "presentation_score": round(average_score * 0.85, 1),
            "clarity_score": round(average_score * 0.9, 1),
            "confidence_score": round(average_score * 0.8, 1),
            "problem_solving_score": round(average_score, 1),
            "overall_score": round(average_score, 1),
            "summary": "Overall solid performance. Focus on structuring responses and practicing clarity.",
            "suggestions": ["Structure answers with 3 steps (what/why/how).", "Practice concise explanations out loud."]
        }

    # Build result object
    result = {
        "session_id": session_id,
        "candidate_name": session.candidate_name,
        "candidate_email": session.candidate_email,
        "college_name": session.college_name,
        "roll_number": session.roll_number,
        "skill_level": session.role_level,
        "started_at": session.started_at.isoformat(),
        "completed_at": session.completed_at.isoformat(),
        "overall_score": round(average_score, 1),
        "total_questions": len(answers),
        "total_time_minutes": round(total_time / 60, 1),
        "answers": answers,
        "communication_score": analysis.get("communication_score"),
        "presentation_score": analysis.get("presentation_score"),
        "clarity_score": analysis.get("clarity_score"),
        "confidence_score": analysis.get("confidence_score"),
        "problem_solving_score": analysis.get("problem_solving_score"),
        "summary": analysis.get("summary"),
        "suggestions": analysis.get("suggestions", []),
    }

    # Create PDF report and return URL
    pdf_url = create_pdf_report(result, session_id)
    result["report_url"] = pdf_url

    try:
        json_path = os.path.join(REPORTS_DIR, f"report_{session_id}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
    except Exception as e:
        print("Failed to write JSON report:", e)

    # Return result with finish_url (frontend can redirect to this)
    finish_url = f"/finish?session_id={session_id}"
    result["finish_url"] = finish_url
    return result


@app.get("/api/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
