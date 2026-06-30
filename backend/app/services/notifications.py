import logging

logger = logging.getLogger("notifications")


def notify(target: str, message: str) -> None:
    """Single integration point for outbound notifications.

    Phase 11 will replace this with a real aiogram send to `target`
    (a Telegram group/chat id or link); until then it just logs so
    callers don't need to change when the real transport lands.
    """
    logger.info("NOTIFY -> %s: %s", target or "(no target configured)", message)
