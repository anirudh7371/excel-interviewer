import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Mic,
  MicOff,
  Camera,
  CameraOff,
  BrainCircuit,
  User,
  Phone,
  Mail,
  School,
  GraduationCap,
} from 'lucide-react';

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000/api";
const SERVER_ROOT = API_BASE.replace('/api', '');
// Finish redirect settings (can be set in env)
const FINISH_REDIRECT_URL = process.env.REACT_APP_FINISH_REDIRECT_URL || "";
const FINISH_REDIRECT_DELAY_MS = parseInt(process.env.REACT_APP_FINISH_REDIRECT_DELAY_MS || "5000", 10);

// --- Reusable Components ---
const SiriWave = ({ active }) => (
  <div className="w-full h-16 flex justify-center items-center space-x-1.5">
    {[0.1, 0.2, 0.3, 0.4, 0.5, 0.4, 0.3, 0.2].map((delay, i) => (
      <div
        key={i}
        className={`w-1.5 rounded-full bg-purple-400 transition-all duration-300 ${
          active ? 'animate-wave' : 'h-2'
        }`}
        style={{ animationDelay: `${delay}s` }}
      ></div>
    ))}
  </div>
);

// --- Landing Page ---
const LandingPage = ({ onStart }) => (
  <div className="w-full h-full flex flex-col items-center justify-center text-center p-8 bg-slate-900 text-white">
    <div className="absolute inset-0 bg-grid-slate-700/[0.2] bg-center [mask-image:linear-gradient(180deg,white,rgba(255,255,255,0))]"></div>
    <div className="relative z-10 animate-fade-in">
      <h1 className="text-5xl md:text-7xl font-bold bg-gradient-to-r from-purple-400 to-pink-500 bg-clip-text text-transparent mb-4">
        AI Interview Prep
      </h1>
      <p className="text-lg md:text-xl text-slate-300 max-w-2xl mx-auto mb-8">
        Sharpen your skills with a realistic, AI-powered interview experience.
        Get instant feedback and practice until you're perfect.
      </p>
      <button
        onClick={onStart}
        className="px-8 py-4 bg-purple-600 text-white font-bold rounded-full hover:bg-purple-700 transition-transform transform hover:scale-105 shadow-lg shadow-purple-500/50"
      >
        Start Your Interview
      </button>
    </div>
  </div>
);

// --- Input Field ---
const InputField = ({
  icon,
  placeholder,
  name,
  value,
  onChange,
  type = 'text',
  required = true,
}) => (
  <div className="relative">
    <div className="absolute inset-y-0 left-0 flex items-center pl-4 pointer-events-none text-slate-400">
      {icon}
    </div>
    <input
      type={type}
      name={name}
      placeholder={placeholder}
      value={value}
      onChange={onChange}
      required={required}
      className="w-full pl-12 pr-4 py-3 bg-slate-800/50 border border-slate-700 rounded-lg text-white placeholder-slate-400 focus:ring-2 focus:ring-purple-500 focus:outline-none"
    />
  </div>
);

