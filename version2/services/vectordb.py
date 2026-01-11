"""
Vector database operations using ChromaDB.
"""

import logging
from typing import Optional, Tuple

from config import (
    log_event,
    slugify_project,
    chroma_client,
    embed_model,
)
from state import CHROMA_COLLECTIONS
from services.markdown import read_notes_file, parse_markdown_sections


def get_embedding(text: str) -> list:
    """Get embedding vector for text using FastEmbed."""
    embeddings = list(embed_model.embed([text]))
    return embeddings[0].tolist()


def get_collection(project_name: str):
    """Get or create a Chroma collection for a project."""
    slug = slugify_project(project_name)
    coll_name = f"latent_loop_sections_{slug}"
    if coll_name in CHROMA_COLLECTIONS:
        return CHROMA_COLLECTIONS[coll_name]
    collection = chroma_client.get_or_create_collection(
        name=coll_name,
        metadata={"hnsw:space": "cosine", "project": project_name}
    )
    CHROMA_COLLECTIONS[coll_name] = collection
    return collection


def sync_chromadb_with_file(project_name: str):
    """Sync ChromaDB with the current state of a project's notes."""
    slug = slugify_project(project_name)
    coll_name = f"latent_loop_sections_{slug}"
    log_event(logging.INFO, "chroma_sync_start", project=project_name)
    
    # Clear cache
    if coll_name in CHROMA_COLLECTIONS:
        del CHROMA_COLLECTIONS[coll_name]
    
    # Get or create collection, then clear all existing data
    collection = chroma_client.get_or_create_collection(
        name=coll_name,
        metadata={"hnsw:space": "cosine", "project": project_name}
    )
    
    # Clear existing documents in the collection
    try:
        existing = collection.get()
        if existing and existing['ids']:
            collection.delete(ids=existing['ids'])
            log_event(logging.DEBUG, "chroma_cleared_existing", project=project_name, count=len(existing['ids']))
    except Exception as e:
        log_event(logging.DEBUG, "chroma_clear_skip", project=project_name, error=str(e))
    
    CHROMA_COLLECTIONS[coll_name] = collection
    
    content = read_notes_file(project_name)
    sections = parse_markdown_sections(content)
    
    if not sections:
        log_event(logging.INFO, "chroma_sync_no_sections", project=project_name)
        return
    
    # Index each section
    ids = []
    documents = []
    embeddings = []
    metadatas = []
    
    for section in sections:
        # Skip the main title
        if section.level == 1 and section.heading == project_name:
            continue
            
        ids.append(section.id)
        documents.append(f"{section.heading}: {section.content}")
        embeddings.append(get_embedding(f"{section.heading}: {section.content}"))
        metadatas.append({
            "heading": section.heading,
            "level": section.level,
            "line_start": section.line_start,
            "line_end": section.line_end
        })
    
    if ids:
        collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )
        log_event(logging.INFO, "chroma_sync_complete", project=project_name, sections=len(ids))
    else:
        log_event(logging.INFO, "chroma_sync_empty_after_filter", project=project_name)


def find_relevant_section(text: str, project_name: str) -> Tuple[Optional[str], Optional[str], float]:
    """
    Find the most relevant existing section for the given text within a project.
    Returns (section_id, heading, similarity_score) or (None, None, 0).
    """
    # First sync the DB with the file
    sync_chromadb_with_file(project_name)
    
    try:
        collection = get_collection(project_name)
        results = collection.query(
            query_embeddings=[get_embedding(text)],
            n_results=1,
            include=["documents", "metadatas", "distances"]
        )
    except Exception as e:
        log_event(logging.ERROR, "chroma_query_error", project=project_name, error=str(e))
        return None, None, 0
    
    if results['documents'] and results['documents'][0]:
        distance = results['distances'][0][0]
        similarity = 1 - distance  # Convert distance to similarity
        
        section_id = results['ids'][0][0]
        heading = results['metadatas'][0][0].get('heading', '')
        log_event(
            logging.INFO,
            "similarity_match",
            project=project_name,
            similarity=round(similarity, 3),
            heading=heading,
            section_id=section_id,
        )
        return section_id, heading, similarity
    
    log_event(logging.INFO, "similarity_no_match", project=project_name)
    return None, None, 0
