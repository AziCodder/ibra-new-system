# HARDEN Report

| # | Проверка | Результат | Фикс (коммит) |
|---|----------|-----------|---------------|
| 1 | Отрицательный/нулевой курс обмена (ledger, payment, logistics) | БАГ → OK | `[HARDEN] reject negative exchange rates on logistics create + UI min` |
| 2 | Наблюдатель создаёт заметки к заказу | БАГ → OK | `[HARDEN] block observer note creation and hide admin nav` |
| 3 | Пункт «База данных» виден менеджеру/наблюдателю | БАГ → OK | `[HARDEN] block observer note creation and hide admin nav` |
