import json
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.concurrency import iterate_in_threadpool, run_in_threadpool

from app.services import agent_client, blob_service
from app.telemetry import setup_telemetry

setup_telemetry()


@asynccontextmanager
async def lifespan(app: FastAPI):
    agent_client.startup()
    blob_service.startup()
    yield
    agent_client.shutdown()
    blob_service.shutdown()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _chat_stream(message: str, conversation_id: Optional[str]):
    if not conversation_id:
        conversation_id = agent_client.create_conversation()
    yield _sse("meta", {"conversation_id": conversation_id})
    for delta in agent_client.stream_reply(message, conversation_id):
        yield _sse("delta", {"text": delta})
    yield _sse("done", {})


@app.post("/api/chat")
async def chat(req: ChatRequest):
    stream = iterate_in_threadpool(_chat_stream(req.message, req.conversation_id))
    return StreamingResponse(stream, media_type="text/event-stream")


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    content = await file.read()
    url = await run_in_threadpool(blob_service.upload_file, file.filename, content)
    return {"filename": file.filename, "url": url}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def index():
    return FileResponse("app/static/index.html")
