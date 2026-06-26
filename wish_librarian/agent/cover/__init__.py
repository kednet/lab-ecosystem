"""
Cover generator — генерация SVG/PNG обложек книг.

Публичный API:
    from agent.cover import CoverGenerator, CoverStyle
"""
from .generator import CoverGenerator, CoverStyle


__all__ = ["CoverGenerator", "CoverStyle"]
