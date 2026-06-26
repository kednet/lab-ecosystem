/**
 * Клиентская логика страницы /wish-map/.
 *
 * Вынесена в отдельный модуль, чтобы dep-scan Vite в dev-режиме не падал
 * на большом inlined script-тегов в Astro (esbuild ошибочно парсит строки с кириллицей).
 *
 * Стейт-машина: hydrate из localStorage → step 1 (выбор сфер) → step 2 (желания)
 * → step 3 (превью + скачивание PDF/PNG).
 *
 * Гейтинг:
 *   anon: 3 сферы × 1 желание
 *   free: 6 сфер × 2 желания
 *   paid: 6 сфер × 3 желания + доступ к конкурсу
 *
 * PDF — jsPDF; встраиваем растровое превью (SVG→Canvas→PNG) одной картинкой.
 * Текст и кириллица идут как пиксели, не как PDF-шрифт — превью и файл совпадают пиксель-в-пиксель.
 * PNG — тот же SVG→Image→Canvas, без html2canvas (быстрее и надёжнее для SVG).
 */

import { getToken, getUser, onAuthChange } from '../lib/auth';
import { reachGoal, GOALS } from '../lib/metrika';
import { spheres, spheresById, sphereOrder, type SphereId } from '../data/wish-map/spheres';
import { goldenWishes, wishTypeLabels } from '../data/wish-map/wishes-golden';

const STORAGE_KEY = 'lab_wishmap_draft';

interface WishMapState {
  selectedSphereIds: SphereId[];
  wishes: Partial<Record<SphereId, string[]>>;
  wishSource: Partial<Record<SphereId, ('example' | 'own')[]>>;
  contestOptIn: boolean;
  referrerCode: string;
}

const LIMITS = {
  anon: { spheres: 3, wishesPerSphere: 1 },
  free: { spheres: 6, wishesPerSphere: 2 },
  paid: { spheres: 6, wishesPerSphere: 3 },
} as const;

let state: WishMapState = {
  selectedSphereIds: [],
  wishes: {},
  wishSource: {},
  contestOptIn: false,
  referrerCode: '',
};

function getUserPlan(): 'anon' | 'free' | 'paid' {
  const u = getUser();
  if (!u) return 'anon';
  if (u.plan === 'free') return 'free';
  return 'paid';
}

function getLimits() {
  return LIMITS[getUserPlan()];
}

function persist() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // localStorage переполнен
  }
}

function hydrate() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw) as WishMapState;
    if (parsed && typeof parsed === 'object') {
      state = { ...state, ...parsed };
    }
  } catch {
    // ignore
  }
}

function totalWishes(): number {
  return Object.values(state.wishes).reduce(
    (sum, arr) => sum + (arr?.filter(Boolean).length ?? 0),
    0,
  );
}

function sphereWishes(id: SphereId): string[] {
  return (state.wishes[id] ?? []).filter(Boolean);
}

/**
 * Транслитерация больше не используется (кириллица через Noto Sans в PDF).
 * Оставлена как no-op, чтобы старые вызовы (если бы остались) не падали.
 * Удали эту функцию после следующего рефакторинга.
 */
function transliterate(s: string): string {
  return s;
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!
  ));
}

function truncate(s: string, n: number): string {
  if (s.length <= n) return s;
  return s.slice(0, n - 1) + '…';
}

const $ = (sel: string) => document.querySelector(sel) as HTMLElement | null;
const $$ = (sel: string) =>
  Array.from(document.querySelectorAll(sel) as NodeListOf<HTMLElement>);

// ────────────────────────────────────────────────
// Modal
// ────────────────────────────────────────────────
interface ModalAction {
  label: string;
  href?: string;
  onClick?: () => void;
  primary?: boolean;
}

