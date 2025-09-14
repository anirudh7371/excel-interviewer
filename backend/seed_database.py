# seed_database.py - Intelligent question seeding with free AI models
import os
import asyncio
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import Question, Base, FreeAIService
import google.generativeai as genai
from groq import Groq
import requests
from datetime import datetime
from main import Question, Base
from ai_service import FreeAIService

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:anirudh@localhost/excel_interviewer")

# Free AI API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini")

# Setup database
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

# Initialize AI service based on provider
if AI_PROVIDER == "gemini" and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
elif AI_PROVIDER == "groq" and GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)

class IntelligentQuestionGenerator:
    """Generate contextually relevant Excel interview questions using free AI models"""
    
    def __init__(self):
        self.ai_service = FreeAIService(provider=AI_PROVIDER)
        self.categories = [
            "Basic Formulas", "Lookup Functions", "Conditional Logic", "Text Functions",
            "Date Functions", "Data Analysis", "Pivot Tables", "Charts & Visualization",
            "Data Validation", "Array Formulas", "Power Query", "VBA Basics",
            "Financial Functions", "Statistical Functions", "Database Functions"
        ]
        
        self.difficulty_levels = ["beginner", "intermediate", "advanced"]
        self.question_types = ["formula", "explanation", "scenario", "multiple_choice"]

    async def generate_comprehensive_question_bank(self, questions_per_category=3):
        """Generate a comprehensive question bank across all categories and difficulties"""
        questions = []
        
        print(f"Starting question generation with {AI_PROVIDER} provider...")
        
        for category in self.categories:
            for difficulty in self.difficulty_levels:
                for _ in range(questions_per_category):
                    question = await self.generate_smart_question(category, difficulty)
                    if question:
                        questions.append(question)
                        print(f"Generated {difficulty} {category} question")
                    
                    # Rate limiting for API calls
                    await asyncio.sleep(2)  # Increased delay for free APIs
        
        return questions

    async def generate_smart_question(self, category, difficulty):
        """Generate a single intelligent question with comprehensive metadata"""
        
        prompt = f"""Generate an Excel interview question for {category} at {difficulty} level.

Requirements:
1. Question should be practical and job-relevant
2. Include multiple valid solution approaches where applicable
3. Provide progressive hints that guide without giving away the answer
4. Include realistic test scenarios

Return ONLY valid JSON format:
{{
    "question_text": "Clear, specific question",
    "question_type": "formula|explanation|scenario",
    "canonical_answer": "Best/expected answer",
    "alternatives": ["alternative valid answers"],
    "explanation": "Why this matters in real work",
    "hints": ["hint1 (gentle)", "hint2 (more specific)", "hint3 (near solution)"],
    "test_cases": [{{"scenario": "description", "expected": "result"}}],
    "skills_tested": ["skill1", "skill2"],
    "real_world_context": "Brief context where this applies",
    "common_mistakes": ["mistake1", "mistake2"],
    "difficulty_justification": "Why this is {difficulty} level",
    "category": "{category}",
    "difficulty": "{difficulty}"
}}

Category: {category}
Difficulty: {difficulty}

Make it challenging but fair for {difficulty} level candidates."""

        try:
            response = await self.ai_service._make_ai_call(prompt)
            
            if not response:
                print(f"No response from AI for {category} {difficulty}")
                return None
            
            # Clean up potential markdown formatting
            content = response.strip()
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "")
            elif content.startswith("```"):
                content = content.replace("```", "")
            
            # Extract JSON from response
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start != -1 and json_end != -1:
                json_str = content[json_start:json_end]
                question_data = json.loads(json_str)
                
                # Ensure required fields
                question_data["category"] = category
                question_data["difficulty"] = difficulty
                
                # Validate required fields
                required_fields = ["question_text", "question_type", "canonical_answer"]
                if all(field in question_data for field in required_fields):
                    return question_data
                else:
                    print(f"Generated question missing required fields: {category} {difficulty}")
                    return self._create_fallback_question(category, difficulty)
            else:
                print(f"Could not extract JSON from response for {category} {difficulty}")
                return self._create_fallback_question(category, difficulty)
                
        except json.JSONDecodeError as e:
            print(f"JSON parsing error for {category} {difficulty}: {e}")
            return self._create_fallback_question(category, difficulty)
        except Exception as e:
            print(f"Error generating question for {category} {difficulty}: {e}")
            return self._create_fallback_question(category, difficulty)

    def _create_fallback_question(self, category, difficulty):
        """Create a fallback question when AI generation fails"""
        fallback_questions = {
            ("Basic Formulas", "beginner"): {
                "question_text": f"What is the most common function used to add numbers in Excel?",
                "question_type": "explanation",
                "canonical_answer": "The SUM function is the most common function used to add numbers in Excel. Syntax: =SUM(range)",
                "alternatives": ["SUM function", "=SUM()"],
                "explanation": "SUM is fundamental for basic calculations in Excel",
                "hints": ["Think about basic arithmetic operations", "It starts with S", "Used for addition"],
                "test_cases": [{"scenario": "Adding cells A1:A5", "expected": "=SUM(A1:A5)"}],
                "skills_tested": ["basic_formulas"],
                "real_world_context": "Used in financial reports and data analysis",
                "common_mistakes": ["Forgetting the = sign", "Wrong range syntax"],
                "difficulty_justification": "Basic knowledge required for Excel use"
            },
            ("Lookup Functions", "intermediate"): {
                "question_text": f"How would you look up a value in a table using Excel?",
                "question_type": "explanation", 
                "canonical_answer": "Use VLOOKUP function to search for a value in the first column of a table and return a value in the same row from another column. Syntax: =VLOOKUP(lookup_value, table_array, col_index_num, range_lookup)",
                "alternatives": ["VLOOKUP", "INDEX/MATCH", "XLOOKUP"],
                "explanation": "Essential for data retrieval and analysis",
                "hints": ["Think about vertical lookup", "V stands for vertical", "Need table array and column index"],
                "test_cases": [{"scenario": "Employee lookup", "expected": "VLOOKUP formula"}],
                "skills_tested": ["vlookup", "data_retrieval"],
                "real_world_context": "HR data, inventory management, sales analysis",
                "common_mistakes": ["Wrong column index", "Absolute vs relative references"],
                "difficulty_justification": "Requires understanding of table structures"
            }
        }
        
        key = (category, difficulty)
        if key in fallback_questions:
            fallback = fallback_questions[key].copy()
            fallback["category"] = category
            fallback["difficulty"] = difficulty
            return fallback
        
        # Generic fallback
        return {
            "question_text": f"Explain a key concept in Excel {category} for {difficulty} level users.",
            "question_type": "explanation",
            "canonical_answer": f"This is a {difficulty} level concept in {category} that requires understanding of Excel fundamentals.",
            "alternatives": [],
            "explanation": f"Important for {category} mastery",
            "hints": ["Review Excel documentation", "Practice with examples", "Start with basics"],
            "test_cases": [],
            "skills_tested": [category.lower().replace(" ", "_")],
            "real_world_context": f"Used in business scenarios involving {category}",
            "common_mistakes": ["Lack of practice", "Not understanding fundamentals"],
            "difficulty_justification": f"Appropriate for {difficulty} level",
            "category": category,
            "difficulty": difficulty
        }

    async def generate_adaptive_follow_ups(self, base_question, performance_context):
        """Generate follow-up questions based on candidate performance"""
        
        prompt = f"""Based on this Excel interview question and candidate performance, generate an appropriate follow-up question.

Original Question: {base_question['question_text']}
Candidate Performance: {performance_context}

Generate a follow-up that:
1. Builds on the original concept
2. Adjusts difficulty based on performance
3. Explores practical applications
4. Tests deeper understanding

Return ONLY valid JSON with same format as original question."""

        try:
            response = await self.ai_service._make_ai_call(prompt)
            if response:
                # Extract JSON
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                if json_start != -1 and json_end != -1:
                    json_str = response[json_start:json_end]
                    return json.loads(json_str)
            return None
            
        except Exception as e:
            print(f"Error generating follow-up: {e}")
            return None

    def create_question_variants(self, base_question):
        """Create multiple variants of a question for A/B testing"""
        variants = []
        
        # Different data scenarios
        data_contexts = [
            "sales data", "employee records", "inventory tracking", 
            "financial reports", "survey responses", "project metrics"
        ]
        
        # Different complexity levels
        complexity_adjustments = {
            "simpler": "with fewer conditions",
            "standard": "with typical business constraints", 
            "complex": "with multiple criteria and edge cases"
        }
        
        for context in data_contexts[:2]:  # Limit variants
            for complexity, adjustment in complexity_adjustments.items():
                variant = base_question.copy()
                variant['question_text'] = variant['question_text'].replace(
                    "data", f"{context} {adjustment}"
                )
                variant['real_world_context'] = f"Applied to {context} analysis"
                variants.append(variant)
        
        return variants

