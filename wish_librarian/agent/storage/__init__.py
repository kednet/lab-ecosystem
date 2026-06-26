"""Хранилище и шаблоны WishLibrarian."""
from agent.storage.file_manager import FileManager
from agent.storage.templates import (
    render_metadata_json,
    render_reviews_md,
    render_scientific_md,
    render_buy_links_md,
    render_tips_md_fallback,
    render_cover_note,
)

__all__ = [
    "FileManager",
    "render_metadata_json",
    "render_reviews_md",
    "render_scientific_md",
    "render_buy_links_md",
    "render_tips_md_fallback",
    "render_cover_note",
]
