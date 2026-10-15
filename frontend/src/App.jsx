import React, { useEffect, useRef, useState } from "react";
import "./styles.css";
import {Activity,CalendarClock,CheckCircle2,Clock,Globe2,HeartPulse,History,Languages,Mic,MicOff,Pill,Repeat,RotateCcw,Send,Trash2,Volume2,XCircle} from "lucide-react";

// Languages the backend can translate (code is used for speech recognition AND sent to the backend)
const LANGUAGES = [
  { label: "हिन्दी", name: "Hindi", code: "hi-IN" },
  { label: "தமிழ்", name: "Tamil", code: "ta-IN" },
  { label: "తెలుగు", name: "Telugu", code: "te-IN" },
  { label: "বাংলা", name: "Bengali", code: "bn-IN" },
];

// Python backend (uvicorn listens on IPv4 only, so avoid "localhost" which can resolve to IPv6)
const API_URL = "http://127.0.0.1:8000";

// How often to retry while the backend is still starting up (loading models)
const RETRY_DELAY_MS = 2000;

// "daily" -> "Every day", "every monday" -> "Every Monday", "next 5 days" -> "Next 5 days"
function formatFrequency(frequency = "") {
  const text = frequency.trim().toLowerCase();

  if (["daily", "everyday", "every day"].includes(text)) {
    return "Every day";
  }

  const weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];

  const words = text.split(/\s+/).map((word) =>
    weekdays.includes(word) ? word[0].toUpperCase() + word.slice(1) : word
  );

  const sentence = words.join(" ");

  return sentence.charAt(0).toUpperCase() + sentence.slice(1);
}

