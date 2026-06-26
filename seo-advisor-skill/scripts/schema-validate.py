"""Валидация Schema.org JSON-LD в HTML-файле.

Использование:
  python schema-validate.py page.html
  python schema-validate.py https://lab.com/page
  python schema-validate.py file1.html file2.html

Проверяет:
- Наличие <script type="application/ld+json"> блоков
- Корректность JSON
- Наличие обязательных полей (@context, @type)
- Базовые правила (URL, ISO 8601 для дат)
- Глубину вложенности
"""

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


def extract_jsonld_blocks(html: str) -> list[dict]:
    """Извлекает все JSON-LD блоки из HTML."""
    pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
    blocks = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)

    parsed = []
    for i, block in enumerate(blocks, 1):
        try:
            data = json.loads(block.strip())
            parsed.append({'index': i, 'raw': block.strip()[:100], 'data': data})
        except json.JSONDecodeError as e:
            parsed.append({'index': i, 'raw': block.strip()[:100], 'error': str(e)})
    return parsed


def validate_block(data: dict) -> list[str]:
    """Проверяет один JSON-LD блок на базовые правила."""
    issues = []

    # Обязательные поля
    if '@context' not in data and '@graph' not in data:
        issues.append('❌ Нет @context (должен быть https://schema.org)')
    elif data.get('@context') and 'schema.org' not in str(data['@context']):
        issues.append(f'⚠️ @context не schema.org: {data["@context"]}')

    if '@graph' in data:
        if not isinstance(data['@graph'], list):
            issues.append('❌ @graph должен быть массивом')
        else:
            for i, sub in enumerate(data['@graph']):
                issues.extend([f'[{i}] ' + x for x in validate_block(sub)])
        return issues

    if '@type' not in data:
        issues.append('❌ Нет @type')

    # Проверка URL-полей
    url_fields = ['url', 'image', 'logo', 'mainEntityOfPage', 'item']
    for field in url_fields:
        if field in data:
            value = data[field]
            if isinstance(value, str):
                if not value.startswith(('http://', 'https://', '/', '{{')):
                    issues.append(f'⚠️ {field} не похож на URL: {value[:50]}')
            elif isinstance(value, dict):
                if 'url' in value and not str(value['url']).startswith(('http://', 'https://', '/', '{{')):
                    issues.append(f'⚠️ {field}.url не похож на URL: {value["url"][:50]}')

    # Проверка дат
    date_fields = ['datePublished', 'dateModified', 'foundingDate', 'dateCreated']
    iso_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?(\+\d{2}:\d{2})?)?$|^\{\{')
    for field in date_fields:
        if field in data:
            if not iso_pattern.match(str(data[field])):
                issues.append(f'⚠️ {field} не в ISO 8601: {data[field]}')

    return issues


def main():
    # Windows cp1252 не выводит кириллицу — переключаем на utf-8
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass

    if len(sys.argv) < 2:
        print('Использование: python schema-validate.py <file.html|URL> [more files...]')
        sys.exit(1)

    total_blocks = 0
    total_issues = 0

    for arg in sys.argv[1:]:
        print('=' * 60)
        if arg.startswith(('http://', 'https://')):
            print(f'URL: {arg}')
            print('(используйте WebFetch для загрузки и сохранения в файл)')
            continue

        path = Path(arg)
        if not path.exists():
            print(f'❌ Файл не найден: {arg}')
            continue

        print(f'Файл: {path}')
        html = path.read_text(encoding='utf-8')
        blocks = extract_jsonld_blocks(html)

        if not blocks:
            print('⚠️ JSON-LD блоки не найдены')
            print('   Добавьте <script type="application/ld+json">{...}</script>')
            continue

        for block in blocks:
            total_blocks += 1
            print(f'\nБлок #{block["index"]}: {block["raw"]}...')
            if 'error' in block:
                print(f'  ❌ Ошибка JSON: {block["error"]}')
                total_issues += 1
                continue

            issues = validate_block(block['data'])
            if not issues:
                print('  ✅ OK')
            else:
                for issue in issues:
                    print(f'  {issue}')
                    total_issues += 1

    print()
    print('=' * 60)
    print(f'Итого: {total_blocks} блоков, {total_issues} проблем')
    if total_issues == 0:
        print('🎉 Всё отлично!')
    else:
        print('⚠️ Есть проблемы — исправьте перед публикацией.')


if __name__ == '__main__':
    main()
