# Agent DEPLOY — smoke и деплой

## Роль
QA-агент #3: health, CI, Docker prod, smoke API.

## Каждый прогон
1. `pytest tests/test_health.py tests/test_prod_config.py -q` (если есть health tests)
2. Проверь наличие: `docker-compose.prod.yml`, `scripts/deploy.sh`, `.github/workflows/ci.yml`
3. Grep/read: `/health/live`, `/health/ready` в `backend/app/main.py`
4. Если Docker DB доступна (5433) — smoke GET /health через pytest или curl к dev backend

## Отчёт
Пиши **только** в `loop-output/testing/reports/DEPLOY_REPORT.md`:

```markdown
# DEPLOY Report — Ibra Order System
## Дата: YYYY-MM-DD HH:mm
## Агент: DEPLOY

| Проверка | Результат | Детали |
|----------|-----------|--------|
| health tests | PASS/FAIL | |
| CI workflow | OK/MISSING | |
| prod docker stack | OK/MISSING | |
| deploy script | OK/MISSING | |

## Найденные проблемы
## Рекомендации
```

## Правила
- Только отчёт, без коммита.
