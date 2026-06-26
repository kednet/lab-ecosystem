/**
 * pay-yookassa.ts — минимальный клиент ЮKassa API v3.
 *
 * Использует 2 эндпоинта:
 *   - POST https://api.yookassa.ru/v3/payments      — создание платежа
 *   - верификация подписи webhook (HMAC-SHA256)
 *
 * Mock-режим:
 *   Если YOOKASSA_SECRET_KEY пустой или содержит 'REPLACE_ME', возвращаем
 *   {mock: true, mockUrl: returnUrl + '?mock_pay=1&payment_id=mock_xxx'}.
 *   Это позволяет пройти всю цепочку без реальных ключей. После того, как
 *   kfigh подменит ключи в /etc/lab-site.env, mock-режим автоматически
 *   отключится.
 *
 * Документация: https://yookassa.ru/developers/api
 */

export interface YookassaEnv {
  YOOKASSA_SHOP_ID?: string;
  YOOKASSA_SECRET_KEY?: string;
  YOOKASSA_WEBHOOK_SECRET?: string;
}

export interface CreatePaymentParams {
  /** Сумма в копейках (59000 = 590 ₽). */
  amount: number;
  /** Описание для чека. */
  description: string;
  /** Email плательщика (для чека, и для удобства сопоставления). */
  email: string;
  /** Идентификатор плательщика в нашей системе (наш payment.id). */
  metadataKey: string;
  /** URL возврата после оплаты/отмены. */
  returnUrl: string;
  /** Время жизни платежа (ISO-8601). Необязательно. */
  expiresAt?: string;
}

export interface CreatePaymentResult {
  ok: boolean;
  /** ID платежа в ЮKassa (или mock-xxxx). */
  yookassaPaymentId: string;
  /** URL для редиректа пользователя (в ЮKassa или наш mock). */
  confirmationUrl: string;
  mock?: boolean;
  error?: string;
  code?: string;
}

const YK_API = 'https://api.yookassa.ru/v3/payments';

/**
 * True, если в env стоят заглушки или ключи не заданы.
 * В этом случае createPayment вернёт mock-результат.
 */
export function isMockMode(env: YookassaEnv): boolean {
  const k = env.YOOKASSA_SECRET_KEY;
  if (!k) return true;
  if (k.includes('REPLACE_ME')) return true;
  if (!env.YOOKASSA_SHOP_ID) return true;
  if (env.YOOKASSA_SHOP_ID.includes('REPLACE_ME')) return true;
  return false;
}

/**
 * Генерирует стабильный mock-ID для разработки.
 * Чтобы можно было найти запись в БД и привязать magic-link.
 */
function mockPaymentId(metadataKey: string): string {
  return `mock_${metadataKey.replace(/[^a-zA-Z0-9_-]/g, '').slice(0, 16)}`;
}

export async function createPayment(
  env: YookassaEnv,
  p: CreatePaymentParams,
): Promise<CreatePaymentResult> {
  // Mock-режим: возвращаем URL, который сразу редиректит на returnUrl с пометкой.
  if (isMockMode(env)) {
    const yid = mockPaymentId(p.metadataKey);
    // Возвращаем returnUrl напрямую — фронт отправит туда, эмулируя "платёж прошёл"
    const url = new URL(p.returnUrl);
    url.searchParams.set('mock_pay', '1');
    url.searchParams.set('payment_id', yid);
    url.searchParams.set('plan', p.metadataKey.includes('year') ? 'year' : 'month');
    return {
      ok: true,
      yookassaPaymentId: yid,
      confirmationUrl: url.toString(),
      mock: true,
    };
  }

  // Реальный режим
  const idempotenceKey = p.metadataKey;
  const body = {
    amount: { value: (p.amount / 100).toFixed(2), currency: 'RUB' },
    capture: true,
    confirmation: {
      type: 'redirect',
      return_url: p.returnUrl,
    },
    description: p.description,
    receipt: {
      customer: { email: p.email },
      items: [
        {
          description: p.description,
          amount: { value: (p.amount / 100).toFixed(2), currency: 'RUB' },
          vat_code: 1, // Без НДС (самозанятый)
          quantity: '1',
        },
      ],
    },
    metadata: { order_id: p.metadataKey },
  };

  try {
    const auth = Buffer.from(`${env.YOOKASSA_SHOP_ID}:${env.YOOKASSA_SECRET_KEY}`).toString('base64');
    const resp = await fetch(YK_API, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Idempotence-Key': idempotenceKey,
        'Authorization': `Basic ${auth}`,
      },
      body: JSON.stringify(body),
    });
    const data = (await resp.json().catch(() => ({}))) as {
      id?: string;
      confirmation?: { confirmation_url?: string };
      status?: string;
      description?: string;
    };

    if (!resp.ok || !data.id || !data.confirmation?.confirmation_url) {
      console.error('[yookassa:create:error]', resp.status, JSON.stringify(data));
      return {
        ok: false,
        yookassaPaymentId: '',
        confirmationUrl: '',
        error: data.description ?? `HTTP ${resp.status}`,
        code: 'yk_error',
      };
    }

    return {
      ok: true,
      yookassaPaymentId: data.id,
      confirmationUrl: data.confirmation.confirmation_url,
    };
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error('[yookassa:create:fetch_error]', msg);
    return { ok: false, yookassaPaymentId: '', confirmationUrl: '', error: msg, code: 'network' };
  }
}

/**
 * Проверка подписи webhook от ЮKassa.
 * ЮKassa присылает заголовок `Signature` в формате "t=...,v1=...".
 * HMAC-SHA256 от "{t}.{body}" с ключом YOOKASSA_WEBHOOK_SECRET.
 *
 * Возвращает true, если подпись валидна. В mock-режиме пропускаем всё.
 */
export async function verifyWebhookSignature(
  env: YookassaEnv,
  body: string,
  signatureHeader: string | null,
): Promise<boolean> {
  if (isMockMode(env)) return true; // mock — всегда пропускаем
  if (!signatureHeader || !env.YOOKASSA_WEBHOOK_SECRET) return false;

  // Парсим заголовок вида: "t=1234567890,v1=abcdef..."
  const parts: Record<string, string> = {};
  for (const seg of signatureHeader.split(',')) {
    const [k, v] = seg.split('=');
    if (k && v) parts[k.trim()] = v.trim();
  }
  const t = parts['t'];
  const v1 = parts['v1'];
  if (!t || !v1) return false;

  // Подпись считается от "{t}.{body}"
  const secret = await importKey(env.YOOKASSA_WEBHOOK_SECRET);
  const data = new TextEncoder().encode(`${t}.${body}`);
  const sig = await crypto.subtle.sign('HMAC', secret, data);
  const expected = Array.from(new Uint8Array(sig))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
  return expected === v1;
}

async function importKey(secret: string): Promise<CryptoKey> {
  const enc = new TextEncoder();
  return crypto.subtle.importKey(
    'raw',
    enc.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  );
}
