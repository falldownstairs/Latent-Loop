"""
Latent Loop v2 - Single-Source Architecture
A recursive note-taking app that updates a single Markdown file in real-time.

JourneyHacks 2026 | Team: Prajwal & Eric
"""

import io
import json
import os
import re
import time
import uuid
import hashlib
import queue
import logging
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, Tuple, List, Dict

from flask import Flask, Response, request, jsonify, stream_with_context, render_template
from flask_cors import CORS
from dotenv import load_dotenv
import chromadb
import google.generativeai as genai

# --- CONFIG ---
load_dotenv()
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("latent_loop")

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

# File paths
NOTES_FILE = Path(__file__).parent / "notes.md"

# API Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize Groq client for Whisper transcription
groq_client = None
if GROQ_API_KEY:
    from groq import Groq
    groq_client = Groq(api_key=GROQ_API_KEY)

# Initialize Gemini for synthesis
gemini_model = None
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-3-flash-preview')  # used to be gemini-2.0-flash-exp

# --- VECTOR DB & EMBEDDINGS ---
chroma_client = chromadb.Client()
collection = chroma_client.create_collection(
    name="latent_loop_sections",
    metadata={"hnsw:space": "cosine"}
)

# FastEmbed for local embeddings
from fastembed import TextEmbedding
embed_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

# --- CONSTANTS ---
SIMILARITY_THRESHOLD = 0.55


# --- LOGGING HELPERS ---

def log_event(level: int, message: str, **data):
    """Lightweight structured logging helper."""
    try:
        serialized = " | ".join(f"{k}={v}" for k, v in data.items())
        logger.log(level, f"{message}{' | ' + serialized if serialized else ''}")
    except Exception:
        logger.log(level, message)

# --- DATA STRUCTURES ---

@dataclass
class MarkdownSection:
    """Represents a section in the markdown file."""
    id: str
    heading: str
    level: int  # 1 for #, 2 for ##, etc.
    content: str  # Full content including heading
    line_start: int
    line_end: int


@dataclass
class PendingUpdate:
    """Represents an ambiguous update awaiting user confirmation."""
    id: str
    transcript: str
    matched_section: Optional[str]
    similarity: float
    suggested_action: str  # "update", "create", "delete"
    reason: str
    timestamp: str


# --- STATE ---
TRANSCRIPT_LOG: List[Dict] = []
PENDING_UPDATES: List[PendingUpdate] = []
CONNECTED_CLIENTS: List = []  # For SSE broadcasting


# --- MARKDOWN FILE OPERATIONS ---

def ensure_notes_file():
    """Create notes.md if it doesn't exist."""
    if not NOTES_FILE.exists():
        NOTES_FILE.write_text(
            "# Latent Loop Notes\n\n"
            "*Your recursive notes will appear here.*\n"
        )
        log_event(logging.INFO, "notes_file_created", path=str(NOTES_FILE))


def read_notes_file() -> str:
    """Read the current state of notes.md."""
    ensure_notes_file()
    content = NOTES_FILE.read_text(encoding='utf-8')
    log_event(logging.DEBUG, "notes_file_read", bytes=len(content))
    return content


def write_notes_file(content: str) -> bool:
    """Write content to notes.md. Returns True on success."""
    try:
        NOTES_FILE.write_text(content, encoding='utf-8')
        log_event(logging.INFO, "notes_file_written", bytes=len(content))
        return True
    except Exception as e:
        print(f"Error writing notes file: {e}")
        log_event(logging.ERROR, "notes_file_write_failed", error=str(e))
        return False


def parse_markdown_sections(content: str) -> List[MarkdownSection]:
    """
    Parse markdown content into sections based on headings.
    Each section includes the heading and all content until the next heading.
    """
    lines = content.split('\n')
    sections = []
    current_section = None
    
    heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$')
    
    for i, line in enumerate(lines):
        match = heading_pattern.match(line)
        
        if match:
            # Close previous section
            if current_section:
                current_section.line_end = i - 1
                current_section.content = '\n'.join(
                    lines[current_section.line_start:i]
                ).strip()
                sections.append(current_section)
            
            # Start new section
            level = len(match.group(1))
            heading = match.group(2).strip()
            section_id = hashlib.md5(f"{heading}:{i}".encode()).hexdigest()[:12]
            
            current_section = MarkdownSection(
                id=section_id,
                heading=heading,
                level=level,
                content="",
                line_start=i,
                line_end=i
            )
    
    # Close last section
    if current_section:
        current_section.line_end = len(lines) - 1
        current_section.content = '\n'.join(
            lines[current_section.line_start:]
        ).strip()
        sections.append(current_section)
    
    log_event(logging.DEBUG, "markdown_sections_parsed", sections=len(sections))
    return sections


