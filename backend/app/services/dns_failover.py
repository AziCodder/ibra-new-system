"""Перевод домена на другой сервер при аварии.

Серверы стоят у разных провайдеров (HostKey и AdminVPS), поэтому общего
«плавающего» IP между ними не существует: переносить адрес умеет только
провайдер внутри своей сети. Значит, переключение делается на уровне DNS —
A-запись ``flow.cargo-ibragim.ru`` перенаправляется на IP живого сервера.

Честная оговорка про сроки. DNS — это кэш: даже при TTL 60 секунд часть
клиентов, провайдерских резолверов и браузеров какое-то время продолжит
ходить на старый адрес. Реальное переключение занимает от минуты до
нескольких (у reg.ru минимальный TTL выше, чем у Cloudflare). Это не
«секунды», как было бы с плавающим IP у одного провайдера, — и обещать
секунды было бы неправдой.

Драйверы:

* ``cloudflare`` — если зону делегировать в Cloudflare (TTL 60 c, API
  быстрый и предсказуемый);
* ``regru`` — домен управляется там, где куплен;
* ``none`` — переключение записывается в журнал, но не выполняется:
  режим наблюдения, когда автоматике ещё не доверяют.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

REGRU_API = "https://api.reg.ru/api/regru2"
CLOUDFLARE_API = "https://api.cloudflare.com/client/v4"
TIMEOUT = 20.0


class DnsError(Exception):
    pass


def fqdn() -> str:
    record = settings.dns_record.strip()
    return f"{record}.{settings.dns_zone}" if record and record != "@" else settings.dns_zone


async def point_domain_to(ip: str) -> dict:
    """Перевести домен на указанный IP. Возвращает отчёт о попытке."""
    provider = settings.dns_provider
    if not ip:
        return {"provider": provider, "changed": False, "detail": "IP узла не задан (NODE_PUBLIC_IP)"}

    if provider == "cloudflare":
        handler = _cloudflare
    elif provider == "regru":
        handler = _regru
    else:
        logger.warning(
            "переключение DNS не настроено: %s должен указывать на %s — переключите вручную",
            fqdn(), ip,
        )
        return {"provider": "none", "changed": False, "detail": "ручной режим: смените запись сами"}

    try:
        detail = await handler(ip)
    except (DnsError, httpx.HTTPError) as exc:
        logger.error("не удалось перевести %s на %s: %s", fqdn(), ip, exc)
        return {"provider": provider, "changed": False, "detail": str(exc)[:300]}

    logger.warning("домен %s переведён на %s (%s)", fqdn(), ip, provider)
    return {"provider": provider, "changed": True, "ip": ip, "detail": detail}


# ─────────────────────────────────────────────────────────────────── Cloudflare


async def _cloudflare(ip: str) -> str:
    token, zone = settings.cloudflare_api_token, settings.cloudflare_zone_id
    if not token or not zone:
        raise DnsError("не заданы CLOUDFLARE_API_TOKEN / CLOUDFLARE_ZONE_ID")

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    name = fqdn()
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=headers) as client:
        found = await client.get(
            f"{CLOUDFLARE_API}/zones/{zone}/dns_records", params={"type": "A", "name": name}
        )
        payload = _cf_result(found)
        body = {"type": "A", "name": name, "content": ip, "ttl": settings.dns_ttl, "proxied": False}
        if payload:
            record_id = payload[0]["id"]
            _cf_result(await client.put(f"{CLOUDFLARE_API}/zones/{zone}/dns_records/{record_id}", json=body))
            return f"запись обновлена (ttl {settings.dns_ttl})"
        _cf_result(await client.post(f"{CLOUDFLARE_API}/zones/{zone}/dns_records", json=body))
        return f"запись создана (ttl {settings.dns_ttl})"


def _cf_result(response: httpx.Response):
    data = response.json()
    if not data.get("success"):
        errors = "; ".join(e.get("message", "") for e in data.get("errors", []))
        raise DnsError(f"Cloudflare: {errors or response.text[:200]}")
    return data.get("result")


# ───────────────────────────────────────────────────────────────────── reg.ru


async def _regru(ip: str) -> str:
    login, password = settings.regru_login, settings.regru_password
    if not login or not password:
        raise DnsError("не заданы REGRU_LOGIN / REGRU_PASSWORD (пароль для API)")

    auth = {
        "username": login,
        "password": password,
        "domain_name": settings.dns_zone,
        "subdomain": settings.dns_record or "@",
        "output_content_type": "plain",
    }
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # У reg.ru нет «обновить запись»: старую снимаем, новую добавляем.
        # Порядок именно такой — иначе на домене какое-то время будут висеть
        # два A-адреса, и половина клиентов пойдёт на мёртвый сервер.
        await _regru_call(client, "zone/remove_record", {**auth, "record_type": "A"})
        await _regru_call(client, "zone/add_alias", {**auth, "ipaddr": ip})
    return "A-запись заменена"


async def _regru_call(client: httpx.AsyncClient, method: str, params: dict) -> dict:
    response = await client.post(f"{REGRU_API}/{method}", data=params)
    response.raise_for_status()
    data = response.json()
    if data.get("result") != "success":
        raise DnsError(f"reg.ru {method}: {data.get('error_text') or data}")
    return data
