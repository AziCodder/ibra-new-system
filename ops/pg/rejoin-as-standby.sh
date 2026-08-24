#!/usr/bin/env bash
# Вернуть бывшего главного в строй — резервом за новым главным.
#
# После аварийного переключения старый сервер поднимается со своей копией
# данных, которая уже отстала от жизни. Поднять его главным нельзя: получатся
# два главных с разными данными, и часть заказов будет существовать только на
# одном из них. Правильный путь один — заново налить его с нового главного.
#
#   sudo REPLICATION_PASSWORD='...' PRIMARY_IP=10.8.0.2 ./ops/pg/rejoin-as-standby.sh
#
# Перед этим скрипт снимает копию текущего состояния сервера: если на нём
# успели появиться записи, которых нет у нового главного, они сохранятся в
# дампе, и их можно будет разобрать вручную.
set -euo pipefail

COMPOSE="${COMPOSE:-docker compose -f docker-compose.prod.yml}"
DB_SERVICE="${DB_SERVICE:-db}"
PG_USER="${POSTGRES_USER:-postgres}"
PG_DB="${POSTGRES_DB:-ibra_orders}"
OUT_DIR="${OUT_DIR:-./backups/before-rejoin}"

mkdir -p "$OUT_DIR"
STAMP="$(date -u +%Y%m%d_%H%M%S)"
DUMP="$OUT_DIR/before_rejoin_$STAMP.dump"

echo "== Сохраняю текущее состояние этого сервера в $DUMP"
$COMPOSE exec -T "$DB_SERVICE" pg_dump -U "$PG_USER" -d "$PG_DB" \
  --format=custom --no-owner --no-privileges > "$DUMP"
echo "   размер: $(du -h "$DUMP" | cut -f1)"
echo "   Здесь лежат данные, которые могли не доехать до нового главного."

echo ""
echo "== Наливаю базу заново с нового главного"
exec "$(dirname "$0")/setup-standby.sh"