function showModal(opts: { title: string; text: string; actions: ModalAction[] }) {
  const modal = $('[data-role="modal"]')!;
  const title = $('[data-role="modal-title"]')!;
  const text = $('[data-role="modal-text"]')!;
  const actions = $('[data-role="modal-actions"]')!;
  title.textContent = opts.title;
  text.textContent = opts.text;
  actions.innerHTML = '';
  opts.actions.forEach((a) => {
    const btn = document.createElement('a');
    btn.className = `btn ${a.primary ? 'btn--primary' : 'btn--ghost'}`;
    btn.textContent = a.label;
    if (a.href) {
      btn.href = a.href;
    } else {
      btn.href = '#';
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        a.onClick?.();
      });
    }
    actions.appendChild(btn);
  });
  modal.hidden = false;
}

function closeModal() {
  $('[data-role="modal"]')!.hidden = true;
}

function showGateModal(kind: 'spheres' | 'wishes') {
  const plan = getUserPlan();
  if (kind === 'spheres') {
    if (LIMITS[plan].spheres === 3) {
      showModal({
        title: 'Войди, чтобы открыть все 6 сфер',
        text: 'Бесплатно доступно 3 сферы. На подписке — все 6 и до 3 желаний в каждой.',
        actions: [
          { label: 'Войти по email', href: '/auth/?next=/wish-map/', primary: true },
          { label: 'Посмотреть тарифы', href: '/pricing/' },
        ],
      });
    } else {
      showModal({
        title: 'Нужна подписка',
        text: 'Ты уже выбрал все 6 сфер — но больше 2 желаний в сфере можно только на платной подписке.',
        actions: [
          { label: 'Оформить подписку', href: '/pricing/', primary: true },
          { label: 'Закрыть', onClick: closeModal },
        ],
      });
    }
  } else {
    if (plan === 'anon') {
      showModal({
        title: 'Войди, чтобы добавить больше',
        text: `Бесплатно — ${LIMITS.anon.wishesPerSphere} желание в сфере. С подпиской — до ${LIMITS.paid.wishesPerSphere}.`,
        actions: [
          { label: 'Войти по email', href: '/auth/?next=/wish-map/', primary: true },
          { label: 'Посмотреть тарифы', href: '/pricing/' },
        ],
      });
    } else {
      showModal({
        title: 'Нужна подписка',
        text: `Ты на бесплатном тарифе — больше ${LIMITS.free.wishesPerSphere} желаний в сфере только на подписке.`,
        actions: [
          { label: 'Оформить подписку', href: '/pricing/', primary: true },
          { label: 'Закрыть', onClick: closeModal },
        ],
      });
    }
  }
}

// ────────────────────────────────────────────────
// Step navigation
// ────────────────────────────────────────────────
function goToStep(step: 1 | 2 | 3) {
  const step1 = $('#step-1')!;
  const step2 = $('#step-2')!;
  const step3 = $('#step-3')!;
  step1.hidden = step !== 1;
  step2.hidden = step !== 2;
  step3.hidden = step !== 3;
  if (step === 2) renderWishForms();
  if (step === 3) {
    renderPreview();
    updateQuotaNote();
    const isPaid = getUserPlan() === 'paid';
    const contest = $('[data-role="contest"]')!;
    contest.hidden = !isPaid;
    if (!isPaid) {
      state.contestOptIn = false;
      state.referrerCode = '';
      const toggle = $('[data-role="contest-toggle"]') as HTMLInputElement;
      const referrer = $('[data-role="contest-referrer"]') as HTMLInputElement;
      if (toggle) toggle.checked = false;
      if (referrer) {
        referrer.hidden = true;
        referrer.value = '';
      }
    }
  }
  const target = step === 1 ? step1 : step === 2 ? step2 : step3;
  window.scrollTo({ top: target.offsetTop - 80, behavior: 'smooth' });
}

// ────────────────────────────────────────────────
// Step 1
// ────────────────────────────────────────────────
function renderSelectedCount() {
  $$('[data-role="selected-count"]').forEach((n) => (n.textContent = String(state.selectedSphereIds.length)));
}

