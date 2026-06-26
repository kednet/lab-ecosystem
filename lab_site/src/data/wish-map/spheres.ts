/**
 * 6 финальных сфер жизни для конструктора карты желаний (/wish-map/).
 *
 * Объединение 8 исходных сфер (health/relations/finance/career/spiritual/rest/learning/appearance)
 * в 6 финальных (см. C:\Users\kfigh\.claude\plans\fluttering-dancing-metcalfe.md).
 *
 * Цвет используется и для UI (карточки, wheel), и для PDF (jsPDF setFillColor).
 * `gradient` — [from, to] для декоративной заливки сектора.
 * `order` — порядок отображения в topnav/sidebar.
 */

export type SphereId = 'health' | 'relations' | 'finance' | 'career' | 'spiritual' | 'rest';

export interface Sphere {
  id: SphereId;
  name: string;
  /** Краткое описание для UI и мета-тегов. */
  description: string;
  emoji: string;
  /** HEX-цвет (например #10b981). */
  color: string;
  /** Два HEX-цвета для градиента [from, to]. */
  gradient: [string, string];
  /** Порядок отображения (1..6). */
  order: 1 | 2 | 3 | 4 | 5 | 6;
}

export const spheres: readonly Sphere[] = [
  {
    id: 'health',
    name: 'Здоровье и внешность',
    description: 'Сон, движение, питание, уход за собой. Базовые привычки, на которых держится всё остальное.',
    emoji: '💪',
    color: '#10b981',
    gradient: ['#34d399', '#059669'],
    order: 1,
  },
  {
    id: 'relations',
    name: 'Семья и отношения',
    description: 'Близкие, друзья, партнёр. Качество времени и разговоров, а не количество контактов.',
    emoji: '❤️',
    color: '#ec4899',
    gradient: ['#f472b6', '#be185d'],
    order: 2,
  },
  {
    id: 'finance',
    name: 'Финансы',
    description: 'Доход, накопления, подушка, инвестиции. Спокойствие через управление деньгами.',
    emoji: '💰',
    color: '#f59e0b',
    gradient: ['#fbbf24', '#b45309'],
    order: 3,
  },
  {
    id: 'career',
    name: 'Карьера и обучение',
    description: 'Работа, навыки, проекты, менторы. Движение к делу, которое нравится.',
    emoji: '🚀',
    color: '#3b82f6',
    gradient: ['#60a5fa', '#1d4ed8'],
    order: 4,
  },
  {
    id: 'spiritual',
    name: 'Осознанность',
    description: 'Медитация, дневник, цифровой детокс, ретриты. Возвращение к себе.',
    emoji: '🧘',
    color: '#8b5cf6',
    gradient: ['#a78bfa', '#6d28d9'],
    order: 5,
  },
  {
    id: 'rest',
    name: 'Хобби и отдых',
    description: 'Отпуска, новые увлечения, дни без целей. Восстановление как часть системы.',
    emoji: '🏖️',
    color: '#06b6d4',
    gradient: ['#22d3ee', '#0e7490'],
    order: 6,
  },
] as const;

/** Карта sphere.id → Sphere для быстрого доступа. */
export const spheresById: Record<SphereId, Sphere> = spheres.reduce(
  (acc, s) => ({ ...acc, [s.id]: s }),
  {} as Record<SphereId, Sphere>,
);

/** Список ID в правильном порядке (для wheel-of-balance). */
export const sphereOrder: readonly SphereId[] = spheres
  .slice()
  .sort((a, b) => a.order - b.order)
  .map((s) => s.id);
