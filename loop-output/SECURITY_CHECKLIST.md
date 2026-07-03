# Security checklist — Phase 15.2 (production configuration)

| # | Проверка | Статус | Реализация |
|---|----------|--------|------------|
| 1 | Prod-переменные отделены от dev | ✅ | `APP_ENV`, `.env.production.example` |
| 2 | SESSION_SECRET обязателен и ≥32 символов в prod | ✅ | `Settings.validate_production_security` |
| 3 | Session cookie: HttpOnly | ✅ | `session_cookie_params()` |
| 4 | Session cookie: Secure в prod (HTTPS) | ✅ | `cookie_secure` при `APP_ENV=production` |
| 5 | Session cookie: SameSite | ✅ | `COOKIE_SAMESITE` (default `lax`) |
| 6 | CORS — явный список origin, без `*` в prod | ✅ | validator в `config.py` |
| 7 | Trusted Host (Host header) в prod | ✅ | `TrustedHostMiddleware` |
| 8 | HTTPS / reverse proxy headers | ✅ | `ProxyHeadersMiddleware`, uvicorn `--proxy-headers` |
| 9 | OpenAPI/docs отключены в prod | ✅ | `docs_url=None` в `main.py` |
| 10 | Бэкап БД | ✅ | `python -m app.scripts.backup_db`, `docker compose --profile backup` |

## Запуск бэкапа

```bash
# Локально (нужен pg_dump)
cd backend && python -m app.scripts.backup_db ../backups

# Docker one-shot
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile backup run --rm backup
```

## Prod checklist перед деплоем

- [ ] Скопировать `.env.production.example` → `.env`, заполнить секреты
- [ ] Настроить TLS на reverse proxy (443 → frontend/backend)
- [ ] `CORS_ORIGINS` = публичный URL фронтенда
- [ ] `TRUSTED_HOSTS` = домены API/фронта
- [ ] Настроить cron/systemd для регулярного бэкапа
