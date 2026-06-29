from fastapi import FastAPI

from app.core.config import settings

app = FastAPI(
    title="Ibra Order System",
    description="Система внутреннего учёта заказов",
    version="0.1.0",
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "db_configured": bool(settings.database_url),
    }
