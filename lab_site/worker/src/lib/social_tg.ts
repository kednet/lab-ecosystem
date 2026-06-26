/**
 * Telegram Bot API адаптер.
 *
 * - Личный админу: TELEGRAM_ADMIN_ID (с inline-кнопками)
 * - В канал:     TELEGRAM_CHANNEL_ID (например @wishlab_channel)
 *
 * Документация: https://core.telegram.org/bots/api
 *
 * Если bot-token не задан — работаем в dev-режиме (логируем, не шлём).
 *
 * Прокси (опц.):
 *   TELEGRAM_PROXY_URL=socks5://user:pass@host:port
 *   Применяется ко всем исходящим запросам к api.telegram.org.
 *   Нужен на VPS в РФ, где Telegram API напрямую недоступен.
 *   Использует undici.ProxyAgent (SOCKS5 поддерживается нативно с undici 5+).
 */
import type { Env } from '../types';
import { ProxyAgent, fetch as undiciFetch } from 'undici';

const TG_API = 'https://api.telegram.org/bot';

export interface InlineButton {
  text: string;
  url?: string;
  callback_data?: string;
}

export interface TgMessageResult {
  message_id: number;
  chat: { id: number | string; type?: string };
  url?: string;
  raw: unknown;
}

export interface TgSendParams {
  text: string;
  /** Inline-кнопки. */
  buttons?: InlineButton[][];
  /** Ссылка превью, если нужна. */
  linkPreview?: boolean;
  /** parse_mode — 'HTML' (по умолчанию) или 'MarkdownV2'. */
  parseMode?: 'HTML' | 'MarkdownV2';
}

export class TelegramAdapter {
  constructor(private readonly env: Env) {}

  private isDevMode(): boolean {
    return !this.env.TELEGRAM_BOT_TOKEN;
  }

  /** SOCKS5/HTTP прокси-агент (undici ProxyAgent) для fetch, если TELEGRAM_PROXY_URL задан. */
  private proxyDispatcher(): ProxyAgent | undefined {
    const url = this.env.TELEGRAM_PROXY_URL;
    if (!url || !url.trim()) return undefined;
    try {
      return new ProxyAgent({ uri: url.trim() });
    } catch (err) {
      console.error('[tg:proxy-init-failed]', err);
      return undefined;
    }
  }

  /** fetch с прокси (если задан) через undici.fetch, иначе — нативный fetch. */
  private async tgFetch(url: string, init: RequestInit): Promise<Response> {
    const dispatcher = this.proxyDispatcher();
    if (!dispatcher) {
      return fetch(url, init);
    }
    // undici.fetch понимает `dispatcher` напрямую
    return undiciFetch(url as unknown as string, { ...(init as never), dispatcher } as never);
  }

  private apiUrl(method: string): string {
    return `${TG_API}${this.env.TELEGRAM_BOT_TOKEN}/${method}`;
  }

  private buildReplyMarkup(buttons?: InlineButton[][]): string | undefined {
    if (!buttons || buttons.length === 0) return undefined;
    return JSON.stringify({ inline_keyboard: buttons });
  }

  /** Отправка в произвольный чат. */
  async sendToChat(chatId: number | string, params: TgSendParams): Promise<TgMessageResult> {
    if (this.isDevMode()) {
      const mockId = Math.floor(Math.random() * 1_000_000);
      console.log('[tg:dev] would send to', chatId, {
        length: params.text.length,
        buttons: params.buttons?.length ?? 0,
        preview: params.text.slice(0, 200) + (params.text.length > 200 ? '…' : ''),
      });
      return {
        message_id: mockId,
        chat: { id: chatId, type: typeof chatId === 'string' ? 'channel' : 'private' },
        url: typeof chatId === 'string'
          ? `https://t.me/${String(chatId).replace('@', '')}/${mockId}`
          : `https://t.me/c/${mockId}`,
        raw: { dev: true, mock: true },
      };
    }

    const body = new URLSearchParams();
    body.set('chat_id', String(chatId));
    body.set('text', params.text);
    body.set('parse_mode', params.parseMode ?? 'HTML');
    body.set('disable_web_page_preview', params.linkPreview === false ? 'true' : 'false');
    const replyMarkup = this.buildReplyMarkup(params.buttons);
    if (replyMarkup) body.set('reply_markup', replyMarkup);

    const res = await this.tgFetch(this.apiUrl('sendMessage'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body.toString(),
    });

    const data = (await res.json()) as
      | { ok: true; result: TgMessageResult }
      | { ok: false; description: string };

    if (!data.ok) {
      console.error('[tg:send-error]', data);
      throw new Error(`Telegram API error: ${data.description}`);
    }
    return data.result;
  }

