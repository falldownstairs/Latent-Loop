"""
Queue processor for FIFO transcript processing.
Ensures transcripts are processed in the order they were received.
"""

import logging
import threading
import uuid
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime

from config import log_event
from state import PROCESSING_QUEUE, PROCESSING_LOCK, PROCESSING_RESULTS


@dataclass
class QueueItem:
    """Item in the processing queue."""
    request_id: str
    text: str
    project: str
    timestamp: datetime
    chunk_num: Optional[int] = None


# Background worker thread
_worker_thread: Optional[threading.Thread] = None
_worker_running = False


def enqueue_transcript(text: str, project: str, chunk_num: Optional[int] = None) -> str:
    """
    Add a transcript to the processing queue.
    Returns a request_id that can be used to check the result.
    """
    request_id = str(uuid.uuid4())[:8]
    
    item = QueueItem(
        request_id=request_id,
        text=text,
        project=project,
        timestamp=datetime.now(),
        chunk_num=chunk_num
    )
    
    # Initialize result slot
    with PROCESSING_LOCK:
        PROCESSING_RESULTS[request_id] = {
            "status": "queued",
            "queued_at": item.timestamp.isoformat(),
            "project": project,
            "chunk_num": chunk_num
        }
    
    PROCESSING_QUEUE.put(item)
    queue_size = PROCESSING_QUEUE.qsize()
    
    log_event(logging.INFO, "queue_enqueue", 
              request_id=request_id, 
              project=project, 
              chunk_num=chunk_num,
              queue_size=queue_size,
              text_preview=text[:50])
    
    return request_id


def get_result(request_id: str) -> Optional[Dict]:
    """Get the result for a request ID."""
    with PROCESSING_LOCK:
        return PROCESSING_RESULTS.get(request_id)


def _process_queue():
    """Background worker that processes queue items in FIFO order."""
    global _worker_running
    
    # Import here to avoid circular imports
    from services.processing import process_transcript
    
    log_event(logging.INFO, "queue_worker_started")
    
    while _worker_running:
        try:
            # Block for up to 1 second waiting for items
            item = PROCESSING_QUEUE.get(timeout=1.0)
        except:
            # Timeout, check if we should keep running
            continue
        
        try:
            log_event(logging.INFO, "queue_process_start",
                      request_id=item.request_id,
                      project=item.project,
                      chunk_num=item.chunk_num,
                      queue_remaining=PROCESSING_QUEUE.qsize())
            
            # Update status to processing
            with PROCESSING_LOCK:
                if item.request_id in PROCESSING_RESULTS:
                    PROCESSING_RESULTS[item.request_id]["status"] = "processing"
                    PROCESSING_RESULTS[item.request_id]["started_at"] = datetime.now().isoformat()
            
            # Actually process the transcript
            result = process_transcript(item.text, item.project)
            result["transcription"] = item.text
            result["project"] = item.project
            result["chunk_num"] = item.chunk_num
            
            # Store result
            with PROCESSING_LOCK:
                if item.request_id in PROCESSING_RESULTS:
                    PROCESSING_RESULTS[item.request_id].update({
                        "status": "completed",
                        "completed_at": datetime.now().isoformat(),
                        "result": result
                    })
            
            log_event(logging.INFO, "queue_process_complete",
                      request_id=item.request_id,
                      project=item.project,
                      chunk_num=item.chunk_num,
                      action=result.get("action"))
            
        except Exception as e:
            log_event(logging.ERROR, "queue_process_error",
                      request_id=item.request_id,
                      error=str(e))
            
            with PROCESSING_LOCK:
                if item.request_id in PROCESSING_RESULTS:
                    PROCESSING_RESULTS[item.request_id].update({
                        "status": "error",
                        "error": str(e),
                        "completed_at": datetime.now().isoformat()
                    })
        
        finally:
            PROCESSING_QUEUE.task_done()
            
            # Clean up old results (keep last 100)
            with PROCESSING_LOCK:
                if len(PROCESSING_RESULTS) > 100:
                    # Remove oldest entries
                    sorted_keys = sorted(
                        PROCESSING_RESULTS.keys(),
                        key=lambda k: PROCESSING_RESULTS[k].get("queued_at", "")
                    )
                    for key in sorted_keys[:-100]:
                        del PROCESSING_RESULTS[key]
    
    log_event(logging.INFO, "queue_worker_stopped")


def start_queue_worker():
    """Start the background queue processing worker."""
    global _worker_thread, _worker_running
    
    if _worker_thread is not None and _worker_thread.is_alive():
        log_event(logging.WARNING, "queue_worker_already_running")
        return
    
    _worker_running = True
    _worker_thread = threading.Thread(target=_process_queue, daemon=True)
    _worker_thread.start()
    log_event(logging.INFO, "queue_worker_thread_started")


def stop_queue_worker():
    """Stop the background queue processing worker."""
    global _worker_running
    _worker_running = False
    if _worker_thread is not None:
        _worker_thread.join(timeout=5.0)
    log_event(logging.INFO, "queue_worker_thread_stopped")