async def seed_initial_questions():
    """Seed the database with a comprehensive initial question set"""
    
    generator = IntelligentQuestionGenerator()
    db = SessionLocal()
    
    try:
        print("Starting intelligent question generation with free AI models...")
        
        # Check if AI provider is available
        api_available = False
        if AI_PROVIDER == "gemini" and GEMINI_API_KEY:
            api_available = True
        elif AI_PROVIDER == "groq" and GROQ_API_KEY:
            api_available = True
        elif AI_PROVIDER == "huggingface" and HUGGINGFACE_API_KEY:
            api_available = True
        elif AI_PROVIDER == "ollama":
            # Check if Ollama is running locally
            try:
                response = requests.get("http://localhost:11434/api/tags", timeout=5)
                api_available = response.status_code == 200
            except:
                api_available = False
        
        if not api_available:
            print(f"AI provider {AI_PROVIDER} not available. Using fallback questions only.")
            # Generate some fallback questions
            questions = []
            for category in generator.categories[:3]:  # Limit to first 3 categories
                for difficulty in generator.difficulty_levels:
                    fallback = generator._create_fallback_question(category, difficulty)
                    if fallback:
                        questions.append(fallback)
        else:
            # Generate comprehensive question bank using AI
            questions = await generator.generate_comprehensive_question_bank(questions_per_category=2)  # Reduced for free tier
        
        print(f"Generated {len(questions)} questions")
        
        # Add questions to database
        added_count = 0
        for q_data in questions:
            try:
                question = Question(
                    category=q_data.get("category", "General"),
                    difficulty=q_data.get("difficulty", "intermediate"), 
                    question_text=q_data["question_text"],
                    question_type=q_data["question_type"],
                    canonical_answer=q_data["canonical_answer"],
                    alternatives=json.dumps(q_data.get("alternatives", [])),
                    explanation=q_data.get("explanation", ""),
                    hints=json.dumps(q_data.get("hints", [])),
                    test_cases=json.dumps(q_data.get("test_cases", [])),
                    tags=",".join(q_data.get("skills_tested", []))
                )
                
                db.add(question)
                added_count += 1
                
            except Exception as e:
                print(f"Error adding question to DB: {e}")
                continue
        
        db.commit()
        print(f"Successfully seeded {added_count} questions to database")
        
        # Generate some adaptive follow-up examples if API is available
        if api_available:
            print("Generating adaptive follow-up examples...")
            base_questions = db.query(Question).limit(3).all()  # Reduced for free tier
            
            follow_ups = []
            for base_q in base_questions:
                performance_contexts = [
                    {"score": 90, "time": "fast", "hints_used": 0},
                    {"score": 30, "time": "slow", "hints_used": 3}
                ]
                
                for context in performance_contexts:
                    follow_up = await generator.generate_adaptive_follow_ups(
                        {
                            "question_text": base_q.question_text,
                            "category": base_q.category,
                            "difficulty": base_q.difficulty
                        },
                        context
                    )
                    
                    if follow_up:
                        follow_ups.append(follow_up)
                        print(f"Generated adaptive follow-up based on {context['score']}% performance")
                    
                    await asyncio.sleep(3)  # Rate limiting for free APIs
            
            print(f"Generated {len(follow_ups)} adaptive follow-up questions")
        
    except Exception as e:
        print(f"Error during seeding: {e}")
        db.rollback()
    finally:
        db.close()

