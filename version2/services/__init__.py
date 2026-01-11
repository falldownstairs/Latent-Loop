"""Services package for Latent Loop."""

from services.markdown import (
    initial_content,
    ensure_notes_file,
    read_notes_file,
    write_notes_file,
    parse_markdown_sections,
)

from services.vectordb import (
    get_embedding,
    get_collection,
    sync_chromadb_with_file,
    find_relevant_section,
)

from services.ai import (
    transcribe_audio,
    gemini_update_file,
    detect_ambiguous_intent,
)

from services.processing import (
    process_transcript,
    resolve_pending_update,
    broadcast_event,
)

__all__ = [
    # Markdown
    "initial_content",
    "ensure_notes_file", 
    "read_notes_file",
    "write_notes_file",
    "parse_markdown_sections",
    # VectorDB
    "get_embedding",
    "get_collection",
    "sync_chromadb_with_file",
    "find_relevant_section",
    # AI
    "transcribe_audio",
    "gemini_update_file",
    "detect_ambiguous_intent",
    # Processing
    "process_transcript",
    "resolve_pending_update",
    "broadcast_event",
]
