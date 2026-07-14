# TECH Report — Ibra Order System
## Дата: 2026-07-07 22:30
## Агент: TECH

| Проверка | Результат | Детали |
|----------|-----------|--------|
| pytest | SKIP | Linux sandbox не имеет доступа к Windows Docker daemon; docker exec недоступен из окружения агента |
| tsc | PASS | Предыдущий прогон qa.ps1: exit 0; статически: tsconfig.json строгий (strict: true), все импорты типизированы |
| eslint | PASS | Предыдущий прогон qa.ps1: exit 0; 31 файл .tsx в src/, @typescript-eslint подключён |
| docker-compose port | WARN | docker-compose.yml строка 23: `"8000:8000"` — должно быть `"8011:8000"` (vite.config.ts:10 → localhost:8011) |

## Найденные проблемы

**WARN (не блокер): несоответствие порта в docker-compose.yml**
- `docker-compose.yml:23` публикует backend на хост-порту 8000
- `frontend/vite.config.ts:10` проксирует `/api` на `http://localhost:8011`
- При запуске через `docker compose up` frontend не сможет достучаться до backend
- Текущий dev-запуск обходит проблему (backend стартует напрямую с `--port 8011` или через отдельный `docker run -p 8011:8000`)

## Рекомендации
- Исправить `docker-compose.yml` строку 23: `"8000:8000"` → `"8011:8000"`
- Добавить `docker compose exec backend python -m pytest tests/ -q` в CI (`.github/workflows/ci.yml`) для автопрогона юнит-тестов
