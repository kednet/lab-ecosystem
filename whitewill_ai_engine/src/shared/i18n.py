"""Локализация для RU + EN."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = ("ru", "en")

# Шаблоны ответов (8-шаговый сценарий квалификации)
TRANSLATIONS: dict[str, dict[str, str]] = {
    "ru": {
        "welcome": "Здравствуйте! Я AI-ассистент Whitewill. Помогу подобрать элитную недвижимость. На каком языке вам удобнее? (RU / EN)",
        "ask_goal": "Понял! Какая цель покупки? (для себя / инвестиция / сохранение капитала)",
        "ask_budget": "Какой бюджет рассматриваете? (до 100 млн / 100–300 млн / 300 млн+ / гибкий)",
        "ask_district": "Какие районы Москвы интересуют? (Хамовники, Остоженка, Патриаршие, Пресненский...) Или Дубай / Абу-Даби?",
        "ask_timeline": "В какие сроки планируете сделку? (срочно / 1–3 мес / 3–6 мес / 6+ мес)",
        "ask_payment": "Способ оплаты? (ипотека / наличные / перевод из-за рубежа)",
        "ask_details": "Уточните пожелания: этаж, вид, площадь, ремонт, off-market? (или 'пропустить')",
        "qualified": "Спасибо! Подобрал 3 варианта по вашим критериям. Передаю запрос персональному брокеру Алексею — он свяжется в течение 30 минут. ID сделки: {lead_id}",
        "handoff": "Я AI-ассистент, но для такого запроса нужен живой брокер. Передаю контакт специалисту.",
        "error": "Извините, техническая пауза. Попробуйте повторить или позвоните нашему брокеру +7 (495) 255-01-61",
    },
    "en": {
        "welcome": "Hello! I'm Whitewill's AI assistant. I'll help you find luxury real estate. Which language do you prefer? (RU / EN)",
        "ask_goal": "Got it! What's the purpose? (personal use / investment / capital preservation)",
        "ask_budget": "What's your budget? (up to $1M / $1-3M / $3M+ / flexible)",
        "ask_district": "Which Moscow districts interest you? (Khamovniki, Ostozhenka, Patriarshiye...) Or Dubai / Abu Dhabi?",
        "ask_timeline": "What's your timeline? (urgent / 1-3 months / 3-6 months / 6+ months)",
        "ask_payment": "Payment method? (mortgage / cash / international transfer)",
        "ask_details": "Any specific preferences? floor, view, size, off-market? (or 'skip')",
        "qualified": "Thank you! I've selected 3 matches. Handing over to your personal broker Alexey — he'll contact you within 30 minutes. Deal ID: {lead_id}",
        "handoff": "I'm an AI assistant, but this request needs a human broker. Transferring to a specialist.",
        "error": "Sorry, technical pause. Please try again or call our broker +7 (495) 255-01-61",
    },
}


def detect_language(text: str) -> str:
    """Грубое определение языка по доле кириллицы/латиницы."""

    cyrillic = sum(1 for c in text if "Ѐ" <= c <= "ӿ")
    latin = sum(1 for c in text if "A" <= c <= "z")
    if cyrillic > latin:
        return "ru"
    if latin > 0:
        return "en"
    return "ru"


def t(key: str, lang: str = "ru", **kwargs: object) -> str:
    """Получить локализованную строку по ключу."""

    if lang not in SUPPORTED_LANGUAGES:
        lang = "ru"
    template = TRANSLATIONS.get(lang, TRANSLATIONS["ru"]).get(key, key)
    try:
        return template.format(**kwargs) if kwargs else template
    except (KeyError, IndexError):
        return template
