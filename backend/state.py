"""
Application state management.
Per-project state for transcript logs, pending updates, SSE clients, etc.
"""

from collections import defaultdict
from queue import Queue
from threading import Lock
from typing import Dict, List

from models import PendingUpdate

# --- STATE CONTAINERS ---

# Transcript logs per project
TRANSCRIPT_LOGS: Dict[str, List[Dict]] = defaultdict(list)

# Pending updates awaiting user confirmation
PENDING_UPDATES: Dict[str, List[PendingUpdate]] = defaultdict(list)

# Connected SSE clients per project
CONNECTED_CLIENTS: Dict[str, List] = defaultdict(list)

# Cached ChromaDB collections per project
CHROMA_COLLECTIONS: Dict[str, object] = {}

# Rolling context history per project (last N transcript chunks)
CONTEXT_HISTORY: Dict[str, List[str]] = defaultdict(list)

# --- PROCESSING QUEUE ---
# FIFO queue for transcript processing to ensure order is maintained
PROCESSING_QUEUE: Queue = Queue()

# Lock for thread-safe operations
PROCESSING_LOCK: Lock = Lock()

# Track processing results by request ID
PROCESSING_RESULTS: Dict[str, Dict] = {}