# Manual seed data for immediate testing (unchanged)
MANUAL_SEED_QUESTIONS = [
    {
        "category": "Basic Formulas",
        "difficulty": "beginner",
        "question_text": "You have monthly sales figures in cells A1 through A12. Write a formula to calculate the total annual sales.",
        "question_type": "formula",
        "canonical_answer": "=SUM(A1:A12)",
        "alternatives": ["=SUM(A:A)", "SUM(A1:A12)"],
        "explanation": "The SUM function is the most efficient way to add multiple cells. Using a specific range (A1:A12) is better than an entire column for performance.",
        "hints": [
            "Think about which function adds numbers together",
            "You need to specify the range of cells containing monthly data",  
            "The syntax is =SUM(starting_cell:ending_cell)"
        ],
        "test_cases": [
            {"scenario": "12 months of sales data", "input": [1000,1200,1100,1300,1400,1250,1350,1500,1450,1600,1550,1650], "expected": 16300}
        ],
        "tags": "sum,basic,annual_totals"
    },
    {
        "category": "Lookup Functions", 
        "difficulty": "intermediate",
        "question_text": "You have an employee table with ID (column A), Name (column B), Department (column C), and Salary (column D) from rows 1-100. Write a formula to find the salary of employee ID 'E001'.",
        "question_type": "formula",
        "canonical_answer": "=VLOOKUP(\"E001\",A1:D100,4,FALSE)",
        "alternatives": ["=INDEX(D1:D100,MATCH(\"E001\",A1:A100,0))", "=XLOOKUP(\"E001\",A1:A100,D1:D100)"],
        "explanation": "VLOOKUP searches for the employee ID in the first column and returns the corresponding salary from the 4th column. INDEX/MATCH is more flexible but VLOOKUP is more commonly used.",
        "hints": [
            "Use a lookup function to search in a table",
            "VLOOKUP syntax: =VLOOKUP(lookup_value, table_array, col_index_num, range_lookup)",
            "You want the 4th column (salary) and exact match (FALSE)"
        ],
        "test_cases": [
            {"scenario": "Finding employee E001 salary", "expected": "Returns salary value from column D"}
        ],
        "tags": "vlookup,employee_data,hr"
    },
    {
        "category": "Data Analysis",
        "difficulty": "advanced", 
        "question_text": "Explain how you would create a dynamic dashboard that shows sales performance by region, with the ability to filter by time period and product category. What Excel features would you use and how would they work together?",
        "question_type": "explanation",
        "canonical_answer": "I would use Excel Tables for the data source to ensure dynamic ranges, create PivotTables connected to the tables for summarizing by region, add Slicers for time period and product category filtering, use PivotCharts for visualization, implement conditional formatting for performance indicators, and use named ranges with INDIRECT function for dynamic chart titles. The dashboard would automatically update when new data is added to the source table.",
        "alternatives": [],
        "explanation": "Dynamic dashboards require structured data sources (Tables) that automatically expand, interactive filtering (Slicers), and visual components (PivotCharts) that refresh automatically when source data changes.",
        "hints": [
            "Think about making your data source expandable automatically",
            "Consider what interactive elements users need for filtering",
            "Think about visual components that update automatically"
        ],
        "test_cases": [],
        "tags": "dashboard,pivot_tables,advanced,dynamic"
    },
    {
        "category": "Conditional Logic",
        "difficulty": "beginner",
        "question_text": "Write a formula to display 'Pass' if a student's score in cell A1 is 60 or above, otherwise display 'Fail'.",
        "question_type": "formula",
        "canonical_answer": "=IF(A1>=60,\"Pass\",\"Fail\")",
        "alternatives": ["=IF(A1>=60,\"Pass\",\"Fail\")", "IF(A1>=60,\"Pass\",\"Fail\")"],
        "explanation": "The IF function allows you to perform logical tests and return different values based on the result.",
        "hints": [
            "Use the IF function for conditional logic",
            "IF syntax: =IF(condition, value_if_true, value_if_false)",
            "Check if A1 is greater than or equal to 60"
        ],
        "test_cases": [
            {"scenario": "Score of 75", "expected": "Pass"},
            {"scenario": "Score of 45", "expected": "Fail"}
        ],
        "tags": "if,conditional,grading"
    },
    {
        "category": "Text Functions",
        "difficulty": "intermediate",
        "question_text": "You have full names in column A (format: 'First Last'). Write a formula to extract just the first name.",
        "question_type": "formula", 
        "canonical_answer": "=LEFT(A1,FIND(\" \",A1)-1)",
        "alternatives": ["=TRIM(LEFT(SUBSTITUTE(A1,\" \",REPT(\" \",100)),100))"],
        "explanation": "This formula finds the position of the first space and extracts everything to the left of it, which gives us the first name.",
        "hints": [
            "You need to find where the space is in the name",
            "Use FIND function to locate the space",
            "Use LEFT function to extract characters from the beginning"
        ],
        "test_cases": [
            {"scenario": "John Doe", "expected": "John"},
            {"scenario": "Mary Smith", "expected": "Mary"}
        ],
        "tags": "text,left,find,name_parsing"
    }
]

