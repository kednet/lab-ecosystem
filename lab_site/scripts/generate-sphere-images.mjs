/**
 * Генератор стоковых картинок для сфер wish-map.
 *
 * Создаёт 6 SVG-абстракций (цвет + emoji-символ) → WebP 800×800 < 200 КБ
 * в public/wish-map/spheres/<id>.webp.
 *
 * Используется:
 *  - на этапе разработки (ручной запуск: `node scripts/generate-sphere-images.mjs`)
 *  - опционально в CI перед `astro build`
 *
 * Зависимости: sharp (есть в devDeps фронта, но здесь используется из lab-site/).
 *
 * Шрифт для emoji: Noto Color Emoji → fallback на встроенный (Win11/серв. Twemoji).
 * На серверах без emoji-шрифта используем Segoe UI Emoji (Windows) / Apple Color Emoji
 * (macOS) / Noto Color Emoji (Linux). Sharp умеет их рендерить, если шрифт установлен
 * в системе. Если в CI рендер emoji не работает — fallback на цветной фон + символ.
 */

import { mkdir, writeFile } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const OUT_DIR = join(ROOT, 'public/wish-map/spheres');

const SPHERES = [
  { id: 'health',    name: 'Здоровье и тело',  emoji: '💪', color: '#10b981' },
  { id: 'relations', name: 'Семья и отношения', emoji: '❤️', color: '#ec4899' },
  { id: 'finance',   name: 'Финансы',          emoji: '💰', color: '#f59e0b' },
  { id: 'career',    name: 'Карьера и обучение', emoji: '🚀', color: '#3b82f6' },
  { id: 'spiritual', name: 'Осознанность',     emoji: '🧘', color: '#8b5cf6' },
  { id: 'rest',      name: 'Хобби и отдых',     emoji: '🏖️', color: '#06b6d4' },
];

/**
 * Светлая/тёмная вариация фона: радиальный градиент от белого к цвету сферы.
 * Поверх — 3-4 декоративных кольца + центральный эмодзи.
 */
function svgForSphere(s) {
  const cx = 400;
  const cy = 400;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="800" height="800" viewBox="0 0 800 800">
  <defs>
    <radialGradient id="bg" cx="50%" cy="40%" r="70%">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="55%" stop-color="${s.color}" stop-opacity="0.20"/>
      <stop offset="100%" stop-color="${s.color}" stop-opacity="0.45"/>
    </radialGradient>
    <filter id="soft" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="2"/>
    </filter>
  </defs>

  <rect width="800" height="800" fill="url(#bg)"/>

  <g opacity="0.35" fill="none" stroke="${s.color}" stroke-width="1.5">
    <circle cx="${cx}" cy="${cy}" r="180"/>
    <circle cx="${cx}" cy="${cy}" r="260" opacity="0.7"/>
    <circle cx="${cx}" cy="${cy}" r="340" opacity="0.5"/>
  </g>

  <g opacity="0.20" fill="${s.color}">
    <circle cx="${cx - 180}" cy="${cy - 200}" r="60"/>
    <circle cx="${cx + 220}" cy="${cy - 180}" r="40"/>
    <circle cx="${cx + 200}" cy="${cy + 220}" r="50"/>
    <circle cx="${cx - 220}" cy="${cy + 200}" r="30"/>
  </g>

  <g transform="translate(${cx - 64} ${cy - 64}) scale(1)">
    <text x="0" y="0" font-size="128" text-anchor="middle" dominant-baseline="central" font-family="Segoe UI Emoji, Apple Color Emoji, Noto Color Emoji, sans-serif">${s.emoji}</text>
  </g>

  <text x="${cx}" y="${cy + 180}" text-anchor="middle" font-family="Manrope, system-ui, sans-serif" font-size="34" font-weight="700" fill="#1f0a14">${s.name}</text>
</svg>`;
}

async function main() {
  await mkdir(OUT_DIR, { recursive: true });
  console.log(`[sphere-images] writing to ${OUT_DIR}`);

  for (const s of SPHERES) {
    const svg = svgForSphere(s);
    const svgPath = join(OUT_DIR, `${s.id}.svg`);
    const webpPath = join(OUT_DIR, `${s.id}.webp`);

    // Save .svg for reference (≤ 2 KB) — fallback if webp fails
    await writeFile(svgPath, svg, 'utf-8');

    try {
      await sharp(Buffer.from(svg), { density: 200 })
        .resize(800, 800, { fit: 'cover' })
        .webp({ quality: 80, effort: 4 })
        .toFile(webpPath);
      console.log(`  ✓ ${s.id}.webp (${s.name})`);
    } catch (err) {
      console.warn(`  ⚠ ${s.id}.webp failed: ${err.message}. SVG-only fallback.`);
    }
  }

  console.log('[sphere-images] done');
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
