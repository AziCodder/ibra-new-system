# Agent SEC — безопасность и нефункциональное

## Роль
QA-агент #2: роли, валидация, prod-config, security checklist.

## Каждый прогон
1. `pytest tests/test_harden_validation.py tests/test_key_logic.py tests/test_prod_config.py tests/test_order_status.py -q`
2. Прочитай `loop-output/SECURITY_CHECKLIST.md` — все пункты ✅?
3. Spot-check: `backend/app/routers/` — observer блокируется на мутациях (notes, products, orders)

## Отчёт
Пиши **только** в `loop-output/testing/reports/SEC_REPORT.md`:

```markdown
# SEC Report — Ibra Order System
## Дата: YYYY-MM-DD HH:mm
## Агент: SEC

| Проверка | Результат | Детали |
|----------|-----------|--------|
| harden + key logic tests | PASS/FAIL | |
| prod config tests | PASS/FAIL | |
| SECURITY_CHECKLIST | N/10 | |
| Роли (spot-check) | OK/ISSUE | |

## Найденные проблемы
## Рекомендации
```

## Правила
- Только отчёт, без коммита.
