import io
import json
import os
import time
import uuid
import wave
import threading
import queue
import re

from flask import Flask, Response, request, jsonify, stream_with_context, render_template
from flask_cors import CORS
from dotenv import load_dotenv
from fastembed import TextEmbedding
from groq import Groq
from colorama import Fore
import chromadb
import numpy as np

# --- CONFIG ---
load_dotenv()
app = Flask(__name__, template_folder="templates")
CORS(app)  # Allow frontend to talk to backend

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Fallback behavior when no Groq key is set (still let the UI work)
USE_GROQ = client is not None

# --- MEMORY & STATE ---
# 1. Vector DB for "Where should this go?"
chroma_client = chromadb.Client() # Ephemeral (RAM) for speed/dev
collection = chroma_client.create_collection(name="notes", metadata={"hnsw:space": "cosine"})

# 2. Embedding Model
embed_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

# 3. The "Living Document" State
# Structure: [{"id": str, "title": str, "content": str (HTML or Markdown)}]
NOTES_STATE = []
TRANSCRIPT_LOG = [] # Just for the "Left Pane" stream

# --- CORE LOGIC ---

def clean_json_response(content):
    """
    Cleans LLM response to ensure valid JSON.
    Removes markdown code blocks (```json ... ```) if present.
    """
    # Remove ```json at start and ``` at end
    pattern = r"```json\s*(.*?)\s*```"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(1)
    
    # Fallback: Remove any code block backticks if pattern didn't match
    return content.replace("```json", "").replace("```", "").strip()


def _append_bullet(existing_html, bullet_text):
    """Simple helper to append a bullet to existing HTML content."""
    if not existing_html:
        return f"<ul><li>{bullet_text}</li></ul>"
    if "</ul>" in existing_html:
        return existing_html.replace("</ul>", f"<li>{bullet_text}</li></ul>", 1)
    return f"<ul>{existing_html}<li>{bullet_text}</li></ul>"

def find_relevant_section(text):
    """Returns the ID of the most relevant note section, or None."""
    if not NOTES_STATE:
        return None
    
    # Embed the incoming text
    query_embed = list(embed_model.embed([text]))[0]
    
    results = collection.query(
        query_embeddings=[query_embed],
        n_results=1
    )
    
    if results['documents'] and results['documents'][0]:
        distance = results['distances'][0][0]
        # Threshold: Lower distance = Closer match. 
        # 0.4 is a strict match, 0.6 is loose. Adjust as needed.
        if distance < 0.55: 
            return results['ids'][0][0]
            
    return None

