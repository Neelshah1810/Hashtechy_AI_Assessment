# importing libraries
import re
from app.config import CHUNK_TARGET_TOKENS, CHUNK_OVERLAP_SENTENCES


# abbreviations we don't want to split on
_ABBREVS = r"(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs|etc|Inc|Ltd|Corp|dept|approx|est|vol|no|Fig|fig|Eq|eq|Ref|ref)"


# function to split text into sentences
def _split_sentences(text):
    working = re.sub(rf"({_ABBREVS})\.", r"\1<DOT>", text)
    working = re.sub(r"(\b[A-Z])\.", r"\1<DOT>", working)
    working = re.sub(r"(\d)\.(\d)", r"\1<DOT>\2", working)
    parts = re.split(r"(?<=[.!?])\s+", working)
    sentences = [p.replace("<DOT>", ".").strip() for p in parts]
    return [s for s in sentences if s]


# function to chunk text into chunks
def chunk_text(text, target_tokens=None, overlap=None):
    if not text or not text.strip():
        return []

    # setting target tokens and overlap   
    target_tokens = target_tokens or CHUNK_TARGET_TOKENS
    overlap = overlap if overlap is not None else CHUNK_OVERLAP_SENTENCES
    target_chars = target_tokens * 4  

    # split into paragraphs
    paragraphs = re.split(r"\n\s*\n", text.strip())

    # collect all sentences across paragraphs
    all_sentences = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        sents = _split_sentences(para)
        all_sentences.extend(sents)

    if not all_sentences:
        return [text.strip()]

    # group sentences into chunks
    chunks = []
    current = []
    current_len = 0

    for sentence in all_sentences:
        sent_len = len(sentence)
        if current_len + sent_len > target_chars and current:
            chunks.append(" ".join(current))
            overlap_start = max(0, len(current) - overlap)
            current = current[overlap_start:]
            current_len = sum(len(s) for s in current)
        current.append(sentence)
        current_len += sent_len

    if current:
        chunks.append(" ".join(current))

    return chunks
