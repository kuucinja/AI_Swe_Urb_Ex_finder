from fastapi import FastAPI
from pydantic import BaseModel
from backend.central_agent import run_agent
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    locations: list = []

@app.post("/chat")
def chat(req: ChatRequest):
    result = run_agent(req.message, req.locations)
    return result