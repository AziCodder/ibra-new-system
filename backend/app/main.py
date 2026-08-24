from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.core.config import settings
from app.core.health import build_health_payload
from app.core.logging_config import setup_logging
from app.middleware.request_logging import RequestLoggingMiddleware, unhandled_exception_handler
from app.routers.action_log import router as action_log_router
from app.routers.auth import router as auth_router
from app.routers.backups import router as backups_router
from app.routers.clients import router as clients_router
from app.routers.files import router as files_router
from app.routers.ledger_entries import router as ledger_entries_router
from app.routers.logistics import router as logistics_router
from app.routers.logistics_global import router as logistics_global_router
from app.routers.notes import router as notes_router
from app.routers.notifications import router as notifications_router
from app.routers.orders import router as orders_router
from app.routers.payment_requests import router as payment_requests_router
from app.routers.payment_requests_global import router as payment_requests_global_router
from app.routers.payments import router as payments_router
from app.routers.process_logs import router as process_logs_router
from app.routers.products import router as products_router
from app.routers.profit import router as profit_router
from app.routers.suppliers import router as suppliers_router
from app.routers.system_health import router as system_health_router
from app.routers.telegram_groups import router as telegram_groups_router
from app.routers.users import router as users_router
from app.services.telegram_bot import close_bot, start_polling, stop_polling


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(production=settings.is_production)
    await start_polling()
    yield
    await stop_polling()
    await close_bot()


app = FastAPI(
    title="Ibra Order System",
    description="Система внутреннего учёта заказов",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

if settings.is_production:
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=settings.trusted_hosts)
    # "localhost" is always allowed alongside the public TRUSTED_HOSTS: the
    # system-health panel probes /health* on itself via http://localhost:8000
    # (see health_self_base) — that loopback call never leaves the container,
    # so it can't be spoofed by an external Host header regardless of domain/IP.
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=[*settings.trusted_hosts, "localhost"]
    )

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(action_log_router)
app.include_router(auth_router)
app.include_router(backups_router)
app.include_router(clients_router)
app.include_router(files_router)
app.include_router(ledger_entries_router)
app.include_router(logistics_router)
app.include_router(logistics_global_router)
app.include_router(notes_router)
app.include_router(notifications_router)
app.include_router(orders_router)
app.include_router(payment_requests_router)
app.include_router(payment_requests_global_router)
app.include_router(payments_router)
app.include_router(process_logs_router)
app.include_router(products_router)
app.include_router(profit_router)
app.include_router(suppliers_router)
app.include_router(system_health_router)
app.include_router(telegram_groups_router)
app.include_router(users_router)

app.add_exception_handler(Exception, unhandled_exception_handler)


@app.get("/health")
async def health():
    return await build_health_payload(deep=False)


@app.get("/health/live")
async def health_live():
    """Liveness — process is up."""
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready():
    """Readiness — DB reachable (for uptime monitors / orchestrators)."""
    payload = await build_health_payload(deep=True)
    if payload.get("db") != "ok":
        return JSONResponse(status_code=503, content=payload)
    return payload
