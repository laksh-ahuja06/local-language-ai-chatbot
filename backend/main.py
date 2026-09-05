## install line of code: pip install -r requirements.txt
# uvicorn main:app --reload to run the server
# server is live on localhost:8000

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

### Actual function imported from other files
from models import indicTrans2
from models import Qwen
# from models import indicF5
from services.pipeline import pipeline_message
from services.scheduler import start_scheduler

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    print("Loading IndicTrans2...")
        indicTrans2.load_model()
        print("IndicTrans2 loaded.")
        print("Loading Qwen...")
        Qwen.load_model()
        print("Qwen loaded.")
        print("Loading IndicF5...")
        start_scheduler ()
        # indicF5.load_model()
        # print("IndicF5 loaded.")
        print("All models loaded...")

@app.get("/")
def home():
    return {"message": "MedVoice backend is running on localhost:8000"}

class ReminderData(BaseModel):
    message: str

@app.post("/sendData")
def receive_reminder(data: ReminderData):
    print("Reminder received:", data.message)
    result = pipeline_message(data.message)
    return {
        "success": True,
        "message": "Reminder received by Python",
        "received_text": data.message,
        "result": result
    }
