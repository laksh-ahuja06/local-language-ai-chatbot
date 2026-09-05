import React, { useEffect, useRef, useState } from "react";
import "./styles.css";
import {Activity,CheckCircle2,Globe2,HeartPulse,History,Languages,Mic,MicOff,Pill,RotateCcw,Send,Volume2,XCircle} from "lucide-react";

const LANGUAGES = [
  { label: "English", code: "en-IN" },
  { label: "हिन्दी", code: "hi-IN" },
  { label: "தமிழ்", code: "ta-IN" },
  { label: "తెలుగు", code: "te-IN" },
  { label: "বাংলা", code: "bn-IN" },
  { label: "मराठी", code: "mr-IN" },
];

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
  useEffect(() => {
    fetch("http://localhost:8000/reminders")
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          setReminders(data.reminders);
        }
      })
      .catch((error) => {
        console.error("Error fetching reminders:", error);
      });
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
      const res = await fetch("http://localhost:8000/sendData", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: transcript,
        }),
      });

      const data = await res.json();

      console.log("Python response:", data);

      if (data.success) {
        // Fetch the updated reminders from MongoDB
        const remindersRes = await fetch(
          "http://localhost:8000/reminders"
        );

        const remindersData = await remindersRes.json();

        if (remindersData.success) {
          setReminders(remindersData.reminders);
        }
      }

    } catch (error) {
      console.error("Error sending reminder:", error);

    } finally {
      // Processing is finished
      setIsProcessing(false);
    }
  };

  // Delete button for reminders
  const deleteReminder = async (id) => {
    try {
      const res = await fetch(
        `http://localhost:8000/reminders/${id}`,
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
          <label className="language-control">
            <Languages size={19} />

            <select
              value={language.code}
              onChange={(e) => {
                const selected =
                  LANGUAGES.find(
                    (item) => item.code === e.target.value);
                setLanguage(selected);
              }}
            >
              {LANGUAGES.map((item) => (
                <option key={item.code} value={item.code}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
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

      <div className="reminders-container">
        {reminders.map((reminder) => (
          <div className="reminder-card" key={reminder._id}>
            <h3>{reminder.medicine}</h3>
            <p>
              <strong>Dose:</strong> {reminder.dose}
            </p>
            <p>
              <strong>Time:</strong> {reminder.time}
            </p>
            <p>
              <strong>Frequency:</strong> {reminder.frequency}
            </p>
            <button
              onClick={() => deleteReminder(reminder._id)}
            > Delete
            </button>
          </div>
        ))}
      </div>

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
