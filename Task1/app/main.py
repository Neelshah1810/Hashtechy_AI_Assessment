"""
EzeeChatBot API — main application.

Three endpoints:
  POST /upload  — ingest text or URL into a new bot's knowledge base
  POST /chat    — ask a question, get a streamed grounded answer
  GET  /stats   — usage stats for a bot
"""

import uuid
import time
import json

import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from app.models import UploadRequest, UploadResponse, ChatRequest, StatsResponse
from app.chunker import chunk_text
from app.embeddings import generate_embeddings, generate_single_embedding
from app.vector_store import store_chunks, query_similar, bot_exists
from app.llm import stream_chat, FALLBACK_RESPONSE, is_unanswered, estimate_tokens
from app.stats_tracker import init_db, record_message, get_stats
from app.config import TOP_K, RELEVANCE_THRESHOLD


app = FastAPI(
    title="EzeeChatBot API",
    description="Upload your knowledge base, then chat with it. Answers are grounded in your content only.",
    version="1.0.0",
)


@app.on_event("startup")
def on_startup():
    """Initialize the stats database on server start."""
    init_db()


# ─── helpers ───────────────────────────────────────────────────────────

def fetch_url_content(url):
    """
    Fetch a URL and extract readable text from the HTML.
    Strips out scripts, styles, nav, and other boilerplate.
    """
    try:
        resp = requests.get(
            url,
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0 (compatible; EzeeChatBot/1.0)"},
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Could not fetch URL: {str(e)}")

    soup = BeautifulSoup(resp.text, "html.parser")

    # strip elements that aren't useful content
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)

    # clean up excessive blank lines
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n\n".join(lines)


# ─── routes ────────────────────────────────────────────────────────────

@app.post("/upload", response_model=UploadResponse)
def upload_knowledge(req: UploadRequest):
    """
    Upload text or a URL to create a new chatbot knowledge base.
    Returns a bot_id you can use for /chat and /stats.
    """
    if not req.text and not req.url:
        raise HTTPException(
            status_code=400,
            detail="You need to provide at least one of 'text' or 'url'.",
        )

    # gather content
    parts = []
    source = ""

    if req.text:
        parts.append(req.text.strip())
        source = "text"

    if req.url:
        url_text = fetch_url_content(req.url)
        if not url_text:
            raise HTTPException(
                status_code=400, detail="Couldn't extract any text from that URL."
            )
        parts.append(url_text)
        source = "url" if not req.text else "text+url"

    full_text = "\n\n".join(parts)

    if len(full_text.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="Content too short — need at least 50 characters to build a useful knowledge base.",
        )

    # chunk the text
    chunks = chunk_text(full_text)
    if not chunks:
        raise HTTPException(
            status_code=400, detail="Chunking produced no output. Check your content."
        )

    # embed all chunks in one batch call
    embeddings = generate_embeddings(chunks)

    # store under a fresh bot_id
    bot_id = str(uuid.uuid4())
    store_chunks(bot_id, chunks, embeddings)

    return UploadResponse(
        bot_id=bot_id,
        chunks_created=len(chunks),
        source=source,
        message=f"Knowledge base ready. Use bot_id '{bot_id}' to start chatting.",
    )


@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Chat with a bot. Streams the response back via Server-Sent Events.
    The bot only answers from its uploaded knowledge base.
    """
    if not bot_exists(req.bot_id):
        raise HTTPException(status_code=404, detail=f"No bot found with id '{req.bot_id}'.")

    # embed the question and find relevant chunks
    query_vec = generate_single_embedding(req.user_message)
    docs, distances = query_similar(req.bot_id, query_vec, top_k=TOP_K)

    # filter by relevance — chromadb gives cosine distance, we want similarity
    relevant = []
    for doc, dist in zip(docs, distances):
        similarity = 1.0 - dist
        if similarity >= RELEVANCE_THRESHOLD:
            relevant.append(doc)

    start = time.time()

    # no relevant chunks? don't even call the LLM — just say so
    if not relevant:
        latency = (time.time() - start) * 1000
        record_message(
            req.bot_id,
            latency_ms=latency,
            input_tokens=estimate_tokens(req.user_message),
            output_tokens=estimate_tokens(FALLBACK_RESPONSE),
            unanswered=True,
        )

        async def fallback():
            yield f"data: {json.dumps({'token': FALLBACK_RESPONSE})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(fallback(), media_type="text/event-stream")

    # stream from the LLM
    async def generate():
        full_response = ""
        try:
            for token in stream_chat(relevant, req.user_message, req.conversation_history):
                full_response += token
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as e:
            error_msg = f"LLM error: {str(e)}"
            yield f"data: {json.dumps({'error': error_msg})}\n\n"

        yield "data: [DONE]\n\n"

        # record stats now that we know the full response
        latency = (time.time() - start) * 1000
        ctx_text = " ".join(relevant)
        record_message(
            req.bot_id,
            latency_ms=latency,
            input_tokens=estimate_tokens(ctx_text + req.user_message),
            output_tokens=estimate_tokens(full_response),
            unanswered=is_unanswered(full_response),
        )

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/stats/{bot_id}", response_model=StatsResponse)
def bot_stats(bot_id: str):
    """Get usage statistics for a specific bot."""
    if not bot_exists(bot_id):
        raise HTTPException(status_code=404, detail=f"No bot found with id '{bot_id}'.")

    stats = get_stats(bot_id)
    return StatsResponse(bot_id=bot_id, **stats)


@app.get("/")
def root():
    """Health check / API info."""
    return {
        "name": "EzeeChatBot API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "POST /upload": "Upload text or URL to create a knowledge base",
            "POST /chat": "Chat with a bot (streams via SSE)",
            "GET /stats/{bot_id}": "Get usage stats for a bot",
        },
    }
