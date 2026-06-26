"""
Шаблон обложки: мистический (эзотерика, духовные практики).
Плейсхолдеры: {{TITLE}} {{AUTHOR}} {{COLOR1}} {{COLOR2}} {{TEXT_COLOR}} {{ACCENT}} {{BRAND_NAME}} {{DISCLAIMER}}
{{TITLE_Y}} — базовая y-координата первой строки title (выставляется генератором
              с учётом числа строк после wrap, чтобы блок центрировался по высоте).
{{TITLE_LH}} — line-height между строками (выставляется генератором).
"""
TEMPLATE = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 600" width="400" height="600">
  <defs>
    <radialGradient id="g" cx="50%" cy="30%" r="70%">
      <stop offset="0%" stop-color="{{COLOR2}}"/>
      <stop offset="100%" stop-color="{{COLOR1}}"/>
    </radialGradient>
  </defs>
  <rect width="400" height="600" rx="8" fill="url(#g)"/>
  <circle cx="200" cy="120" r="40" fill="{{TEXT_COLOR}}" opacity="0.12"/>
  <circle cx="80" cy="80" r="2" fill="{{TEXT_COLOR}}" opacity="0.6"/>
  <circle cx="320" cy="100" r="1.5" fill="{{TEXT_COLOR}}" opacity="0.5"/>
  <circle cx="60" cy="500" r="1.5" fill="{{TEXT_COLOR}}" opacity="0.4"/>
  <circle cx="350" cy="450" r="2" fill="{{TEXT_COLOR}}" opacity="0.5"/>
  <text x="200" y="{{TITLE_Y}}" font-family="Georgia, 'Times New Roman', serif" font-size="26" font-weight="bold" fill="{{TEXT_COLOR}}" text-anchor="middle" letter-spacing="2">{{TITLE}}</text>
  <text x="200" y="455" font-family="Arial, 'Helvetica', sans-serif" font-size="13" fill="{{TEXT_COLOR}}" text-anchor="middle" opacity="0.7">{{AUTHOR}}</text>
  <text x="200" y="540" font-family="Arial, 'Helvetica', sans-serif" font-size="9" fill="{{TEXT_COLOR}}" text-anchor="middle" opacity="0.4">{{BRAND_NAME}}</text>
  <text x="200" y="565" font-family="Arial, 'Helvetica', sans-serif" font-size="6" fill="{{TEXT_COLOR}}" text-anchor="middle" opacity="0.3">{{DISCLAIMER}}</text>
</svg>'''
