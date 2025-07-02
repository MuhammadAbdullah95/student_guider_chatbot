import os
from typing import List, Dict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from fastapi.responses import Response

import chromadb
from google import genai
from chromadb.utils import embedding_functions
from google.genai.types import EmbedContentConfig

from agents import Agent, Runner, AsyncOpenAI, OpenAIChatCompletionsModel, set_tracing_disabled
from agents.run import RunConfig
from agents.tool import function_tool

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable not set.")

chroma_client = chromadb.PersistentClient(path="chroma_db")
collection = chroma_client.get_or_create_collection(name="knowledge_base1")

client = genai.Client(api_key=GOOGLE_API_KEY)

external_client = AsyncOpenAI(api_key=GOOGLE_API_KEY, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")

MODEL_NAME = "gemini-2.5-flash"
model = OpenAIChatCompletionsModel(
    model=MODEL_NAME,
    openai_client=external_client
)
config = RunConfig(model=model, model_provider=external_client, tracing_disabled=True)
set_tracing_disabled(True)

@function_tool
def get_answer(query: str):
    query_response = client.models.embed_content(
        model="models/text-embedding-004",
        contents=[query],
        config=EmbedContentConfig(task_type="RETRIEVAL_QUERY")
    )
    query_vector = query_response.embeddings[0].values
    results = collection.query(
        query_embeddings=[query_vector],
        n_results=5,
        include=["documents", "distances"]
    )
    prompt = f"Context:\n{results}\n\nQuestion:\n{query}\n\nAnswer the question using only the context above."
    resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    return resp.text

agent = Agent(
    name="Student Guide",
    instructions="You are a helpful assistant. If the user asks a question, use your tools to find information in the knowledge base and answer with that information.",
    tools=[get_answer],
)

# --- In-memory session store (for demo only!) ---
chat_sessions: Dict[str, List[Dict[str, str]]] = {}

# --- Pydantic schemas ---
class MessageInput(BaseModel):
    session_id: str = Field(..., description="Unique identifier for the chat session")
    message: str = Field(..., min_length=1, description="The user's message")

class ChatResponse(BaseModel):
    session_id: str
    response: str

# --- FastAPI app ---
app = FastAPI(
    title="Student Guider Chatbot API",
    description="API for interacting with the Student Guider chatbot."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust as needed for production
    allow_credentials=True,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

import logging
logging.basicConfig(level=logging.DEBUG)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logging.debug(f"Received request: {request.method} {request.url}")
    response = await call_next(request)
    logging.debug(f"Response status: {response.status_code}")
    return response

@app.options("/chat")
async def options_chat_endpoint():
    return Response(status_code=200)

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(payload: MessageInput):
    session_id = payload.session_id
    user_message = payload.message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="`message` cannot be empty.")

    history = chat_sessions.setdefault(session_id, [])
    history.append({"role": "user", "content": user_message})

    try:
        result = await Runner.run(
            starting_agent=agent,
            input=history,
            run_config=config
        )
        bot_reply = result.final_output or "🤖 (no reply generated)"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

    history.append({"role": "assistant", "content": bot_reply})
    print(history)
    print("Session Id is ----->", session_id)
    return ChatResponse(session_id=session_id, response=bot_reply)

@app.get("/")
def welcome():
    return {
        "message": "👋 Welcome! POST JSON `{ session_id, message }` to /chat.",
        "status": "healthy"
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "message": "Service is running"
    }












