import type { Env } from '../types';
import { corsOrigins } from '../types';

/**
 * CORS middleware: разрешает запросы с любого origin из FRONTEND_ORIGIN (CSV).
 * Поддерживает preflight (OPTIONS) и credentials.
 */
export function corsHeaders(env: Env, request: Request): Headers {
  const origin = request.headers.get('Origin') ?? '';
  const allowed = corsOrigins(env);

  const headers = new Headers();
  if (origin && allowed.has(origin)) {
    headers.set('Access-Control-Allow-Origin', origin);
    headers.set('Vary', 'Origin');
    headers.set('Access-Control-Allow-Credentials', 'true');
    headers.set('Access-Control-Allow-Methods', 'GET, POST, PATCH, DELETE, OPTIONS');
    headers.set('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Admin-Token');
    headers.set('Access-Control-Max-Age', '86400');
  }
  return headers;
}

export function applyCors(response: Response, env: Env, request: Request): Response {
  const cors = corsHeaders(env, request);
  cors.forEach((value, key) => response.headers.set(key, value));
  return response;
}