def seed_manual_questions():
    """Seed database with manually curated questions for immediate testing"""
    db = SessionLocal()
    
    try:
        print("Seeding manual questions for immediate testing...")
        
        for q_data in MANUAL_SEED_QUESTIONS:
            question = Question(
                category=q_data["category"],
                difficulty=q_data["difficulty"],
                question_text=q_data["question_text"],
                question_type=q_data["question_type"],
                canonical_answer=q_data["canonical_answer"],
                alternatives=json.dumps(q_data["alternatives"]),
                explanation=q_data["explanation"],
                hints=json.dumps(q_data["hints"]),
                test_cases=json.dumps(q_data["test_cases"]),
                tags=q_data["tags"]
            )
            
            db.add(question)
        
        db.commit()
        print(f"Seeded {len(MANUAL_SEED_QUESTIONS)} manual questions successfully")
        
    except Exception as e:
        print(f"Error seeding manual questions: {e}")
        db.rollback()
    finally:
        db.close()

async def generate_role_specific_questions():
    """Generate questions tailored to specific job roles using free AI"""
    
    roles = {
        "Data Analyst": {
            "focus_areas": ["pivot_tables", "data_cleaning", "vlookup", "charts"],
            "scenarios": ["analyzing sales trends", "cleaning survey data", "creating reports"]
        },
        "Financial Analyst": {
            "focus_areas": ["financial_functions", "modeling", "scenario_analysis", "charts"],
            "scenarios": ["budget planning", "financial modeling", "variance analysis"]
        },
        "Operations Manager": {
            "focus_areas": ["basic_formulas", "conditional_formatting", "data_validation", "dashboards"],
            "scenarios": ["inventory tracking", "performance monitoring", "resource planning"]
        }
    }
    
    generator = IntelligentQuestionGenerator()
    db = SessionLocal()
    
    try:
        # Check if AI is available
        api_available = (AI_PROVIDER == "gemini" and GEMINI_API_KEY) or \
                       (AI_PROVIDER == "groq" and GROQ_API_KEY) or \
                       (AI_PROVIDER == "huggingface" and HUGGINGFACE_API_KEY)
        
        if not api_available:
            print("No AI provider available for role-specific generation. Skipping.")
            return
        
        for role, details in roles.items():
            print(f"Generating questions for {role}...")
            
            for scenario in details["scenarios"][:2]:  # Limit for free tier
                for difficulty in ["intermediate"]:  # Focus on one difficulty
                    prompt = f"""Create an Excel interview question for a {role} position.

Context: {scenario}
Difficulty: {difficulty}
Focus Areas: {', '.join(details['focus_areas'])}

The question should be directly relevant to what a {role} would encounter in their daily work.

Return ONLY valid JSON format:
{{
    "question_text": "specific question text",
    "question_type": "formula|explanation|scenario",
    "canonical_answer": "expected answer",
    "alternatives": ["alternative answers"],
    "explanation": "why important for {role}",
    "hints": ["hint1", "hint2", "hint3"],
    "test_cases": [{{"scenario": "description", "expected": "result"}}],
    "skills_tested": ["skill1", "skill2"],
    "real_world_context": "specific to {role}",
    "common_mistakes": ["mistake1", "mistake2"],
    "difficulty_justification": "why {difficulty} level",
    "category": "{role} Specific",
    "difficulty": "{difficulty}"
}}"""

                    try:
                        ai_service = FreeAIService(provider=AI_PROVIDER)
                        response = await ai_service._make_ai_call(prompt)
                        
                        if response:
                            # Extract JSON
                            json_start = response.find('{')
                            json_end = response.rfind('}') + 1
                            if json_start != -1 and json_end != -1:
                                json_str = response[json_start:json_end]
                                q_data = json.loads(json_str)
                                
                                question = Question(
                                    category=f"{role} Specific",
                                    difficulty=difficulty,
                                    question_text=q_data["question_text"],
                                    question_type=q_data["question_type"],
                                    canonical_answer=q_data["canonical_answer"],
                                    alternatives=json.dumps(q_data.get("alternatives", [])),
                                    explanation=q_data.get("explanation", ""),
                                    hints=json.dumps(q_data.get("hints", [])),
                                    test_cases=json.dumps(q_data.get("test_cases", [])),
                                    tags=f"{role.lower().replace(' ', '_')},{scenario.replace(' ', '_')}"
                                )
                                
                                db.add(question)
                                print(f"Generated {role} question: {scenario}")
                        
                        await asyncio.sleep(3)  # Rate limiting for free APIs
                        
                    except Exception as e:
                        print(f"Error generating {role} question: {e}")
                        continue
        
        db.commit()
        print("Role-specific questions generated successfully")
        
    except Exception as e:
        print(f"Error generating role-specific questions: {e}")
        db.rollback()
    finally:
        db.close()

