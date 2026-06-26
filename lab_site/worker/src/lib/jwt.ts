/**
 * Минималистичный JWT (HS256) на базе Web Crypto API.
 * Без зависимостей — Workers не любят тяжёлые npm-пакеты.
 *
 * Формат: base64url(header).base64url(payload).base64url(hmac_sha256)
 */

export interface JWTPayload {
  sub: string; // userId
  email: string;
  iat: number; // issued at, epoch seconds
  exp: number; // expires at, epoch seconds
}

const HEADER = { alg: 'HS256', typ: 'JWT' };

function base64urlEncode(bytes: Uint8Array): string {
  let binary = '';
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function base64urlDecode(str: string): Uint8Array {
  // Add padding back
  const padded = str + '='.repeat((4 - (str.length % 4)) % 4);
  const binary = atob(padded.replace(/-/g, '+').replace(/_/g, '/'));
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

function strToBytes(s: string): Uint8Array {
  return new TextEncoder().encode(s);
}

async function importKey(secret: string): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    'raw',
    strToBytes(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign', 'verify'],
  );
}

export async function signJWT(payload: Omit<JWTPayload, 'iat' | 'exp'>, secret: string, expiresInSec = 30 * 24 * 60 * 60): Promise<string> {
  const now = Math.floor(Date.now() / 1000);
  const fullPayload: JWTPayload = {
    ...payload,
    iat: now,
    exp: now + expiresInSec,
  };

  const headerB64 = base64urlEncode(strToBytes(JSON.stringify(HEADER)));
  const payloadB64 = base64urlEncode(strToBytes(JSON.stringify(fullPayload)));
  const signingInput = `${headerB64}.${payloadB64}`;

  const key = await importKey(secret);
  const sig = await crypto.subtle.sign('HMAC', key, strToBytes(signingInput));
  const sigB64 = base64urlEncode(new Uint8Array(sig));

  return `${signingInput}.${sigB64}`;
}

export async function verifyJWT(token: string, secret: string): Promise<JWTPayload | null> {
  const parts = token.split('.');
  if (parts.length !== 3) return null;

  const [headerB64, payloadB64, sigB64] = parts;
  const signingInput = `${headerB64}.${payloadB64}`;

  try {
    const key = await importKey(secret);
    const sigBytes = base64urlDecode(sigB64);
    const valid = await crypto.subtle.verify('HMAC', key, sigBytes, strToBytes(signingInput));
    if (!valid) return null;

    const payloadBytes = base64urlDecode(payloadB64);
    const payload = JSON.parse(new TextDecoder().decode(payloadBytes)) as JWTPayload;

    if (payload.exp < Math.floor(Date.now() / 1000)) return null;

    return payload;
  } catch {
    return null;
  }
}

/**
 * Достать секрет из env (приоритет prod, fallback dev).
 */
export function getJWTSecret(env: { JWT_SECRET?: string; JWT_SECRET_DEV?: string }): string {
  if (env.JWT_SECRET) return env.JWT_SECRET;
  if (env.JWT_SECRET_DEV) return env.JWT_SECRET_DEV;
  throw new Error('JWT_SECRET not configured. Set it via `wrangler secret put JWT_SECRET`.');
}
