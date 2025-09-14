import React, { useState, useRef, useEffect } from "react";
import { Mic, Send, MicOff, Volume2 } from "lucide-react";

const API_BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000/api";
const SPEECH_SETTINGS = { lang: "en-US", rate: 0.9, pitch: 1 };

// 🎵 Audio Visualization
const AudioWaveform = ({ isRecording, isActive }) => {
  const [levels, setLevels] = useState(Array(8).fill(0.1));

  useEffect(() => {
    let animationId;
    if (isRecording || isActive) {
      const animate = () => {
        setLevels(prev => prev.map(() => Math.random() * 0.8 + 0.2));
        animationId = requestAnimationFrame(animate);
      };
      animate();
    } else {
      setLevels(Array(8).fill(0.1));
    }
    return () => animationId && cancelAnimationFrame(animationId);
  }, [isRecording, isActive]);

  return (
    <div className="flex items-center justify-center space-x-1 h-16">
      {levels.map((level, i) => (
        <div
          key={i}
          className={`w-1 rounded-full transition-all duration-150 ${
            isRecording || isActive
              ? "bg-gradient-to-t from-purple-500 via-purple-400 to-pink-400 opacity-100"
              : "bg-purple-500/40 opacity-30"
          }`}
          style={{ height: `${Math.max(4, level * 40)}px` }}
        />
      ))}
    </div>
  );
};

// 🎤 Mic Button
const FloatingMicButton = ({ isRecording, onClick }) => (
  <div className="relative">
    <button
      onClick={onClick}
      className={`relative w-16 h-16 rounded-full flex items-center justify-center transition-all transform hover:scale-105 ${
        isRecording
          ? "bg-red-500 shadow-lg shadow-red-500/50"
          : "bg-gradient-to-br from-purple-500 to-pink-500 shadow-lg shadow-purple-500/50"
      }`}
    >
      {isRecording ? <MicOff className="w-6 h-6 text-white" /> : <Mic className="w-6 h-6 text-white" />}
      {isRecording && (
        <>
          <div className="absolute inset-0 rounded-full bg-red-500 animate-ping opacity-75" />
          <div className="absolute inset-0 rounded-full bg-red-400 animate-pulse opacity-50" />
        </>
      )}
    </button>
    <div className="absolute -inset-4 rounded-full bg-white/10 backdrop-blur-sm border border-white/20" />
  </div>
);

