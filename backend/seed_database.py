import os
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import Base, Question
import google.generativeai as genai

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./excel_interviewer.db")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-1.5-flash-latest")

def create_database():
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
    )
    Base.metadata.create_all(bind=engine)
    return engine

def generate_questions():
    """Ask Gemini to generate Excel interview questions"""
    prompt = """
    Generate 15 Excel interview questions in JSON.
    Each item must have:
    {
      "category": "string",
      "difficulty": "beginner|intermediate|advanced",
      "question_text": "string",
      "question_type": "conceptual|practical",
      "canonical_answer": "string",
      "hints": ["string", "string", "string"],
      "tags": "comma,separated,tags"
    }
    Ensure valid JSON array only, no markdown or explanation.
    """
    response = gemini_model.generate_content(prompt)
    text = response.text.strip()
    # remove any accidental formatting
    text = text.replace("```json", "").replace("```", "")
    return json.loads(text)

def seed_questions():
    """Seed database with AI-generated questions"""
    engine = create_database()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        questions = generate_questions()
        added = 0
        for q in questions:
            exists = db.query(Question).filter(Question.question_text == q["question_text"]).first()
            if exists:
                continue
            question = Question(
                category=q["category"],
                difficulty=q["difficulty"],
                question_text=q["question_text"],
                question_type=q["question_type"],
                canonical_answer=q["canonical_answer"],
                hints=json.dumps(q["hints"]),
                tags=q.get("tags", "")
            )
            db.add(question)
            added += 1

        db.commit()
        print(f"✅ Added {added} AI-generated questions")
    except Exception as e:
        print(f"❌ Error seeding: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_questions()
