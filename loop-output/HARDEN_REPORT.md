# HARDEN Report

| # | Проверка | Результат | Фикс (коммит) |
|---|----------|-----------|---------------|
| 1 | Отрицательный/нулевой курс обмена (ledger, payment, logistics) | БАГ → OK | `[HARDEN] reject negative exchange rates on logistics create + UI min` |