function App() {
  const [question, setQuestion] = useState("🎤 Click the mic or type to begin your Excel interview.");
  const [userAnswer, setUserAnswer] = useState("");
  const [transcription, setTranscription] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  // 🔊 Speak Question
  const speak = (text) => {
    if (!window.speechSynthesis) return;
    const utterance = new SpeechSynthesisUtterance(text);
    Object.assign(utterance, SPEECH_SETTINGS);

    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);

    window.speechSynthesis.speak(utterance);
  };

  // 🎙 Start Recording
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (e) => audioChunksRef.current.push(e.data);

      mediaRecorderRef.current.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/wav" });
        await transcribeAudio(audioBlob);
        stream.getTracks().forEach((t) => t.stop());
      };

      mediaRecorderRef.current.start();
      setIsRecording(true);
    } catch (err) {
      alert("🎙 Microphone access denied. Please allow permissions.");
    }
  };

  // ⏹ Stop Recording
  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  // 🔁 Transcribe Speech → Text
  const transcribeAudio = async (audioBlob) => {
    setIsLoading(true);
    try {
      const formData = new FormData();
      formData.append("audio", audioBlob, "recording.wav");
      const res = await fetch(`${API_BASE_URL}/transcribe`, { method: "POST", body: formData });
      if (!res.ok) throw new Error();
      const { transcription } = await res.json();
      setTranscription(transcription);
      setUserAnswer(transcription);
    } catch {
      setTranscription("⚠️ Demo transcription - backend not connected.");
      setUserAnswer("Demo transcription - backend not connected.");
    } finally {
      setIsLoading(false);
    }
  };

  // 📤 Submit Answer
  const handleSubmit = async () => {
    if (!userAnswer.trim()) return alert("✍️ Please provide an answer first!");
    setIsLoading(true);

    try {
      const res = await fetch(`${API_BASE_URL}/answer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answer: userAnswer }),
      });
      if (!res.ok) throw new Error();

      const data = await res.json();
      if (data.next_question) {
        setQuestion(data.next_question);
        speak(data.next_question);
      } else {
        setQuestion("✅ Interview complete! Check your results.");
      }
      setUserAnswer("");
      setTranscription("");
    } catch {
      // Demo fallback
      const demoQs = [
        "What does VLOOKUP do?",
        "How do you build a Pivot Table?",
        "Difference between absolute & relative references?",
        "✅ Demo interview complete! Great job!"
      ];
      const q = demoQs[Math.floor(Math.random() * demoQs.length)];
      setQuestion(q);
      speak(q);
      setUserAnswer("");
      setTranscription("");
    } finally {
      setIsLoading(false);
    }
  };

  // 🚀 Start Interview
  const startInterview = () => {
    const q = "Let's begin! Can you tell me about your experience with Excel formulas?";
    setQuestion(q);
    speak(q);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 relative overflow-hidden">
      {/* Background */}
      <div className="absolute inset-0 opacity-30">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-purple-500 rounded-full blur-xl animate-pulse"></div>
        <div className="absolute top-1/3 right-1/4 w-96 h-96 bg-pink-500 rounded-full blur-xl animate-pulse delay-2000"></div>
        <div className="absolute bottom-1/4 left-1/3 w-96 h-96 bg-indigo-500 rounded-full blur-xl animate-pulse delay-4000"></div>
      </div>

      {/* Main Card */}
      <div className="relative z-10 flex flex-col items-center justify-center min-h-screen p-6">
        <div className="bg-white/10 backdrop-blur-lg rounded-3xl shadow-2xl p-8 w-full max-w-2xl border border-white/20">
          {/* Header */}
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
              AI Excel Interviewer
            </h1>
            <p className="text-gray-300">Practice your Excel skills with AI-powered interviews</p>
          </div>

          {/* Question */}
          <div className="bg-white/5 border border-white/10 rounded-2xl p-6 mb-6">
            <div className="flex items-start gap-3">
              {isSpeaking && <Volume2 className="w-5 h-5 text-purple-400 animate-pulse mt-1" />}
              <p className="text-white leading-relaxed flex-1">{question}</p>
            </div>
          </div>

          {/* Waveform */}
          {(isRecording || isSpeaking) && (
            <div className="flex justify-center mb-6">
              <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
                <AudioWaveform isRecording={isRecording} isActive={isSpeaking} />
                <p className="text-center text-gray-300 text-sm mt-2">
                  {isRecording ? "Listening..." : "Speaking..."}
                </p>
              </div>
            </div>
          )}

          {/* Answer */}
          <textarea
            value={userAnswer}
            onChange={(e) => setUserAnswer(e.target.value)}
            placeholder="Type or speak your answer..."
            className="w-full p-4 bg-white/10 border border-white/20 rounded-2xl text-white placeholder-gray-400 focus:ring-2 focus:ring-purple-500 focus:outline-none mb-6"
            rows="4"
          />

          {/* Transcription */}
          {transcription && (
            <div className="bg-purple-500/20 border border-purple-400/30 rounded-xl p-4 mb-6">
              <div className="flex items-center gap-2 mb-2">
                <Mic className="w-4 h-4 text-purple-400" />
                <span className="text-purple-300 text-sm font-medium">Voice Input:</span>
              </div>
              <p className="text-white text-sm">{transcription}</p>
            </div>
          )}

          {/* Buttons */}
          <div className="flex flex-col sm:flex-row gap-4 items-center justify-center">
            <FloatingMicButton
              isRecording={isRecording}
              onClick={isRecording ? stopRecording : startRecording}
            />
            <button
              onClick={handleSubmit}
              disabled={isLoading || !userAnswer.trim()}
              className="flex items-center gap-3 bg-gradient-to-r from-green-500 to-green-600 text-white px-6 py-3 rounded-2xl hover:scale-105 transition disabled:opacity-50 shadow-lg"
            >
              <Send className="w-5 h-5" />
              {isLoading ? "Processing..." : "Submit"}
            </button>
            {question.includes("begin") && (
              <button
                onClick={startInterview}
                className="flex items-center gap-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white px-6 py-3 rounded-2xl hover:scale-105 transition shadow-lg"
              >
                🚀 Start Interview
              </button>
            )}
          </div>
        </div>

        {/* Tips */}
        <div className="mt-8 text-center max-w-md">
          <p className="text-gray-400 text-sm">
            💡 <strong>Tip:</strong> Use the 🎤 mic or type your answer. AI adapts follow-ups based on you.
          </p>
        </div>
      </div>
    </div>
  );
}

export default App;
