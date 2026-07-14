# E2E Report — Ibra Order System
## Дата: 2026-07-07 22:30
## Агент: E2E
## Окружение: LIVE (backend :8011, frontend :5173, Postgres :5433)

Полный E2E-цикл выполнен в браузере через Chrome MCP. Тестовые данные созданы через REST API (более надёжно, чем UI-клики для создания), результаты верифицированы визуально в браузере.

## Тестовые учётные записи
- `qa_admin` / `QaAdmin2026!` — роль admin (создана и использована в этом прогоне)
- `qa_observer_test` / `QaObserver2026!` — роль observer (создана и деактивирована после прогона)

## Результаты по шагам

| Шаг | Действие | Результат | Детали |
|-----|----------|-----------|--------|
| 1 | Логин (admin) | ✅ PASS | POST /api/auth/login → session cookie; редирект на /; sidebar с «База данных», кнопка «+ Создать заказ» видны |
| 2 | Создать заказ + товар | ✅ PASS | Заказ QATEST-1 (id=8218, клиент QA Test Client, валюта USD); товар QA Widget 10 шт × $50; оба отображаются в OrderDetailPage |
| 3 | Запрос на оплату + частичная оплата | ✅ PASS | PaymentRequest id=1679 на $500; внесена оплата $200; остаток на UI: **$300** (progress bar ~40%); API: remaining=$300 |
| 4 | Логистика + приёмка | ✅ PASS | Logistics id=3386 (10 шт, расход $50); PATCH status=accepted → 200; is_ready=true проставлен бэкендом |
| 5 | ДиР (доходы/расходы) | ✅ PASS | Доход $800 и расход $30 добавлены через LedgerEntry API; итоги отображаются в LedgerTab |
| 6 | Блок прибыли | ✅ PASS | ProfitBlock: 800 − 200 − 50 − 30 = **$520** (65%); is_ready=true; бэкенд profit.py расчёт верен |
| 7 | Роль observer | ✅ PASS | Нет кнопки «+ Создать заказ»; нет пункта «База данных»; canEdit=false — все кнопки действий скрыты; заметки недоступны |

## Верификация profit formula (шаг 6)
```
income:    $800 (LedgerEntry type=income, exchange_rate=1.0)
purchases: $200 (оплата по payment request, exchange_rate=1.0)
logistics: $50  (logistics.expense_amount, status=accepted)
expenses:  $30  (LedgerEntry type=expense, exchange_rate=1.0)
─────────────────────────────
profit:    $520 (65.0%)   ← совпадает с UI и API /api/orders/8218
```

## Верификация ролей (шаг 7)
- Observer: нет «+ Создать заказ» ✅, нет «База данных» ✅, canEdit=false (кнопки редактирования скрыты) ✅
- Notes API: POST /api/orders/8218/notes с токеном observer → 403 ✅
- NotesSection.tsx:87: `{user?.role !== 'observer' && (` → форма скрыта ✅

## Найденные проблемы

**MINOR ⚠️: Observer не может добавлять заметки к заказу**
- Реализация: notes.py → 403, NotesSection.tsx:87 скрывает форму
- Обе стороны (BE + FE) согласованы, но ТЗ §9 подразумевает доступ observer к заметкам
- **Не является блокером.** Требует уточнения ТЗ.

**INFO: Тестовые данные не удалены полностью**
- Заказ QATEST-1 (id=8218), клиент QA Test Client (8163), поставщик QA Supplier (6160) остались в БД
- Причина: бизнес-правило — логистика со статусом accepted/cancelled не удаляется (аудит-трейл)
- qa_observer_test (id=16472) деактивирован через PATCH is_active=false
- **Не является блокером.** Данные изолированы и не влияют на функционал.

## Рекомендации
1. Уточнить ТЗ §9 по доступу observer к заметкам (см. SEC_REPORT)
2. Добавить seed-скрипт для создания тестовых пользователей в dev-окружении
3. Добавить API-эндпоинт или admin-UI для удаления тестовых заказов (force-delete с bypass бизнес-правил)
