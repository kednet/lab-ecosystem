# Превью статьи — OG-image (2:1, flat, bold)

**Формат:** OG-image (2:1, target 1200×630)
**Профиль:** lab
**Стиль:** flat
**Настроение:** bold

## Исходный запрос

```
5 ошибок карты желаний которые мешают исполнению
```

## Финальный EN-промпт

```
Bold modern flat design poster with abstract rose-pink shapes and golden accent dots, 
bright contrasting colors, dramatic composition, vibrant and decisive mood, 
rose-pink color scheme with #E11D48 primary, no text, no watermark, 
high quality, professional graphic design
```

## Параметры

| Поле | Значение |
|------|----------|
| format | og |
| width_ratio | 6 |
| height_ratio | 3 |
| aspect | 2:1 |
| target_size | [1200, 630] |
| style | flat (override из CLI) |
| mood | bold (override из CLI) |
| Размер PNG | 384×192 (~10-30 КБ в Phase 1) |

## Команда

```bash
python scripts/image.py generate og "5 ошибок карты желаний которые мешают исполнению" --style=flat --mood=bold --profile=lab
```

## Use case

Картинка для Open Graph — будет показана при шаринге статьи в VK, TG, FB, Twitter.
Phase 3 прикрепится к `publisher_skill/data/<slug>.md` через frontmatter `og_image:`.

## Связано с

- [[template-og]] — формат og
- [[publisher-skill-built]] — целевой интеграционный партнёр (Phase 3)