def get_section_by_heading(heading: str) -> Optional[MarkdownSection]:
    """Find a section by its heading text."""
    content = read_notes_file()
    sections = parse_markdown_sections(content)
    
    for section in sections:
        if section.heading.lower() == heading.lower():
            return section
    
    return None


# --- VECTOR DB OPERATIONS ---

def sync_chromadb_with_file():
    """
    Sync ChromaDB with the current state of notes.md.
    This rebuilds the index from the file (single source of truth).
    """
    global collection
    
    # Clear and recreate collection
    log_event(logging.INFO, "chroma_sync_start")
    try:
        chroma_client.delete_collection("latent_loop_sections")
    except Exception as e:
        log_event(logging.DEBUG, "chroma_delete_collection_skip", error=str(e))
    
    try:
        collection = chroma_client.create_collection(
            name="latent_loop_sections",
            metadata={"hnsw:space": "cosine"}
        )
    except Exception:
        # Collection might already exist
        collection = chroma_client.get_collection("latent_loop_sections")
    
    content = read_notes_file()
    sections = parse_markdown_sections(content)
    
    if not sections:
        log_event(logging.INFO, "chroma_sync_no_sections")
        return
    
    # Index each section
    ids = []
    documents = []
    embeddings = []
    metadatas = []
    
    for section in sections:
        # Skip the main title
        if section.level == 1 and section.heading == "Latent Loop Notes":
            continue
            
        ids.append(section.id)
        documents.append(f"{section.heading}: {section.content}")
        embeddings.append(get_embedding(f"{section.heading}: {section.content}"))
        metadatas.append({
            "heading": section.heading,
            "level": section.level,
            "line_start": section.line_start,
            "line_end": section.line_end
        })
    
    if ids:
        collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )
        log_event(logging.INFO, "chroma_sync_complete", sections=len(ids))
    else:
        log_event(logging.INFO, "chroma_sync_empty_after_filter")


def get_embedding(text: str) -> list:
    """Get embedding vector for text using FastEmbed."""
    embeddings = list(embed_model.embed([text]))
    return embeddings[0].tolist()


def find_relevant_section(text: str) -> Tuple[Optional[str], Optional[str], float]:
    """
    Find the most relevant existing section for the given text.
    Returns (section_id, heading, similarity_score) or (None, None, 0).
    """
    # First sync the DB with the file
    sync_chromadb_with_file()
    
    try:
        results = collection.query(
            query_embeddings=[get_embedding(text)],
            n_results=1,
            include=["documents", "metadatas", "distances"]
        )
    except Exception as e:
        log_event(logging.ERROR, "chroma_query_error", error=str(e))
        return None, None, 0
    
    if results['documents'] and results['documents'][0]:
        distance = results['distances'][0][0]
        similarity = 1 - distance  # Convert distance to similarity
        
        section_id = results['ids'][0][0]
        heading = results['metadatas'][0][0].get('heading', '')
        log_event(
            logging.INFO,
            "similarity_match",
            similarity=round(similarity, 3),
            heading=heading,
            section_id=section_id,
        )
        return section_id, heading, similarity
    
    log_event(logging.INFO, "similarity_no_match")
    return None, None, 0


# --- INTENT DETECTION (95% Certainty Rule) ---

def detect_ambiguous_intent(text: str) -> Tuple[bool, str]:
    """
    Detect if the user's intent is ambiguous.
    Returns (is_ambiguous, reason).
    """
    # Patterns that suggest uncertainty or correction-in-progress
    ambiguous_patterns = [
        (r'\bwait\b.*\bno\b', "User said 'wait, no' - unclear if deleting or pausing"),
        (r'\bactually\b.*\bwait\b', "User said 'actually wait' - intent unclear"),
        (r'\bhmm+\b', "User is thinking/hesitating"),
        (r'\buh+\b.*\blet me\b', "User is reconsidering"),
        (r'\bscratch that\b(?!\s*,)', "User wants to undo but scope unclear"),
        (r'\bnevermind\b', "User cancelled but unclear what"),
        (r'\bforget\s+(what\s+)?i\s+said\b', "User wants to forget but scope unclear"),
    ]
    
    text_lower = text.lower()
    
    for pattern, reason in ambiguous_patterns:
        if re.search(pattern, text_lower):
            log_event(logging.INFO, "ambiguous_intent_detected", pattern=pattern, reason=reason)
            return True, reason
    
    return False, ""





