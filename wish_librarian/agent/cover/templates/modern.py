"""
Шаблон обложки: modern.

Bold sans-serif, контрастный фон, плашка-категория сверху.
Подходит для: саморазвитие, бизнес, неметаллическая «модерн-философия».

Плейсхолдеры: {{TITLE}} {{AUTHOR}} {{COLOR1}} {{COLOR2}} {{TEXT_COLOR}} {{ACCENT}} {{BRAND_NAME}} {{DISCLAIMER}} {{CATEGORY}}
"""
TEMPLATE = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 600" width="400" height="600">
  <rect width="400" height="600" fill="{{COLOR1}}"/>
  <!-- Плашка-категория сверху -->
  <rect x="40" y="60" width="200" height="38" fill="{{ACCENT}}"/>
  <text x="140" y="85" font-family="Arial, 'Helvetica', sans-serif" font-size="14"
        font-weight="bold" fill="{{COLOR1}}" text-anchor="middle" letter-spacing="2">{{CATEGORY}}</text>
  <!-- Горизонтальная акцент-линия -->
  <line x1="40" y1="170" x2="220" y2="170" stroke="{{ACCENT}}" stroke-width="3"/>
  <!-- Title (bold sans-serif) -->
  <text x="40" y="290" font-family="'Helvetica Neue', Arial, sans-serif" font-size="38"
        font-weight="900" fill="{{TEXT_COLOR}}">{{TITLE}}</text>
  <!-- Author -->
  <text x="40" y="325" font-family="Arial, 'Helvetica', sans-serif" font-size="15"
        fill="{{TEXT_COLOR}}" opacity="0.85">{{AUTHOR}}</text>
  <!-- Усиленный бренд-блок внизу -->
  <rect x="40" y="500" width="180" height="2" fill="{{ACCENT}}"/>
  <text x="40" y="525" font-family="Arial, 'Helvetica', sans-serif" font-size="11"
        font-weight="bold" fill="{{TEXT_COLOR}}" letter-spacing="3">{{BRAND_NAME}}</text>
  <text x="40" y="544" font-family="Arial, 'Helvetica', sans-serif" font-size="8"
        fill="{{TEXT_COLOR}}" opacity="0.55">осознанные желания · сообщество</text>
  <text x="40" y="582" font-family="Arial, 'Helvetica', sans-serif" font-size="6"
        fill="{{TEXT_COLOR}}" opacity="0.4">{{DISCLAIMER}}</text>
</svg>'''
