"""
Точка входа: собирает сессии, прокси и цели, распределяет задачи и
запускает все аккаунты конкурентно через asyncio.gather.

Запуск:
    python main.py
Параметры берутся из config.py (можно переопределить переменными окружения).
"""
from __future__ import annotations

import asyncio
import logging

import config
from proxy_manager import load_proxies
from session_manager import discover_sessions, bind_proxies
from task_distributor import load_targets, split_targets
from worker import run_account, WorkerResult


def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


async def main() -> None:
    setup_logging()
    log = logging.getLogger("main")

    if not config.API_ID or not config.API_HASH:
        raise SystemExit(
            "Не заданы TG_API_ID / TG_API_HASH. "
            "Получите их на https://my.telegram.org и задайте в config.py "
            "или через переменные окружения."
        )

    # 1. Загружаем ресурсы.
    sessions = discover_sessions(config.SESSIONS_DIR)
    proxies = load_proxies(config.PROXIES_FILE)
    targets = load_targets(config.TARGETS_FILE)

    # 2. Биндим уникальный прокси к каждой сессии.
    bindings = bind_proxies(sessions, proxies, allow_reuse=False)
    if not bindings:
        raise SystemExit("Нет активных сессий с прокси — нечего запускать.")

    # 3. Делим цели поровну между активными аккаунтами.
    buckets = split_targets(targets, len(bindings))

    # 4. Запускаем все аккаунты конкурентно.
    log.info("Старт: %d аккаунтов, %d целей.", len(bindings), len(targets))
    coros = [run_account(b, bucket) for b, bucket in zip(bindings, buckets)]
    results: list[WorkerResult] = await asyncio.gather(*coros, return_exceptions=False)

    # 5. Итоговый отчёт.
    total_ok = sum(r.processed for r in results)
    total_fail = sum(r.failed for r in results)
    total_skip = sum(r.skipped for r in results)
    log.info("=" * 60)
    log.info("ИТОГО: обработано=%d, ошибок=%d, пропущено=%d", total_ok, total_fail, total_skip)
    for r in results:
        log.info(
            "  %-20s ok=%-4d fail=%-3d skip=%-3d %s",
            r.account, r.processed, r.failed, r.skipped,
            f"[{r.stopped_reason}]" if r.stopped_reason else "",
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.getLogger("main").info("Прервано пользователем.")
