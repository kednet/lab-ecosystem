import type { Env } from '../types';
import { KV_KEYS } from './kv';

/**
 * Транслит-слагификатор для русского/латиницы. Безопасный для URL.
 * Зеркало одноимённой функции в python-service.
 */
export function slugify(text: string): string {
  const table: Record<string, string> = {
    а: 'a', б: 'b', в: 'v', г: 'g', д: 'd', е: 'e', ё: 'e',
    ж: 'zh', з: 'z', и: 'i', й: 'i', к: 'k', л: 'l', м: 'm',
    н: 'n', о: 'o', п: 'p', р: 'r', с: 's', т: 't', у: 'u',
    ф: 'f', х: 'h', ц: 'ts', ч: 'ch', ш: 'sh', щ: 'shch',
    ъ: '', ы: 'y', ь: '', э: 'e', ю: 'yu', я: 'ya',
  };
  const out: string[] = [];
  for (const ch of text.toLowerCase()) {
    if (table[ch]) out.push(table[ch]!);
    else if (/[a-z0-9]/.test(ch) && ch.charCodeAt(0) < 128) out.push(ch);
    else if (ch === ' ' || ch === '-' || ch === '_') out.push('-');
  }
  return out.join('').replace(/-+/g, '-').replace(/^-|-$/g, '').slice(0, 80) || 'book';
}

const CONTENT_TYPES: Record<string, string> = {
  md: 'text/markdown; charset=utf-8',
  txt: 'text/plain; charset=utf-8',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  png: 'image/png',
  webp: 'image/webp',
  pdf: 'application/pdf',
  json: 'application/json; charset=utf-8',
};

export function contentTypeFor(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase() ?? '';
  return CONTENT_TYPES[ext] ?? 'application/octet-stream';
}

/**
 * Один файл книги, хранится в KV под book:{slug}:file:{name} отдельно
 * (иначе 25 МБ на значение KV). Метаданные (BookRecord) — отдельно.
 */
export interface BookFileBlob {
  slug: string;
  name: string;
  contentType: string;
  /** base64 от бинарника (для картинок/PDF) или UTF-8 текст. */
  dataBase64: string;
  size: number;
  kind: 'summary' | 'workbook' | 'tips' | 'cover' | 'other';
}

export interface BookFileMeta {
  name: string;
  size: number;
  contentType: string;
  kind: BookFileBlob['kind'];
}

/**
 * Публичный BookRecord: лежит в KV по ключу book:{slug}.
 * Без полей с данными файлов — только мета.
 */
export interface BookRecord {
  slug: string;
  title: string;
  author: string;
  year?: number | null;
  description?: string;
  files: BookFileMeta[];
  createdAt: string;
  generatedBy?: string;
  generatedByJob?: string;
}

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 МБ на файл (md и jpg легко влезают)

function bytesToBase64(bytes: ArrayBuffer | Uint8Array): string {
  const arr = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  let bin = '';
  const chunk = 0x8000;
  for (let i = 0; i < arr.length; i += chunk) {
    bin += String.fromCharCode.apply(null, Array.from(arr.subarray(i, i + chunk)));
  }
  return btoa(bin);
}

function base64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

/**
 * Сохраняет книгу в KV. Создаёт:
 * - book:{slug}              → BookRecord (метаданные)
 * - book:{slug}:file:{name}  → BookFileBlob (base64 данные) для каждого файла
 *
 * Проверяет, что общий размер не превышает лимиты KV (25 МБ / значение, ~несколько МБ / namespace).
 * Для простого MVP — не строгая проверка, полагаемся на размер md/jpg.
 */
export async function uploadBook(
  env: Env,
  args: {
    slug: string;
    title: string;
    author: string;
    year?: number | null;
    description?: string;
    files: { kind: BookFileBlob['kind']; name: string; body: ArrayBuffer | Uint8Array }[];
    generatedBy?: string;
    generatedByJob?: string;
  },
): Promise<BookRecord> {
  const { slug, title, author, year, description, files } = args;

  const safeName = (n: string) => n.replace(/[^a-zA-Z0-9._-]/g, '_').slice(0, 80) || 'file';

  const metas: BookFileMeta[] = [];
  const blobs: { key: string; blob: BookFileBlob }[] = [];

  for (const f of files) {
    const name = safeName(f.name);
    const ct = contentTypeFor(name);
    const bytes = f.body instanceof Uint8Array ? f.body : new Uint8Array(f.body);
    if (bytes.byteLength > MAX_FILE_SIZE) {
      throw new Error(`Файл ${name} слишком большой (${bytes.byteLength} > ${MAX_FILE_SIZE})`);
    }
    const blob: BookFileBlob = {
      slug,
      name,
      contentType: ct,
      dataBase64: bytesToBase64(bytes),
      size: bytes.byteLength,
      kind: f.kind,
    };
    blobs.push({ key: KV_KEYS.bookFile(slug, name), blob });
    metas.push({ name, size: bytes.byteLength, contentType: ct, kind: f.kind });
  }

  const record: BookRecord = {
    slug,
    title,
    author,
    year: year ?? null,
    description: description ?? '',
    files: metas,
    createdAt: new Date().toISOString(),
    generatedBy: args.generatedBy,
    generatedByJob: args.generatedByJob,
  };

  // Сначала пишем все blob'ы, потом record — если record упадёт, blob'ы
  // останутся, но это не страшно (перезатрём при следующей генерации того же slug)
  await Promise.all(blobs.map((b) => env.LAB_KV.put(b.key, JSON.stringify(b.blob))));
  await env.LAB_KV.put(KV_KEYS.book(slug), JSON.stringify(record));

  return record;
}

export async function getBook(env: Env, slug: string): Promise<BookRecord | null> {
  const raw = await env.LAB_KV.get(KV_KEYS.book(slug));
  if (!raw) return null;
  try {
    return JSON.parse(raw) as BookRecord;
  } catch {
    return null;
  }
}

export async function getBookFile(env: Env, slug: string, name: string): Promise<BookFileBlob | null> {
  // Безопасный slug/name — только [a-zA-Z0-9._-]
  if (!/^[a-zA-Z0-9._-]{1,80}$/.test(slug) || !/^[a-zA-Z0-9._-]{1,80}$/.test(name)) {
    return null;
  }
  const raw = await env.LAB_KV.get(KV_KEYS.bookFile(slug, name));
  if (!raw) return null;
  try {
    return JSON.parse(raw) as BookFileBlob;
  } catch {
    return null;
  }
}

/** Совместимость со старым кодом: fileBody, нужно для будущих R2-миграций. */
export function fileBlobToBytes(blob: BookFileBlob): Uint8Array {
  return base64ToBytes(blob.dataBase64);
}
