"""
Воркер одного аккаунта: подключается через свой прокси и обрабатывает
свою порцию целевых user_id.

Жёсткая обработка ошибок:
  * FloodWaitError — логируем тайм-аут и безопасно засыпаем (asyncio.sleep),
    не блокируя остальные задачи. Если ожидание дольше MAX_FLOOD_WAIT —
    аккаунт прекращает текущий цикл, остальные продолжают работать.
  * PeerFloodError — Telegram пометил аккаунт как спамящий. Логируем,
    выводим аккаунт из работы на PEER_FLOOD_COOLDOWN и завершаем его цикл
    без падения всей программы.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import List

from telethon import TelegramClient
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.types import InputPeerUser
from telethon.errors import (
    FloodWaitError,
    PeerFloodError,
    UserPrivacyRestrictedError,
    UserDeactivatedError,
    UserDeactivatedBanError,
    UserNotMutualContactError,
    UserChannelsTooMuchError,
    UserAlreadyParticipantError,
    UserKickedError,
    ChatAdminRequiredError,
    UserBlockedError,
)

import config
from session_manager import SessionBinding


@dataclass
class WorkerResult:
    """Итог работы одного аккаунта — для финального отчёта."""
    account: str
    processed: int = 0
    failed: int = 0
    skipped: int = 0
    stopped_reason: str | None = None
    errors: List[str] = field(default_factory=list)


async def process_target(client: TelegramClient, group_entity, user_id: int) -> None:
    """
    ДЕЙСТВИЕ: добавить пользователя user_id в group_entity (группа/канал).

    group_entity резолвится один раз на аккаунт в run_account() и передаётся сюда,
    чтобы не дёргать сеть на каждой цели.

    Возможные исключения пробрасываются наверх и разбираются в run_account()
    (FloodWait, PeerFlood, приватность и т.д.).
    """
    # Резолвим самого пользователя в InputPeer (нужен access_hash).
    user = await client.get_input_entity(user_id)
    if not isinstance(user, InputPeerUser):
        raise ValueError(f"user_id={user_id} не является пользователем.")
    await client(InviteToChannelRequest(channel=group_entity, users=[user]))


async def run_account(
    binding: SessionBinding,
    targets: List[int],
) -> WorkerResult:
    """Полный жизненный цикл одного аккаунта в рамках одного запуска."""
    log = logging.getLogger(f"acct:{binding.name}")
    result = WorkerResult(account=binding.name)

    if not targets:
        log.info("Нет целей для этого аккаунта — пропуск.")
        result.stopped_reason = "no_targets"
        return result

    client = TelegramClient(
        str(binding.session_path),
        config.API_ID,
        config.API_HASH,
        proxy=binding.proxy,
    )

    try:
        await client.connect()
        if not await client.is_user_authorized():
            log.error("Сессия не авторизована — пропуск аккаунта.")
            result.stopped_reason = "unauthorized"
            return result

        me = await client.get_me()
        log.info("Подключён как %s (id=%s). Целей: %d",
                 getattr(me, "username", None) or me.first_name, me.id, len(targets))

        # Резолвим целевую группу один раз. Аккаунт уже должен в ней состоять.
        try:
            group_entity = await client.get_entity(config.TARGET_GROUP)
        except Exception as e:  # noqa: BLE001
            log.error("Не удалось получить целевую группу %r: %s. Аккаунт пропущен.",
                      config.TARGET_GROUP, e)
            result.stopped_reason = "bad_target_group"
            return result

        for uid in targets:
            try:
                await process_target(client, group_entity, uid)
                result.processed += 1
                log.debug("OK user_id=%s", uid)
                await asyncio.sleep(config.ACTION_DELAY)

            except FloodWaitError as e:
                # Telegram просит подождать e.seconds секунд.
                log.warning("FloodWait на %d сек (user_id=%s).", e.seconds, uid)
                if config.MAX_FLOOD_WAIT and e.seconds > config.MAX_FLOOD_WAIT:
                    log.error(
                        "FloodWait %d сек превышает порог %d — аккаунт завершает цикл.",
                        e.seconds, config.MAX_FLOOD_WAIT,
                    )
                    result.stopped_reason = f"flood_wait_{e.seconds}s"
                    break
                # Безопасная пауза: другие корутины продолжают работать.
                await asyncio.sleep(e.seconds + 1)

            except PeerFloodError:
                # Аккаунт ограничен за «спамное» поведение — выводим из работы.
                log.error(
                    "PeerFloodError: аккаунт ограничен. Остужаем на %d сек и "
                    "прекращаем его задачи (остальные аккаунты продолжают).",
                    config.PEER_FLOOD_COOLDOWN,
                )
                result.stopped_reason = "peer_flood"
                await asyncio.sleep(config.PEER_FLOOD_COOLDOWN)
                break

            except (UserDeactivatedError, UserDeactivatedBanError):
                # Сам аккаунт забанен/удалён — дальше работать им бессмысленно.
                log.error("Аккаунт деактивирован/забанен — завершаем цикл.")
                result.stopped_reason = "account_banned"
                break

            except UserPrivacyRestrictedError:
                # Конкретная цель недоступна по настройкам приватности — пропускаем.
                log.info("user_id=%s недоступен (приватность) — пропуск.", uid)
                result.skipped += 1

            except UserAlreadyParticipantError:
                # Уже в группе — считаем успехом, не тратим попытку зря.
                log.debug("user_id=%s уже в группе — пропуск.", uid)
                result.skipped += 1

            except (UserNotMutualContactError, UserChannelsTooMuchError,
                    UserKickedError, UserBlockedError):
                # «Мягкие» причины: не во взаимных контактах, перебор групп,
                # был кикнут, заблокировал — пропускаем конкретную цель.
                log.info("user_id=%s нельзя добавить (ограничение пользователя) — пропуск.", uid)
                result.skipped += 1

            except ChatAdminRequiredError:
                # У аккаунта нет прав добавлять участников — дальше бессмысленно.
                log.error("Нет прав на добавление участников в группу — завершаем цикл.")
                result.stopped_reason = "no_admin_rights"
                break

            except Exception as e:  # noqa: BLE001 — изолируем одну цель, не весь аккаунт
                result.failed += 1
                msg = f"user_id={uid}: {type(e).__name__}: {e}"
                result.errors.append(msg)
                log.exception("Ошибка на цели %s", uid)

    except Exception as e:  # noqa: BLE001 — сбой подключения аккаунта не должен ронять остальных
        result.stopped_reason = f"connect_error:{type(e).__name__}"
        result.errors.append(str(e))
        log.exception("Фатальная ошибка аккаунта при подключении/работе.")
    finally:
        await client.disconnect()
        log.info(
            "Готово. Обработано=%d, ошибок=%d, пропущено=%d, причина_останова=%s",
            result.processed, result.failed, result.skipped, result.stopped_reason,
        )

    return result