function refreshSphereUI() {
  const limits = getLimits();
  const reachedMax = state.selectedSphereIds.length >= limits.spheres;
  $$('[data-role="sphere-card"]').forEach((card) => {
    const id = card.dataset.sphere as SphereId;
    const selected = state.selectedSphereIds.includes(id);
    card.classList.toggle('is-selected', selected);
    card.setAttribute('aria-pressed', selected ? 'true' : 'false');
    card.classList.toggle('is-disabled', !selected && reachedMax);
  });
  $$('.wish-wheel__sector').forEach((s) => {
    const id = s.dataset.sphere as SphereId;
    const selected = state.selectedSphereIds.includes(id);
    s.classList.toggle('is-selected', selected);
    s.setAttribute('aria-pressed', selected ? 'true' : 'false');
  });
  renderSelectedCount();
  const toStep2Btn = $('[data-role="to-step-2"]') as HTMLButtonElement;
  if (toStep2Btn) toStep2Btn.disabled = state.selectedSphereIds.length === 0;
}

function toggleSphere(id: SphereId) {
  const limits = getLimits();
  if (state.selectedSphereIds.includes(id)) {
    state.selectedSphereIds = state.selectedSphereIds.filter((s) => s !== id);
  } else {
    if (state.selectedSphereIds.length >= limits.spheres) {
      showGateModal('spheres');
      return;
    }
    state.selectedSphereIds = [...state.selectedSphereIds, id];
    reachGoal(GOALS.wishMapSphereSelected, { sphere: id });
  }
  persist();
  refreshSphereUI();
}

// ────────────────────────────────────────────────
// Step 2
// ────────────────────────────────────────────────
function renderWishForms() {
  const root = $('[data-role="wish-forms"]')!;
  root.innerHTML = '';
  if (state.selectedSphereIds.length === 0) {
    root.innerHTML =
      '<p style="text-align:center;color:var(--muted);">Выбери хотя бы одну сферу на шаге 1.</p>';
    return;
  }
  state.selectedSphereIds.forEach((id) => {
    const sphere = spheresById[id];
    const wishes = state.wishes[id] ?? [''];
    const sources = state.wishSource[id] ?? [];
    const block = document.createElement('details');
    block.className = 'wish-form';
    block.open = true;
    block.dataset.sphere = id;
    const limit = getLimits().wishesPerSphere;
    const filled = wishes.filter(Boolean).length;
    block.innerHTML = `
      <summary>
        <span class="wish-form__emoji">${sphere.emoji}</span>
        <span class="wish-form__title">${sphere.name}</span>
        <span class="wish-form__count" data-role="count">${filled}/${limit}</span>
      </summary>
      <div class="wish-form__body">
        <p class="wish-form__hint">Готовые примеры — кликни, чтобы подставить:</p>
        <div class="wish-form__chips" data-role="chips" data-sphere="${id}"></div>
        <div class="wish-form__inputs" data-role="inputs"></div>
        <button type="button" class="wish-form__add" data-role="add">+ Добавить ещё одно желание</button>
      </div>
    `;
    const chipsRoot = block.querySelector<HTMLElement>('[data-role="chips"]')!;
    goldenWishes[id].forEach((w, idx) => {
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'wish-chip';
      // Номер (1..5) + цветная точка сферы + текст. Тип вынесен в aria-label.
      chip.dataset.type = w.type;
      chip.setAttribute('aria-label', `${w.text} — ${wishTypeLabels[w.type]}`);
      chip.innerHTML = `<span class="wish-chip__num">${idx + 1}</span><span class="wish-chip__text">${w.text}</span><span class="wish-chip__type">${wishTypeLabels[w.type]}</span>`;
      chip.addEventListener('click', () => addWish(id, w.text, 'example'));
      chipsRoot.appendChild(chip);
    });

    const inputsRoot = block.querySelector<HTMLElement>('[data-role="inputs"]')!;
    wishes.forEach((w, idx) => {
      inputsRoot.appendChild(createWishInput(id, w, sources[idx] ?? 'own', idx));
    });

    const addBtn = block.querySelector<HTMLButtonElement>('[data-role="add"]')!;
    addBtn.addEventListener('click', () => {
      const current = (state.wishes[id] ?? []).filter(Boolean).length;
      if (current >= limit) {
        showGateModal('wishes');
        return;
      }
      const arr = state.wishes[id] ?? [];
      state.wishes[id] = [...arr, ''];
      renderWishForms();
    });
    root.appendChild(block);
  });
}

