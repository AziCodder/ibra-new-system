from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.core.config import settings
from app.routers.action_log import router as action_log_router
from app.routers.auth import router as auth_router
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
from app.routers.products import router as products_router
from app.routers.profit import router as profit_router
from app.routers.suppliers import router as suppliers_router
from app.routers.users import router as users_router
from app.services.telegram_bot import close_bot


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Close the shared aiogram bot session cleanly on shutdown.
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
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(action_log_router)
app.include_router(auth_router)
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
app.include_router(products_router)
app.include_router(profit_router)
app.include_router(suppliers_router)
app.include_router(users_router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "db_configured": bool(settings.database_url),
    }