# Performance Analytics (unchanged)
class QuestionAnalytics:
    """Analyze question performance and suggest improvements"""
    
    def __init__(self):
        self.db = SessionLocal()
    
    def analyze_question_difficulty(self):
        """Analyze if questions are appropriately difficult"""
        
        query = """
        SELECT 
            q.difficulty,
            AVG(a.score) as avg_score,
            COUNT(a.id) as attempts,
            AVG(a.time_spent) as avg_time,
            COUNT(CASE WHEN a.score < 50 THEN 1 END) as low_scores
        FROM questions q
        LEFT JOIN answers a ON q.id = a.question_id
        GROUP BY q.difficulty
        """
        
        results = self.db.execute(query).fetchall()
        
        for row in results:
            print(f"\n{row.difficulty.upper()} Questions:")
            print(f"   Average Score: {row.avg_score:.1f}%")
            print(f"   Total Attempts: {row.attempts}")
            print(f"   Average Time: {row.avg_time:.1f}s")
            print(f"   Low Scores (<50%): {row.low_scores}")
            
            # Recommendations
            if row.avg_score > 85:
                print(f"   Consider making {row.difficulty} questions more challenging")
            elif row.avg_score < 60:
                print(f"   Consider simplifying {row.difficulty} questions")
            else:
                print(f"   {row.difficulty} questions are well-balanced")
    
    def identify_problematic_questions(self):
        """Find questions that need review"""
        
        query = """
        SELECT 
            q.id,
            q.question_text,
            q.category,
            q.difficulty,
            AVG(a.score) as avg_score,
            COUNT(a.id) as attempts,
            AVG(a.time_spent) as avg_time
        FROM questions q
        LEFT JOIN answers a ON q.id = a.question_id
        GROUP BY q.id, q.question_text, q.category, q.difficulty
        HAVING COUNT(a.id) >= 5 AND (AVG(a.score) < 40 OR AVG(a.score) > 95 OR AVG(a.time_spent) > 300)
        ORDER BY avg_score ASC
        """
        
        results = self.db.execute(query).fetchall()
        
        print(f"\nFound {len(results)} questions that need review:")
        
        for row in results:
            print(f"\nQuestion ID {row.id} ({row.category} - {row.difficulty})")
            print(f"   Text: {row.question_text[:100]}...")
            print(f"   Avg Score: {row.avg_score:.1f}% | Attempts: {row.attempts} | Avg Time: {row.avg_time:.1f}s")
            
            if row.avg_score < 40:
                print("   Too difficult - consider simplifying")
            elif row.avg_score > 95:
                print("   Too easy - consider adding complexity")
            elif row.avg_time > 300:
                print("   Takes too long - consider streamlining")
    
    def close(self):
        self.db.close()

