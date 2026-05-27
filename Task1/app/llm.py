# importing libraries
from groq import Groq
from app.config import GROQ_API_KEY, LLM_MODEL

# client for Groq API
_client = None


# function to get the client
def _get_client():
    global _client
    if _client is None:
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not set. Add it to your .env file.")
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


# prompt engineering
SYSTEM_PROMPT_TEMPLATE = """You are a helpful assistant that answers questions based ONLY on the provided context.

RULES:
(1) Use ONLY the information from the CONTEXT section below to answer.
(2) If the context does not contain enough information to answer the question, say exactly: "I could not find the answer to that in the provided knowledge base."
(3) Do NOT make up facts, speculate, or draw from general knowledge.
(4) Be concise and direct in your answers.
(5) You may rephrase or summarize the context, but never add information that isn't there.

CONTEXT:
{context}"""


# fallback response
FALLBACK_RESPONSE = (
    "I could not find any relevant information in the knowledge base to answer "
    "your question. Could you try rephrasing, or ask something related to the "
    "uploaded content?"
)


# possible phrases that signal the bot couldn't answer from its knowledge base
_UNANSWERED_PHRASES = [
    "could not find",
    "don't have enough information",
    "not mentioned in",
    "no relevant information",
    "not covered in the",
    "cannot find",
    "not in the provided",
    "no information about",
    "doesn't contain",
    "does not contain",
    "outside the provided",
    "not available in",
]


# function to check if the LLM couldn't find the answer
def is_unanswered(response_text):
    lower = response_text.lower()
    return any(phrase in lower for phrase in _UNANSWERED_PHRASES)


# function to assemble the full message for the LLM call
def build_messages(context_chunks, user_message, conversation_history=None):
    context = "\n\n---\n\n".join(context_chunks)
    system_msg = SYSTEM_PROMPT_TEMPLATE.format(context=context)
    messages = [{"role": "system", "content": system_msg}]
    # include recent conversation history
    if conversation_history:
        for msg in conversation_history[-20:]:
            messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})
    return messages


# function to stream a grounded response from Groq
def stream_chat(context_chunks, user_message, conversation_history=None):
    client = _get_client()
    messages = build_messages(context_chunks, user_message, conversation_history)
    stream = client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        stream=True,
        temperature=0.3,
        max_tokens=1024,
    )
    for chunk in stream:
        choice = chunk.choices[0] if chunk.choices else None
        if choice and choice.delta and choice.delta.content:
            yield choice.delta.content


# function to estimate tokens
def estimate_tokens(text):
    return len(text) // 4
