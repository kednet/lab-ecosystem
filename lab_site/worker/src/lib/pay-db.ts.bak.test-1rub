/**
 * pay-db.ts — таблицы для платежей и подписок.
 *
 * Использует тот же файл БД что и KV (по умолчанию /var/lib/lab-site/kv.db),
 * но свои таблицы с префиксом pay_*. Так не пересекаемся с KV-данными и можем
 * использовать SQL-индексы (по email, yookassa_payment_id, valid_until).
 *
 * Схема:
 *   pay_payments — заказы (статус pending → paid/canceled/refunded)
 *   pay_subscriptions — активные подписки (по email)
 *
 * Доступ к БД — через node:sqlite DatabaseSync. Lazy init + CREATE TABLE IF NOT EXISTS.
 * PRAGMA WAL уже выставлен через kv-sqlite.ts (общий файл), так что тут не дублируем.
 */

import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import path from 'node:path';

const DB_PATH = process.env.SQLITE_PATH || '/var/lib/lab-site/kv.db';

let _db: DatabaseSync | null = null;

function getDb(): DatabaseSync {
  if (_db) return _db;
  const dir = path.dirname(DB_PATH);
  fs.mkdirSync(dir, { recursive: true });
  _db = new DatabaseSync(DB_PATH);
  _db.exec(`
    CREATE TABLE IF NOT EXISTS pay_payments (
      id TEXT PRIMARY KEY,
      yookassa_payment_id TEXT,
      plan TEXT NOT NULL,
      email TEXT NOT NULL,
      amount INTEGER NOT NULL,
      status TEXT NOT NULL DEFAULT 'pending',
      return_url TEXT,
      created_at INTEGER NOT NULL,
      paid_at INTEGER
    );
    CREATE INDEX IF NOT EXISTS idx_pay_payments_email ON pay_payments(email);
    CREATE INDEX IF NOT EXISTS idx_pay_payments_yk ON pay_payments(yookassa_payment_id);
    CREATE INDEX IF NOT EXISTS idx_pay_payments_status ON pay_payments(status);

    CREATE TABLE IF NOT EXISTS pay_subscriptions (
      email TEXT PRIMARY KEY,
      plan TEXT NOT NULL,
      valid_until INTEGER NOT NULL,
      payment_id TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'active',
      created_at INTEGER NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_pay_subs_valid ON pay_subscriptions(valid_until);
  `);
  return _db;
}

// ────────────────────────────────────────────────
// Types
// ────────────────────────────────────────────────

export type Plan = 'month' | 'year';
export type PaymentStatus = 'pending' | 'paid' | 'canceled' | 'refunded';
export type SubscriptionStatus = 'active' | 'expired' | 'canceled';

export interface PaymentRow {
  id: string;
  yookassa_payment_id: string | null;
  plan: Plan;
  email: string;
  amount: number; // копейки
  status: PaymentStatus;
  return_url: string | null;
  created_at: number;
  paid_at: number | null;
}

export interface SubscriptionRow {
  email: string;
  plan: Plan;
  valid_until: number; // epoch ms
  payment_id: string;
  status: SubscriptionStatus;
  created_at: number;
}

// ────────────────────────────────────────────────
// Plans (единственный источник цен — бэкенд тоже)
// ────────────────────────────────────────────────

export const PLANS: Record<Plan, { name: string; amount: number; days: number; description: string }> = {
  month: { name: 'Месяц', amount: 59000, days: 30, description: 'Подписка на месяц' },
  year:  { name: 'Год',   amount: 499000, days: 365, description: 'Подписка на год (экономия 30%)' },
};

// ────────────────────────────────────────────────
// Payments
// ────────────────────────────────────────────────

export function createPayment(p: Omit<PaymentRow, 'yookassa_payment_id' | 'status' | 'paid_at'>): void {
  const db = getDb();
  db.prepare(
    `INSERT INTO pay_payments (id, plan, email, amount, status, return_url, created_at)
     VALUES (?, ?, ?, ?, 'pending', ?, ?)`,
  ).run(p.id, p.plan, p.email, p.amount, p.return_url, p.created_at);
}

