"""
Markdown file operations.
"""

import re
import hashlib
import logging
from typing import List

from config import (
    log_event,
    get_project_path,
)
from models import MarkdownSection


def initial_content(project_name: str) -> str:
    """Generate initial content for a new project."""
    return f"# {project_name}\n\n"


def ensure_notes_file(project_name: str):
    """Create project notes file if it doesn't exist and return its path."""
    path = get_project_path(project_name)
    if not path.exists():
        path.write_text(initial_content(project_name))
        log_event(logging.INFO, "notes_file_created", project=project_name, path=str(path))
    return path


def read_notes_file(project_name: str) -> str:
    """Read the current state of the project's notes."""
    path = ensure_notes_file(project_name)
    content = path.read_text(encoding='utf-8')
    log_event(logging.DEBUG, "notes_file_read", project=project_name, bytes=len(content))
    return content


def write_notes_file(project_name: str, content: str) -> bool:
    """Write content to a project's notes.md. Returns True on success."""
    try:
        path = ensure_notes_file(project_name)
        path.write_text(content, encoding='utf-8')
        log_event(logging.INFO, "notes_file_written", project=project_name, bytes=len(content))
        return True
    except Exception as e:
        log_event(logging.ERROR, "notes_file_write_failed", project=project_name, error=str(e))
        return False


def parse_markdown_sections(content: str) -> List[MarkdownSection]:
    """
    Parse markdown content into sections based on headings.
    Each section includes the heading and all content until the next heading.
    """
    lines = content.split('\n')
    sections = []
    current_section = None
    
    heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$')
    
    for i, line in enumerate(lines):
        match = heading_pattern.match(line)
        
        if match:
            # Close previous section
            if current_section:
                current_section.line_end = i - 1
                current_section.content = '\n'.join(
                    lines[current_section.line_start:i]
                ).strip()
                sections.append(current_section)
            
            # Start new section
            level = len(match.group(1))
            heading = match.group(2).strip()
            section_id = hashlib.md5(f"{heading}:{i}".encode()).hexdigest()[:12]
            
            current_section = MarkdownSection(
                id=section_id,
                heading=heading,
                level=level,
                content="",
                line_start=i,
                line_end=i
            )
    
    # Close last section
    if current_section:
        current_section.line_end = len(lines) - 1
        current_section.content = '\n'.join(
            lines[current_section.line_start:]
        ).strip()
        sections.append(current_section)
    
    log_event(logging.DEBUG, "markdown_sections_parsed", sections=len(sections))
    return sections