# --- GEMINI OPERATIONS ---

def gemini_update_file(
    current_content: str,
    target_section: Optional[str],
    new_transcript: str,
    action: str  # "update" or "create"
) -> Tuple[str, Dict]:
    """
    Use Gemini to update the markdown file.
    Returns (new_content, change_info).
    """
    if not gemini_model:
        log_event(logging.WARNING, "gemini_unavailable_fallback", action=action)
        return fallback_update(current_content, target_section, new_transcript, action)
    
    if action == "create":
        prompt = f"""You are a Recursive Markdown Editor for a note-taking app.

**Current File State:**
```markdown
{current_content}
```

**New Input (from voice transcription):**
"{new_transcript}"

**Instruction:**
This is a NEW TOPIC. Create a new section (## heading) for this content.
- Place it at the END of the file, before any closing content.
- Create a short, punchy heading (3-5 words).
- Convert the transcript into concise bullet points.
- Return the ENTIRE updated Markdown file.

Return ONLY the markdown content, no code blocks or explanations."""

    else:  # update
        prompt = f"""You are a Recursive Markdown Editor for a note-taking app.

**Current File State:**
```markdown
{current_content}
```

**Target Section:** {target_section}

**New Input (from voice transcription):**
"{new_transcript}"

**Instruction:**
Rewrite the **Target Section** only to incorporate the new information:
1. If the user CORRECTED themselves (e.g., "actually, use X instead of Y"), use ~~strikethrough~~ on the old text and add the correction.
2. If they ADDED detail, integrate it into existing bullet points or add new ones.
3. If they EXPANDED on a point, refine that bullet.
4. Keep it concise - no redundant information.

Return the ENTIRE updated Markdown file with only the target section modified.
Return ONLY the markdown content, no code blocks or explanations."""

    try:
        log_event(logging.INFO, "gemini_request", action=action, target_section=target_section)
        response = gemini_model.generate_content(prompt)
        new_content = response.text.strip()
        
        # Clean up if wrapped in code blocks
        if new_content.startswith("```markdown"):
            new_content = new_content[11:]
        if new_content.startswith("```"):
            new_content = new_content[3:]
        if new_content.endswith("```"):
            new_content = new_content[:-3]
        new_content = new_content.strip()
        
        # Calculate diff info
        change_info = calculate_diff(current_content, new_content, target_section)
        log_event(logging.INFO, "gemini_update_success", changes=change_info.get("total_changes"))
        
        return new_content, change_info
        
    except Exception as e:
        log_event(logging.ERROR, "gemini_error_fallback", error=str(e), action=action)
        return fallback_update(current_content, target_section, new_transcript, action)


def fallback_update(
    current_content: str,
    target_section: Optional[str],
    new_transcript: str,
    action: str
) -> Tuple[str, Dict]:
    """Fallback update without Gemini."""
    
    if action == "create":
        # Generate simple heading from first words
        words = new_transcript.split()
        heading = " ".join(words[:4]).title() if len(words) >= 4 else new_transcript.title()
        
        new_section = f"\n\n## {heading}\n\n- {new_transcript}\n"
        new_content = current_content.rstrip() + new_section
        log_event(logging.INFO, "fallback_create_section", heading=heading)
        
        return new_content, {
            "action": "create",
            "heading": heading,
            "lines_added": [len(current_content.split('\n')) + 1]
        }
    
    else:  # update
        # Find and append to section
        lines = current_content.split('\n')
        new_lines = []
        in_target = False
        updated = False
        target_line = -1
        
        for i, line in enumerate(lines):
            new_lines.append(line)
            
            # Check if we're entering target section
            if target_section and line.strip().endswith(target_section):
                in_target = True
                target_line = i
            # Check if we're leaving (next heading)
            elif in_target and line.startswith('#'):
                # Insert before this heading
                new_lines.insert(-1, f"- {new_transcript}")
                in_target = False
                updated = True
        
        # If still in target at end of file
        if in_target and not updated:
            new_lines.append(f"- {new_transcript}")
            updated = True
        
        log_event(logging.INFO, "fallback_update_section", heading=target_section)
        return '\n'.join(new_lines), {
            "action": "update",
            "heading": target_section,
            "lines_modified": [target_line] if target_line >= 0 else []
        }


