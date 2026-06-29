from fastapi import FastAPI

app = FastAPI(
    title="Ibra Order System",
    description="Система внутреннего учёта заказов",
    version="0.1.0",
)


@app.get("/health")
async def health():
    return {"status": "ok"}
