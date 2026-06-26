# /publish-audio <slug>

Полный цикл: YAML → SSML → TTS (Yandex SpeechKit) → ffmpeg mix → R2 → Astro-страница → deploy → анонс.

## Использование

```bash
# В чате: «опубликуй аудио zolotye-pravila» или
# /publish-audio zolotye-pravila

# Только превью (без R2/deploy/VK):
/publish-audio zolotye-pravila --dry-run

# Только TTS + mix (без заливки и анонса):
/publish-audio zolotye-pravila --only=tts

# Только render страницы (если mp3 уже в R2):
/publish-audio zolotye-pravila --only=render
```

## Алгоритм

1. **state check** — `python scripts/state.py show <slug>`. Если `status=published` и нет `--force` → СТОП.
2. **YAML check** — `data/library/<slug>.yaml` существует? Если нет → СТОП, ссылка на `/adapt-pdf` или `/adapt-text`.
3. **SSML build** — `python scripts/ssml_build.py data/library/<slug>.yaml --out=tmp/<slug>.ssml`. Пометить `state[slug].ssml_path`.
4. **TTS** — `python scripts/tts_yandex.py tmp/<slug>.ssml --voice=<voice> --out=tmp/<slug>-voice.mp3`. Пометить `state[slug].voice_path`, `voice_duration_sec`.
5. **Mix** — `python scripts/mix_audio.py tmp/<slug>-voice.mp3 --background=<bg> --out=tmp/<slug>-full.mp3`. Пометить `state[slug].mixed_path`, `final_duration_sec`.
6. **Upload R2** — `python scripts/upload_r2.py tmp/<slug>-full.mp3 --key=<slug>.mp3`. Пометить `state[slug].r2_url`, `uploaded_at`.
7. **Render** — `python scripts/render_audio.py data/library/<slug>.yaml --r2-url=<state[slug].r2_url>`. Пометить `state[slug].page_path`.
8. **Deploy** — вызвать `python publisher_skill/scripts/deploy_pages.py` (через обёртку `scripts/deploy_audio.py`). Пометить `state[slug].deployed_at`, `live_url`.
9. **Announce** — `python scripts/announce_audio.py <slug> --channels=tg,vk,email`. Использует `publisher_skill/scripts/post_telegram.py`, `post_vk.py`, `send_email.py` с шаблонами `templates/announcement-tg-audio.md`, `announcement-vk-audio.md`. Пометить `state[slug].channels_posted`.
10. **Notify** — `python publisher_skill/scripts/notify_admin.py` → @kfigh в TG: «Аудио «<title>» опубликовано ✅».
11. **Final** — `state[slug].status = "published"`, `published_at = now()`.

## Ошибки

- Если шаг 4 (TTS) падает → `state[slug].status = "failed"`, `error = "<TTS error>"`, откатить всё до TTS не нужно (можно начать с шага 4).
- Если шаг 7 (Render) падает → `state[slug].status = "failed"`, начать с шага 7 при повторном запуске.
- `python scripts/state.py reset <slug> --force` — полный сброс.

## Зависимости от других скиллов

- `publisher_skill/scripts/deploy_pages.py` — build + wrangler pages deploy
- `publisher_skill/scripts/post_telegram.py` + `post_vk.py` + `send_email.py` — анонсы
- `publisher_skill/scripts/notify_admin.py` — уведомление админа
- `wish_librarian/agent/ai/factory.py` — LLM-фабрика (Phase 2, для /adapt-pdf если не хватает локальной адаптации)