def calculate_diff(old_content: str, new_content: str, target_section: Optional[str]) -> Dict:
    """Calculate what changed between old and new content."""
    old_lines = old_content.split('\n')
    new_lines = new_content.split('\n')
    
    changed_lines = []
    added_lines = []
    
    # Simple diff - find changed lines
    max_len = max(len(old_lines), len(new_lines))
    
    for i in range(max_len):
        old_line = old_lines[i] if i < len(old_lines) else None
        new_line = new_lines[i] if i < len(new_lines) else None
        
        if old_line != new_line:
            if old_line is None:
                added_lines.append(i + 1)
            else:
                changed_lines.append(i + 1)
    
    return {
        "target_section": target_section,
        "changed_lines": changed_lines,
        "added_lines": added_lines,
        "total_changes": len(changed_lines) + len(added_lines)
    }


# --- MAIN PROCESSING LOGIC ---

def process_transcript(text: str) -> Dict:
    """
    Main logic: Process new transcript and update notes.md.
    Uses vector similarity (threshold: 0.55) to match to existing sections.
    Only creates pending updates for ambiguous intent (e.g., "wait, no...").
    """
    global PENDING_UPDATES
    
    # Add to transcript log
    TRANSCRIPT_LOG.append({
        "text": text,
        "timestamp": datetime.now().isoformat()
    })
    if len(TRANSCRIPT_LOG) > 20:
        TRANSCRIPT_LOG.pop(0)
    
    # Step 1: Check for ambiguous intent (e.g., "wait, no...", "scratch that")
    is_ambiguous, ambiguity_reason = detect_ambiguous_intent(text)
    
    # Step 2: Find relevant section via vector similarity
    section_id, heading, similarity = find_relevant_section(text)
    has_match = similarity >= SIMILARITY_THRESHOLD
    
    # Step 3: Handle ambiguous intent - ask user to confirm
    log_event(
        logging.INFO,
        "transcript_received",
        text_preview=text[:120],
        ambiguous=is_ambiguous,
        similarity=round(similarity, 3),
        has_match=has_match,
    )
    
    if is_ambiguous:
        pending = PendingUpdate(
            id=str(uuid.uuid4())[:8],
            transcript=text,
            matched_section=heading if has_match else None,
            similarity=similarity,
            suggested_action="update" if has_match else "create",
            reason=ambiguity_reason,
            timestamp=datetime.now().isoformat()
        )
        PENDING_UPDATES.append(pending)
        log_event(logging.INFO, "pending_update_created", pending_id=pending.id, reason=pending.reason)
        
        # Broadcast pending update
        broadcast_event({
            "type": "pending_update",
            "pending": asdict(pending)
        })
        
        return {
            "status": "pending",
            "pending_id": pending.id,
            "reason": pending.reason,
            "suggested_action": pending.suggested_action,
            "matched_section": heading
        }
    
    # Step 5: Execute the update
    current_content = read_notes_file()
    action = "update" if has_match else "create"
    
    new_content, change_info = gemini_update_file(
        current_content,
        heading,
        text,
        action
    )
    
    # Step 6: Write to file
    if write_notes_file(new_content):
        # Sync ChromaDB
        sync_chromadb_with_file()
        log_event(
            logging.INFO,
            "transcript_applied",
            action=action,
            section=heading or change_info.get("heading"),
            similarity=round(similarity, 3)
        )
        
        # Broadcast update
        broadcast_event({
            "type": "file_updated",
            "content": new_content,
            "change_info": change_info,
            "action": action,
            "section": heading
        })
        
        return {
            "status": "success",
            "action": action,
            "section": heading or change_info.get("heading"),
            "similarity": similarity,
            "change_info": change_info
        }
    
    log_event(logging.ERROR, "transcript_apply_failed")
    return {"status": "error", "message": "Failed to write file"}