// --- Details Form ---
const DetailsForm = ({ onDetailsSubmit }) => {
  const [details, setDetails] = useState({
    candidate_name: '',
    candidate_email: '',
    candidate_phone: '',
    college_name: '',
    roll_number: '',
  });

  const handleChange = (e) =>
    setDetails({ ...details, [e.target.name]: e.target.value });

  const handleSubmit = (e) => {
    e.preventDefault();
    onDetailsSubmit(details);
  };

  return (
    <div className="w-full h-full flex items-center justify-center p-4 bg-slate-900">
      <div className="w-full max-w-md p-8 bg-slate-800/50 backdrop-blur-sm rounded-2xl border border-slate-700 shadow-2xl animate-fade-in">
        <h2 className="text-3xl font-bold text-white text-center mb-2">
          Interview Details
        </h2>
        <p className="text-slate-400 text-center mb-8">
          Please provide your information to begin.
        </p>
        <form onSubmit={handleSubmit} className="space-y-6">
          <InputField
            icon={<User size={20} />}
            placeholder="Full Name"
            name="candidate_name"
            value={details.candidate_name}
            onChange={handleChange}
          />
          <InputField
            icon={<Mail size={20} />}
            placeholder="Email Address"
            name="candidate_email"
            value={details.candidate_email}
            onChange={handleChange}
            type="email"
          />
          <InputField
            icon={<Phone size={20} />}
            placeholder="Phone Number"
            name="candidate_phone"
            value={details.candidate_phone}
            onChange={handleChange}
            type="tel"
          />
          <InputField
            icon={<School size={20} />}
            placeholder="College Name"
            name="college_name"
            value={details.college_name}
            onChange={handleChange}
          />
          <InputField
            icon={<GraduationCap size={20} />}
            placeholder="College Roll Number"
            name="roll_number"
            value={details.roll_number}
            onChange={handleChange}
          />
          <button
            type="submit"
            className="w-full px-6 py-3 bg-purple-600 text-white font-bold rounded-lg hover:bg-purple-700 transition-all shadow-lg shadow-purple-500/30"
          >
            Proceed to Interview
          </button>
        </form>
      </div>
    </div>
  );
};

