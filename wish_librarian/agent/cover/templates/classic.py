"""
Шаблон обложки: classic.

Типографский серифный, светлый «бумажный» фон, двойная рамка.
Подходит для: психология, философия, биографии, нон-фикшн классика.

⚠️ Контраст: текст рендерится через {{COLOR1}} (тёмный) на #F5F0E6 (светлый) — проходит WCAG-AA.
{{TEXT_COLOR}} используется только для disclaimer.

Плейсхолдеры: {{TITLE}} {{AUTHOR}} {{COLOR1}} {{COLOR2}} {{TEXT_COLOR}} {{ACCENT}} {{BRAND_NAME}} {{DISCLAIMER}} {{CATEGORY}}
"""
TEMPLATE = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 600" width="400" height="600">
  <rect width="400" height="600" fill="#F5F0E6"/>
  <rect x="0" y="0" width="400" height="600" fill="none" stroke="{{COLOR1}}" stroke-width="3"/>
  <rect x="12" y="12" width="376" height="576" fill="none" stroke="{{COLOR1}}" stroke-width="1"/>
  <!-- Категория-капс с разрядкой -->
  <text x="200" y="95" font-family="Georgia, 'Times New Roman', serif" font-size="13"
        font-weight="bold" fill="{{COLOR1}}" text-anchor="middle" letter-spacing="4">{{CATEGORY}}</text>
  <line x1="155" y1="115" x2="245" y2="115" stroke="{{ACCENT}}" stroke-width="1"/>
  <!-- Title (классика, крупно) -->
  <text x="200" y="290" font-family="Georgia, 'Times New Roman', serif" font-size="34"
        font-weight="bold" fill="{{COLOR1}}" text-anchor="middle">{{TITLE}}</text>
  <!-- Author (italic) -->
  <text x="200" y="325" font-family="Georgia, 'Times New Roman', serif" font-size="15"
        fill="{{COLOR1}}" text-anchor="middle" font-style="italic">{{AUTHOR}}</text>
  <!-- Декоративный ромб по центру -->
  <g transform="translate(200 420)">
    <line x1="-25" y1="0" x2="25" y2="0" stroke="{{ACCENT}}" stroke-width="1"/>
    <line x1="0" y1="-8" x2="0" y2="8" stroke="{{ACCENT}}" stroke-width="1"/>
    <circle cx="0" cy="0" r="3" fill="{{ACCENT}}"/>
  </g>
  <!-- Бренд-блок (на светлом, COLOR1 тёмный) -->
  <text x="200" y="530" font-family="Georgia, 'Times New Roman', serif" font-size="10"
        fill="{{COLOR1}}" text-anchor="middle" letter-spacing="2">{{BRAND_NAME}}</text>
  <text x="200" y="555" font-family="Georgia, 'Times New Roman', serif" font-size="6"
        fill="{{COLOR1}}" text-anchor="middle" opacity="0.55">{{DISCLAIMER}}</text>
</svg>'''
