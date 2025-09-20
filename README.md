# AI Excel Interviewer

This project is an AI-powered interview platform designed to help users practice for Excel-related job interviews. It provides a realistic interview experience with an AI interviewer that asks questions, evaluates answers, and provides feedback in real-time.

## Live Demo

* 🚀 Live App: https://ai-excel-interviewer.web.app
* 📄 API Docs: https://backend-209144746039.us-central1.run.app/docs
## Features

  * **Realistic Interview Experience:** Simulates a real job interview with an AI interviewer.
  * **AI-Powered Evaluation:** Uses Google's Gemini AI to evaluate user's answers and provide a score and feedback.
  * **Speech-to-Text:** Transcribes user's audio answers to text using Google's Speech-to-Text API.
  * **Text-to-Speech:** Converts the AI interviewer's questions to audio using gTTS.
  * **Comprehensive Reporting:** Generates a detailed report at the end of the interview with an overall score, breakdown of performance in different areas, and suggestions for improvement.
  * **PDF and JSON Reports:** The report can be downloaded in both PDF and JSON formats.
  * **User-friendly Interface:** A clean and intuitive user interface built with React.

## Tech Stack

### Backend

  * **Framework:** FastAPI
  * **Database:** SQLAlchemy with a PostgreSQL database.
  * **AI:** Google Generative AI (Gemini)
  * **Speech Recognition:** Google Cloud Speech
  * **Text-to-Speech:** gTTS
  * **PDF Generation:** ReportLab
  * **Deployment:** Docker

### Frontend

  * **Framework:** React
  * **Styling:** Tailwind CSS
  * **Build Tool:** Vite

## Getting Started

### Prerequisites

  * Python 3.11+
  * Node.js and npm
  * Docker
  * Google Cloud SDK

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/anirudh7371/excel-interviewer.git
    cd excel-interviewer
    ```
2.  **Backend Setup:**
      * Install Python dependencies:
        ```bash
        pip install -r backend/requirements.txt
        ```
      * Set up environment variables by creating a `.env` file in the `backend` directory. See `.env.example` for the required variables.
3.  **Frontend Setup:**
      * Install Node.js dependencies:
        ```bash
        cd frontend
        npm install
        ```
      * Set up environment variables by creating a `.env` file in the `frontend` directory. See `.env.example` for the required variables.

### Running the Application

1.  **Start the backend server:**
    ```bash
    uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
    ```
2.  **Start the frontend development server:**
    ```bash
    cd frontend
    npm run dev
    ```

## API Endpoints

  * `POST /api/sessions`: Create a new interview session.
  * `GET /api/sessions/{session_id}/question`: Get the next question for a given session.
  * `POST /api/sessions/{session_id}/answer`: Submit an answer for a given question.
  * `GET /api/sessions/{session_id}/report`: Get the final report for a given session.
  * `GET /api/health`: Health check endpoint.

## Database Schema

The database consists of three tables:

  * `questions`: Stores the interview questions with their category, difficulty, question text, type, canonical answer, alternatives, explanation, and tags.
  * `sessions`: Stores information about each interview session, including candidate details, status, scores, and timestamps.
  * `answers`: Stores the user's answers for each question in a session, including the user's answer, score, time spent, feedback, and whether it was a follow-up question.

## Future Improvements

  * Add support for more question types, such as practical Excel exercises.
  * Implement user authentication and accounts to track progress over time.
  * Implementing proctoring features to ensure the integrity of the interview process.
  * Add more detailed analytics and visualizations to the report.
  * Improve the AI's ability to understand and evaluate more complex answers.