# My Project 7

## Journey Hacks 2026
- Journey hacks for 2026
- Project: LatentLoop
  - Tagline: Notes that evolve as you speak
  - Design Philosophy: Built to think iteratively, like human thought.
  - Motivation: Human thought is recursive, constantly refining ideas. Current transcription tools are linear, creating endless walls of text.
  - Core Functionality: Listens to your conversations and updates your notes in real time. Unlike traditional transcripts that require manual processing later, LatentLoop understands context and intelligently updates existing sections.
  - Potential Feature: Automatically tidies up notes periodically (reorganizing sections, changing content, creating subsections) to maintain clarity, structure, and improve note-taking capability.
  - Current Progress: As a proof of concept, the product is working really well.
  - Issues:
    - We are currently struggling with implementing a queue to address program crashes and content overrides when two recordings are processed simultaneously.
    - We are also struggling with implementing animations for the modification of live notes; different animation styles were explored, and one was ultimately selected.
  - Development Workflow: We balanced our workload, took turns coding, used Live Share and VS Code, and spent a good distribution of time testing, coding, and documenting the project with user testimonials.
  - Overall Performance Summary: When asked "How does LatentLoop turn out?", the confident answer is: "It wins!"
- For the front end, the process is likely due to the time being changed from 7 seconds to 12 seconds.

## Backend Technology & Issues
- We are using Flask for the backend.
- There are significant issues/confusion regarding its current state.
- Currently facing problems or re-evaluating its implementation.
- What model are we using?
- **Frontend:**
  - Currently using a template `index.html` file.
  - Future plan: use Next.js.

## Resolved Implementation Issues
- LatentLoop's first implementation similarity threshold was 0.95, causing new sections for each transcribed chunk.
- Resolved by overriding the code, setting threshold to 0.55.
- Further issue identified: When two recordings processed simultaneously, the program tended to crash, and a later program process could override content from a previous process.

## AI Tools Used
- Heavily relied on Cloud Opus 4.5 via GitHub Copilot.
- Each request to these AI tools often took many minutes to complete.

## Language Barrier Reaction
- Expressed confusion and acknowledged not being Korean.
- Questioned the unexpected foreign language, asking for its meaning and translation.