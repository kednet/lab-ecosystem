/**
 * Каталог аудио-треков (медитации, аффермации).
 *
 * Один источник правды для страницы /audio/:
 *  - src/data/audio.ts      — метаданные (этот файл)
 *  - src/lib/audio.ts       — хелперы (getAllTracks, getPublicTracks, getLockedTracks, getTrackBySlug)
 *  - public/audio/<slug>.mp3 — сам файл
 *  - src/components/TrackCard.astro — рендер
 *
 * Чтобы добавить новый трек:
 *  1. Положить MP3 в public/audio/<slug>.mp3
 *  2. Добавить запись в массив `audioTracks` ниже
 *  3. Сделать `npm run build` и залить dist/ на VPS
 *
 * Доступ:
 *  - public: true   — слушает любой посетитель сайта
 *  - public: false  — карточка показывает 🔒, по клику редирект на /auth/ или /pricing/
 *    (гейт UX-уровня, MP3-файл при этом лежит в публичной статике — для v1 этого достаточно)
 *
 * Треки сгенерированы в audio_skill (Yandex SpeechKit, v5 mixed, 2026-06-12):
 *  - голоса: Ermil (М) + Alena (Ж), чередование
 *  - фоны: bowls_warm / tide_calm / ambient_deep / bowls_deep / silence / sea_mantra
 *  - формат: 1 public + 9 locked (freemium-paywall)
 *
 * Обложки: фирменные градиенты «Лаборатории желаний» (брендбук 2026-06-16):
 *  - Ermil (М) → Coral Pink     #FECDD3 → #E11D48
 *  - Alena (Ж) → Blush Mauve    #FFE4E6 → #9F1239
 */

export interface AudioTrack {
  /** URL-slug, должен совпадать с именем файла в public/audio/<slug>.mp3 */
  slug: string;

  /** Название трека (как увидит пользователь) */
  title: string;

  /** 1-2 предложения: что за трек, для кого */
  description: string;

  /** Длительность в формате 'mm:ss' или 'h:mm:ss' — для UI.
   *  Реальная длительность подтягивается браузером из MP3 meta. */
  duration: string;

  /** Путь к MP3 относительно корня сайта (public/…) */
  file: string;

  /** Эмодзи-иконка для обложки (1-2 символа) */
  emoji: string;

  /** Два цвета для градиента обложки (от светлого к тёмному) */
  gradient: [string, string];

  /** true — слушает любой. false — только подписчики (см. locked-карточка) */
  public: boolean;

  /** Дата публикации ISO 'YYYY-MM-DD' */
  publishedAt: string;

  /** Голос: ermil (М) | alena (Ж) */
  voice?: 'ermil' | 'alena';

  /** Стиль/фон для UI-подсказок */
  background?: string;

  /** Теги для фильтра/поиска (опционально) */
  tags?: string[];

  /** true — у трека есть микро-CTA с открытым вопросом, показывать кнопку
   *  «Рассказать свой опыт» → /my-experiment/?from=audio-<slug> */
  has_micro_cta?: boolean;
}

/**
 * Каталог 10 аудио-треков «Лаборатории желаний».
 * Источник: audio_skill/data/library/*.yaml + tmp/library/V5_FINAL_REPORT.md.
 */
