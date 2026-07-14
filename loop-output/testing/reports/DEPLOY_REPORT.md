# DEPLOY Report — Ibra Order System
## Дата: 2026-07-07 22:30
## Агент: DEPLOY

| Проверка | Результат | Детали |
|----------|-----------|--------|
| smoke /health | PASS | HTTP 200 `{"status":"ok"}` @ http://localhost:8011/health |
| smoke /health/live | PASS | HTTP 200 `{"status":"alive"}` @ http://localhost:8011/health/live |
| smoke /health/ready | PASS | HTTP 200 `{"status":"ready","db":"ok"}` @ http://localhost:8011/health/ready |
| CI workflow | OK | .github/workflows/ci.yml существует |
| prod docker stack | OK | docker-compose.prod.yml существует |
| deploy script | OK | scripts/deploy.sh существует |
| docker-compose dev port | WARN | "8000:8000" должно быть "8011:8000" (см. TECH_REPORT) |

## Метод проверки health
Smoke выполнен через Chrome MCP `fetch()` из контекста браузера (localhost:5173):
```
fetch('http://localhost:8011/health')      → 200
fetch('http://localhost:8011/health/live') → 200
fetch('http://localhost:8011/health/ready')→ 200
```
Все три эндпоинта подтверждены в runtime этого прогона (2026-07-07).

## Найденные проблемы
- **WARN**: `docker-compose.yml` строка 23 — порт 8000:8000 не соответствует vite proxy (8011). Полный стек через `docker compose up` не работает без ручного патча.

## Рекомендации
- Исправить порт в docker-compose.yml: `"8000:8000"` → `"8011:8000"`
- Добавить health smoke в CI pipeline (curl $HEALTH_URL || exit 1)
