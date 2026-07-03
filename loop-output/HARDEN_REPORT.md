# HARDEN Report

| # | Проверка | Результат | Фикс (коммит) |
|---|----------|-----------|---------------|
| 1 | Отрицательный/нулевой курс обмена (ledger, payment, logistics) | БАГ → OK | `[HARDEN] reject negative exchange rates on logistics create + UI min` |
| 2 | Наблюдатель создаёт заметки к заказу | БАГ → OK | `[HARDEN] block observer note creation and hide admin nav` |
| 3 | Пункт «База данных» виден менеджеру/наблюдателю | БАГ → OK | `[HARDEN] block observer note creation and hide admin nav` |
| 4 | Длинные названия клиента/поставщика/товара (>255) | БАГ → OK | `[HARDEN] validate max_length on client supplier product names` |
| 5 | Мобильная вёрстка 375px (формы БД, фильтры, панели) | БАГ → OK | `[HARDEN] responsive mobile layout for filters and forms` |