function createWishInput(sphereId: SphereId, value: string, _source: 'example' | 'own', index: number) {
  const wrap = document.createElement('div');
  wrap.className = 'wish-input';
  wrap.innerHTML = `
    <textarea
      class="wish-input__field"
      maxlength="150"
      rows="2"
      placeholder="Или напиши своё — например, «бегать 5 км по утрам»"
    >${escapeHtml(value)}</textarea>
    <div class="wish-input__meta">
      <span class="wish-input__count" data-role="counter">${value.length}/150</span>
      <button type="button" class="wish-input__remove" aria-label="Удалить">×</button>
    </div>
  `;
  const ta = wrap.querySelector<HTMLTextAreaElement>('textarea')!;
  const counter = wrap.querySelector<HTMLElement>('[data-role="counter"]')!;
  const remove = wrap.querySelector<HTMLButtonElement>('.wish-input__remove')!;
  ta.addEventListener('input', () => {
    const v = ta.value.trim();
    const arr = state.wishes[sphereId] ?? [];
    const newArr = [...arr];
    newArr[index] = v;
    state.wishes[sphereId] = newArr;
    const srcs = state.wishSource[sphereId] ?? [];
    const newSrcs = [...srcs];
    newSrcs[index] = 'own';
    state.wishSource[sphereId] = newSrcs;
    counter.textContent = `${v.length}/150`;
    persist();
    const countEl = document.querySelector<HTMLElement>(
      `details[data-sphere="${sphereId}"] [data-role="count"]`,
    );
    if (countEl) {
      const filled = (state.wishes[sphereId] ?? []).filter(Boolean).length;
      countEl.textContent = `${filled}/${getLimits().wishesPerSphere}`;
    }
  });
  ta.addEventListener('blur', () => {
    const v = ta.value.trim();
    if (v.length >= 5) {
      reachGoal(GOALS.wishMapWishAdded, { sphere: sphereId, source: 'own' });
    }
  });
  remove.addEventListener('click', () => {
    const arr = (state.wishes[sphereId] ?? []).filter((_, i) => i !== index);
    state.wishes[sphereId] = arr;
    const srcs = (state.wishSource[sphereId] ?? []).filter((_, i) => i !== index);
    state.wishSource[sphereId] = srcs;
    renderWishForms();
    persist();
  });
  return wrap;
}

function addWish(sphereId: SphereId, text: string, source: 'example' | 'own') {
  const limits = getLimits();
  const filled = (state.wishes[sphereId] ?? []).filter(Boolean).length;
  if (filled >= limits.wishesPerSphere) {
    showGateModal('wishes');
    return;
  }
  const arr = state.wishes[sphereId] ?? [];
  state.wishes[sphereId] = [...arr, text];
  const srcs = state.wishSource[sphereId] ?? [];
  state.wishSource[sphereId] = [...srcs, source];
  reachGoal(GOALS.wishMapWishAdded, { sphere: sphereId, source });
  renderWishForms();
  persist();
}

// ────────────────────────────────────────────────
// Step 3: preview + export
// ────────────────────────────────────────────────
function renderPreview() {
  const previewRoot = $('[data-role="preview"]')!;
  const previewEmpty = $('[data-role="preview-empty"]')!;
  const hasAny = totalWishes() > 0;
  previewEmpty.hidden = hasAny;
  previewRoot.style.opacity = hasAny ? '1' : '0.3';
  if (!hasAny) {
    previewRoot.innerHTML = '';
    return;
  }
  previewRoot.innerHTML = buildPreviewSvg();
}

/**
 * Разбивает строку на строки не шире `maxChars` (по пробелам; если слово длиннее — режет как есть).
 */
function wrapText(s: string, maxChars: number): string[] {
  const words = s.split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let cur = '';
  for (const w of words) {
    if (!cur.length) {
      cur = w;
    } else if (cur.length + 1 + w.length <= maxChars) {
      cur += ' ' + w;
    } else {
      lines.push(cur);
      cur = w;
    }
  }
  if (cur) lines.push(cur);
  return lines;
}

