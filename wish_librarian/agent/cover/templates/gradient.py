"""
Шаблон обложки: градиентный.
Плейсхолдеры: {{TITLE}} {{AUTHOR}} {{COLOR1}} {{COLOR2}} {{TEXT_COLOR}} {{ACCENT}} {{BRAND_NAME}} {{DISCLAIMER}}
"""
TEMPLATE = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 600" width="400" height="600">
  <defs>
    <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{{COLOR1}}"/>
      <stop offset="100%" stop-color="{{COLOR2}}"/>
    </linearGradient>
  </defs>
  <rect width="400" height="600" rx="8" fill="url(#g)"/>
  <circle cx="200" cy="180" r="60" fill="{{TEXT_COLOR}}" opacity="0.08"/>
  <text x="200" y="320" font-family="Georgia, 'Times New Roman', serif" font-size="26" font-weight="bold" fill="{{TEXT_COLOR}}" text-anchor="middle">{{TITLE}}</text>
  <text x="200" y="370" font-family="Arial, 'Helvetica', sans-serif" font-size="13" fill="{{TEXT_COLOR}}" text-anchor="middle" opacity="0.8">{{AUTHOR}}</text>
  <text x="200" y="540" font-family="Arial, 'Helvetica', sans-serif" font-size="9" fill="{{TEXT_COLOR}}" text-anchor="middle" opacity="0.4">{{BRAND_NAME}}</text>
  <text x="200" y="565" font-family="Arial, 'Helvetica', sans-serif" font-size="6" fill="{{TEXT_COLOR}}" text-anchor="middle" opacity="0.3">{{DISCLAIMER}}</text>
</svg>'''
