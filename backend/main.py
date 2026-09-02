import torch
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from transformers import AutoModelForSequenceClassification, AutoTokenizer

### Actual function
from models import Qwen

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
    AICalling.load_model()
    print("Ready!")


@app.get("/")
def home():
    return {"message": "Server running"}


class UserData(BaseModel):
    prompt: str
    tone: str


@app.post("/sendData")
def predict(data: UserData):
    try:
        print(data.prompt)
        result = Qwen.run_model(data.prompt)
        return {result}
    except Exception as e:
        import traceback

        traceback.print_exc()
        return {"error": str(e)}