def update_notes_with_gemini(text, section_id=None):
    """
    Calls Gemini to either:
    A) Create a new section (if section_id is None)
    B) Update an existing section
    """
    global NOTES_STATE

    def local_create_stub():
        # Create a lightweight note without hitting Groq
        title_tokens = text.split()
        title = " ".join(title_tokens[:4]).title() if title_tokens else "New Topic"
        content = f"<ul><li>{text}</li></ul>"
        new_id = str(uuid.uuid4())
        return {
            "id": new_id,
            "title": title or "New Topic",
            "content": content
        }

    def local_update_stub(target_note):
        target_note["content"] = _append_bullet(target_note.get("content", ""), text)
        return target_note

    if section_id:
        # --- UPDATE EXISTING ---
        target_note = next((n for n in NOTES_STATE if n["id"] == section_id), None)
        if not target_note: return # Safety catch
        
        if USE_GROQ:
            prompt = f"""
            You are a smart technical note-taker.
            
            EXISTING NOTE SECTION:
            Title: {target_note['title']}
            Content: {target_note['content']}
            
            NEW SPOKEN AUDIO:
            "{text}"
            
            TASK:
            Merge the new audio into the existing content. 
            - Fix facts if the user corrects themselves.
            - Add new bullet points if it's new info.
            - Keep it concise (bullet points).
            - Return ONLY the updated HTML content (<ul><li>...</li></ul>). Do not include markdown code blocks.
            """
            
            try:
                completion = client.chat.completions.create(
                    messages=[{"role": "system", "content": prompt}],
                    model="llama3-70b-8192", # Or gemma-7b-it, or whisper-large-v3 logic
                )
                new_content = completion.choices[0].message.content
                target_note['content'] = new_content
                return "updated", target_note['title']
            except Exception as e:
                print(f"{Fore.YELLOW}Groq unavailable, falling back to local update: {e}")

        # Local fallback update
        updated = local_update_stub(target_note)
        return "updated", updated['title']

    else:
        # --- CREATE NEW ---
        if USE_GROQ:
            prompt = f"""
            You are a smart technical note-taker.
            The user has started a NEW topic: "{text}"
            
            TASK:
            1. Create a short, punchy Title (3-5 words).
            2. Create the initial bullet points (HTML <ul> format).
            3. Return strictly valid JSON: {{"title": "...", "content": "..."}}.
            """
            try:
                completion = client.chat.completions.create(
                    messages=[{"role": "system", "content": prompt}, {"role": "user", "content": text}],
                    model="llama3-70b-8192",
                    response_format={"type": "json_object"}
                )
                raw_content = completion.choices[0].message.content
                cleaned_content = clean_json_response(raw_content) 
                data = json.loads(cleaned_content)
                new_id = str(uuid.uuid4())
                new_note = {
                    "id": new_id,
                    "title": data['title'],
                    "content": data['content']
                }
                NOTES_STATE.append(new_note)
                vector_text = f"{data['title']}: {data['content']}"
                collection.add(
                    documents=[vector_text],
                    embeddings=list(embed_model.embed([vector_text])),
                    ids=[new_id]
                )
                return "created", data['title']
            except Exception as e:
                print(f"{Fore.YELLOW}Groq unavailable, falling back to local create: {e}")

        # Local fallback create
        new_note = local_create_stub()
        NOTES_STATE.append(new_note)
        vector_text = f"{new_note['title']}: {new_note['content']}"
        collection.add(
            documents=[vector_text],
            embeddings=list(embed_model.embed([vector_text])),
            ids=[new_note['id']]
        )
        return "created", new_note['title']

# --- FLASK ENDPOINTS ---

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/health')
def health():
    return jsonify({"status": "ok"})

@app.route('/upload_audio', methods=['POST'])
def upload_audio():
    # This endpoint receives text (since your local script handles whisper)
    # OR receives audio blob. Let's assume your Python script sends TEXT for simplicity
    # to offload processing from the server if you run the "listener" locally.
    
    # BUT for a pure web app, send the WAV file here.
    
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
        
    file = request.files['file']
    # 1. Transcribe (Whisper)
    # Save temp to transcribe
    # (Implementation omitted for brevity - reuse your existing whisper code here)
    # ... assuming we get `text` string ...
    
    # MOCK for testing without mic:
    text = request.form.get('mock_text', '') 
    
    if not text:
        # Do the whisper transcription here using Groq
        pass 

    # 2. Logic
    TRANSCRIPT_LOG.append(text)
    
    relevant_id = find_relevant_section(text)
    status, title = update_notes_with_gemini(text, relevant_id)
    
    print(f"Processed: {text[:20]}... -> {status} ({title})")
    
    return jsonify({"status": "success", "action": status})


@app.route('/stream')
def stream():
    """Server-Sent Events to push state to Frontend"""
    def event_stream():
        while True:
            # Push the entire state every 1s (simplest way for hackathon)
            json_data = json.dumps({
                "transcript": TRANSCRIPT_LOG[-5:], # Last 5 lines
                "notes": NOTES_STATE
            })
            yield f"data: {json_data}\n\n"
            time.sleep(1.0) 

    return Response(stream_with_context(event_stream()), mimetype="text/event-stream")

# --- SIMULATION ENDPOINT (Use this to test without mic) ---
@app.route('/simulate', methods=['POST'])
def simulate():
    data = request.json
    text = data.get('text')
    
    TRANSCRIPT_LOG.append(text)
    relevant_id = find_relevant_section(text)
    status, title = update_notes_with_gemini(text, relevant_id)
    
    return jsonify({"message": "Simulated", "notes": NOTES_STATE})

if __name__ == '__main__':
    app.run(debug=True, port=int(os.getenv("PORT", 5050)))
