# FIN Report — Ibra Order System
## Дата: 2026-07-07 —
## Агент: FIN

| Проверка | Результат | Детали |
|----------|-----------|--------|
| расчётные тесты (profit/remaining/validation) | PASS | 34 passed (test_key_logic, test_payment_requests, test_logistics, test_logistics_validation, test_harden_validation); доп. 15 passed (test_profit, test_payment_request_validation) |
| формула прибыли (валюта заказа) | OK | `profit.py:124` — income − purchases − logistics − other_expenses; каждый компонент приведён к валюте заказа через `amount * exchange_rate` |
| остатки закупки/отправки | OK | закупка: `payment_request_validation.py:37` (total = quantity*price − already_requested); отправка: `logistics_validation.py:38` (quantity − shipped, `cancelled` исключён) |
| запрет смешения валют | OK | `payment_request_validation.py:62-66` — >1 валюты → PaymentRequestValidationError; покрыт `test_validate_rejects_mixed_currencies` |
| граничные суммы/курсы (0, отриц.) | OK | нулевой/отриц. курс и сумма отклоняются на слоях ledger/payment/logistics/product (test_harden_validation, 15 тестов); превышение остатков — key_balance |

## Найденные проблемы
- нет

## Детали проверок

### 1. Расчётные тесты
Прогон FIN-набора (Postgres 5433 поднят через `docker compose up -d db`):
```
tests/test_key_logic.py tests/test_payment_requests.py tests/test_logistics.py
tests/test_logistics_validation.py tests/test_harden_validation.py
→ 34 passed in 6.07s
```
Дополнительно для сверки формулы прибыли и запрета смешения валют:
```
tests/test_profit.py tests/test_payment_request_validation.py → 15 passed in 3.17s
```

### 2. Формула прибыли (спот-чек `app/services/profit.py`)
- Доходы и прочие расходы — `SUM(LedgerEntry.amount * exchange_rate)` по типам `income` / `expense` (`profit.py:75-111`).
- Закупки — `SUM(Payment.amount * exchange_rate)` по всем оплатам заявок заказа (`profit.py:84-90`).
- Логистика — `SUM(Logistics.expense_amount * exchange_rate)` только по `status=accepted` и непустому `expense_amount` (`profit.py:92-102`); `in_transit`/`cancelled` не учитываются.
- Итог: `profit = income − purchases − logistics − other_expenses`, валюта = валюта заказа (`profit.py:113-126`).
- Курс трактуется как «единиц валюты заказа за 1 единицу валюты операции» — согласовано с ТЗ §11 и тестами.

### 3. Остатки (спот-чек)
- **Закупка** (`payment_remaining.py` + `payment_request_validation.py`): остаток товара = `quantity*price − Σ уже запрошенных сумм`; перерасход отклоняется (`validate_payment_request_items`, `payment_request_validation.py:68-73`). `exclude_request_id` не даёт задвоить собственные строки при редактировании.
- **Отправка** (`logistics_validation.py`): остаток = `product.quantity − Σ отправленного`, где `status=cancelled` исключён (`logistics_validation.py:30-38`). Перерасход отклоняется (`:49-52`). `exclude_logistics_id` корректно поддерживает редактирование той же отправки.

### 4. Сверка примеров ТЗ §11
- **Пример 1 (заказ в рублях):** 245 000 − 121 000 − 40 000 − 10 000 = **74 000 ₽** — совпадает (`test_key_logic.py:147`, `test_profit.py:144`).
- **Пример 2 (заказ в долларах):** 1 100 − 80 − 3 − 50 = **967 USD** — совпадает (`test_profit.py::test_usd_order_tz_example_2`). Мультивалютные доходы/закупки/логистика приведены к USD по курсам (0.2 USD/CNY, 0.01 USD/RUB).

### 5. Граничные кейсы (покрытие тестами)
- Нулевой курс / отрицательный курс — ledger, payment, logistics (create/accept): отклоняются.
- Нулевая / отрицательная сумма — ledger amount, payment amount, logistics expense_amount, product quantity: отклоняются.
- `logistics_create_allows_null_exchange_rate` — null-курс на создании допустим (курс задаётся при приёмке) — ожидаемо.
- Превышение остатка закупки (201 при остатке 200) и остатка отправки (21 при 20) — отклоняются (`test_key_logic::test_payment_and_shipment_remaining_guards`).
- Смешение валют в одной заявке — отклоняется.

## Рекомендации
- Замечаний нет: финансово-расчётный слой корректен, формула прибыли и оба примера ТЗ сходятся, граничные кейсы (0/отриц. суммы и курсы, перерасход остатков, смешение валют) покрыты тестами.
- Тестовый Postgres (5433) поднимается только через Docker; для стабильных прогонов FIN-набора держать контейнер `db` запущенным — иначе 34 теста падают на этапе подключения (OSError к 5433), а не по бизнес-логике.
