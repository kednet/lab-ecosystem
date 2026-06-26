"""
Template loader for WishLibrarian.

Templates are Markdown files with optional YAML frontmatter that declare
sections, defaults, and a system_prompt override. The Markdown body is a
user-prompt template with ``{{placeholder}}`` substitution.

Path resolution order on ``TemplateRegistry.get(kind, name)``:
  1. ``$TEMPLATES_DIR/{kind}/{name}.md``  (env override)
  2. ``<project_root>/templates/{kind}/{name}.md``  (user override)
  3. ``agent/templates/builtin/{kind}/{name}.md``  (shipped defaults)
  4. Hard-coded default per kind.

PyYAML is used when available. If not installed, a minimal flat-key parser
is used (only ``key: value`` lines, no nested structures). To enable full
frontmatter support, install ``pyyaml`` (already in requirements.txt).
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("wishlibrarian.templates")

try:  # PyYAML is optional
    import yaml  # type: ignore
    _HAS_YAML = True
except ImportError:  # pragma: no cover
    _HAS_YAML = False
    yaml = None  # type: ignore


BUILTIN_TEMPLATES_DIR = Path(__file__).parent / "builtin"
USER_TEMPLATES_DIR_NAME = "templates"

#: Defaults used when the user does not pick a template by name.
DEFAULTS: dict[str, str] = {
    "summary": "summary_v2",
    "workbook": "workbook_v2",
    "tips": "tips_v1",
}


# ── Data classes ─────────────────────────────────────────────────────
@dataclass
class SectionSpec:
    """A declared section of a content template."""

    id: str
    title: str
    type: str  # "questions" | "actions" | "table" | "scenarios" |
               # "if_then" | "habit_grid" | "reflection" | "free" | "meta"
    count: int = 0
    options: dict = field(default_factory=dict)


@dataclass
class ContentTemplate:
    """A parsed template file."""

    name: str
    kind: str  # "summary" | "workbook" | "tips"
    version: str
    description: str = ""
    sections: list[SectionSpec] = field(default_factory=list)
    body: str = ""
    system_prompt: str = ""
    raw_path: Optional[Path] = None


# ── Frontmatter parsing ──────────────────────────────────────────────
_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL,
)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Return (meta_dict, body) from a markdown file with YAML frontmatter."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    raw_meta, body = m.group(1), m.group(2)
    if _HAS_YAML:
        try:
            meta = yaml.safe_load(raw_meta) or {}
            if not isinstance(meta, dict):
                logger.warning("Frontmatter is not a dict: %r", type(meta))
                meta = {}
            return meta, body
        except Exception as e:  # noqa: BLE001
            logger.warning("YAML parse failed (%s); falling back to flat parser", e)
    # Fallback: flat key: value parser (top-level scalars only).
    meta: dict[str, Any] = {}
    for line in raw_meta.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta, body


def parse_template_file(path: Path) -> ContentTemplate:
    """Parse a single template .md file into :class:`ContentTemplate`."""
    text = path.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(text)

    raw_sections = meta.get("sections") or []
    sections: list[SectionSpec] = []
    for s in raw_sections:
        if not isinstance(s, dict):
            continue
        try:
            sections.append(
                SectionSpec(
                    id=str(s.get("id", "")),
                    title=str(s.get("title", "")),
                    type=str(s.get("type", "free")),
                    count=int(s.get("count", 0) or 0),
                    options=dict(s.get("options") or {}),
                )
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Bad section spec in %s: %s", path, e)

    return ContentTemplate(
        name=str(meta.get("name", path.stem)),
        kind=str(meta.get("kind", "workbook")),
        version=str(meta.get("version", "v1")),
        description=str(meta.get("description", "")),
        sections=sections,
        body=body,
        system_prompt=str(meta.get("system_prompt", "")),
        raw_path=path,
    )


# ── Body rendering ───────────────────────────────────────────────────
_PLACEHOLDER_RE = re.compile(r"\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}")


def render_body(tpl: ContentTemplate, variables: dict[str, Any]) -> str:
    """
    Substitute ``{{var}}`` placeholders in ``tpl.body``.

    Семантика: ``{{var}}`` в шаблоне — placeholder. Если ключ есть в
    ``variables``, заменяется на значение. Если нет — плейсхолдер
    остаётся в выводе как ``{{var}}`` (НЕ вызывает ошибку).

    Конфликт с Python format_map (где ``{{`` = литеральная ``{``) решаем
    через двухпроходный алгоритм: сначала собираем *какие* плейсхолдеры
    присутствуют в теле, потом format_map подставляет найденные значения,
    а отсутствующие оставляет ``{name}`` (через SafeDict.__missing__).
    На втором проходе превращаем нерезолвленные ``{name}`` обратно в
    ``{{name}}``.
    """
    # Найдём все {{var}} и соберём множество имён
    placeholders = set(_PLACEHOLDER_RE.findall(tpl.body))

    # Временно заменим {{var}} на {var} — это синтаксис format_map
    body = _PLACEHOLDER_RE.sub(r"{\1}", tpl.body)

    # Подставим только те переменные, для которых есть плейсхолдеры
    class _SafeDict(dict):
        def __missing__(self, key: str) -> str:  # type: ignore[override]
            return "{" + key + "}"
    out = body.format_map(_SafeDict({k: variables[k] for k in placeholders if k in variables}))

    # Теперь {name} в out — это НЕразрешённые плейсхолдеры (мы их восстановим)
    # Но ВАЖНО: format_map мог сделать экранирование {{ → { для значений,
    # содержащих { или }. Чтобы их отличить от нерезолвленных — смотрим
    # только на «{name}» где name ∈ placeholders.
    def _restore(m: re.Match) -> str:
        name = m.group(1)
        if name in placeholders and name not in variables:
            return "{{" + name + "}}"
        # иначе — это часть резолвленного значения, оставляем {name} как есть
        return m.group(0)
    out = re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", _restore, out)
    return out


# ── Registry ─────────────────────────────────────────────────────────
class TemplateRegistry:
    """
    Resolve templates by (kind, name) with priority:
    env override → user project dir → builtin → kind default.
    """

    def __init__(
        self,
        project_root: Path,
        env_templates_dir: Optional[Path] = None,
    ):
        self.project_root = Path(project_root)
        self.env_dir = Path(env_templates_dir) if env_templates_dir else None
        self.user_dir = self.project_root / USER_TEMPLATES_DIR_NAME
        self.builtin_dir = BUILTIN_TEMPLATES_DIR
        self._cache: dict[tuple[str, str], ContentTemplate] = {}

    def _candidate_paths(self, kind: str, name: str) -> list[Path]:
        paths: list[Path] = []
        if self.env_dir:
            paths.append(self.env_dir / kind / f"{name}.md")
        paths.append(self.user_dir / kind / f"{name}.md")
        paths.append(self.builtin_dir / kind / f"{name}.md")
        return paths

    def get(self, kind: str, name: str) -> ContentTemplate:
        """Return template by (kind, name). Falls back to kind default."""
        key = (kind, name)
        if key in self._cache:
            return self._cache[key]
        for cand in self._candidate_paths(kind, name):
            if cand.exists():
                tpl = parse_template_file(cand)
                self._cache[key] = tpl
                return tpl
        # Fallback: default for the kind
        default = DEFAULTS.get(kind, name)
        if default != name:
            return self.get(kind, default)
        raise FileNotFoundError(
            f"Template '{name}' (kind={kind}) not found in any of: "
            f"{[str(p) for p in self._candidate_paths(kind, name)]}"
        )

    def list(self, kind: Optional[str] = None) -> list[ContentTemplate]:
        """List all available templates (user overrides shadow builtins)."""
        out: list[ContentTemplate] = []
        seen: set[tuple[str, str]] = set()
        sources: list[Path] = []
        if self.env_dir and self.env_dir.exists():
            sources.append(self.env_dir)
        if self.user_dir.exists():
            sources.append(self.user_dir)
        if self.builtin_dir.exists():
            sources.append(self.builtin_dir)
        for base in sources:
            for p in sorted(base.rglob("*.md")):
                tpl = parse_template_file(p)
                if kind and tpl.kind != kind:
                    continue
                key = (tpl.kind, tpl.name)
                if key in seen:
                    continue
                seen.add(key)
                out.append(tpl)
        return out

    def clear_cache(self) -> None:
        """Drop the in-process template cache (e.g. after editing files)."""
        self._cache.clear()


# ── Style hashing ────────────────────────────────────────────────────
def style_hash(tone: str, length: str, audience: str, language: str) -> str:
    """Stable 6-char hash of the style fields (used in cache key)."""
    h = hashlib.sha1(
        f"{tone}|{length}|{audience}|{language}".encode("utf-8")
    ).hexdigest()
    return h[:6]


__all__ = [
    "BUILTIN_TEMPLATES_DIR",
    "DEFAULTS",
    "SectionSpec",
    "ContentTemplate",
    "TemplateRegistry",
    "parse_template_file",
    "render_body",
    "style_hash",
]