def resolve_pending_update(pending_id: str, action: str) -> Dict:
    """
    Resolve a pending update with user confirmation.
    action: "approve", "reject", "create_new", "update_section"
    """
    global PENDING_UPDATES
    
    pending = next((p for p in PENDING_UPDATES if p.id == pending_id), None)
    if not pending:
        log_event(logging.WARNING, "pending_update_not_found", pending_id=pending_id)
        return {"status": "error", "message": "Pending update not found"}
    
    if action == "reject":
        PENDING_UPDATES = [p for p in PENDING_UPDATES if p.id != pending_id]
        broadcast_event({"type": "pending_resolved", "pending_id": pending_id, "action": "rejected"})
        log_event(logging.INFO, "pending_update_rejected", pending_id=pending_id)
        return {"status": "rejected"}
    
    # Execute the action
    current_content = read_notes_file()
    
    if action == "create_new":
        new_content, change_info = gemini_update_file(
            current_content, None, pending.transcript, "create"
        )
    elif action in ["approve", "update_section"]:
        target = pending.matched_section
        new_content, change_info = gemini_update_file(
            current_content, target, pending.transcript, "update" if target else "create"
        )
    else:
        log_event(logging.WARNING, "pending_update_unknown_action", action=action)
        return {"status": "error", "message": f"Unknown action: {action}"}
    
    if write_notes_file(new_content):
        PENDING_UPDATES = [p for p in PENDING_UPDATES if p.id != pending_id]
        sync_chromadb_with_file()
        log_event(logging.INFO, "pending_update_applied", pending_id=pending_id, action=action)
        
        broadcast_event({
            "type": "file_updated",
            "content": new_content,
            "change_info": change_info,
            "pending_resolved": pending_id
        })
        
        return {"status": "success", "change_info": change_info}
    
    log_event(logging.ERROR, "pending_update_apply_failed", pending_id=pending_id)
    return {"status": "error", "message": "Failed to write file"}


# --- SSE BROADCASTING ---

def broadcast_event(data: Dict):
    """Broadcast an event to all connected SSE clients."""
    # Events are picked up by the generator in the stream endpoint
    for client_queue in CONNECTED_CLIENTS:
        try:
            client_queue.put(data)
        except:
            pass
    log_event(logging.DEBUG, "sse_broadcast", type=data.get("type"))


# --- AUDIO TRANSCRIPTION ---

def transcribe_audio(audio_data: bytes) -> str:
    """Transcribe audio using Groq's Whisper API."""
    if not groq_client:
        log_event(logging.WARNING, "groq_unavailable")
        return ""
    
    try:
        audio_file = io.BytesIO(audio_data)
        audio_file.name = "audio.wav"
        
        transcription = groq_client.audio.transcriptions.create(
            file=audio_file,
            model="whisper-large-v3",
            response_format="text"
        )
        
        text = transcription.strip()
        log_event(logging.INFO, "audio_transcribed", chars=len(text))
        return text
        
    except Exception as e:
        log_event(logging.ERROR, "transcription_error", error=str(e))
        return ""


# --- FLASK ROUTES ---

@app.route('/')
def index():
    """Serve the main interface."""
    ensure_notes_file()
    sync_chromadb_with_file()
    return render_template('index.html')


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "groq_available": groq_client is not None,
        "gemini_available": gemini_model is not None,
        "notes_file": str(NOTES_FILE),
        "pending_updates": len(PENDING_UPDATES)
    })


@app.route('/api/notes')
def get_notes():
    """Get the current notes.md content."""
    try:
        content = read_notes_file()
        sections = parse_markdown_sections(content)
        
        return jsonify({
            "content": content,
            "sections": [asdict(s) for s in sections],
            "pending_updates": [asdict(p) for p in PENDING_UPDATES]
        })
    except Exception as e:
        print(f"Error in /api/notes: {e}")
        return jsonify({
            "content": "# Latent Loop Notes\n\n*Your recursive notes will appear here.*",
            "sections": [],
            "pending_updates": []
        })


@app.route('/api/transcript')
def get_transcript():
    """Get recent transcript log."""
    return jsonify({"transcript": TRANSCRIPT_LOG[-10:]})


@app.route('/api/process', methods=['POST'])
def process_text():
    """Process text input."""
    data = request.json
    text = data.get('text', '').strip()
    
    if not text:
        return jsonify({"error": "No text provided"}), 400
    log_event(logging.INFO, "api_process_text", chars=len(text))
    
    result = process_transcript(text)
    return jsonify(result)