# Main execution functions
async def full_seed():
    """Complete database seeding with AI-generated questions"""
    print("Starting comprehensive database seeding with free AI models...")
    
    # Step 1: Manual questions for immediate testing
    seed_manual_questions()
    
    # Step 2: AI-generated comprehensive question bank
    ai_available = (AI_PROVIDER == "gemini" and GEMINI_API_KEY) or \
                   (AI_PROVIDER == "groq" and GROQ_API_KEY) or \
                   (AI_PROVIDER == "huggingface" and HUGGINGFACE_API_KEY) or \
                   (AI_PROVIDER == "ollama")
    
    if ai_available:
        print(f"AI provider {AI_PROVIDER} available - generating intelligent questions...")
        await seed_initial_questions()
        await generate_role_specific_questions()
    else:
        print("No AI provider configured - using only manual questions")
    
    print("Database seeding complete!")

def quick_seed():
    """Quick seeding with just manual questions"""
    print("Quick seeding with manual questions...")
    seed_manual_questions()
    print("Quick seed complete!")

def analyze_performance():
    """Analyze question performance"""
    print("Analyzing question performance...")
    analytics = QuestionAnalytics()
    try:
        analytics.analyze_question_difficulty()
        analytics.identify_problematic_questions()
    finally:
        analytics.close()

