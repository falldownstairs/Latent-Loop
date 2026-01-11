"""
Configuration, constants, and service initialization.
"""

import os
import re
import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
import chromadb
import google.generativeai as genai

# --- LOAD ENV ---
load_dotenv()

# --- LOGGING ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("latent_loop")


def log_event(level: int, message: str, **data):
    """Lightweight structured logging helper."""
    try:
        serialized = " | ".join(f"{k}={v}" for k, v in data.items())
        logger.log(level, f"{message}{' | ' + serialized if serialized else ''}")
    except Exception:
        logger.log(level, message)


# --- PATHS ---
PROJECTS_DIR = Path(__file__).parent / "projects"
PROJECTS_DIR.mkdir(exist_ok=True)

# --- CONSTANTS ---
SIMILARITY_THRESHOLD = 0.61
DEFAULT_PROJECT_NAME = "Latent Loop"

# --- API KEYS ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- INITIALIZE SERVICES ---

# Groq client for Whisper transcription
groq_client = None
if GROQ_API_KEY:
    from groq import Groq
    groq_client = Groq(api_key=GROQ_API_KEY)

# Gemini for synthesis
gemini_model = None
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-3-flash-preview') # old: gemini-2.5-flash

# ChromaDB client
chroma_client = chromadb.Client()

# FastEmbed for local embeddings
from fastembed import TextEmbedding
embed_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")


# --- PROJECT HELPERS ---

def slugify_project(name: str) -> str:
    """Convert project name to URL-safe slug."""
    cleaned = name.strip().lower() if name else DEFAULT_PROJECT_NAME.lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", cleaned).strip("-")
    return cleaned or "default"


def resolve_project_name(value: Optional[str]) -> str:
    """Resolve project name from input, falling back to default."""
    return value.strip() if value and value.strip() else DEFAULT_PROJECT_NAME


def get_project_path(project_name: str) -> Path:
    """Get the file path for a project's notes."""
    slug = slugify_project(project_name)
    return PROJECTS_DIR / f"{slug}.md"
