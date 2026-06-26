/**
 * VK API адаптер для анонсов в группе "ЛАБОРАТОРИЯ ЖЕЛАНИЙ" (id 237295798).
 *
 * Документация: https://dev.vk.com/method/wall.post
 *
 * Используется "по-простому": POST wall.post с from_group=1, signed=0,
 * owner_id = -groupId (минус — это паблик/группа). Без загрузки фото в первой версии.
 *
 * Если в env нет токенов → работаем в dev-режиме (логируем в консоль, не публикуем).
 */
import type { Env } from '../types';

const VK_API_VERSION = '5.199';
const VK_TEXT_LIMIT = 16_384;

export interface VkPostResult {
  post_id: number;
  owner_id: number;
  url: string;
  raw: unknown;
}

export interface VkPostParams {
  /** Текст поста (с эмодзи, хештегами, ссылкой). */
  message: string;
  /** Ссылка в подписи (если нужна отдельно). */
  link?: { url: string; title?: string };
  /** Откуда пост (от имени группы). По умолчанию true. */
  fromGroup?: boolean;
}

export class VKAdapter {
  constructor(private readonly env: Env) {}

  /** В dev-режиме, если нет токенов — не публикуем, а возвращаем mock-результат. */
  private isDevMode(): boolean {
    return !this.env.VK_GROUP_TOKEN || !this.env.VK_GROUP_ID;
  }

  /**
   * Публикует пост на стене группы.
   * @throws если превышен лимит символов, либо API вернул ошибку.
   */
  async publishPost(params: VkPostParams): Promise<VkPostResult> {
    if (params.message.length > VK_TEXT_LIMIT) {
      throw new Error(
        `VK message too long: ${params.message.length} > ${VK_TEXT_LIMIT}`,
      );
    }

    if (this.isDevMode()) {
      const mockId = Math.floor(Math.random() * 1_000_000);
      console.log('[vk:dev] would publish:', {
        length: params.message.length,
        fromGroup: params.fromGroup ?? true,
        link: params.link,
        preview: params.message.slice(0, 200) + (params.message.length > 200 ? '…' : ''),
      });
      return {
        post_id: mockId,
        owner_id: -237295798,
        url: `https://vk.com/club237295798?w=wall-{dev}${mockId}`,
        raw: { dev: true, mock: true },
      };
    }

    const groupId = this.env.VK_GROUP_ID!;
    const fromGroup = params.fromGroup ?? true;
    // Для паблика/группы owner_id = -groupId
    const ownerId = `-${groupId}`;

    const body = new URLSearchParams();
    body.set('owner_id', ownerId);
    body.set('from_group', fromGroup ? '1' : '0');
    body.set('message', params.message);
    body.set('signed', '0');
    body.set('v', VK_API_VERSION);
    if (params.link) {
      body.set('attachments', params.link.url);
    }

    const res = await fetch('https://api.vk.com/method/wall.post', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.env.VK_GROUP_TOKEN}`,
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: body.toString(),
    });

    const data = (await res.json()) as
      | { response: { post_id: number; owner_id: number } }
      | { error: { error_code: number; error_msg: string } };

    if ('error' in data) {
      console.error('[vk:error]', data.error);
      throw new Error(`VK API error: ${data.error.error_msg} (code ${data.error.error_code})`);
    }

    const owner = data.response.owner_id;
    const postId = data.response.post_id;
    const url = owner > 0
      ? `https://vk.com/id${owner}?w=wall${owner}_${postId}`
      : `https://vk.com/club${Math.abs(owner)}?w=wall${owner}_${postId}`;

    return {
      post_id: postId,
      owner_id: owner,
      url,
      raw: data,
    };
  }

  /** Редактирование уже опубликованного поста. */
  async editPost(postId: number, message: string, ownerId: number): Promise<boolean> {
    if (this.isDevMode()) {
      console.log('[vk:dev] would edit post', postId, 'len=', message.length);
      return true;
    }
    const body = new URLSearchParams();
    body.set('owner_id', String(ownerId));
    body.set('post_id', String(postId));
    body.set('message', message);
    body.set('v', VK_API_VERSION);

    const res = await fetch('https://api.vk.com/method/wall.edit', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.env.VK_GROUP_TOKEN}`,
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: body.toString(),
    });
    const data = (await res.json()) as { response?: number; error?: { error_msg: string } };
    if (data.error) {
      console.error('[vk:edit-error]', data.error);
      return false;
    }
    return data.response === 1;
  }

  /** Удаление поста. */
  async deletePost(postId: number, ownerId: number): Promise<boolean> {
    if (this.isDevMode()) {
      console.log('[vk:dev] would delete post', postId);
      return true;
    }
    const body = new URLSearchParams();
    body.set('owner_id', String(ownerId));
    body.set('post_id', String(postId));
    body.set('v', VK_API_VERSION);

    const res = await fetch('https://api.vk.com/method/wall.delete', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.env.VK_GROUP_TOKEN}`,
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: body.toString(),
    });
    const data = (await res.json()) as { response?: number; error?: { error_msg: string } };
    if (data.error) {
      console.error('[vk:delete-error]', data.error);
      return false;
    }
    return data.response === 1;
  }
}
