/**
 * Хелпер для отправки пользовательских целей в Яндекс.Метрику.
 *
 * Счётчик 109734669 подключён в `Base.astro` глобально. Метрика доступна
 * через `window.ym` только после загрузки её скрипта. Если скрипт ещё
 * не загрузился (или заблокирован в РФ) — вызовы тихо проглатываются.
 *
 * Имя цели должно быть заранее создано в настройках счётчика в
 * Яндекс.Метрике (counter 109734669 → Настройка → Цели → Добавить цель →
 * "JavaScript-событие"). Один источник правды — `GOALS` ниже; добавил
 * новую цель — зарегистрируй её там же.
 */

export const GOALS = {
  // === AUTH FLOW ===
  authCodeRequested: 'auth_code_requested',
  authCodeEntered: 'auth_code_entered',
  authLoginSuccessful: 'auth_login_successful',
  authLoginFailed: 'auth_login_failed',

  // === GENERATE FLOW ===
  generateStarted: 'generate_started',
  generateCompleted: 'generate_completed',
  generateFailed: 'generate_failed',

  // === TRACKER (устарело, оставлено на период миграции со /tracker/ на /wish-map/) ===
  // Не удаляем, чтобы не сломать старые записи в Метрике; новые события не шлём.
  trackerGoalAdded: 'tracker_goal_added',
  trackerHabitChecked: 'tracker_habit_checked',
  trackerGoalCompleted: 'tracker_goal_completed',

  // === WISH MAP (/wish-map/) ===
  wishMapStarted: 'wish_map_started',
  wishMapSphereSelected: 'wish_map_sphere_selected',
  wishMapWishAdded: 'wish_map_wish_added',
  wishMapExported: 'wish_map_exported',
  wishMapContestJoined: 'wish_map_contest_joined',

  // === AUDIO ===
  audioPlay: 'audio_play',
  audioPause: 'audio_pause',
  audioComplete: 'audio_complete',
  audioDownload: 'audio_download',
  audioLockedClicked: 'audio_locked_clicked',

  // === PRICING / CHECKOUT ===
  pricingPlanViewed: 'pricing_plan_viewed',
  pricingCheckoutStarted: 'pricing_checkout_started',

  // === SHARE ===
  shareVk: 'share_vk',
  shareTelegram: 'share_telegram',

  // === LIBRARY ===
  libraryBookOpened: 'library_book_opened',
  libraryTabSwitched: 'library_tab_switched',
  bookPdfClicked: 'book_pdf_clicked',

  // === BLOG ===
  blogFaqOpened: 'blog_faq_opened',
  blogRelatedClicked: 'blog_related_clicked',
  blogReadCompleted: 'blog_read_completed',

  // === DETECTOR (/detector/) ===
  detectorStarted: 'detector_started',
  detectorCompleted: 'detector_completed',
  detectorResultShared: 'detector_result_shared',
  detectorCtaClicked: 'detector_cta_clicked',

  // === NEWSLETTER (главная) ===
  newsletterFormSubmitted: 'newsletter_form_submitted',
  newsletterFormSuccess: 'newsletter_form_success',
  newsletterFormError: 'newsletter_form_error',

  // === MY EXPERIMENT (/my-experiment/) ===
  myExperimentFormSubmitted: 'my_experiment_form_submitted',
  myExperimentFormSuccess: 'my_experiment_form_success',
  myExperimentFormError: 'my_experiment_form_error',

  // === BOOK CLUB (/book-club/) ===
  bookClubSignupStarted: 'book_club_signup_started',
  bookClubSignupSuccess: 'book_club_signup_success',
  bookClubSignupError: 'book_club_signup_error',

  // === CLUB (/club/) — «Найти себя через книги» ===
  clubHeroCtaClicked: 'club_hero_cta_clicked',
  clubSectionViewed: 'club_section_viewed',
  clubFaqOpened: 'club_faq_opened',
  clubBookCardClicked: 'club_book_card_clicked',
  clubTgChannelClicked: 'club_tg_channel_clicked',
  clubSignupStarted: 'club_signup_started',
  clubSignupSuccess: 'club_signup_success',
  clubSignupError: 'club_signup_error',
} as const;

export type GoalName = (typeof GOALS)[keyof typeof GOALS];

/**
 * Безопасно отправляет цель в Метрику. Если Метрика ещё не загрузилась
 * (например, в DevTools при медленной сети), вызов проглатывается.
 *
 * Поддерживает также передачу дополнительных параметров для content
 * experiments (params, callback).
 */
export function reachGoal(goal: GoalName, params?: Record<string, unknown>): void {
  if (typeof window === 'undefined') return;
  const ym = (window as unknown as { ym?: (id: number, method: string, goal: string, params?: unknown) => void }).ym;
  if (typeof ym !== 'function') return;
  try {
    if (params) {
      ym(109734669, 'reachGoal', goal, params);
    } else {
      ym(109734669, 'reachGoal', goal);
    }
  } catch {
    // не критично — просто не отправили
  }
}
