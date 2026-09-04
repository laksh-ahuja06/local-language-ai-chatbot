## install line of code: pip install -r requirements.txt
# uvicorn app:app --reload to run the server
# server is live on localhost:8000

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from transformers import AutoModelForSequenceClassification, AutoTokenizer

### Actual function imported from other files
from models import indicTrans2
from models import Qwen
from models import indicF5

app = FastAPI()

tokenizer = None
model = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    print("Loading model...")
    # Qwen.load_model()
    print("Ready!")

@app.get("/")
def home():
    return {"message": "MedVoice backend is running on localhost:8000"}

class ReminderData(BaseModel):
    message: str

@app.post("/sendData")
def receive_reminder(data: ReminderData):
    print("Reminder received:", data.message)

    return {
        "success": True,
        "message": "Reminder received by Python",
        "received_text": data.message
    }
