import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Keys
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")

# Flask
SECRET_KEY = os.getenv("SECRET_KEY", "deep-research-ai-secret-key")

# Models - Ensure llama-3.3-70b-versatile is first and default
GROQ_MODELS = {
    "llama-3.3-70b-versatile": "llama-3.3-70b-versatile",
    "mixtral-8x7b-32768": "mixtral-8x7b-32768",
    "gemma-7b-it": "gemma-7b-it"
}
DEFAULT_MODEL = "llama-3.3-70b-versatile"

# Analysis settings
MIN_WORDS = 2000
MAX_TOKENS = 8000

# Rate limits
RATE_LIMITS = {
    "llama-3.3-70b-versatile": {"requests_per_minute": 10, "tokens_per_minute": 50000},
    "mixtral-8x7b-32768": {"requests_per_minute": 15, "tokens_per_minute": 75000},
    "gemma-7b-it": {"requests_per_minute": 20, "tokens_per_minute": 100000}
}

