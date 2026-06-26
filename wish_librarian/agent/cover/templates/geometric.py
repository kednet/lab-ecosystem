"""
Шаблон обложки: геометрический.
Плейсхолдеры: {{TITLE}} {{AUTHOR}} {{COLOR1}} {{COLOR2}} {{TEXT_COLOR}} {{ACCENT}} {{BRAND_NAME}} {{DISCLAIMER}}
"""
TEMPLATE = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 600" width="400" height="600">
  <rect width="400" height="600" rx="8" fill="{{COLOR1}}"/>
  <polygon points="50,450 200,400 350,450" fill="{{COLOR2}}" opacity="0.15"/>
  <polygon points="100,500 200,440 300,500" fill="{{ACCENT}}" opacity="0.1"/>
  <line x1="60" y1="200" x2="340" y2="200" stroke="{{ACCENT}}" stroke-width="1" opacity="0.5"/>
  <text x="200" y="330" font-family="Georgia, 'Times New Roman', serif" font-size="27" font-weight="bold" fill="{{TEXT_COLOR}}" text-anchor="middle">{{TITLE}}</text>
  <text x="200" y="380" font-family="Arial, 'Helvetica', sans-serif" font-size="13" fill="{{TEXT_COLOR}}" text-anchor="middle" opacity="0.7">{{AUTHOR}}</text>
  <text x="200" y="540" font-family="Arial, 'Helvetica', sans-serif" font-size="9" fill="{{TEXT_COLOR}}" text-anchor="middle" opacity="0.4">{{BRAND_NAME}}</text>
  <text x="200" y="565" font-family="Arial, 'Helvetica', sans-serif" font-size="6" fill="{{TEXT_COLOR}}" text-anchor="middle" opacity="0.3">{{DISCLAIMER}}</text>
</svg>'''
