#  Local-Language AI Chatbot For Elderly Medicine Reminders: A low-cost NLP/AI system designed for voice-first, multilingual medication support

AI models which I’ve chosen :
IndicTrans2's role — using it as a pivot-language normalizer (local language → English/Hindi → back) 
makes sense given Qwen2.5's Indic-language support is comparatively weak versus English. Keep this, 
but be aware every added hop (ASR→MT→LLM→MT→TTS) adds latency — for elderly users expecting a conversational feel, 
test end-to-end latency early, not at the end.

Qwen2.5-1.5B-Instruct for intent extraction — fine for structured JSON extraction, but for a medical use case,
don't trust it blind. Add a validation/confirmation layer: schema-check the extracted fields (drug name against
a known list, dose within sane bounds, time in valid format), and always read the parsed entry back to the user 
via TTS for confirmation before writing to MongoDB. Medicine-name misrecognition is the single biggest safety risk 
in this pipeline — ASR errors on drug names are common and consequences are real.

Frontpage: React — A React webpage only works while someone has it open in a browser tab. Elderly users won't 
keep a tab open waiting for reminders. You need a backend scheduler (e.g., node-cron or a Celery/APScheduler job) 
that fires independently of the browser and pushes the reminder through a channel that reaches them passively — a phone call 
(IVR-style, reusing your TTS), SMS, or WhatsApp, not just an in-page notification.  (Only implemented the react part yet)

<p align="center">
  <img src="medicine_reminder_architecture.svg" alt="Medicine Reminder Architecture Diagram" width="800">
</p>

### Text Recognition
For the text recognition, i've used the google built-in Web Speech API (SpeechRecognition) which captures the voice.
The voice is then converted to text in finalVariable, and later stored in the <b>transcript</b> variable. 


