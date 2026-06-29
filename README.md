# Ibra Order System

Система внутреннего учёта заказов. Объединяет весь процесс: принятие заказа → закупка → логистика → приёмка → подсчёт прибыли.

## Стек

- **Backend:** FastAPI + SQLAlchemy 2.0 + PostgreSQL 16
- **Frontend:** React + Vite + TypeScript + Tailwind CSS
- **Telegram:** aiogram (уведомления в группы клиентов)

## Быстрый старт

```bash
# 1. Скопировать конфиг
cp .env.example .env

# 2. Поднять БД
docker compose up db -d

# 3. Backend
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# 4. Frontend
cd frontend
npm install
npm run dev
```

## Структура

```
backend/          — FastAPI приложение
  app/
    models/       — SQLAlchemy модели
    routers/      — API эндпоинты
    services/     — бизнес-логика
    schemas/      — Pydantic схемы
    core/         — конфиг, auth, зависимости
  tests/          — pytest тесты
frontend/         — React приложение
  src/
    components/   — компоненты страниц
    pages/        — страницы (роуты)
    ui/           — переиспользуемые UI-компоненты, токены
    hooks/        — кастомные хуки
    api/          — API-клиент
    types/        — TypeScript типы
```
