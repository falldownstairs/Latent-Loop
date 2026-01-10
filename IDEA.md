# 🚀 Project Blueprint: Latent Loop

**JourneyHacks 2026** | **Team:** Prajwal & Eric

### 💡 The Core Concept

**The Pitch:**
"Human thought is recursive; we circle back, refine, and edit our ideas as we speak. But traditional transcription tools are linear—they just create an endless wall of text. **Latent Loop** is the first 'recursive' note-taker. It listens to your conversation, understands context, and **updates existing notes** in real-time instead of just appending new ones."

**The Metaphor:**

* **Existing Tools:** A Typewriter (Linear, permanent, chronological).
* **Latent Loop:** A Clay Sculptor (Iterative, molding, refining shape over time).

---

### 🧠 User Experience (UX) & Design

*Targeting: "Best UI" Track*

**The Interface: "Split-Brain" Layout**

1. **Left Pane: The Stream (Ephemeral)**
* Displays a fading, scrolling transcript of exactly what is being said *right now*.
* *Visuals:* Grey text, low contrast. Disappears after ~30 seconds.
* *Purpose:* Confidence monitor. "Did it hear me?"


2. **Right Pane: The Knowledge Graph (Persistent - "Smart Buckets")**
* This is the main document. It is organized into **Sections** (Buckets) with **Bullet Points**.
* *Visuals:* High contrast, clean typography (Notion-style).



**The "Loop" Interaction (The Wow Factor):**

* **Step 1:** Users discuss a new topic (e.g., "Marketing"). A new Section creates itself.
* **Step 2:** Users discuss "Tech Stack". A new Section creates itself below.
* **Step 3:** Users return to "Marketing".
* **The Magic:** The Right Pane automatically **smooth-scrolls** back up to the "Marketing" section.
* **The Pulse:** The specific bullet point being updated glows (Gold/Purple gradient).
* **The Synthesis:** The text morphs live. A bullet point changes from *"Plan to use ads"* to *"Plan to use ads, specifically targeting Instagram Reels (Budget: $500)."*



---

### ⚙️ The Logic Flow

*Targeting: "Best Use of Gemini API" Track*

**1. Input & Buffer**

* **Audio Capture:** 10-second rolling buffers (handled by your existing Python script).
* **Transcription:** `whisper-large-v3` (via Groq) for speed.

**2. The Retrieval (Vector Search)**

* **Embedding:** Embed the new 10s text chunk (`BAAI/bge-small`).
* **Query:** Search ChromaDB for the most relevant *existing* Section or Bullet Point.
* **Threshold:**
* *If Similarity > 0.65:* It’s a continuation/refinement of an old topic. -> **TRIGGER LOOP.**
* *If Similarity < 0.65:* It’s a new topic. -> **CREATE NEW SECTION.**



**3. The Synthesis (Gemini 3 Flash)**

* **The Prompt:**
> "You are a real-time secretary. Here is the **Current Note Section** regarding '[Topic]'. Here is the **New Spoken Transcript**.
> **Task:** Update the Current Note Section to incorporate the new information.


> * If the new info contradicts the old, cross out the old info and add the new info.
> * If it adds detail, append or refine the bullet point.
> * Do NOT repeat information. Keep it concise."
> 
> 


* **Why Gemini 3?** Low latency is non-negotiable here. The UI update must feel "live."

**4. The Update**

* The backend sends a JSON payload to the frontend:
```json
{
  "action": "update_section",
  "section_id": "marketing_uuid",
  "new_content": "..."
}

```



---

### 🏗️ Technical Stack

* **Frontend:** React or Svelte (Svelte is great for handling the reactive state of the notes without complex re-rendering logic).
* **Backend:** Python (FastAPI or Flask) - *You already have the core logic in your script.*
* **Database:**
* **Vector:** ChromaDB (for finding *where* to write).
* **State:** In-memory JSON or simple SQLite (to hold the current state of the document text).


* **AI Models:**
* **Transcription:** Whisper (via Groq).
* **Synthesis:** **Gemini 3 Flash** (via Google AI Studio API).
* **Embeddings:** FastEmbed (local).



---

### 🏆 Hackathon Strategy: Winning The Tracks

**1. Best Use of Gemini API**

* **Context Caching:** If the notes get long, use Gemini's Context Caching (if available/needed) to keep the whole document in memory so it understands global context.
* **Conflict Resolution:** Explicitly demo a moment where you *change your mind*.
* *You:* "Actually, wait, let's not use AWS, let's use Vercel."
* *Gemini:* Finds the "AWS" bullet and updates it to "~~AWS~~ -> Vercel." (This shows reasoning capabilities).



**2. Best Pitch**

* **The "Live" Demo:** Start the pitch by casually talking. Have the screen behind you running Latent Loop.
* **The Reveal:** "I haven't been clicking slides. I've just been talking. And if you look at the screen, Latent Loop has just written the executive summary of our pitch, organized by the topics I covered, while I was covering them."

**3. Best UI**

* **Animation is King:** The difference between a "glitchy reload" and a "magical update" is `framer-motion` (React) or Svelte transitions.
* **Focus State:** When the system "recalls" a topic, dim the rest of the document and spotlight the active section.

---

### 📝 Immediate Next Steps (The Plan)

1. **Backend:** Convert your script into an API that maintains a "Document State" (List of Objects: `{id, title, bullets[]}`).
2. **Frontend:** Build a simple view that renders that List of Objects.
3. **Connection:** Connect the "Recall" logic in your script to trigger a Gemini call that rewrites the specific object found.
