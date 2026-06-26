"""
Шаблон обложки: деловой (бизнес, финансы, карьера).
Плейсхолдеры: {{TITLE}} {{AUTHOR}} {{COLOR1}} {{COLOR2}} {{TEXT_COLOR}} {{ACCENT}} {{BRAND_NAME}} {{DISCLAIMER}}
"""
TEMPLATE = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 600" width="400" height="600">
  <defs>
    <linearGradient id="g" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="{{COLOR1}}"/>
      <stop offset="100%" stop-color="{{COLOR2}}"/>
    </linearGradient>
  </defs>
  <rect width="400" height="600" rx="8" fill="url(#g)"/>
  <rect x="0" y="0" width="8" height="600" fill="{{ACCENT}}" opacity="0.8"/>
  <rect x="392" y="0" width="8" height="600" fill="{{ACCENT}}" opacity="0.8"/>
  <text x="200" y="310" font-family="Georgia, 'Times New Roman', serif" font-size="24" font-weight="bold" fill="{{TEXT_COLOR}}" text-anchor="middle">{{TITLE}}</text>
  <line x1="140" y1="340" x2="260" y2="340" stroke="{{ACCENT}}" stroke-width="2"/>
  <text x="200" y="380" font-family="Arial, 'Helvetica', sans-serif" font-size="13" fill="{{TEXT_COLOR}}" text-anchor="middle" opacity="0.7">{{AUTHOR}}</text>
  <text x="200" y="540" font-family="Arial, 'Helvetica', sans-serif" font-size="9" fill="{{TEXT_COLOR}}" text-anchor="middle" opacity="0.4">{{BRAND_NAME}}</text>
  <text x="200" y="565" font-family="Arial, 'Helvetica', sans-serif" font-size="6" fill="{{TEXT_COLOR}}" text-anchor="middle" opacity="0.3">{{DISCLAIMER}}</text>
</svg>'''
