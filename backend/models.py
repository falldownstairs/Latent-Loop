"""
Data structures (dataclasses) for Latent Loop.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class MarkdownSection:
    """Represents a section in the markdown file."""
    id: str
    heading: str
    level: int  # 1 for #, 2 for ##, etc.
    content: str  # Full content including heading
    line_start: int
    line_end: int


@dataclass
class PendingUpdate:
    """Represents an ambiguous update awaiting user confirmation."""
    id: str
    transcript: str
    matched_section: Optional[str]
    similarity: float
    suggested_action: str  # "update", "create", "delete"
    reason: str
    timestamp: str