# Production Utils (updated for free AI models)
class ProductionUtils:
    """Utilities for production environment"""
    
    @staticmethod
    def backup_questions():
        """Backup all questions to JSON file"""
        db = SessionLocal()
        try:
            questions = db.query(Question).all()
            
            backup_data = []
            for q in questions:
                backup_data.append({
                    "id": q.id,
                    "category": q.category,
                    "difficulty": q.difficulty,
                    "question_text": q.question_text,
                    "question_type": q.question_type,
                    "canonical_answer": q.canonical_answer,
                    "alternatives": q.alternatives,
                    "explanation": q.explanation,
                    "hints": q.hints,
                    "test_cases": q.test_cases,
                    "tags": q.tags,
                    "created_at": q.created_at.isoformat() if q.created_at else None
                })
            
            with open(f"questions_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", 'w') as f:
                json.dump(backup_data, f, indent=2)
            
            print(f"Backed up {len(backup_data)} questions")
            
        finally:
            db.close()
    
    @staticmethod
    def import_questions_from_json(filename):
        """Import questions from JSON backup"""
        db = SessionLocal()
        try:
            with open(filename, 'r') as f:
                questions_data = json.load(f)
            
            imported = 0
            for q_data in questions_data:
                # Skip if question already exists
                existing = db.query(Question).filter(
                    Question.question_text == q_data["question_text"]
                ).first()
                
                if existing:
                    continue
                
                question = Question(
                    category=q_data["category"],
                    difficulty=q_data["difficulty"],
                    question_text=q_data["question_text"],
                    question_type=q_data["question_type"],
                    canonical_answer=q_data["canonical_answer"],
                    alternatives=q_data["alternatives"],
                    explanation=q_data["explanation"],
                    hints=q_data["hints"],
                    test_cases=q_data["test_cases"],
                    tags=q_data["tags"]
                )
                
                db.add(question)
                imported += 1
            
            db.commit()
            print(f"Imported {imported} new questions")
            
        finally:
            db.close()

    @staticmethod
    def generate_question_report():
        """Generate a comprehensive question bank report"""
        db = SessionLocal()
        try:
            # Count by category and difficulty
            stats = db.execute("""
                SELECT category, difficulty, COUNT(*) as count
                FROM questions 
                GROUP BY category, difficulty
                ORDER BY category, 
                    CASE difficulty 
                        WHEN 'beginner' THEN 1 
                        WHEN 'intermediate' THEN 2 
                        WHEN 'advanced' THEN 3 
                    END
            """).fetchall()
            
            print("\nQuestion Bank Report")
            print("=" * 50)
            
            current_category = None
            total_questions = 0
            
            for stat in stats:
                if stat.category != current_category:
                    if current_category:
                        print()
                    print(f"\n{stat.category}")
                    current_category = stat.category
                
                print(f"   {stat.difficulty.title()}: {stat.count} questions")
                total_questions += stat.count
            
            print(f"\nTotal Questions: {total_questions}")
            
            # Usage statistics if available
            usage_stats = db.execute("""
                SELECT 
                    COUNT(DISTINCT session_id) as total_sessions,
                    COUNT(*) as total_answers,
                    AVG(score) as avg_score
                FROM answers
            """).fetchone()
            
            if usage_stats and usage_stats.total_sessions > 0:
                print(f"\nUsage Statistics:")
                print(f"   Total Sessions: {usage_stats.total_sessions}")
                print(f"   Total Answers: {usage_stats.total_answers}")
                print(f"   Average Score: {usage_stats.avg_score:.1f}%")
            
        finally:
            db.close()
    
    @staticmethod
    def check_ai_provider_status():
        """Check the status of configured AI providers"""
        print(f"AI Provider Configuration:")
        print(f"Current Provider: {AI_PROVIDER}")
        
        # Check Gemini
        if GEMINI_API_KEY:
            print(f"Gemini API Key: Configured")
            try:
                genai.configure(api_key=GEMINI_API_KEY)
                model = genai.GenerativeModel('gemini-1.5-flash')
                # Quick test
                response = model.generate_content("Test")
                print(f"Gemini Status: Available")
            except Exception as e:
                print(f"Gemini Status: Error - {e}")
        else:
            print(f"Gemini API Key: Not configured")
        
        # Check Groq
        if GROQ_API_KEY:
            print(f"Groq API Key: Configured")
            try:
                client = Groq(api_key=GROQ_API_KEY)
                # Test with a simple request
                print(f"Groq Status: Configured (test requires actual API call)")
            except Exception as e:
                print(f"Groq Status: Error - {e}")
        else:
            print(f"Groq API Key: Not configured")
        
        # Check HuggingFace
        if HUGGINGFACE_API_KEY:
            print(f"HuggingFace API Key: Configured")
            try:
                headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
                response = requests.get("https://api-inference.huggingface.co/models/microsoft/DialoGPT-medium", 
                                      headers=headers, timeout=5)
                print(f"HuggingFace Status: Available" if response.status_code == 200 else f"HuggingFace Status: Error {response.status_code}")
            except Exception as e:
                print(f"HuggingFace Status: Error - {e}")
        else:
            print(f"HuggingFace API Key: Not configured")
        
        # Check Ollama
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json()
                print(f"Ollama Status: Available with {len(models.get('models', []))} models")
            else:
                print(f"Ollama Status: Server running but error {response.status_code}")
        except Exception as e:
            print(f"Ollama Status: Not available - {e}")

