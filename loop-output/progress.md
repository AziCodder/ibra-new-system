# Progress — Ibra Order System

## Текущая фаза: 4
## Текущая задача: 4.10 — Заметки заказа

## Выполненные задачи

| Задача | Описание | Дата | Статус |
|--------|----------|------|--------|
| 0.1 | Структура репозитория (backend/, frontend/, docker-compose, .gitignore, README, docs) | 2026-06-29 19:45 | ✅ |
| 0.2 | PostgreSQL в Docker (healthcheck, pg_isready + psql подключение проверено) | 2026-06-29 19:51 | ✅ |
| 0.3 | Скелет FastAPI (main.py, /health, /docs, requirements.txt) | 2026-06-29 19:57 | ✅ |
| 0.4 | Конфиг через pydantic-settings (Settings из .env, проверено) | 2026-06-29 20:03 | ✅ |
| 0.5 | SQLAlchemy + Alembic (async engine, Base, sync psycopg миграции, port 5433) | 2026-06-29 20:11 | ✅ |
| 0.6 | Скелет фронтенда (Vite+React+TS+Tailwind+Router+Query, dark/light токены, health check) | 2026-06-29 20:19 | ✅ |
| 0.7 | CORS и dev-прокси (FastAPI CORSMiddleware + Vite proxy) | 2026-06-29 20:24 | ✅ |
| 0.8 | Линтеры (ruff backend, eslint+typescript-eslint frontend, оба чистые) | 2026-06-29 20:30 | ✅ |
| 0.9 | Docker-compose dev-окружение (db + backend + frontend, hot-reload) | 2026-06-29 21:15 | ✅ |
| 1.1 | Модель User (id, login, password_hash, role, full_name, is_active, created_at) + миграция | 2026-06-29 21:20 | ✅ |
| 1.2 | Хеширование паролей argon2 (hash_password/verify_password + 3 теста) | 2026-06-29 21:25 | ✅ |
| 1.3 | Сидинг первого админа (CLI: python -m app.scripts.create_admin) | 2026-06-29 21:30 | ✅ |
| 1.4 | Логин/логаут с httpOnly cookie сессией (itsdangerous) | 2026-06-29 21:35 | ✅ |
| 1.5 | GET /api/auth/me — текущий пользователь | 2026-06-29 21:40 | ✅ |
| 1.6 | require_role dependency для проверки ролей на бэкенде | 2026-06-29 21:45 | ✅ |
| 1.7 | Фронт: страница логина (AuthContext, LoginPage, RequireAuth) | 2026-06-29 21:55 | ✅ |
| 1.8 | Фронт: защита маршрутов (RequireAuth + redirect to /login) | 2026-06-29 21:55 | ✅ |
| 1.9 | Управление пользователями CRUD (только админ, backend+frontend) | 2026-06-29 22:05 | ✅ |
| 2.1 | Модель Client (code, full_name, description, tg_link) + миграция | 2026-06-29 22:15 | ✅ |
| 2.2 | CRUD клиентов API (list/create/update/delete, admin only) | 2026-06-29 22:20 | ✅ |
| 2.3 | Модель Supplier (name, contacts, details) + миграция | 2026-06-29 22:25 | ✅ |
| 2.4 | CRUD поставщиков API | 2026-06-29 22:25 | ✅ |
| 2.5 | Фронт: раздел «База данных» (вкладки Users/Clients/Suppliers) | 2026-06-29 22:30 | ✅ |
| 3.1 | Абстракция хранилища файлов (LocalStorage + 4 теста) | 2026-06-29 22:35 | ✅ |
| 3.2 | Загрузка/выдача файлов API (upload/download/delete) | 2026-06-29 22:40 | ✅ |
| 3.3 | Фронт: компонент загрузки файлов (drag&drop, прогресс, список) | 2026-06-29 22:45 | ✅ |
| 4.1 | Модель Order (number, client_id, manager_id, status, currency) + миграция, проверено в БД | 2026-06-30 09:10 | ✅ |
| 4.2 | Автогенерация номера заказа (FOR UPDATE lock, тест на конкурентность) | 2026-06-30 09:20 | ✅ |
| 4.3 | API создания/чтения заказа (POST/GET), проверено end-to-end | 2026-06-30 09:30 | ✅ |
| 4.4 | Список заказов: фильтры (client/status/manager) + пагинация, проверено | 2026-06-30 09:45 | ✅ |
| 4.5 | Права видимости заказов (manager видит только свои), проверено | 2026-06-30 10:00 | ✅ |
| 4.6 | Фронт: AppShell (sidebar) + список заказов плиткой, фильтры, пагинация. Проверено в браузере — нашёл и исправил 2 бага: vite-proxy /api rewrite, LoginPage без редиректа | 2026-06-30 10:30 | ✅ |
| 4.7 | Фронт: модалка создания заказа + переход на страницу заказа (OrderDetailPage-плейсхолдер). Проверено в браузере end-to-end после восстановления Docker: модалка открывается, клиент/валюта/детали заполняются, менеджер показан read-only, сохранение создаёт заказ и переходит на /orders/:id, страница заказа отображает корректные данные, "← Назад" возвращает в список с новой плиткой | 2026-06-30 12:05 | ✅ |
| 4.8 | Фронт: каркас страницы заказа — 4 вкладки (Товары/Запросы на оплату/Логистика/ДиР), переключение с индиго-подчёркиванием, пустые плейсхолдеры. tsc+eslint чисто, паттерн идентичен уже проверенным (4.6 TabBar, 4.7 шапка). Docker не поднялся 2 тика подряд — закрываю по статической проверке; полная визуальная сверка по плану будет в фазе HARDEN (§7 инструкции) | 2026-06-30 12:05 | ✅ |
| 4.9 | PATCH/DELETE /api/orders/{id} (admin only) + count_order_dependencies() + 3 теста. Docker снова поднялся — запустил pytest: 3 теста падали с asyncpg `InterfaceError`/`Event loop is closed` при прогоне всего набора (module-level engine делил connection pool между тестами на разных event loop в pytest-asyncio strict mode на Windows ProactorEventLoop). Исправил добавлением `tests/conftest.py` с autouse `@pytest_asyncio.fixture`, который вызывает `engine.dispose()` после каждого теста — это инфраструктурный фикс тестового набора, не относится к бизнес-логике 4.9. Полный набор: 11 passed | 2026-06-30 16:50 | ✅ |

## Блокеры / заметки
- Docker DB на порту 5433 (не 5432 — конфликт с локальным Postgres)
- pip install требует --trusted-host из-за SSL на этой машине
- Python 3.11 путь: C:/Users/Абдул-Азиз/AppData/Local/Programs/Python/Python311/python.exe
- Alembic использует psycopg (sync) для миграций, runtime — asyncpg
- Docker Desktop иногда падает/перезапускается — если миграции не идут (Connect call failed на 5433), писать миграцию вручную (на основе модели), затем `alembic upgrade head` когда Docker снова поднимется
- Vite dev-сервер по умолчанию слушает только [::1] (IPv6) — для preview/curl-проверки нужен флаг `--host 127.0.0.1` (см. .claude/launch.json)
- Новые backend-роуты ВСЕ регистрируются с префиксом `/api/...` — vite.config.ts проксирует `/api` без rewrite (раньше rewrite вырезал префикс — баг, исправлен в Phase 4.6)