function buildPreviewSvg(): string {
  // Альбомный viewBox 900×600 (3:2). Внутри — сетка ячеек по числу выбранных сфер.
  // Сначала пробуем уложить всё в 1 ряд (n ячеек в ряд → горизонтальные полосы).
  // Если в 1 ряд не помещается — добиваем до 2 рядов.
  const W = 900;
  const H = 600;
  const PAD = 16; // внешние поля превью
  const GAP = 8;  // зазор между ячейками
  const selectedIds = state.selectedSphereIds;
  if (selectedIds.length === 0) return '';
  const selectedOrder = sphereOrder.filter((id) => selectedIds.includes(id));
  const n = selectedOrder.length;
  // Стратегия: cols=1 если n=1; cols=2 если n=2-4; cols=3 если n=5-6.
  // Это даёт широкие ячейки в альбомной ориентации (как на скрине).
  const cols = n <= 1 ? 1 : n <= 4 ? 2 : 3;
  const rows = Math.ceil(n / cols);
  const innerW = W - PAD * 2 - GAP * (cols - 1);
  const innerH = H - PAD * 2 - GAP * (rows - 1);
  // В альбомном виде ячейки получаются "прямоугольные-вертикальные" (выше, чем шире),
  // но cols=2 при n=2 даёт почти квадратные ячейки. Подгоняем под квадрат (1:1),
  // а лишнее место распределяем по вертикали.
  const cellSize = Math.min(innerW / cols, innerH / rows);
  const gridW = cellSize * cols + GAP * (cols - 1);
  const gridH = cellSize * rows + GAP * (rows - 1);
  const offsetX = (W - gridW) / 2;
  const offsetY = (H - gridH) / 2;

  const cells = selectedOrder.map((id, i) => {
    const sphere = spheresById[id];
    const col = i % cols;
    const row = Math.floor(i / cols);
    const x = offsetX + col * (cellSize + GAP);
    const y = offsetY + row * (cellSize + GAP);
    // Название — крупно, в верхней части ячейки
    const nameLines = wrapText(sphere.name, 18);
    // Желания — список 1-3 шт
    const wishes = sphereWishes(id).slice(0, 3);
    // Ширина ячейки в "символах" для переноса строк желаний
    const wishChars = Math.max(16, Math.floor(cellSize / 12));
    const nameFontSize = 20;
    const wishFontSize = 13;
    const lineGapName = 26;
    const lineGapWish = 18;
    const nameBlockHeight = nameLines.length * lineGapName;
    const wishesBlock = wishes
      .map((w) => wrapText('• ' + w, wishChars))
      .map((lines) => lines.join('\n'))
      .join('\n');
    const wishLineCount = wishesBlock ? wishesBlock.split('\n').length : 0;
    const wishBlockHeight = wishLineCount * lineGapWish;
    const nameStartY = y + 26;
    const wishStartY = nameStartY + nameBlockHeight + 16;
    const nameTexts = nameLines
      .map(
        (ln, li) =>
          `<text x="${x + cellSize / 2}" y="${nameStartY + li * lineGapName}" text-anchor="middle" fill="#fff" font-size="${nameFontSize}" font-weight="700">${escapeHtml(ln)}</text>`,
      )
      .join('');
    const wishTexts = wishesBlock
      ? wishesBlock
          .split('\n')
          .map(
            (ln, li) =>
              `<text x="${x + 18}" y="${wishStartY + li * lineGapWish}" fill="#fff" font-size="${wishFontSize}">${escapeHtml(ln)}</text>`,
          )
          .join('')
      : '';
    return `
      <g>
        <rect x="${x}" y="${y}" width="${cellSize}" height="${cellSize}" rx="14" fill="${sphere.color}" />
        ${nameTexts}
        ${wishTexts}
      </g>
    `;
  }).join('');

  return `
    <svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
      <rect x="0" y="0" width="${W}" height="${H}" fill="#fffaf2" />
      ${cells}
    </svg>
  `;
}