  /** Удобный алиас — личное сообщение админу. */
  async sendToAdmin(text: string, buttons?: InlineButton[][]): Promise<TgMessageResult> {
    if (!this.env.TELEGRAM_ADMIN_ID) {
      console.log('[tg:dev] TELEGRAM_ADMIN_ID не задан, вывод в консоль:', text.slice(0, 200));
      return {
        message_id: 0,
        chat: { id: 0, type: 'private' },
        raw: { dev: true, noAdminId: true },
      };
    }
    return this.sendToChat(this.env.TELEGRAM_ADMIN_ID, { text, buttons });
  }

  /** Алиас — в канал. */
  async sendToChannel(text: string, buttons?: InlineButton[][]): Promise<TgMessageResult> {
    if (!this.env.TELEGRAM_CHANNEL_ID) {
      console.log('[tg:dev] TELEGRAM_CHANNEL_ID не задан, вывод в консоль:', text.slice(0, 200));
      return {
        message_id: 0,
        chat: { id: 0, type: 'channel' },
        raw: { dev: true, noChannelId: true },
      };
    }
    return this.sendToChat(this.env.TELEGRAM_CHANNEL_ID, { text, buttons });
  }

  /** Редактирование сообщения. */
  async editMessage(chatId: number | string, messageId: number, params: TgSendParams): Promise<boolean> {
    if (this.isDevMode()) {
      console.log('[tg:dev] would edit', chatId, messageId);
      return true;
    }
    const body = new URLSearchParams();
    body.set('chat_id', String(chatId));
    body.set('message_id', String(messageId));
    body.set('text', params.text);
    body.set('parse_mode', params.parseMode ?? 'HTML');
    const replyMarkup = this.buildReplyMarkup(params.buttons);
    if (replyMarkup) body.set('reply_markup', replyMarkup);

    const res = await this.tgFetch(this.apiUrl('editMessageText'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body.toString(),
    });
    const data = (await res.json()) as { ok: boolean; description?: string };
    if (!data.ok) {
      console.error('[tg:edit-error]', data.description);
      return false;
    }
    return true;
  }

  /** Удаление сообщения. */
  async deleteMessage(chatId: number | string, messageId: number): Promise<boolean> {
    if (this.isDevMode()) {
      console.log('[tg:dev] would delete', chatId, messageId);
      return true;
    }
    const body = new URLSearchParams();
    body.set('chat_id', String(chatId));
    body.set('message_id', String(messageId));

    const res = await this.tgFetch(this.apiUrl('deleteMessage'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body.toString(),
    });
    const data = (await res.json()) as { ok: boolean; description?: string };
    if (!data.ok) {
      console.error('[tg:delete-error]', data.description);
      return false;
    }
    return true;
  }

  /**
   * Ответ на callback (нажатие inline-кнопки).
   * Telegram требует ответить в течение 30 сек, иначе таймаут.
   */
  async answerCallback(callbackQueryId: string, text?: string, showAlert = false): Promise<boolean> {
    if (this.isDevMode()) {
      console.log('[tg:dev] would answer callback', callbackQueryId, text);
      return true;
    }
    const body = new URLSearchParams();
    body.set('callback_query_id', callbackQueryId);
    if (text) body.set('text', text);
    body.set('show_alert', showAlert ? 'true' : 'false');

    const res = await this.tgFetch(this.apiUrl('answerCallbackQuery'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body.toString(),
    });
    const data = (await res.json()) as { ok: boolean; description?: string };
    return data.ok;
  }
}
