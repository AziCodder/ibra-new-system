# Ibra Order System

Система внутреннего учёта заказов. Объединяет весь процесс: принятие заказа → закупка → логистика → приёмка → подсчёт прибыли.

## Стек

- **Backend:** FastAPI + SQLAlchemy 2.0 + PostgreSQL 16
- **Frontend:** React + Vite + TypeScript + Tailwind CSS
- **Telegram:** aiogram (уведомления в группы клиентов)

## Быстрый старт

Нужен только Docker. Python, Node и npm на машине не требуются.

```bash
docker compose up -d --build
```

Одна команда поднимает всё: базу, миграции, API, фоновый воркер и фронтенд.
Первый запуск занимает несколько минут (сборка образов), дальше — секунды.

- Приложение: http://localhost:5173
- API: http://localhost:8011 (документация — `/docs`)
- База: `localhost:5433`

Первый администратор (один раз на чистой базе):

```bash
docker compose exec backend python -m app.scripts.create_admin admin ПАРОЛЬ "Имя Фамилия"
```

Правки в `backend/` и `frontend/` подхватываются на лету — перезапускать
контейнеры не нужно. Изменили `requirements.txt` или `package.json`:

```bash
docker compose up -d --build
```

### Повседневные команды

```bash
docker compose logs -f backend     # логи API
docker compose ps                  # что запущено
docker compose down                # остановить (данные в базе сохранятся)
docker compose down -v             # остановить и стереть базу начисто
scripts/run-tests.sh               # тесты на отдельной базе ibra_test
```

### Настройки

Стек стартует и без конфига — со значениями по умолчанию. Для Telegram-бота и
прочих секретов создайте `backend/.env` по образцу [`.env.example`](.env.example)
и перезапустите: `docker compose up -d`.

## Продакшен

Разворачивается отдельным файлом `docker-compose.prod.yml`; кластер из двух
серверов, S3 и домен описаны в [РАЗВЁРТЫВАНИЕ_КЛАСТЕРА.md](РАЗВЁРТЫВАНИЕ_КЛАСТЕРА.md).

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