function updateQuotaNote() {
  const plan = getUserPlan();
  const limit = LIMITS[plan].wishesPerSphere;
  const labels = { anon: 'Гость', free: 'Свободный', paid: 'Подписка' };
  const note = $('[data-role="quota-note"]')!;
  note.textContent = `Тариф: ${labels[plan]} · до ${limit} желаний в сфере.`;
}

function setExportButtonLoading(btn: HTMLButtonElement, loading: boolean) {
  btn.disabled = loading;
  const label = btn.querySelector<HTMLElement>('[data-role$="-label"]');
  if (!label) return;
  if (loading) {
    label.dataset.original = label.textContent ?? '';
    label.textContent = 'Готовим файл…';
  } else if (label.dataset.original) {
    label.textContent = label.dataset.original;
  }
}

/**
 * Рендерит превью (тот же SVG, что показан в браузере на шаге 3) в PNG через Canvas.
 * Используется и для кнопки «Скачать PNG», и для «Скачать PDF» (PDF получает PNG-растр —
 * пиксель-в-пиксель совпадает с тем, что пользователь видит на экране).
 *
 * PNG: 1800×1200 (2× от альбомного viewBox 900×600) — резкости хватает для A3-печати.
 */
async function renderPreviewToPng(): Promise<{ dataUrl: string; width: number; height: number }> {
  const svg = buildPreviewSvg();
  if (!svg) throw new Error('Превью пустое — выбери хотя бы одну сферу.');
  const blob = new Blob([svg], { type: 'image/svg+xml;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  try {
    const img = new Image();
    img.decoding = 'sync';
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve();
      img.onerror = () => reject(new Error('Не удалось загрузить SVG превью'));
      img.src = url;
    });
    const SCALE = 2;
    const W = 900 * SCALE;
    const H = 600 * SCALE;
    const canvas = document.createElement('canvas');
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext('2d')!;
    // Подложка цвета страницы на случай прозрачных пикселей по краям (PNG заливка превью).
    ctx.fillStyle = '#fffaf2';
    ctx.fillRect(0, 0, W, H);
    ctx.drawImage(img, 0, 0, W, H);
    return { dataUrl: canvas.toDataURL('image/png'), width: W, height: H };
  } finally {
    URL.revokeObjectURL(url);
  }
}

async function generatePdf() {
  const btn = $('[data-role="download-pdf"]') as HTMLButtonElement;
  setExportButtonLoading(btn, true);
  try {
    if (state.selectedSphereIds.length === 0) {
      alert('Сначала выбери хотя бы одну сферу.');
      return;
    }
    const { jsPDF } = await import('jspdf');
    const { dataUrl } = await renderPreviewToPng();
    // A3 landscape: 420×297 мм. Альбомная сетка занимает почти всю страницу.
    const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a3' });
    const pageW = 420;
    const pageH = 297;
    // Карта 380×~253 мм (3:2) по центру. URL-подвал — в правом нижнем углу.
    const mapW = 380;
    const mapH = (600 / 900) * mapW; // = 253.33 мм
    const xOffset = (pageW - mapW) / 2;
    const yOffset = (pageH - mapH) / 2;
    doc.addImage(dataUrl, 'PNG', xOffset, yOffset, mapW, mapH, undefined, 'FAST');
    // Подвал с URL — в правом нижнем углу (мелким шрифтом)
    doc.setFontSize(9);
    doc.setTextColor(107, 58, 74);
    doc.text('app.pulab.ru/wish-map/', pageW - 15, pageH - 8, { align: 'right' });

    const filename = `karta-zhelanij-${new Date().toISOString().slice(0, 10)}.pdf`;
    doc.save(filename);
    reachGoal(GOALS.wishMapExported, { format: 'pdf' });
  } catch (err) {
    console.error('PDF generation failed', err);
    alert('Не удалось создать PDF. Попробуй PNG или обнови страницу.');
  } finally {
    setExportButtonLoading(btn, false);
  }
}

