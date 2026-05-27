# importing libraries
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


# FastAPI app
app = FastAPI(
    title="EzeeChatBot API",
    description="Upload your knowledge base and chat with it using Groq API.",
    version="1.0.0",
)


# initializing the database on startup
@app.on_event("startup")
def on_startup():
    init_db()


# function to fetch URL content
def fetch_url_content(url):
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

    # strip elements that are not useful content
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)

    # clean up excessive blank lines
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n\n".join(lines)



# Routes 

# route for uploading knowledge base
@app.post("/upload", response_model=UploadResponse)
def upload_knowledge(req: UploadRequest):
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


# route for chatting with the bot
@app.post("/chat")
async def chat(req: ChatRequest):
    if not bot_exists(req.bot_id):
        raise HTTPException(status_code=404, detail=f"No bot found with id '{req.bot_id}'.")

    # embed the question and find relevant chunks
    query_vec = generate_single_embedding(req.user_message)
    docs, distances = query_similar(req.bot_id, query_vec, top_k=TOP_K)

    # filter by relevance
    relevant = []
    for doc, dist in zip(docs, distances):
        similarity = 1.0 - dist
        if similarity >= RELEVANCE_THRESHOLD:
            relevant.append(doc)

    start = time.time()

    # if no relevant chunks then dont even call the LLM
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


# route for bot stats
@app.get("/stats/{bot_id}", response_model=StatsResponse)
def bot_stats(bot_id: str):
    if not bot_exists(bot_id):
        raise HTTPException(status_code=404, detail=f"No bot found with id '{bot_id}'.")

    stats = get_stats(bot_id)
    return StatsResponse(bot_id=bot_id, **stats)


# route for health check
@app.get("/")
def root():
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
