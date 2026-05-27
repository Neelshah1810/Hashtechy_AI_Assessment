# importing libraries
import chromadb
from app.config import CHROMA_DIR

# client for ChromaDB
_client = None


# function to get the client
def _get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_DIR)
    return _client


# function to get the collection name
def _collection_name(bot_id):
    return f"bot_{bot_id.replace('-', '_')}"


# function to get the collection
def get_collection(bot_id):
    client = _get_client()
    return client.get_or_create_collection(
        name=_collection_name(bot_id),
        metadata={"hnsw:space": "cosine"},
    )


# function to store chunks
def store_chunks(bot_id, chunks, embeddings):
    collection = get_collection(bot_id)
    ids = [f"{bot_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [{"chunk_index": i, "bot_id": bot_id} for i in range(len(chunks))]
    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas,
    )
    return len(chunks)


# function to query similar chunks
def query_similar(bot_id, query_embedding, top_k=5):
    collection = get_collection(bot_id)
    count = collection.count()
    if count == 0:
        return [], []
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, count),
    )
    docs = results["documents"][0] if results["documents"] else []
    dists = results["distances"][0] if results["distances"] else []
    return docs, dists


# function to check if the bot exists
def bot_exists(bot_id):
    try:
        collection = get_collection(bot_id)
        return collection.count() > 0
    except Exception:
        return False