export const audioTracks: AudioTrack[] = [
  {
    slug: 'zolotye-pravila-ispolneniya-zhelaniy',
    title: 'Золотые правила исполнения желаний',
    description: 'Шесть правил, которые превращают мечты в реальность. Без воды и эзотерики — практическая база для загадывания.',
    duration: '01:55',
    file: '/audio/zolotye-pravila-ispolneniya-zhelaniy.mp3',
    emoji: '⭐',
    gradient: ['#FECDD3', '#E11D48'],
    public: true,
    publishedAt: '2026-06-13',
    voice: 'ermil',
    background: 'bowls_warm',
    tags: ['база', 'правила', 'для-старта'],
  },
  {
    slug: 'chuvstvo-ispolnennogo-zhelaniya',
    title: 'Чувство исполненного желания',
    description: 'Главная медитация «Лаборатории желаний». Почувствуй желание уже сбывшимся — и запусти механизм исполнения.',
    duration: '02:30',
    file: '/audio/chuvstvo-ispolnennogo-zhelaniya.mp3',
    emoji: '🌟',
    gradient: ['#FFE4E6', '#9F1239'],
    public: false,
    publishedAt: '2026-06-13',
    voice: 'alena',
    background: 'tide_calm',
    tags: ['медитация', 'главная-техника'],
  },
  {
    slug: 'detskie-ustanovki-pro-dengi',
    title: 'Детские установки про деньги',
    description: 'Какие фразы родителей до сих пор блокируют твой доход. Практика замены старых программ на новые.',
    duration: '02:14',
    file: '/audio/detskie-ustanovki-pro-dengi.mp3',
    emoji: '💸',
    gradient: ['#FECDD3', '#E11D48'],
    public: false,
    publishedAt: '2026-06-13',
    voice: 'ermil',
    background: 'ambient_deep',
    tags: ['деньги', 'установки', 'детство'],
  },
  {
    slug: 'malenkie-shagi',
    title: 'Маленькие шаги',
    description: 'Мечты сбываются не по волшебству, а через 15-минутные действия каждый день. Практика «кирпичика».',
    duration: '01:51',
    file: '/audio/malenkie-shagi.mp3',
    emoji: '🧱',
    gradient: ['#FFE4E6', '#9F1239'],
    public: false,
    publishedAt: '2026-06-13',
    voice: 'alena',
    background: 'bowls_deep',
    tags: ['действия', 'привычки', 'мотивация'],
  },
  {
    slug: 'razreshenie-sebe',
    title: 'Разрешение себе',
    description: 'Пять главных разрешений: хотеть, просить, получать, ошибаться, быть счастливой. Повторяй за голосом.',
    duration: '01:59',
    file: '/audio/razreshenie-sebe.mp3',
    emoji: '🔓',
    gradient: ['#FECDD3', '#E11D48'],
    public: false,
    publishedAt: '2026-06-13',
    voice: 'ermil',
    background: 'bowls_warm',
    tags: ['аффермации', 'разрешения'],
  },
  {
    slug: 'tehnika-100-zhelaniy',
    title: 'Техника «100 желаний»',
    description: 'Выпиши 100 желаний за 40 минут. После 70-го пункта начинается правда. Возьми ручку и следуй за голосом.',
    duration: '02:37',
    file: '/audio/tehnika-100-zhelaniy.mp3',
    emoji: '📝',
    gradient: ['#FFE4E6', '#9F1239'],
    public: false,
    publishedAt: '2026-06-13',
    voice: 'alena',
    background: 'silence',
    tags: ['практика', 'самопознание'],
  },
  {
    slug: 'proschenie-sebya',
    title: 'Прощение себя',
    description: 'Тот груз, который ты нёс годами. Положи руку на сердце и отпусти — за ошибки, за слабости, за неправильный выбор.',
    duration: '02:07',
    file: '/audio/proschenie-sebya.mp3',
    emoji: '🕊️',
    gradient: ['#FECDD3', '#E11D48'],
    public: false,
    publishedAt: '2026-06-13',
    voice: 'ermil',
    background: 'tide_calm',
    tags: ['медитация', 'прощение', 'исцеление'],
  },
  {
    slug: 'tehnika-zachem',
    title: 'Техника «Зачем?»',
    description: 'Докопайся до сути желания. Пять кругов вопроса — и за «квартирой» откроется совсем другая ценность.',
    duration: '02:34',
    file: '/audio/tehnika-zachem.mp3',
    emoji: '🔍',
    gradient: ['#FFE4E6', '#9F1239'],
    public: false,
    publishedAt: '2026-06-13',
    voice: 'alena',
    background: 'tide_calm',
    tags: ['техника', 'вопросы', 'истинные-желания'],
  },
  {
    slug: 'utrennee-namerenie',
    title: 'Утреннее намерение',
    description: 'Три минуты на настройку дня. Проговори намерение — и весь день будет идти по-другому.',
    duration: '01:15',
    file: '/audio/utrennee-namerenie.mp3',
    emoji: '🌅',
    gradient: ['#FECDD3', '#E11D48'],
    public: false,
    publishedAt: '2026-06-13',
    voice: 'ermil',
    background: 'sea_mantra',
    tags: ['утро', 'намерение', 'короткое'],
  },
  {
    slug: 'rabota-s-vnutrennim-kritikom',
    title: 'Работа с внутренним критиком',
    description: 'Познакомься с критиком поближе, поблагодари его и пригласи на его место внутреннего наставника.',
    duration: '02:12',
    file: '/audio/rabota-s-vnutrennim-kritikom.mp3',
    emoji: '🧭',
    gradient: ['#FFE4E6', '#9F1239'],
    public: false,
    publishedAt: '2026-06-13',
    voice: 'alena',
    background: 'ambient_deep',
    tags: ['внутренний-критик', 'самоподдержка'],
  },
  {
    slug: 'muzhitskaya-teoriya-neveroyatnosti',
    title: 'Теория невероятности — мини-эксперимент',
    description: 'Пять правил Татьяны Мужицкой, которые превращают мечты в реальность, + открытый вопрос для самой себя. После прослушивания — расскажи свой опыт в «Моём эксперименте».',
    duration: '02:27',
    file: '/audio/muzhitskaya-teoriya-neveroyatnosti.mp3',
    emoji: '🧪',
    gradient: ['#FFE4E6', '#9F1239'],
    public: true,
    publishedAt: '2026-06-19',
    voice: 'alena',
    background: 'tide_calm',
    has_micro_cta: true,
    tags: ['микро-эксперимент', 'открытый-вопрос'],
  },
];

export function getAllTracks(): AudioTrack[] {
  return audioTracks;
}

export function getPublicTracks(): AudioTrack[] {
  return audioTracks.filter((t) => t.public);
}

export function getLockedTracks(): AudioTrack[] {
  return audioTracks.filter((t) => !t.public);
}

export function getTrackBySlug(slug: string): AudioTrack | undefined {
  return audioTracks.find((t) => t.slug === slug);
}
