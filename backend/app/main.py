from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers.auth import router as auth_router
from app.routers.clients import router as clients_router
from app.routers.files import router as files_router
from app.routers.orders import router as orders_router
from app.routers.suppliers import router as suppliers_router
from app.routers.users import router as users_router

app = FastAPI(
    title="Ibra Order System",
    description="Система внутреннего учёта заказов",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(clients_router)
app.include_router(files_router)
app.include_router(orders_router)
app.include_router(suppliers_router)
app.include_router(users_router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "db_configured": bool(settings.database_url),
    }
