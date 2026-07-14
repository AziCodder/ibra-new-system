# SEC Report — Ibra Order System
## Дата: 2026-07-07 22:30
## Агент: SEC

| Проверка | Результат | Детали |
|----------|-----------|--------|
| security pytest (harden + key_logic + prod_config + order_status) | PASS | 34 passed — из предыдущего прогона qa.ps1 (тот же код, изменений не было) |
| SECURITY_CHECKLIST | 10/10 ✅ | Все пункты подтверждены статическим анализом |
| Роли backend (spot-check) | OK | observer → 403 на мутации (orders, notes, products, logistics create/accept) |
| Роли frontend (spot-check) | OK | canEdit/canCreate/adminOnly корректно гейтируют UI (64 проверки в 16 файлах) |
| Docs в prod | OK | main.py: openapi_url=None, docs_url=None при ENVIRONMENT=production |
| CORS / Trusted Hosts | OK | settings.py: prod enforces ALLOWED_ORIGINS, ALLOWED_HOSTS — pytest test_prod_config проверяет |
| JWT / Secret key | OK | dev допускает слабый секрет; prod требует ≥32 символов (test_prod_config) |
| Observer создаёт notes | ISSUE (minor) | notes.py:26 → 403 для observer; NotesSection.tsx:87 скрывает форму. Но ТЗ §9 говорит observer должен мочь добавлять заметки — несоответствие |

## Spot-check ролей (backend routers)
- `orders.py:43` — `_require_not_observer(user)` → 403 для observer при создании заказа ✅
- `notes.py:26` — `_get_order_for_write()` → 403 для observer ⚠️ (ТЗ §9 спорно)
- `logistics.py:222` — `_require_admin(user)` для приёмки → только admin ✅
- `orders.py:85` — manager видит только свои заказы (manager_id filter) ✅
- `orders.py:131` — прямой доступ к чужому заказу для manager → 404 ✅

## SECURITY_CHECKLIST (10/10)
Все 10 пунктов из `loop-output/SECURITY_CHECKLIST.md` проверены и подтверждены кодом/тестами.

## Найденные проблемы
1. **MINOR**: Observer не может добавлять заметки (notes.py:26 → 403, NotesSection.tsx:87 скрывает форму). Бэкенд и фронтенд согласованы между собой, но ТЗ §9 трактуется двояко. **Не блокер.**

## Рекомендации
- Уточнить ТЗ §9: должен ли observer добавлять заметки к заказу? Если да — убрать `_get_order_for_write()` для notes и изменить NotesSection.tsx:87.
- Pytest security subset оставить в CI как обязательную проверку.
