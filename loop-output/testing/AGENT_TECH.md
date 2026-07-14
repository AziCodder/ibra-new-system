# Agent TECH — техническое тестирование

## Роль
QA-агент #1: unit/integration, типы, линтеры, regression.

## Каждый прогон
1. `cd backend && python -m pytest tests/ -q --tb=no`
2. `cd frontend && npx tsc --noEmit && npx eslint src/ --ext .ts,.tsx`
3. Опционально: `cd frontend && npm run build` (если <2 мин)

## Отчёт
Пиши **только** в `loop-output/testing/reports/TECH_REPORT.md`:

```markdown
# TECH Report — Ibra Order System
## Дата: YYYY-MM-DD HH:mm
## Агент: TECH

| Проверка | Результат | Детали |
|----------|-----------|--------|
| pytest | PASS/FAIL | N passed |
| tsc | PASS/FAIL | |
| eslint | PASS/FAIL | |

## Найденные проблемы
- (или «нет»)

## Рекомендации
- (кратко)
```

## Правила
- Не меняй код без критического FAIL (только отчёт).
- Коммит не нужен — только отчёт.
