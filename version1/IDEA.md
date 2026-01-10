# 🚀 Project Blueprint: Latent Loop (v2)

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
* *Visuals:* High contrast, clean typography (Notion-style). Cards that grow/shrink.



**The "Loop" Interaction (The Wow Factor):**

* **Step 1:** Users discuss a new topic (e.g., "Marketing"). A new Section card creates itself.
* **Step 2:** Users discuss "Tech Stack". A new Section card creates itself below.
* **Step 3:** Users return to "Marketing".
* **The Magic:** The Right Pane automatically **smooth-scrolls** back up to the "Marketing" card.
* **The Pulse:** The specific card glows (Blue/Purple gradient border) to show it is "listening."
* **The Synthesis:** The text morphs live. A bullet point changes from *"Plan to use ads"* to *"Plan to use ads, specifically targeting Instagram Reels (Budget: $500)."*



---

### ⚙️ The Logic Flow

*Targeting: "Best Use of Gemini API" Track*

**1. Input & Buffer**

* **Audio Capture:** 10-second rolling buffers (handled by local Python script).
* **Transcription:** `whisper-large-v3` (via Groq) for speed.

**2. The Retrieval (Vector Search)**

* **Embedding:** Embed the new 10s text chunk (`BAAI/bge-small`).
* **Query:** Search ChromaDB for the most relevant *existing* Section.
* **Threshold Strategy:**
* *Similarity > 0.60:* **TRIGGER LOOP** (Update existing section).
* *Similarity < 0.60:* **CREATE NEW SECTION** (New topic).
* *Similarity < 0.40:* **PARKING LOT** (Add to "Inbox" section for unsorted thoughts).



**3. The Synthesis (Gemini 3 Flash)**

* **The Prompt Strategy:**
> "You are a real-time secretary. Here is the **Current Note Section**. Here is the **New Spoken Transcript**.
> **Task:** Update the Current Note Section to incorporate the new information.
> * **Conflict Resolution:** If new info contradicts old info, use strikethrough (~~old~~) and add new info.
> * **Refinement:** If it adds detail, append or refine the bullet point.
> * **Strict JSON:** Return ONLY valid JSON."
> 
> 


* **Why Gemini 3?** Low latency is non-negotiable here. The UI update must feel "live."

**4. The Update & Cleanup**

* **JSON Cleaning:** Backend explicitly strips Markdown (```json) to prevent parser crashes.
* **Push:** The backend sends a JSON payload to the frontend via SSE (Server Sent Events).

---

### 🏗️ Technical Stack (Speedrun MVP)

* **Frontend:** Vanilla HTML5 + TailwindCSS + Alpine.js (or simple JS).
* *Why:* Fast to iterate, no build step, easy to debug "Live" updates.


* **Backend:** Python (Flask).
* *Why:* Lightweight, handles SSE easily, integrates natively with existing Python logic.


* **Database:**
* **Vector:** ChromaDB (Ephemeral/In-Memory for hackathon speed).
* **State:** In-memory List of Objects `[{id, title, content}]`.


* **AI Models:**
* **Transcription:** Whisper (Groq).
* **Synthesis:** **Gemini 3 Flash**.
* **Embeddings:** FastEmbed (local).



---

### 🏆 Hackathon Strategy: Winning The Tracks

**1. Best Use of Gemini API**

* **Context Caching:** (Stretch Goal) Keep the whole document in memory if it gets huge.
* **Conflict Resolution Demo:** Explicitly demo a moment where you *change your mind*.
* *You:* "Actually, wait, let's not use AWS, let's use Vercel."
* *Gemini:* Finds the "AWS" bullet and updates it to "~~AWS~~ -> Vercel." (Shows reasoning).



**2. Best Pitch**

* **The "Live" Demo:** Start the pitch by casually talking. Have the screen behind you running Latent Loop.
* **The Reveal:** "I haven't been clicking slides. I've just been talking. And if you look at the screen, Latent Loop has just written the executive summary of our pitch, organized by the topics I covered, while I was covering them."

**3. Best UI**

* **Animation is King:** Use CSS transitions (`transition-all duration-500`) on the cards. When a card updates, it should flash or pulse.
* **Focus State:** When the system "recalls" a topic, dim the rest of the document slightly and spotlight the active section.

---

### 📝 Immediate Next Steps (The Plan)

1. **Backend (DONE):** Flask server up, SSE streaming working, JSON cleaning implemented.
2. **Frontend (IN PROGRESS):** Basic HTML/Tailwind view rendering the state.
3. **Connection:** Connect the "Recall" logic to the "Update" logic (ensure `update_notes_with_gemini` is called correctly).
4. **Audio Link:** Connect the local microphone script to POST to the Flask `/upload_audio` endpoint.