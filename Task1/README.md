# EzeeChatBot

A minimal RAG (Retrieval-Augmented Generation) chatbot API. Upload your own content — plain text or a URL — and get a chatbot that answers questions grounded strictly in that content.

Built with FastAPI, ChromaDB, sentence-transformers, and Groq.

## Setup

### Prerequisites

- Python 3.10+
- A free [Groq API key](https://console.groq.com/) (no credit card needed)

### Installation

```bash
# clone and enter the project
cd Task1

# create a virtual environment
python -m venv venv
source venv/bin/activate   # on Windows: venv\Scripts\activate

# install dependencies
pip install -r requirements.txt

# set up your API key
cp .env.example .env
# then edit .env and paste your Groq API key
```

### Running the server

```bash
uvicorn app.main:app --reload --port 8000
```

The API will be live at `http://localhost:8000`. Interactive docs are at `http://localhost:8000/docs`.

> **First run note:** The first request will take a few extra seconds because the embedding model (~80MB) downloads automatically. After that it's cached locally.

---

## API Endpoints

### POST /upload

Create a new knowledge base from text or a URL.

```bash
# from plain text
curl -X POST http://localhost:8000/upload \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Python is a high-level programming language created by Guido van Rossum in 1991. It emphasizes code readability and supports multiple programming paradigms including procedural, object-oriented, and functional programming."
  }'

# from a URL
curl -X POST http://localhost:8000/upload \
  -H "Content-Type: application/json" \
  -d '{"url": "https://en.wikipedia.org/wiki/Python_(programming_language)"}'
```

**Response:**
```json
{
  "bot_id": "a1b2c3d4-...",
  "chunks_created": 12,
  "source": "text",
  "message": "Knowledge base ready. Use bot_id 'a1b2c3d4-...' to start chatting."
}
```

### POST /chat

Ask a question. The response streams back via Server-Sent Events.

```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "bot_id": "a1b2c3d4-...",
    "user_message": "Who created Python?",
    "conversation_history": []
  }'
```

**Streamed response (SSE format):**
```
data: {"token": "Python"}
data: {"token": " was"}
data: {"token": " created"}
data: {"token": " by"}
data: {"token": " Guido"}
data: {"token": " van"}
data: {"token": " Rossum"}
data: {"token": " in"}
data: {"token": " 1991."}
data: [DONE]
```

You can pass `conversation_history` to maintain multi-turn context:
```json
{
  "bot_id": "...",
  "user_message": "What paradigms does it support?",
  "conversation_history": [
    {"role": "user", "content": "Who created Python?"},
    {"role": "assistant", "content": "Python was created by Guido van Rossum in 1991."}
  ]
}
```

### GET /stats/{bot_id}

Usage stats for a specific bot.

```bash
curl http://localhost:8000/stats/a1b2c3d4-...
```

**Response:**
```json
{
  "bot_id": "a1b2c3d4-...",
  "total_messages": 15,
  "avg_latency_ms": 342.5,
  "estimated_cost_usd": 0.000023,
  "unanswered_questions": 2
}
```

---

## Chunking Strategy

This is where a lot of RAG systems get it wrong, so I want to explain the thinking.

### The problem with naive chunking

The simplest approach is to split text every N characters. But this creates real problems:
- You cut words in half ("the impor | tance of...")
- Sentences get split across chunks, so neither chunk has the complete thought
- When the retriever finds a chunk, the LLM gets a fragment instead of a coherent piece of context

### What I do instead

The chunker in `app/chunker.py` works in three stages:

1. **Paragraph splitting** — The text is first split on double newlines. This preserves the author's own structural boundaries. A paragraph about "pricing" won't get merged with a paragraph about "features."

2. **Sentence detection** — Within each paragraph, I split into sentences using a regex that handles common edge cases: abbreviations (Mr., Dr., etc.), initials (J. K. Rowling), and decimal numbers (3.14). It's not perfect for every language or format, but it covers the vast majority of English text.

3. **Grouping with overlap** — Sentences are accumulated into chunks targeting ~150 tokens (roughly 600 characters). When a chunk reaches the target size, the last sentence is carried forward into the next chunk. This overlap means that if an answer happens to sit right at a chunk boundary, at least one of the two chunks will have the full context.

### Why 150 tokens?

- Small enough that the embedding captures specific meaning (not a vague summary of a whole page)
- Large enough to hold a complete thought or explanation
- Leaves plenty of room in the LLM's context window for multiple retrieved chunks plus conversation history

### Trade-offs

This approach works well for prose — articles, documentation, reports. It's less ideal for heavily structured content like tables or code. With more time I'd add format-specific chunkers (see below).

---

## Hallucination Handling

Three layers of defense:

1. **Relevance gate** — Before the LLM is even called, I check if the retrieved chunks are actually similar to the question (cosine similarity ≥ 0.3). If nothing relevant is found, the API returns a fallback message without wasting an LLM call.

2. **Grounded system prompt** — The system prompt explicitly tells the model to only use the provided context, and to say "I could not find the answer" if the information isn't there. Low temperature (0.3) further discourages creative responses.

3. **Post-response detection** — After the LLM responds, I scan for phrases like "could not find," "not mentioned in," etc. If detected, the message is counted as "unanswered" in the stats. This gives you a metric to monitor.

---

## Multi-Bot Isolation

Each bot gets its own ChromaDB collection (named `bot_{uuid}`). Collections are completely independent — there's no shared index, no chance of one bot's knowledge leaking into another's queries. Stats are also keyed by bot_id in SQLite.

---

## What I'd Do Differently With More Time

1. **PDF support** — Add a `/upload` variant that accepts file uploads (multipart form data) and uses something like PyMuPDF or pdfplumber to extract text. The chunking pipeline is already set up for it; it's just the ingestion layer that's missing.

2. **Smarter chunking for structured content** — The current chunker handles prose well, but tables, lists, and code blocks deserve their own logic. I'd detect these formats and keep them intact as single chunks rather than splitting through them.

3. **Async embedding generation** — Right now embeddings are generated synchronously. For large documents with hundreds of chunks, running the embedding model in a background worker (or using an async-compatible model server) would keep the upload endpoint responsive.

4. **Persistent conversation storage** — Currently conversation history is passed by the client on each request. In production I'd store conversations server-side (keyed by a session ID) so clients don't have to manage that state.

5. **Chunk metadata in responses** — Return which chunks were used to answer each question, so the frontend could show "sources" alongside the answer. The data is already there in ChromaDB; it just needs to be surfaced in the API response.

---

## Project Structure

```
Task1/
├── app/
│   ├── __init__.py          # package marker
│   ├── main.py              # FastAPI app, route handlers
│   ├── config.py            # settings, env vars, constants
│   ├── models.py            # Pydantic request/response schemas
│   ├── chunker.py           # sentence-aware text chunking
│   ├── embeddings.py        # sentence-transformers wrapper
│   ├── vector_store.py      # ChromaDB operations
│   ├── llm.py               # Groq LLM integration
│   └── stats_tracker.py     # SQLite stats recording
├── data/                    # created at runtime (gitignored)
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```
