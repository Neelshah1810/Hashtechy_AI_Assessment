# importing libraries
import os
from dotenv import load_dotenv

load_dotenv()

# LLM API key
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLM_MODEL = "llama-3.1-8b-instant"

# Chunking parameters
CHUNK_TARGET_TOKENS = 500
CHUNK_OVERLAP_SENTENCES = 3 

# Embedding model
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Retrieval parameters
TOP_K = 5
RELEVANCE_THRESHOLD = 0.3

# Storage paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma")
STATS_DB = os.path.join(DATA_DIR, "stats.db")

os.makedirs(DATA_DIR, exist_ok=True)

# Cost estimation - Approximate USD per million tokens for llama 3.1 8b instant
INPUT_COST_PER_M = 0.05
OUTPUT_COST_PER_M = 0.08
