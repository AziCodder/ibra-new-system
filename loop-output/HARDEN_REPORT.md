# HARDEN Report

| # | Проверка | Результат | Фикс (коммит) |
|---|----------|-----------|---------------|
| 1 | Отрицательный/нулевой курс обмена (ledger, payment, logistics) | БАГ → OK | `[HARDEN] reject negative exchange rates on logistics create + UI min` |
| 2 | Наблюдатель создаёт заметки к заказу | БАГ → OK | `[HARDEN] block observer note creation and hide admin nav` |
| 3 | Пункт «База данных» виден менеджеру/наблюдателю | БАГ → OK | `[HARDEN] block observer note creation and hide admin nav` |
| 4 | Длинные названия клиента/поставщика/товара (>255) | БАГ → OK | `[HARDEN] validate max_length on client supplier product names` |
| 5 | Мобильная вёрстка 375px (формы БД, фильтры, панели) | БАГ → OK | `[HARDEN] responsive mobile layout for filters and forms` |
| 6 | Нулевые суммы оплат/ДиР/логистики и нулевое кол-во товара | БАГ → OK | `[HARDEN] reject zero amounts in monetary and quantity fields` |
| 7 | Пустые списки (заказы, оплаты, логистика, товары, ДиР) | OK | — (empty states на всех экранах) |
| 8 | Роли admin/manager/observer (мутации, навигация) | OK | backend `require_role` + frontend `canEdit`/`canCreate` |
| 9 | Полный набор тестов backend + tsc/eslint frontend | OK | 184 passed (2026-07-03) |

## Итог HARDEN

6 багов исправлено, 3 категории проверены без замечаний. Отложено: визуальный аудит 768/1024/1440px (базовый адаптив сделан), модуль «Аналитика» (не в scope MVP).