async function generatePng() {
  const btn = $('[data-role="download-png"]') as HTMLButtonElement;
  setExportButtonLoading(btn, true);
  try {
    const { dataUrl } = await renderPreviewToPng();
    // dataURL → blob → download
    const blob = await (await fetch(dataUrl)).blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `karta-zhelanij-${new Date().toISOString().slice(0, 10)}.png`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    reachGoal(GOALS.wishMapExported, { format: 'png' });
  } catch (err) {
    console.error('PNG generation failed', err);
    alert('Не удалось создать PNG. Попробуй PDF.');
  } finally {
    setExportButtonLoading(btn, false);
  }
}

// ────────────────────────────────────────────────
// Init
// ────────────────────────────────────────────────
export function initWishMap() {
  hydrate();
  refreshSphereUI();

  // Сферы: клики по карточкам + wheel
  const sphereGrid = $('[data-role="sphere-grid"]')!;
  sphereGrid.addEventListener('click', (e) => {
    const card = (e.target as HTMLElement).closest<HTMLElement>('[data-role="sphere-card"]');
    if (!card) return;
    const id = card.dataset.sphere as SphereId | undefined;
    if (id) toggleSphere(id);
  });
  sphereGrid.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    const card = (e.target as HTMLElement).closest<HTMLElement>('[data-role="sphere-card"]');
    if (!card) return;
    e.preventDefault();
    const id = card.dataset.sphere as SphereId | undefined;
    if (id) toggleSphere(id);
  });
  document.querySelector('.wish-wheel')?.addEventListener('click', (e) => {
    const sector = (e.target as SVGElement).closest<SVGElement>('.wish-wheel__sector');
    if (!sector) return;
    const id = sector.dataset.sphere as SphereId | undefined;
    if (id) toggleSphere(id);
  });

  // Step nav
  $('[data-role="to-step-2"]')?.addEventListener('click', () => goToStep(2));
  $('[data-role="to-step-3"]')?.addEventListener('click', () => {
    if (totalWishes() === 0) {
      showModal({
        title: 'Добавь хотя бы одно желание',
        text: 'Без желаний карта будет пустой. Вернись на шаг 2 и заполни хотя бы одну сферу.',
        actions: [{ label: 'Ок', onClick: closeModal }],
      });
      return;
    }
    goToStep(3);
  });
  $('[data-role="back-to-step-1"]')?.addEventListener('click', () => goToStep(1));
  $('[data-role="back-to-step-2"]')?.addEventListener('click', () => goToStep(2));
  $('[data-role="reset"]')?.addEventListener('click', () => {
    if (!confirm('Очистить карту и начать заново?')) return;
    state = { selectedSphereIds: [], wishes: {}, wishSource: {}, contestOptIn: false, referrerCode: '' };
    persist();
    refreshSphereUI();
    goToStep(1);
  });

  // Contest
  const contestToggle = $('[data-role="contest-toggle"]') as HTMLInputElement;
  const contestReferrer = $('[data-role="contest-referrer"]') as HTMLInputElement;
  contestToggle?.addEventListener('change', () => {
    state.contestOptIn = contestToggle.checked;
    contestReferrer.hidden = !contestToggle.checked;
    if (contestToggle.checked) {
      reachGoal(GOALS.wishMapContestJoined, { hasReferrer: false });
    }
    persist();
  });
  contestReferrer?.addEventListener('input', () => {
    state.referrerCode = contestReferrer.value.trim();
    persist();
  });

  // Export
  $('[data-role="download-pdf"]')?.addEventListener('click', generatePdf);
  $('[data-role="download-png"]')?.addEventListener('click', generatePng);

  // Modal
  $('[data-role="modal-close"]')?.addEventListener('click', closeModal);
  $('[data-role="modal-backdrop"]')?.addEventListener('click', closeModal);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !($('[data-role="modal"]')!.hidden)) closeModal();
  });

  // Auth change → лимиты
  onAuthChange(() => {
    refreshSphereUI();
    if (!$('#step-2')!.hidden) renderWishForms();
    if (!$('#step-3')!.hidden) updateQuotaNote();
  });

  // Если есть draft — оставляем на step 1, но сферы уже выделены
  if (state.selectedSphereIds.length > 0) {
    renderWishForms();
  }

  reachGoal(GOALS.wishMapStarted);
}
