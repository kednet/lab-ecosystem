"""
Генератор цветовых схем для обложек.

Детерминированный выбор палитры по md5(title + author).
WCAG-AA контраст-чек для пар (text, primary/secondary).
"""
from __future__ import annotations

import hashlib
from typing import Dict, Optional


# ── Палитры ────────────────────────────────────────────────────────
# Каждая схема: основной фон, акцент, текст, акцент-точка.
# text подобран так, чтобы на primary был контраст ≥ 4.5:1 (WCAG-AA).
SCHEMES: Dict[str, Dict[str, str]] = {
    "blue_teal": {
        "primary":   "#1E3A8A",  # тёмно-синий
        "secondary": "#0F766E",  # тёмный teal (светлый #0D9488 не проходил AA с белым)
        "text":      "#FFFFFF",
        "accent":    "#F59E0B",  # янтарный
    },
    "purple_pink": {
        "primary":   "#6D28D9",  # фиолетовый
        "secondary": "#9D174D",  # тёмно-розовый (DB2777 не проходил AA с белым)
        "text":      "#FFFFFF",
        "accent":    "#FBBF24",  # золотой
    },
    "green_gold": {
        "primary":   "#064E3B",  # тёмно-зелёный (065F46 еле проходил)
        "secondary": "#92400E",  # тёмная бронза
        "text":      "#FFFFFF",
        "accent":    "#FCD34D",  # светло-золотой
    },
    "red_orange": {
        "primary":   "#7F1D1D",  # тёмно-красный (991B1B еле проходил)
        "secondary": "#9A3412",  # тёмно-оранжевый (EA580C не проходил AA)
        "text":      "#FFFFFF",
        "accent":    "#FDE047",  # лимонный
    },
    "dark_slate": {
        "primary":   "#1F2937",  # графит
        "secondary": "#374151",  # серый
        "text":      "#F9FAFB",  # почти белый
        "accent":    "#F59E0B",
    },
    "dark_lavender": {
        "primary":   "#3B0764",  # тёмно-лавандовый (замена плохо-контрастной dark_light)
        "secondary": "#581C87",  # сливовый
        "text":      "#F5F3FF",  # светло-лавандовый
        "accent":    "#FACC15",  # жёлтый
    },
}


# ── WCAG-AA контраст ───────────────────────────────────────────────
def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    """WCAG luminance: https://www.w3.org/TR/WCAG21/#dfn-relative-luminance"""
    def channel(c: int) -> float:
        c_s = c / 255.0
        return c_s / 12.92 if c_s <= 0.03928 else ((c_s + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(fg: str, bg: str) -> float:
    """Контраст между двумя hex-цветами. ≥ 4.5 = WCAG-AA для текста."""
    l1 = _relative_luminance(_hex_to_rgb(fg))
    l2 = _relative_luminance(_hex_to_rgb(bg))
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


# ── Генератор ──────────────────────────────────────────────────────
class ColorGenerator:
    """Детерминированно выбирает и валидирует цветовую схему."""

    SCHEMES = SCHEMES

    def generate(
        self,
        title: str,
        author: str,
        *,
        forced_scheme: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Вернуть валидную палитру.
        - forced_scheme: имя конкретной палитры (иначе — по hash).
        - Авто-фикс контраста: если text на primary < 4.5, переключаем
          text на #FFFFFF или #1F2937 (для светлого primary).
        """
        if forced_scheme and forced_scheme in self.SCHEMES:
            scheme = self.SCHEMES[forced_scheme].copy()
        else:
            scheme = self._pick_by_hash(title, author)

        scheme = self._fix_contrast(scheme)
        return scheme

    def _pick_by_hash(self, title: str, author: str) -> Dict[str, str]:
        seed = f"{title}_{author}".encode("utf-8")
        h = int(hashlib.md5(seed).hexdigest()[:8], 16)
        keys = list(self.SCHEMES.keys())
        return self.SCHEMES[keys[h % len(keys)]].copy()

    def _fix_contrast(self, scheme: Dict[str, str]) -> Dict[str, str]:
        """Гарантировать WCAG-AA контраст text на primary и secondary."""
        for bg_key in ("primary", "secondary"):
            bg = scheme[bg_key]
            if contrast_ratio(scheme["text"], bg) < 4.5:
                # Если фон светлый → тёмный текст, иначе → белый
                bg_lum = _relative_luminance(_hex_to_rgb(bg))
                scheme["text"] = "#1F2937" if bg_lum > 0.5 else "#FFFFFF"
        return scheme

    def check_contrast(self, scheme: Dict[str, str]) -> bool:
        """True, если text контрастен на ОБОИХ primary и secondary ≥ 4.5."""
        return all(
            contrast_ratio(scheme["text"], scheme[bg]) >= 4.5
            for bg in ("primary", "secondary")
        )


# ── Singleton ──────────────────────────────────────────────────────
_default_gen: Optional[ColorGenerator] = None


def get_color_generator() -> ColorGenerator:
    global _default_gen
    if _default_gen is None:
        _default_gen = ColorGenerator()
    return _default_gen
