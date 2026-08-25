#!/usr/bin/env bash
# Подготовить базу главного сервера к репликации.
#
# Запускать на сервере A (главном), из корня проекта:
#   sudo REPLICATION_PASSWORD='...' ./ops/pg/setup-primary.sh
#
# Скрипт можно запускать повторно: всё, что уже настроено, пропускается.
set -euo pipefail

COMPOSE="${COMPOSE:-docker compose -f docker-compose.prod.yml}"
DB_SERVICE="${DB_SERVICE:-db}"
PG_USER="${POSTGRES_USER:-postgres}"
REPL_USER="${REPLICATION_USER:-replicator}"
REPL_PASSWORD="${REPLICATION_PASSWORD:?задайте REPLICATION_PASSWORD}"
PEER_IP="${PEER_IP:-10.8.0.2}"          # адрес резерва внутри туннеля
STANDBY_NAME="${SYNC_STANDBY_NAME:-standby}"
# Синхронный режим осмыслен, когда серверы рядом (задержка 1-3 мс). Если они
# в разных странах, каждая запись ждала бы соседа десятки миллисекунд, поэтому
# режим выключают в .env — и скрипт обязан это уважать, иначе настройка
# молча вернула бы синхронность обратно.
SYNC_REPLICATION="${SYNC_REPLICATION:-true}"
# Сколько WAL главный готов копить для отставшего резерва. Слот держит журналы
# сколько угодно — и однажды забивает диск целиком; потолок превращает эту
# аварию в куда более дешёвую «резерв придётся переналить».
MAX_SLOT_WAL="${MAX_SLOT_WAL_KEEP_SIZE:-10GB}"

psql() { $COMPOSE exec -T "$DB_SERVICE" psql -U "$PG_USER" -d postgres -v ON_ERROR_STOP=1 "$@"; }

echo "== Пользователь репликации"
psql -c "DO \$\$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '$REPL_USER') THEN
    CREATE ROLE $REPL_USER WITH REPLICATION LOGIN PASSWORD '$REPL_PASSWORD';
  ELSE
    ALTER ROLE $REPL_USER WITH REPLICATION LOGIN PASSWORD '$REPL_PASSWORD';
  END IF;
END \$\$;"

echo "== Слот репликации"
# Слот заставляет главный хранить WAL, пока резерв их не заберёт. Без слота
# отставший или временно погасший резерв обнаружит, что нужные ему журналы
# уже удалены, и его придётся переналивать с нуля.
psql -c "SELECT pg_create_physical_replication_slot('${STANDBY_NAME}_slot')
         WHERE NOT EXISTS (SELECT 1 FROM pg_replication_slots WHERE slot_name = '${STANDBY_NAME}_slot');"

echo "== Параметры WAL"
psql -c "ALTER SYSTEM SET wal_level = 'replica';"
psql -c "ALTER SYSTEM SET max_wal_senders = 10;"
psql -c "ALTER SYSTEM SET max_replication_slots = 10;"
psql -c "ALTER SYSTEM SET wal_keep_size = '1GB';"
psql -c "ALTER SYSTEM SET max_slot_wal_keep_size = '$MAX_SLOT_WAL';"
psql -c "ALTER SYSTEM SET hot_standby = on;"
# Сжатие WAL: между странами поток репликации идёт через платный внешний
# канал, и на записях с полными образами страниц сжатие срезает его в разы.
# Цена — немного процессорного времени, которого на этом приложении избыток.
psql -c "ALTER SYSTEM SET wal_compression = on;"

if [ "$SYNC_REPLICATION" = "true" ]; then
  # Синхронный режим: транзакция подтверждается только после записи на резерв.
  # ANY 1 — достаточно одного подтверждения; при пропаже резерва воркер сам
  # опустит режим до асинхронного, иначе запись встала бы целиком.
  echo "   режим: синхронный (транзакция ждёт резерв)"
  psql -c "ALTER SYSTEM SET synchronous_standby_names = 'ANY 1 ($STANDBY_NAME)';"
else
  # Асинхронный режим: главный никого не ждёт. Так делают, когда серверы
  # далеко друг от друга. Плата — окно потери: всё, что не доехало до
  # резерва, исчезнет вместе с главным. За размером окна следит воркер
  # (guard_async_replication) и ругается, когда оно выходит за порог.
  echo "   режим: АСИНХРОННЫЙ (главный не ждёт резерв; возможна потеря последних транзакций)"
  psql -c "ALTER SYSTEM SET synchronous_standby_names = '';"
fi
# Локальный fsync остаётся в любом случае: своё-то мы теряем не хотим.
psql -c "ALTER SYSTEM SET synchronous_commit = 'on';"

echo "== Доступ резерва (pg_hba)"
HBA_LINE="host replication $REPL_USER $PEER_IP/32 scram-sha-256"
$COMPOSE exec -T "$DB_SERVICE" sh -c "
  grep -qF '$HBA_LINE' /var/lib/postgresql/data/pg_hba.conf ||
  echo '$HBA_LINE' >> /var/lib/postgresql/data/pg_hba.conf"

echo "== Применяю"
psql -c "SELECT pg_reload_conf();"

echo ""
echo "Готово. Проверьте после подключения резерва:"
echo "  $COMPOSE exec db psql -U $PG_USER -c 'SELECT application_name, state, sync_state FROM pg_stat_replication;'"
echo ""
echo "ВАЖНО: часть параметров (wal_level, max_wal_senders) применяется только"
echo "при перезапуске базы. Если это первая настройка — перезапустите её:"
echo "  $COMPOSE restart $DB_SERVICE"
