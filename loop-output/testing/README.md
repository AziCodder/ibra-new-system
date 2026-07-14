# Testing Loop — 6 QA-агентов + агрегатор

**Запуск всех сразу: см. [`RUN_ALL.md`](RUN_ALL.md)** (готовые `/loop`-команды).

| Sentinel | Агент | Инструкции | Отчёт |
|----------|-------|------------|-------|
| `AGENT_LOOP_TICK_TECH` | TECH | `AGENT_TECH.md` | `reports/TECH_REPORT.md` |
| `AGENT_LOOP_TICK_SEC` | SEC | `AGENT_SEC.md` | `reports/SEC_REPORT.md` |
| `AGENT_LOOP_TICK_DEPLOY` | DEPLOY | `AGENT_DEPLOY.md` | `reports/DEPLOY_REPORT.md` |
| `AGENT_LOOP_TICK_UX` | UX | `AGENT_UX.md` | `reports/UX_REPORT.md` |
| `AGENT_LOOP_TICK_FIN` | FIN | `AGENT_FIN.md` | `reports/FIN_REPORT.md` |
| `AGENT_LOOP_TICK_E2E` | E2E | `AGENT_E2E.md` | `reports/E2E_REPORT.md` |
| `AGENT_LOOP_TICK_AGG` | AGG (сводит всё) | `AGENT_AGG.md` | `reports/MASTER_REPORT.md` |

Интервал: **10 минут** каждый QA-loop, **15 минут** агрегатор (сдвиг, чтобы читать свежие отчёты). Каждый loop независим.

При tick: прочитать инструкцию агента → выполнить проверки → перезаписать свой отчёт.
Итоговый статус GO/NO-GO — в `reports/MASTER_REPORT.md`.
