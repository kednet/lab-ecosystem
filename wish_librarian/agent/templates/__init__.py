"""
External template package for WishLibrarian.

Re-exports the public API from ``agent.templates.loader``.
"""
from agent.templates.loader import (  # noqa: F401
    BUILTIN_TEMPLATES_DIR,
    DEFAULTS,
    ContentTemplate,
    SectionSpec,
    TemplateRegistry,
    parse_template_file,
    render_body,
    style_hash,
)

__all__ = [
    "BUILTIN_TEMPLATES_DIR",
    "DEFAULTS",
    "ContentTemplate",
    "SectionSpec",
    "TemplateRegistry",
    "parse_template_file",
    "render_body",
    "style_hash",
]
