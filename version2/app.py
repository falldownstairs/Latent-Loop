"""
Latent Loop v2 - Single-Source Architecture
A recursive note-taking app that updates a single Markdown file in real-time.

JourneyHacks 2026 | Team: Prajwal & Eric
"""

import logging
from flask import Flask
from flask_cors import CORS

from config import (
    log_event,
    get_project_path,
    DEFAULT_PROJECT_NAME,
    groq_client,
    gemini_model,
)
from routes import api
from services.markdown import ensure_notes_file
from services.vectordb import sync_chromadb_with_file
from services.queue_processor import start_queue_worker


def create_app():
    """Application factory."""
    app = Flask(__name__, template_folder="templates", static_folder="static")
    CORS(app)
    
    # Register routes
    app.register_blueprint(api)
    
    return app


# Create the app instance
app = create_app()


if __name__ == '__main__':
    import os
    port = int(os.getenv("PORT", 5050))
    default_project = DEFAULT_PROJECT_NAME
    
    # Initialize default project
    ensure_notes_file(default_project)
    sync_chromadb_with_file(default_project)
    
    # Start the FIFO queue processor
    start_queue_worker()
    
    log_event(
        logging.INFO,
        "server_startup",
        groq_ready=bool(groq_client),
        gemini_ready=bool(gemini_model),
        notes_file=str(get_project_path(default_project)),
        port=port,
    )
    
    print(f"""
    ╔═══════════════════════════════════════════════════╗
    ║      🔄 LATENT LOOP v2.0 - Single Source          ║
    ║       The Recursive Note-Taking Experience        ║
    ╠═══════════════════════════════════════════════════╣
    ║   Groq (Whisper):  {'✅ Ready' if groq_client else '❌ No API Key'}                    ║
    ║   Gemini:          {'✅ Ready' if gemini_model else '❌ No API Key'}                    ║
    ║   Queue Worker:    ✅ Running (FIFO)               ║
    ║   Notes File:      {str(get_project_path(default_project)):<25} ║
    ╠═══════════════════════════════════════════════════╣
    ║   Server: http://localhost:{port}                    ║
    ╚═══════════════════════════════════════════════════╝
    """)
    
    app.run(debug=True, port=port, threaded=True)
