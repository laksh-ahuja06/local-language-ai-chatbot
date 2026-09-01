import React, { useEffect, useRef, useState } from "react";
import "./styles.css";
import {
  Activity,
  CheckCircle2,
  Globe2,
  HeartPulse,
  History,
  Languages,
  Mic,
  MicOff,
  Pill,
  RotateCcw,
  Send,
  Volume2,
  XCircle,
} from "lucide-react";

const LANGUAGES = [
  { label: "English", code: "en-IN" },
  { label: "हिन्दी", code: "hi-IN" },
  { label: "தமிழ்", code: "ta-IN" },
  { label: "తెలుగు", code: "te-IN" },
  { label: "বাংলা", code: "bn-IN" },
  { label: "मराठी", code: "mr-IN" },
];

function App() {
  // =========================
  // STATE
  // =========================

  const [language, setLanguage] = useState(
    LANGUAGES[0]
  );

  const [listening, setListening] = useState(false);

  const [transcript, setTranscript] = useState("");

  const [interim, setInterim] = useState("");

  const [message, setMessage] = useState(
    "Tap the microphone and speak naturally."
  );

  const [error, setError] = useState("");

  const [saved, setSaved] = useState(false);

  const recognitionRef = useRef(null);

  // =========================
  // BROWSER SUPPORT
  // =========================

  const supported =
    typeof window !== "undefined" &&
    ("SpeechRecognition" in window ||
      "webkitSpeechRecognition" in window);

  // =========================
  // CLEANUP
  // =========================

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop();
    };
  }, []);

  // =========================
  // START LISTENING
  // =========================

  function startListening() {
    setError("");
    setSaved(false);

    if (!supported) {
      setError(
        "Voice input is not supported in this browser. Please use Google Chrome or Microsoft Edge."
      );

      return;
    }

    const SpeechRecognition =
      window.SpeechRecognition ||
      window.webkitSpeechRecognition;

    const recognition =
      new SpeechRecognition();

    // Selected language
    recognition.lang = language.code;

    // Stop after speech ends
    recognition.continuous = false;

    // Show words while speaking
    recognition.interimResults = true;

    recognition.maxAlternatives = 1;

    // =========================
    // LISTENING STARTED
    // =========================

    recognition.onstart = () => {
      setListening(true);

      setMessage(
        "Listening… speak your medicine and reminder time."
      );
    };

    // =========================
    // SPEECH RESULT
    // =========================

    recognition.onresult = (event) => {
      let finalText = "";

      let interimText = "";

      for (
        let i = event.resultIndex;
        i < event.results.length;
        i++
      ) {
        const text =
          event.results[i][0].transcript;

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

    // =========================
    // ERROR
    // =========================

    recognition.onerror = (event) => {
      setListening(false);

      setInterim("");

      const errors = {
        "not-allowed":
          "Microphone permission was denied. Please allow microphone access.",

        "no-speech":
          "I didn't hear anything. Please try again.",

        "audio-capture":
          "No microphone was found. Please check your microphone.",
      };

      setError(
        errors[event.error] ||
          `Voice input error: ${event.error}`
      );
    };

    // =========================
    // LISTENING ENDED
    // =========================

    recognition.onend = () => {
      setListening(false);

      setInterim("");

      recognitionRef.current = null;
    };

    recognitionRef.current = recognition;

    recognition.start();
  }

  // =========================
  // STOP LISTENING
  // =========================

  function stopListening() {
    recognitionRef.current?.stop();

    setListening(false);

    setMessage("Voice input stopped.");
  }

  // =========================
  // CLEAR
  // =========================

  function clearTranscript() {
    setTranscript("");

    setInterim("");

    setError("");

    setSaved(false);

    setMessage(
      "Tap the microphone and speak naturally."
    );
  }

  // =========================
  // CONFIRM REMINDER
  // =========================

  function saveReminder() {
    if (!transcript.trim()) {
      setError(
        "Please speak a reminder first."
      );

      return;
    }

    setSaved(true);

    setMessage(
      "Reminder captured successfully. Backend scheduling will be connected next."
    );
  }

  // =========================
  // READ BACK
  // =========================

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

    window.speechSynthesis.speak(
      utterance
    );
  }

  // =========================
  // UI
  // =========================

  return (
    <div className="app-shell">

      {/* ==================================
          NAVIGATION BAR
      ================================== */}

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

        {/* LANGUAGE SELECTOR */}

        <div className="top-actions">

          <label className="language-control">

            <Languages size={19} />

            <select
              value={language.code}
              onChange={(e) => {
                const selected =
                  LANGUAGES.find(
                    (item) =>
                      item.code ===
                      e.target.value
                  );

                setLanguage(selected);
              }}
            >

              {LANGUAGES.map((item) => (

                <option
                  key={item.code}
                  value={item.code}
                >
                  {item.label}
                </option>

              ))}

            </select>

          </label>

        </div>

      </header>

      <main>

        {/* ==================================
            HERO
        ================================== */}

        <section className="hero">

          {/* LEFT SIDE */}

          <div className="hero-copy">

            <span className="eyebrow">

              <Activity size={15} />

              Voice-first health assistant

            </span>

            <h1>

              Tell me your
              <br />

              <span>
                medicine reminder.
              </span>

            </h1>

            <p>

              Speak in your preferred
              language. You can say
              something like{" "}

              <strong>
                "Remind me to take my
                medicine at 8 AM."
              </strong>

            </p>

          </div>

          {/* ==================================
              MICROPHONE
          ================================== */}

          <div
            className={`voice-card ${
              listening
                ? "is-listening"
                : ""
            }`}
          >

            <div className="voice-orbit orbit-one"></div>

            <div className="voice-orbit orbit-two"></div>

            <button
              className="mic-button"
              onClick={
                listening
                  ? stopListening
                  : startListening
              }
              aria-label={
                listening
                  ? "Stop listening"
                  : "Start voice input"
              }
            >

              {listening ? (
                <MicOff size={42} />
              ) : (
                <Mic size={42} />
              )}

            </button>

            <div className="voice-status">

              <span
                className={`status-dot ${
                  listening
                    ? "active"
                    : ""
                }`}
              ></span>

              {listening
                ? "Listening…"
                : "Tap to speak"}

            </div>

          </div>

        </section>

        {/* ==================================
            WORKSPACE
        ================================== */}

        <section className="workspace">

          {/* ==================================
              YOUR VOICE
          ================================== */}

          <div className="panel transcript-panel">

            <div className="panel-heading">

              <div>

                <span className="panel-kicker">
                  STEP 01
                </span>

                <h2>
                  Your voice
                </h2>

              </div>

              <button
                className="small-button"
                onClick={
                  clearTranscript
                }
                title="Clear transcript"
              >

                <RotateCcw size={17} />

                Clear

              </button>

            </div>

            {/* TRANSCRIPT BOX */}

            <div
              className={`transcript-box ${
                !transcript &&
                !interim
                  ? "empty"
                  : ""
              }`}
            >

              {transcript ||
              interim ? (

                <>

                  <p>
                    {transcript}
                  </p>

                  {interim && (

                    <p className="interim">
                      {interim}
                    </p>

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

            {/* ==================================
                ACTION BUTTONS
            ================================== */}

            <div className="voice-tools">

              {/* READ BACK */}

              <button
                className="secondary-button"
                onClick={
                  speakBack
                }
                disabled={
                  !transcript
                }
              >

                <Volume2 size={18} />

                Read back

              </button>

              {/* CONFIRM */}

              <button
                className="primary-button"
                onClick={
                  saveReminder
                }
                disabled={
                  !transcript
                }
              >

                <Send size={18} />

                Confirm reminder

              </button>

            </div>

            {/* ERROR */}

            {error && (

              <div className="alert error">

                <XCircle size={19} />

                {error}

              </div>

            )}

            {/* SUCCESS */}

            {saved && (

              <div className="alert success">

                <CheckCircle2
                  size={19}
                />

                {message}

              </div>

            )}

          </div>

          {/* ==================================
              HOW TO USE
          ================================== */}

          <div className="panel guidance-panel">

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

            {/* EXAMPLES */}

            <div className="examples">

              {/* EXAMPLE 1 */}

              <div className="example">

                <span>
                  01
                </span>

                <div>

                  <strong>
                    Medicine
                  </strong>

                  <p>
                    "I need to take
                    Amlodipine."
                  </p>

                </div>

              </div>

              {/* EXAMPLE 2 */}

              <div className="example">

                <span>
                  02
                </span>

                <div>

                  <strong>
                    Time
                  </strong>

                  <p>
                    "Remind me at
                    eight in the
                    morning."
                  </p>

                </div>

              </div>

              {/* EXAMPLE 3 */}

              <div className="example">

                <span>
                  03
                </span>

                <div>

                  <strong>
                    Language
                  </strong>

                  <p>
                    Choose your
                    language above
                    before speaking.
                  </p>

                </div>

              </div>

            </div>

            {/* ELDERLY USER NOTE */}

            <div className="privacy-note">

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

        {/* ==================================
            DISCLAIMER
        ================================== */}

        <p className="disclaimer">

          <strong>
            Prototype:
          </strong>{" "}

          This frontend currently
          captures and reads voice
          directly in the browser.

          Medication parsing,
          validation, database storage,
          scheduling and delivery will
          be connected to the backend
          later.

        </p>

      </main>

      {/* ==================================
          FOOTER
      ================================== */}

      <footer>

        <span>
          MedVoice · Voice-first
          medication support
        </span>

        <span className="footer-right">

          <History size={15} />

          Frontend prototype

        </span>

      </footer>

    </div>
  );
}

export default App;
