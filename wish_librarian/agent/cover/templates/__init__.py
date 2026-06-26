"""
Реестр SVG-шаблонов обложек.

Стили:
  - minimal:   плоский цвет, акцент-линия
  - gradient:  линейный градиент + полупрозрачный круг
  - geometric: плоский цвет + геометрические полигоны
  - mystical:  радиальный градиент + «звёзды» (для эзотерики)
  - business:  вертикальный градиент + акцент-рамка (для бизнеса)
  - modern:    bold sans-serif + плашка-категория (для саморазвития/бизнеса)
  - classic:   типографский серифный, светлый бумажный фон, двойная рамка
  - vintage:   текстурный фон, рукописный шрифт, пунктирная рамка
  - og:        OG-картинка 1200×630 для соцсетей (НЕ обложка книги)
"""
from .minimal import TEMPLATE as MINIMAL
from .gradient import TEMPLATE as GRADIENT
from .geometric import TEMPLATE as GEOMETRIC
from .mystical import TEMPLATE as MYSTICAL
from .business import TEMPLATE as BUSINESS
from .modern import TEMPLATE as MODERN
from .classic import TEMPLATE as CLASSIC
from .vintage import TEMPLATE as VINTAGE
from .og import TEMPLATE as OG


TEMPLATES: dict[str, str] = {
    "minimal":   MINIMAL,
    "gradient":  GRADIENT,
    "geometric": GEOMETRIC,
    "mystical":  MYSTICAL,
    "business":  BUSINESS,
    "modern":    MODERN,
    "classic":   CLASSIC,
    "vintage":   VINTAGE,
    "og":        OG,
}


def get_template(style: str) -> str:
    """Вернуть SVG-шаблон по имени стиля. Неизвестный стиль → minimal."""
    return TEMPLATES.get(style, MINIMAL)
