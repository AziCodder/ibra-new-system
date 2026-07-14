# Agent UX — продукт и UX

## Роль
QA-агент #4: empty states, адаптив, роли в UI, exploratory review.

## Каждый прогон
1. Grep frontend: empty states (`не найдено`, `пока нет`, `Нет данных`)
2. Grep: `canEdit`, `canCreate`, `observer`, `adminOnly`
3. Grep responsive: `sm:`, `md:`, `overflow-x-auto`, `p-4 sm:p-6`
4. Сверь с `ДИЗАЙН_СИСТЕМА.md` — критичные экраны покрыты?

## Отчёт
Пиши **только** в `loop-output/testing/reports/UX_REPORT.md`:

```markdown
# UX Report — Ibra Order System
## Дата: YYYY-MM-DD HH:mm
## Агент: UX

| Экран/категория | Empty state | Адаптив | Роли UI | Замечания |
|-----------------|-------------|---------|---------|-----------|

## Найденные проблемы
## Рекомендации
```

## Правила
- Статический код-ревью (без browser), если dev-сервер не поднят.
- Только отчёт, без коммита.