function App() {

  // Set the usestate variables
  const [language, setLanguage] = useState(LANGUAGES[0]);
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [interim, setInterim] = useState("");
  const [message, setMessage] = useState("Tap the microphone and speak naturally.");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const recognitionRef = useRef(null);
  const [reminders, setReminders] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);

  // check browser support
  const supported =
    typeof window !== "undefined" &&
    ("SpeechRecognition" in window ||
      "webkitSpeechRecognition" in window);

  // Take data from mongoDB
  // Keeps retrying until the backend is ready (it only starts answering after the models load)
  useEffect(() => {
    let cancelled = false;
    let retryTimer = null;
    let attempt = 0;

    const loadReminders = async () => {
      attempt += 1;

      try {
        const res = await fetch(`${API_URL}/reminders`);
        const data = await res.json();

        if (cancelled) return;

        if (data.success) {
          setReminders(data.reminders);

          if (attempt > 1) {
            console.info(`Backend ready, reminders loaded after ${attempt} attempts.`);
          }
        }

      } catch (error) {
        if (cancelled) return;

        // Log only the first failure so the console isn't flooded while waiting
        if (attempt === 1) {
          console.warn("Backend not ready yet, retrying every 2s...", error);
        }

        retryTimer = setTimeout(loadReminders, RETRY_DELAY_MS);
      }
    };

    loadReminders();

    // Stop retrying if the component unmounts
    return () => {
      cancelled = true;
      clearTimeout(retryTimer);
    };
  }, []);

  // Cleanup after every refresh
  useEffect(() => {
    return () => {
      recognitionRef.current?.stop();
    };
  }, []);

  // Start listening
  function startListening() {
    setError("");
    setSaved(false);

    if (!supported) {
      setError(
        "Voice input is not supported in this browser. Please use Google Chrome or Microsoft Edge."
      );
      return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.lang = language.code;
    recognition.continuous = false; // Stop after speech ends
    recognition.interimResults = true; // Show words while speaking
    recognition.maxAlternatives = 1;

    recognition.onstart = () => { // Start listening
      setListening(true);

      setMessage(
        "Listening… speak your medicine and reminder time."
      );
    };

    recognition.onresult = (event) => { // Speech result
      let finalText = "";
      let interimText = "";

      for (
        let i = event.resultIndex;
        i < event.results.length;
        i++
      ) {
        const text = event.results[i][0].transcript;

        if (event.results[i].isFinal) {
          finalText += text;
        } else {
          interimText += text;
        }
      }

      // Final speech
      if (finalText) {
        setTranscript((previous) =>
          `${previous} ${finalText}`.trim()
        );

        setMessage(
          "I heard you. Please check the words before confirming."
        );
      }

      // Temporary speech
      setInterim(interimText);
    };


    recognition.onerror = (event) => {
      setListening(false);

      setInterim("");

      const errors = {
        "not-allowed": "Microphone permission was denied. Please allow microphone access.",
        "no-speech": "I didn't hear anything. Please try again.",
        "audio-capture": "No microphone was found. Please check your microphone.",
      };

      setError(
        errors[event.error] ||
          `Voice input error: ${event.error}, Switch to google or safari`
      );
    };


    recognition.onend = () => {
      setListening(false);
      setInterim("");
      recognitionRef.current = null;
    };
    recognitionRef.current = recognition;
    recognition.start();
  }


  function stopListening() {
    recognitionRef.current?.stop();
    setListening(false);
    setMessage("Voice input stopped.");
  }


  function clearTranscript() {
    setTranscript("");
    setInterim("");
    setError("");
    setSaved(false);
    setMessage("Tap the microphone and speak naturally.");
  }


  function saveReminder() {
    if (!transcript.trim()) {
      setError(
        "Please speak a reminder first."
      );
      return;
    }
    setSaved(true);
    setMessage("Reminder captured successfully. Backend scheduling will be connected next.");
  }

  function speakBack() {
    if (
      !transcript.trim() ||
      !("speechSynthesis" in window)
    ) {
      return;
    }

    window.speechSynthesis.cancel();

    const utterance =
      new SpeechSynthesisUtterance(
        `I heard: ${transcript}. Please confirm this reminder.`
      );
    utterance.lang = language.code;
    window.speechSynthesis.speak(utterance);
  }

  // Connect to python server:-
  // Press Confirm reminder button to send text to backend
  const confirmReminder = async () => {
    setIsProcessing(true);

    try {
      const res = await fetch(`${API_URL}/sendData`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: transcript,
          language: language.code,
        }),
      });

      const data = await res.json();

      console.log("Python response:", data);

      if (data.success) {
        // Fetch the updated reminders from MongoDB
        const remindersRes = await fetch(
          `${API_URL}/reminders`
        );

        const remindersData = await remindersRes.json();

        if (remindersData.success) {
          setReminders(remindersData.reminders);
        }
      } else {
        // Show the backend's explanation (e.g. "I couldn't understand the time ...")
        setError(data.message || "Sorry, I couldn't set that reminder. Please try again.");
      }

    } catch (error) {
      console.error("Error sending reminder:", error);
      setError("Couldn't reach the server. Please check the backend is running.");

    } finally {
      // Processing is finished
      setIsProcessing(false);
    }
  };

  // Delete button for reminders
  const deleteReminder = async (id) => {
    try {
      const res = await fetch(
        `${API_URL}/reminders/${id}`,
        {
          method: "DELETE",
        }
      );

      const data = await res.json();

      if (data.success) {
        setReminders((prevReminders) =>
          prevReminders.filter(
            (reminder) => reminder._id !== id
          )
        );
      }
    } catch (error) {
      console.error("Error deleting reminder:", error);
    }
  };

  return (
    <div className="app-shell">

      {/* Navigation bar */}

      <header className="topbar">
        <div className="brand">
          <div className="brand-icon">
            <HeartPulse size={25} />
          </div>
          <div>
            <div className="brand-name">
              MedVoice
            </div>
            <div className="brand-subtitle">
              Medication reminders made simple
            </div>
          </div>
        </div>

        {/* Language selector */}
        <div className="top-actions">
          <div className="language-control">
            <Languages size={19} />

            {/* Sliding language picker */}
            <div
              className="language-slider"
              role="radiogroup"
              aria-label="Speaking language"
              style={{
                "--option-count": LANGUAGES.length,
                "--active-index": LANGUAGES.findIndex(
                  (item) => item.code === language.code
                ),
              }}
            >
              <span className="language-slider-thumb" aria-hidden="true" />

              {LANGUAGES.map((item) => (
                <button
                  key={item.code}
                  type="button"
                  role="radio"
                  aria-checked={item.code === language.code}
                  title={item.name}
                  className={
                    item.code === language.code
                      ? "language-option active"
                      : "language-option"
                  }
                  disabled={listening || isProcessing}
                  onClick={() => setLanguage(item)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </header>

      <main>
        <section className="hero">
          <div className="hero-copy">
            <span className="eyebrow">
              <Activity size={15} /> Voice-first health assistant </span>

            <h1>
              Tell me your
              <br />
              <span> medicine reminder. </span>
            </h1>

            <p>
              Speak in your preferred language. You can say something like {" "}
              <strong> "Remind me to take my medicine at 8 AM."</strong>
            </p>
          </div>

          {/* Main microphone */}
          <div className={`voice-card ${listening ? "is-listening" : "" }`} >

            <div className="voice-orbit orbit-one"></div>
            <div className="voice-orbit orbit-two"></div>

            <button
              className="mic-button"
              onClick={listening ? stopListening : startListening}
              aria-label={listening ? "Stop listening" : "Start voice input"}
              >

              {listening ? ( <MicOff size={42} />) : (<Mic size={42} />)}
            </button>

            <div className="voice-status">
              <span
                className={`status-dot ${listening ? "active" : ""}`}
              ></span>
              {listening ? "Listening…" : "Tap to speak"}
            </div>
          </div>
        </section>

        {/* Workspace */}

        <section className="workspace">
          <div className="panel transcript-panel"> {/* Your voice */}
            <div className="panel-heading">
              <div>
                <span className="panel-kicker">
                  STEP 01
                </span>
                <h2>
                  Your voice
                </h2>
              </div>
              <button className="small-button" onClick={clearTranscript} title="Clear transcript">
                <RotateCcw size={17} />
                Clear
              </button>
            </div>

            {/* Transcript box */}
            <div
              className={`transcript-box ${!transcript && !interim ? "empty" : ""}`}>

              {transcript || interim ? (
                <>
                  <p> {transcript} </p>
                  {interim && (
                    <p className="interim"> {interim} </p>
                  )}
                </>
              ) : (
                <>
                  <Mic size={25} />
                  <span>
                    Your spoken message
                    will appear here.
                  </span>
                </>
              )}
            </div>

            <input
              type="text"
              className="text-input"
              value={transcript}
              onChange={(e) => setTranscript(e.target.value)}
              placeholder="Add text input"
            />

            <br></br><br></br>

            <div className="voice-tools">  {/* Action buttons */}
              <button
                className="secondary-button"
                onClick={speakBack}
                disabled={!transcript}
              >

                <Volume2 size={18} />
                Read back
              </button>

              <button
                className="primary-button"
                onClick={confirmReminder}
                disabled={isProcessing}>
                <Send size={18} />  {isProcessing ? "⏳ Processing..." : "✈ Confirm reminder"}
              </button>
            </div>

            {isProcessing && (
              <div className="processing-message">
                ⏳ Processing your reminder...
              </div>
            )}

            {error && (
              <div className="alert error">  {/* ERROR */}
                <XCircle size={19} />
                {error}
              </div>
            )}

            {saved && (
              <div className="alert success">   {/* SUCCESS */}
                <CheckCircle2
                  size={19}
                />
                {message}
              </div>
            )}
          </div>

          <div className="panel guidance-panel"> {/* How to use guidelines */}
            <div className="panel-heading">
              <div>
                <span className="panel-kicker">
                  HOW TO USE
                </span>
                <h2>
                  Just speak naturally
                </h2>
              </div>

              <div className="round-icon">
                <Globe2 size={19} />
              </div>

            </div>
            <div className="examples">
              <div className="example"> {/* EXAMPLE 1 */}
                <span>
                  01
                </span>
                <div>
                  <strong>
                    Medicine
                  </strong>
                  <p>
                    "I need to take Amlodipine."
                  </p>
                </div>
              </div>
              <div className="example">  {/* EXAMPLE 2 */}
                <span>
                  02
                </span>
                <div>
                  <strong>
                    Time
                  </strong>
                  <p>
                    "Remind me at eight in the morning."
                  </p>

                </div>
              </div>
              <div className="example">  {/* EXAMPLE 3 */}
                <span>
                  03
                </span>
                <div>
                  <strong>
                    Language
                  </strong>
                  <p>
                    Choose your language above before speaking.
                  </p>
                </div>
              </div>
            </div>
            <div className="privacy-note">  {/* ELDERLY USER NOTE */}
              <Pill size={19} />
              <div>
                <strong>
                  Designed for older
                  adults
                </strong>
                <p>
                  Large controls,
                  simple language and
                  voice-first interaction.
                </p>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Saved reminders from MongoDB */}
      <section className="schedule panel">
        <div className="panel-heading">
          <div>
            <span className="panel-kicker">
              YOUR SCHEDULE
            </span>
            <h2>
              Active reminders
            </h2>
          </div>

          <span className="reminder-count">
            {reminders.length} {reminders.length === 1 ? "reminder" : "reminders"}
          </span>
        </div>

        {reminders.length === 0 ? (
          <div className="schedule-empty">
            <div className="round-icon">
              <CalendarClock size={19} />
            </div>
            <p>
              No reminders yet. Tap the microphone above and say your first one.
            </p>
          </div>
        ) : (
          <div className="reminders-container">
            {reminders.map((reminder) => (
              <article className="reminder-card" key={reminder._id}>
                <div className="reminder-card-top">
                  <div className="round-icon">
                    <Pill size={18} />
                  </div>

                  <div className="reminder-card-title">
                    <h3>{reminder.medicine}</h3>
                    <span>{reminder.dose}</span>
                  </div>
                </div>

                <div className="reminder-chips">
                  <span className="reminder-chip">
                    <Clock size={14} />
                    {reminder.time}
                  </span>
                  <span className="reminder-chip">
                    <Repeat size={14} />
                    {formatFrequency(reminder.frequency)}
                  </span>
                </div>

                <button
                  type="button"
                  className="reminder-delete"
                  aria-label={`Delete ${reminder.medicine} reminder`}
                  onClick={() => deleteReminder(reminder._id)}
                >
                  <Trash2 size={15} />
                  Delete
                </button>
              </article>
            ))}
          </div>
        )}
      </section>

      <footer>
        <span>
          MedVoice · Voice-first
          medication support
        </span>
      </footer>

    </div>
  );
}

export default App;
