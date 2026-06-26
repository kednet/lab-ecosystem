"""
Шаблон обложки: vintage.

Текстурный фон (grain-pattern), рукописная плашка-категория, двойная пунктирная рамка.
Подходит для: история, эпос, классика прошлых лет, «архивные» тексты.

⚠️ Контраст: текст рендерится {{TEXT_COLOR}} на {{COLOR2}} (тёмный фон) — проходит WCAG-AA.

Плейсхолдеры: {{TITLE}} {{AUTHOR}} {{COLOR1}} {{COLOR2}} {{TEXT_COLOR}} {{ACCENT}} {{BRAND_NAME}} {{DISCLAIMER}} {{CATEGORY}}
"""
TEMPLATE = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 600" width="400" height="600">
  <defs>
    <pattern id="grain" x="0" y="0" width="4" height="4" patternUnits="userSpaceOnUse">
      <circle cx="2" cy="2" r="0.6" fill="{{COLOR1}}" opacity="0.12"/>
    </pattern>
  </defs>
  <rect width="400" height="600" fill="{{COLOR2}}"/>
  <rect width="400" height="600" fill="url(#grain)"/>
  <!-- Двойная пунктирная рамка -->
  <rect x="20" y="20" width="360" height="560" fill="none"
        stroke="{{ACCENT}}" stroke-width="2" stroke-dasharray="4,3"/>
  <rect x="32" y="32" width="336" height="536" fill="none"
        stroke="{{ACCENT}}" stroke-width="1" stroke-dasharray="2,2" opacity="0.5"/>
  <!-- Категория-капс с тильдами (рукописный акцент) -->
  <text x="200" y="80" font-family="'Brush Script MT', 'Lucida Handwriting', cursive"
        font-size="22" fill="{{ACCENT}}" text-anchor="middle" font-style="italic">~ {{CATEGORY}} ~</text>
  <!-- Title -->
  <text x="200" y="295" font-family="Georgia, 'Times New Roman', serif" font-size="32"
        font-weight="bold" fill="{{TEXT_COLOR}}" text-anchor="middle">{{TITLE}}</text>
  <!-- Author (italic) -->
  <text x="200" y="330" font-family="Georgia, 'Times New Roman', serif" font-size="14"
        fill="{{TEXT_COLOR}}" text-anchor="middle" opacity="0.85" font-style="italic">{{AUTHOR}}</text>
  <!-- Декоративная линия -->
  <line x1="120" y1="455" x2="280" y2="455" stroke="{{ACCENT}}" stroke-width="1"/>
  <circle cx="200" cy="455" r="3" fill="{{ACCENT}}"/>
  <!-- Бренд-блок -->
  <text x="200" y="530" font-family="Georgia, 'Times New Roman', serif" font-size="9"
        fill="{{ACCENT}}" text-anchor="middle" letter-spacing="3">{{BRAND_NAME}}</text>
  <text x="200" y="555" font-family="Arial, 'Helvetica', sans-serif" font-size="6"
        fill="{{TEXT_COLOR}}" text-anchor="middle" opacity="0.45">{{DISCLAIMER}}</text>
</svg>'''
