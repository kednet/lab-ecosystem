"""ML-скоринг off-market сигналов. Простая эвристика + расширяемость под ML-модель."""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class OffMarketScorer:
    """Скоринг off-market сигналов готовности к продаже.

    Сейчас — эвристика с весами. В production — обученная модель
    на исторических сделках Whitewill.
    """

    # Веса сигналов
    WEIGHTS = {
        "egrn_change_inheritance": 0.4,
        "egrn_change_sale": 0.2,
        "egrn_change_gift": 0.1,
        "encumbrance_mortgage": 0.15,
        "encumbrance_arrest": 0.3,
        "fssp_high": 0.3,
        "fssp_low": 0.1,
        "inheritance_recent": 0.35,
        "bankruptcy": 0.4,
        "cao_premium": 0.15,
        "high_value": 0.1,
    }

    PREMIUM_DISTRICTS = {
        "хамовники",
        "остоженка",
        "патриаршие пруды",
        "пресненский",
        "арбат",
        "тверской",
        "замоскворечье",
    }

    def score(self, cadastral_number: str, signals: dict) -> dict:
        """Скоринг сигналов готовности к продаже. Возвращает {score, signals, priority}."""

        score = 0.0
        trigger_signals = []

        # 1. Смена собственника
        change_type = signals.get("egrn_change_type", "")
        change_date = signals.get("egrn_change_date")

        if change_type == "inheritance" and self._recent(change_date, days=180):
            score += self.WEIGHTS["egrn_change_inheritance"]
            trigger_signals.append("Смена собственника по наследству (≤6 мес)")
        elif change_type == "sale" and self._recent(change_date, days=90):
            score += self.WEIGHTS["egrn_change_sale"]
            trigger_signals.append("Недавняя продажа соседнего объекта")
        elif change_type == "gift" and self._recent(change_date, days=180):
            score += self.WEIGHTS["egrn_change_gift"]
            trigger_signals.append("Дарение в собственности")

        # 2. Обременения
        if signals.get("has_encumbrance"):
            enc_type = signals.get("encumbrance_type", "")
            if enc_type == "arrest":
                score += self.WEIGHTS["encumbrance_arrest"]
                trigger_signals.append("Арест на объект (вероятная финансовая проблема)")
            elif enc_type == "mortgage":
                score += self.WEIGHTS["encumbrance_mortgage"]
                trigger_signals.append("Ипотека — собственник может быть мотивирован к продаже")

        # 3. ФССП
        fssp_amount = signals.get("fssp_amount", 0)
        if fssp_amount > 10_000_000:
            score += self.WEIGHTS["fssp_high"]
            trigger_signals.append(f"Крупные исп. производства (>{fssp_amount / 1_000_000:.1f} млн)")
        elif fssp_amount > 0:
            score += self.WEIGHTS["fssp_low"]
            trigger_signals.append(f"Исп. производства ({fssp_amount / 1_000_000:.1f} млн)")

        # 4. Наследственное дело
        if signals.get("has_inheritance"):
            inherit_date = signals.get("inheritance_date")
            if self._recent(inherit_date, days=180):
                score += self.WEIGHTS["inheritance_recent"]
                trigger_signals.append("Открыто наследственное дело (≤6 мес)")

        # 5. Банкротство
        if signals.get("is_bankruptcy"):
            score += self.WEIGHTS["bankruptcy"]
            trigger_signals.append("Собственник — банкрот")

        # 6. Премиум локация (бонус)
        district = signals.get("district", "").lower()
        if any(d in district for d in self.PREMIUM_DISTRICTS):
            score += self.WEIGHTS["cao_premium"]
            trigger_signals.append(f"Премиум район: {signals.get('district', '')}")

        # 7. Крупный объект (бонус)
        if signals.get("estimated_value_rub", 0) > 100_000_000:
            score += self.WEIGHTS["high_value"]
            trigger_signals.append(
                f"Крупный объект: {signals['estimated_value_rub'] / 1_000_000:.0f} млн ₽"
            )

        # Нормализуем к [0, 1]
        score = min(1.0, score)

        # Приоритет
        if score >= 0.7:
            priority = "high"
        elif score >= 0.4:
            priority = "medium"
        else:
            priority = "low"

        return {
            "score": round(score, 2),
            "signals": trigger_signals,
            "priority": priority,
        }

    def _recent(self, date: datetime | None, days: int = 90) -> bool:
        """Проверить, что событие в последние N дней."""

        if not date:
            return False
        return (datetime.utcnow() - date).days <= days


_scorer: OffMarketScorer | None = None


def get_scorer() -> OffMarketScorer:
    global _scorer
    if _scorer is None:
        _scorer = OffMarketScorer()
    return _scorer
