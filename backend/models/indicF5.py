## install these in terminal
# conda create -n indicf5 python=3.10 -y
# conda activate indicf5
# pip install git+https://github.com/ai4bharat/IndicF5.git
# pip install git+https://github.com/madhav165/IndicF5.git@main

from transformers import AutoModel
import numpy as np
import soundfile as sf

# Hugging Face model
repo_id = "ai4bharat/IndicF5"
# Model will be stored here
model = None

def load_model():
    global model
    print("Loading IndicF5...")
    model = AutoModel.from_pretrained(
        repo_id,
        trust_remote_code=True
    )
    print("IndicF5 loaded successfully.")

def text_to_speech(prompt):
    if model is None:
        raise RuntimeError("IndicF5 model has not been loaded.")
    # Generate speech
    audio = model(
        prompt,
        ref_audio_path="prompts/PAN_F_HAPPY_00001.wav",
        ref_text="ਭਹੰਪੀ ਵਿੱਚ ਸਮਾਰਕਾਂ ਦੇ ਭਵਨ ਨਿਰਮਾਣ ਕਲਾ ਦੇ ਵੇਰਵੇ ਗੁੰਝਲਦਾਰ ਅਤੇ ਹੈਰਾਨ ਕਰਨ ਵਾਲੇ ਹਨ, ਜੋ ਮੈਨੂੰ ਖੁਸ਼ ਕਰਦੇ ਹਨ।"
    )
    # Normalize and save output
    if audio.dtype == np.int16:
        audio = audio.astype(np.float32) / 32768.0
    sf.write(
        "namaste.wav",
        np.array(audio, dtype=np.float32),
        samplerate=24000
    )
    print("Audio saved successfully.")
    return "namaste.wav"


load_model ()
text_to_speech ("नमस्ते, यह आपकी दवा लेने का समय है। कृपया एक पैरासिटामोल की गोली लें।")
