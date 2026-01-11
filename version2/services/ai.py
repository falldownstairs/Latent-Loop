"""
AI operations: Gemini synthesis and Groq Whisper transcription.
"""

import io
import re
import logging
from typing import Optional, Tuple, Dict

from config import log_event, gemini_model, groq_client


# --- INTENT DETECTION ---

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


# --- GEMINI OPERATIONS ---

def gemini_update_file(
    current_content: str,
    target_section: Optional[str],
    new_transcript: str,
    action: str,  # "update" or "create"
    previous_context: Optional[str] = None
) -> Tuple[str, Dict]:
    """
    Use Gemini to update the markdown file.
    Returns (new_content, change_info).
    
    previous_context: Recent transcription for continuity understanding
    """
    if not gemini_model:
        log_event(logging.WARNING, "gemini_unavailable_fallback", action=action)
        return fallback_update(current_content, target_section, new_transcript, action)
    
    context_block = ""
    if previous_context:
        context_block = f"""
**Previous Context (for continuity):**
"{previous_context}"

"""
    
    if action == "create":
        prompt = f"""You are a Recursive Markdown Editor for a note-taking app.

**Current File State:**
```markdown
{current_content}
```
{context_block}**New Input (from voice transcription):**
"{new_transcript}"

**Instruction:**
This is a NEW TOPIC. Create a new section (## heading) for this content.
- Place it at the END of the file, before any closing content.
- Create a short, punchy heading (3-5 words).
- Convert the transcript into concise bullet points.
- Use the previous context to understand continuity if provided.
- Return the ENTIRE updated Markdown file.

Return ONLY the markdown content, no code blocks or explanations."""

    else:  # update
        prompt = f"""You are a Recursive Markdown Editor for a note-taking app.

**Current File State:**
```markdown
{current_content}
```

**Target Section:** {target_section}
{context_block}**New Input (from voice transcription):**
"{new_transcript}"

**Instruction:**
Rewrite the **Target Section** only to incorporate the new information:
1. If the user CORRECTED themselves (e.g., "actually, use X instead of Y"), REPLACE the old information completely with the new correct information. Do NOT use strikethrough - just update to the correct value.
2. If they ADDED detail, integrate it into existing bullet points or add new ones.
3. If they EXPANDED on a point, refine that bullet.
4. Keep it concise - no redundant information.
5. Use the previous context to understand continuity if provided.
6. NEVER use ~~strikethrough~~ formatting - always replace outdated info cleanly.

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
        
        # If create action, try to find the new heading for animation
        extracted_section = target_section
        if action == "create":
            # Find the last ## heading in the new content
            headings = re.findall(r'^##\s+(.+)$', new_content, re.MULTILINE)
            if headings:
                extracted_section = headings[-1].strip()
        
        # Calculate diff info
        change_info = calculate_diff(current_content, new_content, extracted_section)
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
    """Fallback update without Gemini - simple append logic."""
    
    if action == "create":
        # Generate simple heading from first words
        words = new_transcript.split()
        heading = " ".join(words[:4]).title() if len(words) >= 4 else new_transcript.title()
        
        new_section = f"\n\n## {heading}\n\n- {new_transcript}\n"
        new_content = current_content.rstrip() + new_section
        log_event(logging.INFO, "fallback_create_section", heading=heading)
        
        return new_content, {
            "action": "create",
            "target_section": heading,
            "lines_added": [len(current_content.split('\n')) + 1]
        }
    
    # Update: append to target section
    lines = current_content.split('\n')
    new_lines = []
    found_target = False
    inserted = False
    
    for i, line in enumerate(lines):
        new_lines.append(line)
        
        # Find target section heading
        if not found_target and target_section and target_section in line:
            found_target = True
            continue
        
        # Insert before next heading if we found target
        if found_target and not inserted and line.startswith('#'):
            new_lines.insert(len(new_lines) - 1, f"- {new_transcript}")
            inserted = True
    
    # Append at end if target found but no next heading
    if found_target and not inserted:
        new_lines.append(f"- {new_transcript}")
    
    log_event(logging.INFO, "fallback_update_section", heading=target_section)
    return '\n'.join(new_lines), {
        "action": "update",
        "target_section": target_section,
        "lines_modified": []
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
