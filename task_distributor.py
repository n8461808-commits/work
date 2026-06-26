"""
Распределение целевых user_id между аккаунтами.

Список делится равномерно (round-robin), чтобы:
  * нагрузка распределялась равномерно даже если список не делится нацело;
  * соседние по списку ID попадали на разные аккаунты.
Дубликаты задач между аккаунтами исключены — каждый ID обрабатывается один раз.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List

log = logging.getLogger("task_distributor")


def load_targets(path: Path) -> List[int]:
    """Загрузить список user_id из файла (по одному ID в строке)."""
    if not path.exists():
        raise FileNotFoundError(f"Файл с целями не найден: {path}")

    targets: List[int] = []
    seen: set[int] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            uid = int(line)
        except ValueError:
            log.warning("Пропущена нечисловая строка в targets: %r", line)
            continue
        if uid not in seen:          # защита от дублей в самом файле
            seen.add(uid)
            targets.append(uid)

    if not targets:
        raise ValueError(f"В файле {path} не найдено ни одного user_id.")
    return targets


def split_targets(targets: List[int], n_buckets: int) -> List[List[int]]:
    """
    Раздать ID по n_buckets «корзинам» методом round-robin.

    Возвращает список из n_buckets списков (некоторые могут быть пустыми,
    если целей меньше, чем аккаунтов).
    """
    if n_buckets <= 0:
        raise ValueError("Число корзин должно быть > 0")

    buckets: List[List[int]] = [[] for _ in range(n_buckets)]
    for i, uid in enumerate(targets):
        buckets[i % n_buckets].append(uid)

    log.info(
        "Распределено %d целей на %d аккаунтов (~%d на аккаунт).",
        len(targets),
        n_buckets,
        len(targets) // n_buckets if n_buckets else 0,
    )
    return buckets
