"""
Main transcript processing logic.
"""

import uuid
import logging
from datetime import datetime
from dataclasses import asdict
from typing import Optional, Dict

from config import log_event, SIMILARITY_THRESHOLD
from models import PendingUpdate
from state import (
    TRANSCRIPT_LOGS,
    PENDING_UPDATES,
    CONNECTED_CLIENTS,
    CONTEXT_HISTORY,
)
from services.markdown import read_notes_file, write_notes_file
from services.vectordb import sync_chromadb_with_file, find_relevant_section
from services.ai import detect_ambiguous_intent, gemini_update_file


# --- SSE BROADCASTING ---

def broadcast_event(project_name: str, data: Dict):
    """Broadcast an event to all connected SSE clients for a project."""
    for client_queue in CONNECTED_CLIENTS[project_name]:
        try:
            client_queue.put(data)
        except Exception as e:
            log_event(logging.DEBUG, "sse_client_send_failed", project=project_name, error=str(e))
    log_event(logging.DEBUG, "sse_broadcast", project=project_name, type=data.get("type"))


# --- MAIN PROCESSING ---

def process_transcript(text: str, project_name: str, previous_context: Optional[str] = None) -> Dict:
    """
    Main logic: Process new transcript and update notes.md.
    Uses vector similarity (threshold: 0.55) to match to existing sections.
    Only creates pending updates for ambiguous intent (e.g., "wait, no...").
    
    previous_context: Recent transcription context for continuity
    """
    pending_list = PENDING_UPDATES[project_name]
    transcript_log = TRANSCRIPT_LOGS[project_name]
    context_history = CONTEXT_HISTORY[project_name]
    
    # Build combined context from history
    if previous_context:
        combined_context = previous_context
    elif context_history:
        combined_context = " ".join(context_history[-3:])  # Last 3 chunks
    else:
        combined_context = None
    
    # Add current text to context history (keep last 5)
    context_history.append(text)
    if len(context_history) > 5:
        context_history.pop(0)
    
    log_event(logging.INFO, "context_update", project=project_name, history_len=len(context_history), has_prev=bool(combined_context))
    
    # Add to transcript log
    transcript_log.append({
        "text": text,
        "timestamp": datetime.now().isoformat()
    })
    if len(transcript_log) > 20:
        transcript_log.pop(0)
    
    # Step 1: Check for ambiguous intent (e.g., "wait, no...", "scratch that")
    is_ambiguous, ambiguity_reason = detect_ambiguous_intent(text)
    
    # Step 2: Find relevant section via vector similarity
    section_id, heading, similarity = find_relevant_section(text, project_name)
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
        pending_list.append(pending)
        log_event(logging.INFO, "pending_update_created", project=project_name, pending_id=pending.id, reason=pending.reason)
        
        # Broadcast pending update
        broadcast_event(project_name, {
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
    
    # Step 4: Execute the update
    current_content = read_notes_file(project_name)
    action = "update" if has_match else "create"
    
    new_content, change_info = gemini_update_file(
        current_content,
        heading,
        text,
        action,
        previous_context=combined_context
    )
    
    # Step 5: Write to file
    if write_notes_file(project_name, new_content):
        # Sync ChromaDB
        sync_chromadb_with_file(project_name)
        log_event(
            logging.INFO,
            "transcript_applied",
            project=project_name,
            action=action,
            section=heading if action == "update" else change_info.get("target_section"),
            similarity=round(similarity, 3)
        )
        
        # Broadcast update
        broadcast_event(project_name, {
            "type": "file_updated",
            "content": new_content,
            "change_info": change_info,
            "action": action,
            "section": heading if action == "update" else None
        })
        
        return {
            "status": "success",
            "action": action,
            "section": heading if action == "update" else change_info.get("target_section"),
            "similarity": similarity,
            "change_info": change_info
        }
    
    log_event(logging.ERROR, "transcript_apply_failed", project=project_name)
    return {"status": "error", "message": "Failed to write file"}


def resolve_pending_update(pending_id: str, action: str, project_name: str) -> Dict:
    """
    Resolve a pending update with user confirmation.
    action: "approve", "reject", "create_new", "update_section"
    """
    pending_list = PENDING_UPDATES[project_name]
    pending = next((p for p in pending_list if p.id == pending_id), None)
    if not pending:
        log_event(logging.WARNING, "pending_update_not_found", pending_id=pending_id)
        return {"status": "error", "message": "Pending update not found"}
    
    if action == "reject":
        PENDING_UPDATES[project_name] = [p for p in pending_list if p.id != pending_id]
        broadcast_event(project_name, {"type": "pending_resolved", "pending_id": pending_id, "action": "rejected"})
        log_event(logging.INFO, "pending_update_rejected", pending_id=pending_id)
        return {"status": "rejected"}
    
    # Execute the action
    current_content = read_notes_file(project_name)
    
    if action == "create_new":
        new_content, change_info = gemini_update_file(
            current_content, None, pending.transcript, "create", previous_context=None
        )
    elif action in ["approve", "update_section"]:
        target = pending.matched_section
        new_content, change_info = gemini_update_file(
            current_content, target, pending.transcript, "update" if target else "create", previous_context=None
        )
    else:
        log_event(logging.WARNING, "pending_update_unknown_action", action=action)
        return {"status": "error", "message": f"Unknown action: {action}"}
    
    if write_notes_file(project_name, new_content):
        PENDING_UPDATES[project_name] = [p for p in pending_list if p.id != pending_id]
        sync_chromadb_with_file(project_name)
        log_event(logging.INFO, "pending_update_applied", pending_id=pending_id, action=action)
        
        broadcast_event(project_name, {
            "type": "file_updated",
            "content": new_content,
            "change_info": change_info,
            "pending_resolved": pending_id
        })
        
        return {"status": "success", "change_info": change_info}
    
    log_event(logging.ERROR, "pending_update_apply_failed", pending_id=pending_id)
    return {"status": "error", "message": "Failed to write file"}