// --- Results Page (updated with auto redirect to finish URL and PDF download) ---
const ResultsPage = ({ sessionId, onDone }) => {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    const fetchReport = async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/sessions/${sessionId}/report`);
        if (!res.ok) throw new Error("Failed to fetch report");
        const data = await res.json();
        if (!mounted) return;
        setReport(data);
      } catch (err) {
        console.error(err);
      } finally {
        if (mounted) setLoading(false);
      }
    };
    fetchReport();
    return () => { mounted = false; };
  }, [sessionId]);

  useEffect(() => {
    if (!report) return;
    if (FINISH_REDIRECT_URL) {
      const t = setTimeout(() => {
        try {
          // open in new tab
          window.open(FINISH_REDIRECT_URL, "_blank");
        } catch (e) {
          window.location.href = FINISH_REDIRECT_URL;
        }
      }, FINISH_REDIRECT_DELAY_MS);
      return () => clearTimeout(t);
    }
  }, [report]);

  if (loading) return <div className="p-8 text-center">Loading results...</div>;
  if (!report) return <div className="p-8 text-center">Could not retrieve results.</div>;

  return (
    <div className="w-full h-full flex items-center justify-center p-8 bg-slate-900 text-white">
      <div className="w-full max-w-3xl p-8 bg-slate-800/60 rounded-2xl border border-slate-700">
        <h2 className="text-2xl font-bold mb-4">Interview Report</h2>
        <p className="text-slate-300 mb-4">
          Candidate: <strong>{report.candidate_name}</strong> · {report.candidate_email}
        </p>

        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="p-3 bg-slate-800/40 rounded-md">
            <div className="text-sm text-slate-400">Overall Score</div>
            <div className="text-xl font-bold">{report.overall_score}</div>
          </div>
          <div className="p-3 bg-slate-800/40 rounded-md">
            <div className="text-sm text-slate-400">Questions</div>
            <div className="text-xl font-bold">{report.total_questions}</div>
          </div>
          <div className="p-3 bg-slate-800/40 rounded-md">
            <div className="text-sm text-slate-400">Time (min)</div>
            <div className="text-xl font-bold">{report.total_time_minutes}</div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 mb-6">
          <div className="p-4 bg-slate-800/40 rounded-md">
            <div className="text-sm text-slate-400">Communication</div>
            <div className="text-xl font-bold">{report.communication_score}</div>
          </div>
          <div className="p-4 bg-slate-800/40 rounded-md">
            <div className="text-sm text-slate-400">Presentation</div>
            <div className="text-xl font-bold">{report.presentation_score}</div>
          </div>
          <div className="p-4 bg-slate-800/40 rounded-md">
            <div className="text-sm text-slate-400">Clarity</div>
            <div className="text-xl font-bold">{report.clarity_score}</div>
          </div>
          <div className="p-4 bg-slate-800/40 rounded-md">
            <div className="text-sm text-slate-400">Confidence</div>
            <div className="text-xl font-bold">{report.confidence_score}</div>
          </div>
          <div className="p-4 bg-slate-800/40 rounded-md col-span-2">
            <div className="text-sm text-slate-400">Problem Solving</div>
            <div className="text-xl font-bold">{report.problem_solving_score}</div>
          </div>
        </div>

        <div className="mb-6 p-4 bg-slate-800/50 rounded-md">
          <div className="text-sm text-slate-400 mb-2">Summary & Suggestions</div>
          <div className="text-white mb-3">{report.summary}</div>
          <div className="text-slate-300">
            {report.suggestions && report.suggestions.map((s, i) => <div key={i}>• {s}</div>)}
          </div>
        </div>

        <div className="mb-6 max-h-48 overflow-auto space-y-3">
          {report.answers.map((a, idx) => (
            <div key={idx} className="p-3 bg-slate-800/40 rounded-md border border-slate-700">
              <div className="text-sm text-slate-400">Question ID: {String(a.question_id)}</div>
              <div className="text-white my-2">{a.user_answer}</div>
              <div className="text-sm text-slate-400">Score: {a.score} · Followup: {a.is_followup ? "Yes" : "No"}</div>
              <div className="text-sm text-slate-400 mt-1">Feedback: {a.feedback}</div>
            </div>
          ))}
        </div>

        <div className="flex items-center justify-between">
          <div>
            {report.report_url && (
              <>
                <a href={`${SERVER_ROOT}${report.report_url}`} target="_blank" rel="noreferrer" className="text-purple-300 underline mr-4">
                  Download PDF report
                </a>
                <a href={`${SERVER_ROOT}${report.report_url.replace('.pdf', '.json')}`} target="_blank" rel="noreferrer" className="text-purple-300 underline">
                  Download JSON
                </a>
              </>
            )}
          </div>
          <div>
            <button onClick={onDone} className="px-4 py-2 bg-slate-700 rounded-md">Done</button>
          </div>
        </div>
      </div>
    </div>
  );
};

// --- Interview Page (full implementation with onFinish hook) ---
const InterviewPage = ({ userDetails, onFinish }) => {
  const [isCameraOn, setIsCameraOn] = useState(true);
  const [isRecording, setIsRecording] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [questionText, setQuestionText] = useState('Loading your first question...');
  const [questionAudioUrl, setQuestionAudioUrl] = useState(null);
  const [transcript, setTranscript] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const videoRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const lastSpokenRef = useRef("");
  const playedRef = useRef(false);

  // Fetch first question on mount
  useEffect(() => {
    const fetchFirstQuestion = async () => {
      try {
        const res = await fetch(`${API_BASE}/sessions/${userDetails.session_id}/question`);
        if (!res.ok) throw new Error('Failed to fetch question');
        const data = await res.json();
        setQuestionText(data.question_text || 'No question received.');
        setQuestionAudioUrl(data.audio_url || null);
        playedRef.current = false;
        if (data.is_complete) {
          // interview complete -> go to results immediately
          onFinish();
        }
      } catch (err) {
        console.error(err);
        setQuestionText('Error loading first question. Please retry.');
      }
    };
    fetchFirstQuestion();
  }, [userDetails, onFinish]);

  // Camera setup
  useEffect(() => {
    const videoElement = videoRef.current;

    if (isCameraOn) {
      navigator.mediaDevices
        .getUserMedia({ video: true })
        .then((stream) => {
          if (videoElement) videoElement.srcObject = stream;
        })
        .catch((err) => {
          console.error('Camera access denied:', err);
          setIsCameraOn(false);
        });
    } else {
      if (videoElement?.srcObject) {
        videoElement.srcObject.getTracks().forEach((track) => track.stop());
        videoElement.srcObject = null;
      }
    }

    return () => {
      if (videoElement?.srcObject) {
        videoElement.srcObject.getTracks().forEach((track) => track.stop());
      }
    };
  }, [isCameraOn]);

  // TTS fallback (browser speech synthesis)
  const speak = useCallback(
    (text) => {
      if (!window.speechSynthesis || isSpeaking) return;
      setIsSpeaking(true);
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.onend = () => setIsSpeaking(false);
      utterance.onerror = () => setIsSpeaking(false);
      window.speechSynthesis.speak(utterance);
    },
    [isSpeaking]
  );

  // Play question when it changes
  useEffect(() => {
    if (questionText && questionText !== lastSpokenRef.current && !playedRef.current) {
      if (questionAudioUrl) {
        const audio = new Audio(`${SERVER_ROOT}${questionAudioUrl}`);
        audio.play().catch(() => speak(questionText));
      } else {
        speak(questionText);
      }
      lastSpokenRef.current = questionText;
      playedRef.current = true;
    }
  }, [questionText, questionAudioUrl, speak]);

  // Recording
  const toggleRecording = () => {
    isRecording ? stopRecording() : startRecording();
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current = [];
      mediaRecorderRef.current.ondataavailable = (event) =>
        audioChunksRef.current.push(event.data);
      mediaRecorderRef.current.onstop = handleRecordingStop;
      mediaRecorderRef.current.start();
      setIsRecording(true);
      setTranscript('Listening...');
    } catch (err) {
      console.error('Mic access denied:', err);
      setTranscript('Mic access denied.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current) mediaRecorderRef.current.stop();
  };

  const handleRecordingStop = async () => {
    setIsRecording(false);
    setIsLoading(true);
    setTranscript('Processing your answer...');

    const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
    const audioFile = new File([audioBlob], 'answer.webm', { type: 'audio/webm' });
    try {
      const formData = new FormData();
      formData.append('audio', audioFile);
      formData.append('time_spent', "0.0");

      const response = await fetch(`${API_BASE}/sessions/${userDetails.session_id}/answer`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const txt = await response.text();
        throw new Error(`Failed to process audio: ${txt}`);
      }
      const data = await response.json();
      setTranscript(data.user_transcript || 'Processed answer.');

      // if backend says interview is complete, go to results
      if (data.is_complete) {
        onFinish();
        return;
      }

      // Fetch next question
      const nextQ = await fetch(`${API_BASE}/sessions/${userDetails.session_id}/question`);
      if (nextQ.ok) {
        const qData = await nextQ.json();
        setQuestionText(qData.question_text || 'Next question will appear soon.');
        setQuestionAudioUrl(qData.audio_url || null);
        playedRef.current = false;
        if (qData.is_complete) {
          onFinish();
        }
      }
    } catch (err) {
      console.error('Error sending audio:', err);
      setTranscript('Error processing your answer. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // Also add keyboard shortcut (space) to toggle recording
  useEffect(() => {
    const onKey = (e) => {
      if (e.code === "Space") {
        e.preventDefault();
        toggleRecording();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isRecording]);

  return (
    <div className="w-full h-full flex flex-col md:flex-row bg-slate-900 text-white font-sans">
      {/* AI Interviewer Panel */}
      <div className="w-full md:w-1/2 h-1/2 md:h-full flex flex-col p-4 md:p-8">
        <div className="flex-grow flex flex-col justify-center bg-slate-800/70 rounded-2xl p-6 relative backdrop-blur-sm border border-slate-700">
          <div className="absolute top-4 left-6 flex items-center gap-2 text-slate-300">
            <BrainCircuit size={20} />
            <span>AI Interviewer</span>
          </div>
          <div className="my-auto text-center">
            <p className="text-2xl lg:text-3xl leading-relaxed">{questionText}</p>
          </div>
          <div className="h-24">
            <SiriWave active={isSpeaking || isRecording} />
            <p className="text-center text-slate-400 h-5">{transcript}</p>
          </div>
        </div>
      </div>

      {/* User Panel */}
      <div className="w-full md:w-1/2 h-1/2 md:h-full flex flex-col p-4 md:p-8">
        <div className="w-full h-full bg-slate-800 rounded-2xl overflow-hidden relative flex items-center justify-center border border-slate-700">
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className={`w-full h-full object-cover transform scale-x-[-1] transition-opacity ${
              isCameraOn ? 'opacity-100' : 'opacity-0'
            }`}
          ></video>
          {!isCameraOn && (
            <div className="absolute inset-0 bg-black flex items-center justify-center">
              <User size={64} className="text-slate-600" />
            </div>
          )}
          <div className="absolute bottom-6 flex justify-center gap-4">
            <button
              onClick={() => setIsCameraOn(!isCameraOn)}
              className="p-4 bg-black/50 rounded-full backdrop-blur-sm hover:bg-white/20 transition-colors"
            >
              {isCameraOn ? <Camera size={24} /> : <CameraOff size={24} />}
            </button>
            <button
              onClick={toggleRecording}
              className={`p-4 rounded-full backdrop-blur-sm transition-colors ${
                isRecording
                  ? 'bg-red-500/90 animate-pulse'
                  : 'bg-black/50 hover:bg-white/20'
              }`}
            >
              {isRecording ? <Mic size={24} /> : <MicOff size={24} />}
            </button>
          </div>
        </div>
      </div>
      {isLoading && (
        <div className="absolute inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-purple-500"></div>
        </div>
      )}
    </div>
  );
};

// --- Main App ---
export default function App() {
  const [page, setPage] = useState('landing');
  const [userDetails, setUserDetails] = useState(null);

  const handleStart = () => setPage('details');

  const handleDetailsSubmit = async (details) => {
    try {
      const response = await fetch(`${API_BASE}/sessions`, {
        method: 'POST',
        body: JSON.stringify({ ...details, role_level: 'intermediate' }),
        headers: { 'Content-Type': 'application/json' },
      });

      if (!response.ok) throw new Error('Failed to create session');
      const data = await response.json();

      setUserDetails({ ...details, session_id: data.session_id });
      setPage('interview');
    } catch (err) {
      console.error('Failed to start interview session:', err);
    }
  };

  const onFinishInterview = () => {
    setPage('results');
  };

  const onDoneResults = () => {
    setPage('landing');
    setUserDetails(null);
  };

  return (
    <main className="h-screen w-screen font-sans">
      <style>{`
        @keyframes wave { 0%, 100% { transform: scaleY(0.4); opacity: 0.7; } 50% { transform: scaleY(1); opacity: 1; } }
        .animate-wave { animation: wave 1.2s ease-in-out infinite; }
        .bg-grid-slate-700\\/\\[0\\.2\\] { background-image: linear-gradient(to right, rgba(100, 116, 139, 0.2) 1px, transparent 1px), linear-gradient(to bottom, rgba(100, 116, 139, 0.2) 1px, transparent 1px); background-size: 2rem 2rem; }
        .animate-fade-in { animation: fadeIn 0.5s ease-out forwards; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>

      {page === 'landing' && <LandingPage onStart={handleStart} />}
      {page === 'details' && <DetailsForm onDetailsSubmit={handleDetailsSubmit} />}
      {page === 'interview' && userDetails && (
        <InterviewPage userDetails={userDetails} onFinish={onFinishInterview} />
      )}
      {page === 'results' && userDetails && (
        <ResultsPage sessionId={userDetails.session_id} onDone={onDoneResults} />
      )}
    </main>
  );
}