"""
OG-картинка 1200×630 (стандарт OpenGraph для VK / Telegram / Facebook / Twitter).

Горизонтальная композиция:
  • Левая половина (0-720): brand-блок с брендом и дисклеймером.
  • Правая половина (720-1200): мини-обложка книги (background primary, text).

Плейсхолдеры (те же, что у остальных шаблонов):
  {{TITLE}} {{AUTHOR}} {{COLOR1}} {{COLOR2}} {{TEXT_COLOR}} {{ACCENT}}
  {{BRAND_NAME}} {{DISCLAIMER}}
"""
TEMPLATE = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" width="1200" height="630">
  <!-- Фон -->
  <defs>
    <linearGradient id="ogBg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{{COLOR1}}"/>
      <stop offset="100%" stop-color="{{COLOR2}}"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#ogBg)"/>

  <!-- Левая половина: brand-блок -->
  <g transform="translate(60, 100)">
    <!-- Логотип-точка -->
    <circle cx="20" cy="20" r="20" fill="{{ACCENT}}"/>
    <text x="60" y="30" font-family="Georgia, 'Times New Roman', serif" font-size="28" font-weight="bold" fill="{{TEXT_COLOR}}">{{BRAND_NAME}}</text>

    <!-- Главный заголовок -->
    <text x="0" y="200" font-family="Georgia, 'Times New Roman', serif" font-size="56" font-weight="bold" fill="{{TEXT_COLOR}}">{{TITLE}}</text>
    <!-- Автор -->
    <text x="0" y="260" font-family="Arial, 'Helvetica', sans-serif" font-size="28" fill="{{TEXT_COLOR}}" opacity="0.85">{{AUTHOR}}</text>

    <!-- Разделитель -->
    <line x1="0" y1="310" x2="120" y2="310" stroke="{{ACCENT}}" stroke-width="3"/>

    <!-- Подпись -->
    <text x="0" y="360" font-family="Arial, 'Helvetica', sans-serif" font-size="20" fill="{{TEXT_COLOR}}" opacity="0.8">Конспект · практика · упражнения</text>
    <text x="0" y="390" font-family="Arial, 'Helvetica', sans-serif" font-size="18" fill="{{TEXT_COLOR}}" opacity="0.65">pulab.online/books/&lt;slug&gt;</text>
  </g>

  <!-- Правая половина: мини-обложка книги -->
  <g transform="translate(800, 90)">
    <!-- Тень обложки -->
    <rect x="6" y="6" width="320" height="450" rx="6" fill="#000000" opacity="0.25"/>
    <!-- Сама обложка -->
    <rect x="0" y="0" width="320" height="450" rx="6" fill="{{COLOR1}}"/>
    <!-- Акцент-линия -->
    <line x1="32" y1="140" x2="288" y2="140" stroke="{{ACCENT}}" stroke-width="2"/>
    <!-- Title (многократный перенос: до 2 строк) -->
    <text x="160" y="230" font-family="Georgia, 'Times New Roman', serif" font-size="22" font-weight="bold" fill="{{TEXT_COLOR}}" text-anchor="middle">
      <tspan x="160" dy="0">{{TITLE}}</tspan>
    </text>
    <text x="160" y="270" font-family="Arial, 'Helvetica', sans-serif" font-size="14" fill="{{TEXT_COLOR}}" text-anchor="middle" opacity="0.75">{{AUTHOR}}</text>
    <text x="160" y="410" font-family="Arial, 'Helvetica', sans-serif" font-size="8" fill="{{TEXT_COLOR}}" text-anchor="middle" opacity="0.5">{{BRAND_NAME}}</text>
  </g>

  <!-- Footer disclaimer на всю ширину -->
  <text x="60" y="600" font-family="Arial, 'Helvetica', sans-serif" font-size="12" fill="{{TEXT_COLOR}}" opacity="0.45">{{DISCLAIMER}}</text>
</svg>'''
