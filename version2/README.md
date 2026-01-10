# 🔄 Latent Loop v2 - Single Source Architecture

**The Recursive Note-Taking Experience**

> Human thought is recursive; we circle back, refine, and edit our ideas as we speak. Latent Loop listens to your conversation, understands context, and updates a **single Markdown file** in real-time instead of just appending new text.

## 🏗️ Architecture: Single Source of Truth

All notes live in **`notes.md`** - the single source of truth. ChromaDB is only used as a "helper" for finding relevant sections via vector search.

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Browser   │────▶│   Flask     │────▶│  notes.md   │
│  (SSE)      │◀────│   Backend   │◀────│ (Source)    │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌─────────┐  ┌─────────┐  ┌──────────┐
        │ ChromaDB│  │ Gemini  │  │   Groq   │
        │ (Index) │  │ (Flash) │  │ (Whisper)│
        └─────────┘  └─────────┘  └──────────┘
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd version2
pip install -r requirements.txt
```

### 2. Set Up API Keys

```bash
cp .env.example .env
```

Edit `.env` and add:
- **GROQ_API_KEY**: [Groq Console](https://console.groq.com/) - Whisper transcription
- **GEMINI_API_KEY**: [Google AI Studio](https://aistudio.google.com/app/apikey) - Synthesis

### 3. Run the Server

```bash
python app.py
```

Open [http://localhost:5050](http://localhost:5050)

## ⚙️ Technical Workflow

### 1. Input Processing & Categorization

- **Buffer**: 10-second rolling audio buffers
- **Transcription**: Groq Whisper (`whisper-large-v3`)
- **Topic Matching**: 
  - Extract headings from `notes.md`
  - Vector search via ChromaDB
  - **Threshold ≥ 0.65**: Update existing section
  - **Threshold < 0.65**: Create new section

### 2. The 95% Certainty Rule 🛑

If the intent is ambiguous, the system **does not execute a file write**. Instead:

- Creates a "Pending Update" shown in the UI
- User can approve, reject, or modify the action
- Ambiguous patterns detected:
  - "Wait, no..."
  - "Actually, wait..."
  - "Scratch that"
  - "Nevermind"
  - Hedging language ("maybe", "possibly")

### 3. The Stateful Prompt (Gemini)

**For Updates:**
```
System Role: You are a Recursive Markdown Editor.
Current File State: [Full content of notes.md]
Target Section: [e.g., ## Tech Stack]
New Input: [The new transcript chunk]
Instruction: Rewrite the Target Section only...
```

**For Creates:**
```
New Input: [transcript]
Instruction: Create a new ## section with a punchy title...
```

### 4. Frontend Magic

- Real-time SSE updates
- Visual pulse animation on changed sections
- Line-level diff tracking
- Toggle between rendered Markdown and raw view

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main interface |
| `/health` | GET | Health check & API status |
| `/api/notes` | GET | Get notes.md content + sections |
| `/api/transcript` | GET | Get recent transcript log |
| `/api/process` | POST | Process text input |
| `/api/audio` | POST | Process audio file |
| `/api/pending` | GET | Get pending updates |
| `/api/pending/<id>` | POST | Resolve pending update |
| `/api/stream` | GET | SSE for real-time updates |
| `/api/clear` | POST | Reset notes.md |
| `/api/export` | GET | Download notes.md |

## 🎯 Key Features

### ✅ Implemented
- [x] Single `notes.md` file as source of truth
- [x] ChromaDB vector search for section matching
- [x] Gemini-powered synthesis with strikethrough for corrections
- [x] 95% certainty rule with pending updates UI
- [x] Real-time SSE updates
- [x] Visual highlighting of changed sections
- [x] Raw/rendered Markdown view toggle
- [x] Voice recording via browser
- [x] Text simulation input

### 🔧 Configuration

In `app.py`:
- `SIMILARITY_THRESHOLD = 0.65` - Section matching threshold
- `CONFIDENCE_THRESHOLD = 0.95` - Certainty rule threshold

## 🏆 Hackathon Demo Tips

1. **Topic Creation**: "Let's talk about our marketing strategy"
2. **Add Detail**: "We should focus on Instagram Reels"
3. **Loop Back**: "Actually about marketing, let's set a budget of $500"
4. **Contradiction**: "Wait, no, let's use TikTok instead of Instagram"
5. **Watch the Magic**: See the strikethrough appear!

---

**JourneyHacks 2026** | Team: Prajwal & Eric
