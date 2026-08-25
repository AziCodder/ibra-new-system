FROM python:3.12-slim

WORKDIR /app

# pg_dump/pg_restore/psql нужны фоновому воркеру (бэкапы и проверка
# восстановлением). Версия клиента должна совпадать с сервером (16), поэтому
# ставим из репозитория PostgreSQL, а не из базового debian (там 15).
# tzdata — расписание бэкапов живёт в локальной таймзоне, а не в UTC.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends curl ca-certificates gnupg tzdata; \
    codename="$(. /etc/os-release && echo "$VERSION_CODENAME")"; \
    install -d /usr/share/postgresql-common/pgdg; \
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc; \
    echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] http://apt.postgresql.org/pub/repos/apt ${codename}-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends postgresql-client-16; \
    apt-get purge -y curl gnupg; apt-get autoremove -y; \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["sh", "./docker-entrypoint.dev.sh"]
