"""
Flask routes for Latent Loop API.
"""

import json
import queue
import logging
from dataclasses import asdict

from flask import Blueprint, Response, request, jsonify, stream_with_context, render_template

from config import (
    log_event,
    resolve_project_name,
    get_project_path,
    slugify_project,
    groq_client,
    gemini_model,
)
from state import TRANSCRIPT_LOGS, PENDING_UPDATES, CONNECTED_CLIENTS
from services.markdown import (
    initial_content,
    ensure_notes_file,
    read_notes_file,
    write_notes_file,
    parse_markdown_sections,
)
from services.vectordb import sync_chromadb_with_file
from services.ai import transcribe_audio
from services.processing import process_transcript, resolve_pending_update, broadcast_event
from services.queue_processor import enqueue_transcript, get_result

# Create blueprint
api = Blueprint('api', __name__)


# --- PAGE ROUTES ---

@api.route('/')
def index():
    """Serve the main interface."""
    project = resolve_project_name(request.args.get("project"))
    ensure_notes_file(project)
    sync_chromadb_with_file(project)
    return render_template('index.html')


@api.route('/health')
def health():
    """Health check endpoint."""
    project = resolve_project_name(request.args.get("project"))
    return jsonify({
        "status": "ok",
        "groq_available": groq_client is not None,
        "gemini_available": gemini_model is not None,
        "notes_file": str(get_project_path(project)),
        "pending_updates": len(PENDING_UPDATES[project])
    })


# --- API ROUTES ---

@api.route('/api/notes')
def get_notes():
    """Get the current notes.md content."""
    project = resolve_project_name(request.args.get("project"))
    try:
        content = read_notes_file(project)
        sections = parse_markdown_sections(content)
        
        return jsonify({
            "content": content,
            "sections": [asdict(s) for s in sections],
            "pending_updates": [asdict(p) for p in PENDING_UPDATES[project]],
            "project": project
        })
    except Exception as e:
        log_event(logging.ERROR, "api_notes_error", error=str(e))
        return jsonify({
            "content": initial_content(project),
            "sections": [],
            "pending_updates": []
        })


@api.route('/api/transcript')
def get_transcript():
    """Get recent transcript log."""
    project = resolve_project_name(request.args.get("project"))
    return jsonify({"transcript": TRANSCRIPT_LOGS[project][-10:], "project": project})


@api.route('/api/process', methods=['POST'])
def process_text():
    """Process text input."""
    data = request.json
    text = data.get('text', '').strip()
    project = resolve_project_name(data.get('project'))
    
    if not text:
        return jsonify({"error": "No text provided"}), 400
    log_event(logging.INFO, "api_process_text", chars=len(text))
    
    result = process_transcript(text, project)
    result["project"] = project
    return jsonify(result)


@api.route('/api/audio', methods=['POST'])
def process_audio():
    """Process audio input - transcribes then enqueues for FIFO processing."""
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400
    
    audio_file = request.files['audio']
    audio_data = audio_file.read()
    project = resolve_project_name(request.args.get('project'))
    chunk_num = request.args.get('chunk', type=int)
    log_event(logging.INFO, "api_process_audio", bytes=len(audio_data), chunk_num=chunk_num)
    
    # Transcribe immediately
    text = transcribe_audio(audio_data)
    
    if not text:
        return jsonify({"error": "Could not transcribe audio"}), 400
    
    # Enqueue for FIFO processing
    request_id = enqueue_transcript(text, project, chunk_num)
    
    return jsonify({
        "status": "queued",
        "request_id": request_id,
        "transcription": text,
        "project": project,
        "chunk_num": chunk_num
    })


@api.route('/api/queue/status/<request_id>', methods=['GET'])
def queue_status(request_id):
    """Check the status of a queued processing request."""
    result = get_result(request_id)
    if result is None:
        return jsonify({"error": "Request not found"}), 404
    return jsonify(result)


@api.route('/api/pending/<pending_id>', methods=['POST'])
def handle_pending(pending_id):
    """Handle a pending update."""
    data = request.json
    action = data.get('action', 'approve')
    project = resolve_project_name(data.get('project'))
    log_event(logging.INFO, "api_handle_pending", pending_id=pending_id, action=action, project=project)
    
    result = resolve_pending_update(pending_id, action, project)
    return jsonify(result)


@api.route('/api/pending', methods=['GET'])
def get_pending():
    """Get all pending updates."""
    project = resolve_project_name(request.args.get('project'))
    return jsonify({
        "pending": [asdict(p) for p in PENDING_UPDATES[project]],
        "project": project
    })


@api.route('/api/stream')
def stream():
    """SSE endpoint for real-time updates."""
    project = resolve_project_name(request.args.get('project'))
    client_queue = queue.Queue()
    CONNECTED_CLIENTS[project].append(client_queue)
    
    def event_stream():
        # Send initial state
        try:
            content = read_notes_file(project)
            sections = parse_markdown_sections(content)
            
            init_data = {
                'type': 'init',
                'content': content,
                'sections': [asdict(s) for s in sections],
                'transcript': TRANSCRIPT_LOGS[project][-5:],
                'pending': [asdict(p) for p in PENDING_UPDATES[project]],
                'project': project
            }
            yield f"data: {json.dumps(init_data)}\n\n"
        except Exception as e:
            log_event(logging.ERROR, "sse_init_error", error=str(e))
            yield f"data: {json.dumps({'type': 'init', 'content': initial_content(project), 'sections': [], 'transcript': [], 'pending': [], 'project': project})}\n\n"
        
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
            if client_queue in CONNECTED_CLIENTS[project]:
                CONNECTED_CLIENTS[project].remove(client_queue)
    
    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


@api.route('/api/clear', methods=['POST'])
def clear_notes():
    """Reset notes.md to initial state."""
    project = resolve_project_name(request.args.get('project'))
    content = initial_content(project)
    write_notes_file(project, content)
    sync_chromadb_with_file(project)
    log_event(logging.INFO, "notes_cleared", project=project)
    
    PENDING_UPDATES[project].clear()
    TRANSCRIPT_LOGS[project].clear()
    
    broadcast_event(project, {
        "type": "file_updated",
        "content": content,
        "change_info": {"action": "clear"}
    })
    
    return jsonify({"status": "cleared", "project": project})


@api.route('/api/export')
def export_notes():
    """Download notes.md."""
    project = resolve_project_name(request.args.get('project'))
    content = read_notes_file(project)
    slug = slugify_project(project)
    
    return Response(
        content,
        mimetype="text/markdown",
        headers={"Content-Disposition": f"attachment; filename={slug}.md"}
    )