@app.route('/api/audio', methods=['POST'])
def process_audio():
    """Process audio input."""
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400
    
    audio_file = request.files['audio']
    audio_data = audio_file.read()
    log_event(logging.INFO, "api_process_audio", bytes=len(audio_data))
    
    text = transcribe_audio(audio_data)
    
    if not text:
        return jsonify({"error": "Could not transcribe audio"}), 400
    
    result = process_transcript(text)
    result['transcription'] = text
    
    return jsonify(result)


@app.route('/api/pending/<pending_id>', methods=['POST'])
def handle_pending(pending_id):
    """Handle a pending update."""
    data = request.json
    action = data.get('action', 'approve')
    log_event(logging.INFO, "api_handle_pending", pending_id=pending_id, action=action)
    
    result = resolve_pending_update(pending_id, action)
    return jsonify(result)


@app.route('/api/pending', methods=['GET'])
def get_pending():
    """Get all pending updates."""
    return jsonify({
        "pending": [asdict(p) for p in PENDING_UPDATES]
    })


@app.route('/api/stream')
def stream():
    """SSE endpoint for real-time updates."""
    client_queue = queue.Queue()
    CONNECTED_CLIENTS.append(client_queue)
    
    def event_stream():
        # Send initial state
        try:
            content = read_notes_file()
            sections = parse_markdown_sections(content)
            
            init_data = {
                'type': 'init',
                'content': content,
                'sections': [asdict(s) for s in sections],
                'transcript': TRANSCRIPT_LOG[-5:],
                'pending': [asdict(p) for p in PENDING_UPDATES]
            }
            yield f"data: {json.dumps(init_data)}\n\n"
        except Exception as e:
            print(f"SSE init error: {e}")
            yield f"data: {json.dumps({'type': 'init', 'content': '# Latent Loop Notes\n', 'sections': [], 'transcript': [], 'pending': []})}\n\n"
        
        try:
            while True:
                try:
                    data = client_queue.get(timeout=2.0)
                    yield f"data: {json.dumps(data)}\n\n"
                except queue.Empty:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        except GeneratorExit:
            pass
        finally:
            if client_queue in CONNECTED_CLIENTS:
                CONNECTED_CLIENTS.remove(client_queue)
    
    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


@app.route('/api/clear', methods=['POST'])
def clear_notes():
    """Reset notes.md to initial state."""
    initial_content = (
        "# Latent Loop Notes\n\n"
        "*Your recursive notes will appear here.*\n"
    )
    
    write_notes_file(initial_content)
    sync_chromadb_with_file()
    log_event(logging.INFO, "notes_cleared")
    
    PENDING_UPDATES.clear()
    TRANSCRIPT_LOG.clear()
    
    broadcast_event({
        "type": "file_updated",
        "content": initial_content,
        "change_info": {"action": "clear"}
    })
    
    return jsonify({"status": "cleared"})


@app.route('/api/export')
def export_notes():
    """Download notes.md."""
    content = read_notes_file()
    
    return Response(
        content,
        mimetype="text/markdown",
        headers={"Content-Disposition": "attachment; filename=latent_loop_notes.md"}
    )


if __name__ == '__main__':
    port = int(os.getenv("PORT", 5050))
    ensure_notes_file()
    sync_chromadb_with_file()
    log_event(
        logging.INFO,
        "server_startup",
        groq_ready=bool(groq_client),
        gemini_ready=bool(gemini_model),
        notes_file=str(NOTES_FILE),
        port=port,
    )
    
    print(f"""
    ╔═══════════════════════════════════════════════════╗
    ║      🔄 LATENT LOOP v2.0 - Single Source          ║
    ║       The Recursive Note-Taking Experience        ║
    ╠═══════════════════════════════════════════════════╣
    ║   Groq (Whisper):  {'✅ Ready' if groq_client else '❌ No API Key'}                    ║
    ║   Gemini:          {'✅ Ready' if gemini_model else '❌ No API Key'}                    ║
    ║   Notes File:      {str(NOTES_FILE):<25} ║
    ╠═══════════════════════════════════════════════════╣
    ║   Server: http://localhost:{port}                    ║
    ╚═══════════════════════════════════════════════════╝
    """)
    app.run(debug=True, port=port, threaded=True)
