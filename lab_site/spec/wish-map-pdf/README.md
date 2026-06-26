# Wish Map PDF — спецификации для Канвы

3 PDF для страницы `/wish-map/`. Генерируются вручную в Canva, экспортируются PDF, заменяются в `public/downloads/`.

| Файл | Размер | Ориентация | Стр. | Статус |
|---|---|---|---|---|
| `wish-map-blank-a3.pdf` | 420×297 мм | landscape | 1 | ✅ работает (эталон) |
| `wish-map-mini-a4.pdf` | 297×210 мм | landscape | 1 | 🟡 заглушка, нужна замена |
| `30-true-wishes.pdf` | 210×297 мм | portrait | 5 | 🟡 заглушка, нужна замена |

## Документы

- **[_style-guide.md](_style-guide.md)** — палитра, шрифты, поля, сетка, чек-листы
- **[wish-map-blank-a3.md](wish-map-blank-a3.md)** — эталон, сверяйся
- **[30-true-wishes.md](30-true-wishes.md)** — воркбук, есть готовые 30 вопросов
- **[wish-map-mini-a4.md](wish-map-mini-a4.md)** — мини-карта с примерами желаний

## Общий воркфлоу

1. Открой нужную MD-спеку
2. Создай документ в Canva (Custom size)
3. Расставь элементы по координатам
4. Используй готовые тексты/промты из спек (можно копипастить)
5. Экспортируй PDF Standard, замени файл в `public/downloads/`
6. `npm run build` + деплой на VPS
7. Проверь скачивание на `/wish-map/`

## Шрифты для Канвы

Сайт использует DM Serif Display / Manrope / Dancing Script. В Canva:
- DM Serif Display → **DM Serif Display** (есть в Canva free)
- Manrope → **Manrope** (есть в Canva)
- Dancing Script → **Dancing Script** (есть в Canva)

Все три бесплатны в Canva. Если какого-то нет — загрузи woff2 из `public/fonts/` как custom font.
