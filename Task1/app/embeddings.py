# importing libraries
from sentence_transformers import SentenceTransformer
from app.config import EMBEDDING_MODEL

# loading the model once and reusing across requests
_model = None


# function to get the model
def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


# function to generate embeddings
def generate_embeddings(texts):
    model = _get_model()
    vectors = model.encode(
        texts,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    return vectors.tolist()


# function to generate single embedding
def generate_single_embedding(text):
    return generate_embeddings([text])[0]