# Enhanced question generation with better error handling
class RobustQuestionGenerator(IntelligentQuestionGenerator):
    """Enhanced question generator with better error handling for free APIs"""
    
    def __init__(self):
        super().__init__()
        self.retry_count = 3
        self.fallback_enabled = True
    
    async def generate_with_retry(self, prompt, category, difficulty):
        """Generate question with retry logic for free APIs"""
        for attempt in range(self.retry_count):
            try:
                response = await self.ai_service._make_ai_call(prompt)
                if response:
                    # Try to parse the response
                    question_data = self._parse_ai_response(response, category, difficulty)
                    if question_data:
                        return question_data
                
                print(f"Attempt {attempt + 1} failed for {category} {difficulty}")
                await asyncio.sleep(5 * (attempt + 1))  # Exponential backoff
                
            except Exception as e:
                print(f"Attempt {attempt + 1} error for {category} {difficulty}: {e}")
                if attempt < self.retry_count - 1:
                    await asyncio.sleep(5 * (attempt + 1))
        
        # If all attempts failed, return fallback
        if self.fallback_enabled:
            print(f"All attempts failed, using fallback for {category} {difficulty}")
            return self._create_fallback_question(category, difficulty)
        
        return None
    
    def _parse_ai_response(self, response, category, difficulty):
        """Parse AI response with better error handling"""
        try:
            content = response.strip()
            
            # Remove markdown formatting
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "")
            elif content.startswith("```"):
                content = content.replace("```", "")
            
            # Find JSON in response
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start == -1 or json_end <= json_start:
                return None
            
            json_str = content[json_start:json_end]
            question_data = json.loads(json_str)
            
            # Validate and clean data
            question_data["category"] = category
            question_data["difficulty"] = difficulty
            
            # Ensure required fields exist
            required_fields = ["question_text", "question_type", "canonical_answer"]
            for field in required_fields:
                if field not in question_data or not question_data[field]:
                    return None
            
            # Clean and validate arrays
            for field in ["alternatives", "hints", "test_cases", "skills_tested", "common_mistakes"]:
                if field in question_data and not isinstance(question_data[field], list):
                    question_data[field] = []
            
            return question_data
            
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"Parse error: {e}")
            return None

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "full":
            asyncio.run(full_seed())
        elif command == "quick":
            quick_seed()
        elif command == "analyze":
            analyze_performance()
        elif command == "roles":
            asyncio.run(generate_role_specific_questions())
        elif command == "backup":
            ProductionUtils.backup_questions()
        elif command == "report":
            ProductionUtils.generate_question_report()
        elif command == "check":
            ProductionUtils.check_ai_provider_status()
        else:
            print("Usage: python seed_database.py [full|quick|analyze|roles|backup|report|check]")
    else:
        # Default to quick seed
        quick_seed()

# Export functions for easy importing
__all__ = [
    'seed_initial_questions',
    'seed_manual_questions', 
    'generate_role_specific_questions',
    'full_seed',
    'quick_seed',
    'analyze_performance',
    'IntelligentQuestionGenerator',
    'RobustQuestionGenerator',
    'QuestionAnalytics',
    'ProductionUtils'
]