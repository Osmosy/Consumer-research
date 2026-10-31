"""Сопоставление факта корпуса с проверкой агента.

Главный урок: по номеру страницы и числу сопоставлять нельзя — одна строка стоит на двух
слайдах, а «6,6» встречается на трёх страницах. Здесь сравниваются подписи: нормализация
(ё → е, регистр, пунктуация), сравнение по основам слов и difflib, плюс бонус за равное
число. Пороговая пара: «тот же факт» = похожая подпись, «тот же факт, другой слайд» =
похожая подпись и равное число.
"""
import difflib
import re

NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
WORD = re.compile(r"[а-яa-z0-9]+")
STOP = {"доля", "процент", "рублей", "руб", "итого", "всего", "среднее", "значение", "человек"}


def norm(text: str) -> str:
    return (text or "").lower().replace("ё", "е")


def numbers(text: str) -> set[str]:
    return {n.replace(".", ",") for n in NUMBER.findall(text or "")}


def stems(text: str) -> set[str]:
    out = set()
    for word in WORD.findall(norm(text)):
        if len(word) < 4 or word in STOP:
            continue
        out.add(word[:6])
    return out


def score(left: str, right: str) -> float:
    """0..1 — насколько подписи похожи."""
    a, b = norm(left), norm(right)
    if not a or not b:
        return 0.0
    sa, sb = stems(a), stems(b)
    overlap = len(sa & sb) / len(sa | sb) if (sa or sb) else 0.0
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    return round(0.6 * overlap + 0.4 * ratio, 3)


def same_fact(fact_label: str, fact_value: str, check_label: str, check_text: str,
              strong: float = 0.5, weak: float = 0.34) -> tuple[bool, float]:
    """Считается ли факт корпуса тем же фактом, что и проверка."""
    best = max(score(fact_label, check_label), score(fact_label, check_text))
    if best >= strong:
        return True, best
    if numbers(fact_value) & numbers(f"{check_text} {check_label}") and best >= weak:
        return True, best
    return False, best