export function setYookassaId(paymentId: string, yookassaId: string): void {
  const db = getDb();
  db.prepare(`UPDATE pay_payments SET yookassa_payment_id = ? WHERE id = ?`).run(yookassaId, paymentId);
}

export function findPaymentById(id: string): PaymentRow | null {
  const db = getDb();
  const row = db.prepare(`SELECT * FROM pay_payments WHERE id = ?`).get(id) as PaymentRow | undefined;
  return row ?? null;
}

export function findPaymentByYkId(ykId: string): PaymentRow | null {
  const db = getDb();
  const row = db.prepare(`SELECT * FROM pay_payments WHERE yookassa_payment_id = ?`).get(ykId) as PaymentRow | undefined;
  return row ?? null;
}

export function markPaid(id: string): void {
  const db = getDb();
  db.prepare(`UPDATE pay_payments SET status = 'paid', paid_at = ? WHERE id = ?`).run(Date.now(), id);
}

export function markCanceled(id: string): void {
  const db = getDb();
  db.prepare(`UPDATE pay_payments SET status = 'canceled' WHERE id = ?`).run(id);
}

// ────────────────────────────────────────────────
// Subscriptions
// ────────────────────────────────────────────────

/**
 * Создаёт или продлевает подписку для email.
 * Если уже есть активная — продлевает valid_until до max(old, new).
 * Это позволяет покупать «Месяц» несколько раз подряд, не теряя остаток.
 */
export function upsertSubscription(email: string, plan: Plan, paymentId: string): SubscriptionRow {
  const db = getDb();
  const now = Date.now();
  const days = PLANS[plan].days;
  const newValidUntil = now + days * 24 * 60 * 60 * 1000;

  const existing = db.prepare(
    `SELECT * FROM pay_subscriptions WHERE email = ?`,
  ).get(email) as SubscriptionRow | undefined;

  if (existing && existing.status === 'active' && existing.valid_until > now) {
    // Продлеваем от более поздней даты (old или new), не теряя оплаченный остаток
    const newUntil = Math.max(existing.valid_until, newValidUntil);
    // При продлении сохраняем тот же план, если только не идёт апгрейд month→year
    const finalPlan = (existing.plan === 'year' || plan === 'year') ? 'year' : existing.plan;
    db.prepare(
      `UPDATE pay_subscriptions SET valid_until = ?, plan = ?, payment_id = ?, status = 'active' WHERE email = ?`,
    ).run(newUntil, finalPlan, paymentId, email);
    return { ...existing, valid_until: newUntil, plan: finalPlan, payment_id: paymentId, status: 'active' };
  }

  // Новая подписка (или переактивация)
  db.prepare(
    `INSERT INTO pay_subscriptions (email, plan, valid_until, payment_id, status, created_at)
     VALUES (?, ?, ?, ?, 'active', ?)
     ON CONFLICT(email) DO UPDATE SET
       plan = excluded.plan,
       valid_until = excluded.valid_until,
       payment_id = excluded.payment_id,
       status = 'active',
       created_at = excluded.created_at`,
  ).run(email, plan, newValidUntil, paymentId, now);

  return {
    email,
    plan,
    valid_until: newValidUntil,
    payment_id: paymentId,
    status: 'active',
    created_at: now,
  };
}

export function getSubscription(email: string): SubscriptionRow | null {
  const db = getDb();
  const row = db.prepare(`SELECT * FROM pay_subscriptions WHERE email = ?`).get(email) as SubscriptionRow | undefined;
  return row ?? null;
}

export function isAccessActive(email: string): boolean {
  const sub = getSubscription(email);
  if (!sub) return false;
  if (sub.status !== 'active') return false;
  return sub.valid_until > Date.now();
}
