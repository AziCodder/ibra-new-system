#!/usr/bin/env bash
# Налить резервную базу с главного сервера и запустить её репликой.
#
# Запускать на сервере B (резервном), из корня проекта:
#   sudo REPLICATION_PASSWORD='...' PRIMARY_IP=10.8.0.1 ./ops/pg/setup-standby.sh
#
# ВНИМАНИЕ: скрипт ПОЛНОСТЬЮ СТИРАЕТ локальную базу этого сервера и заменяет
# её копией с главного. На резерве это и требуется, но запускать его на
# работающем главном нельзя ни при каких обстоятельствах — поэтому он
# отдельно проверяет, что вы понимаете, что делаете.
set -euo pipefail

COMPOSE="${COMPOSE:-docker compose -f docker-compose.prod.yml}"
DB_SERVICE="${DB_SERVICE:-db}"
REPL_USER="${REPLICATION_USER:-replicator}"
REPL_PASSWORD="${REPLICATION_PASSWORD:?задайте REPLICATION_PASSWORD}"
PRIMARY_IP="${PRIMARY_IP:-10.8.0.1}"
STANDBY_NAME="${SYNC_STANDBY_NAME:-standby}"
PGIMAGE="${PGIMAGE:-postgres:16-alpine}"

VOLUME="$(docker volume ls -q --filter "name=_pgdata" | head -1)"
VOLUME="${PGDATA_VOLUME:-$VOLUME}"
[ -n "$VOLUME" ] || { echo "Не нашёл том с данными базы; задайте PGDATA_VOLUME"; exit 1; }

echo "Данные тома '$VOLUME' будут СТЁРТЫ и заменены копией с $PRIMARY_IP."
# Подтверждение можно передать переменной CONFIRM=да — иначе спрашиваем.
# Через конвейер ответ передать нельзя: `docker compose exec` в вызывающем
# скрипте (rejoin-as-standby.sh) вычитывает stdin себе, и до этого вопроса
# ничего не доходит — процедура молча отменяется на середине.
answer="${CONFIRM:-}"
if [ -z "$answer" ]; then
  read -r -p "Это резервный сервер? Введите 'да' для продолжения: " answer
fi
[ "$answer" = "да" ] || { echo "Отменено"; exit 1; }

echo "== Останавливаю приложение и базу"
$COMPOSE stop backend worker "$DB_SERVICE" >/dev/null

echo "== Наливаю копию с главного (pg_basebackup)"
# Копия снимается прямо в том. --wal-method=stream гарантирует, что вместе с
# данными приедут журналы, накопившиеся за время копирования, иначе резерв
# стартовал бы с дырой и не догнал бы главного.
docker run --rm \
  -e PGPASSWORD="$REPL_PASSWORD" \
  -v "$VOLUME:/var/lib/postgresql/data" \
  --network host \
  "$PGIMAGE" \
  sh -c "rm -rf /var/lib/postgresql/data/* &&
         pg_basebackup -h $PRIMARY_IP -p 5432 -U $REPL_USER \
           -D /var/lib/postgresql/data -Fp -Xs -P -R \
           -S ${STANDBY_NAME}_slot &&
         chown -R postgres:postgres /var/lib/postgresql/data &&
         chmod 700 /var/lib/postgresql/data"

echo "== Прописываю имя резерва"
# По этому имени главный узнаёт свой синхронный резерв
# (synchronous_standby_names = 'ANY 1 (standby)').
docker run --rm -v "$VOLUME:/var/lib/postgresql/data" "$PGIMAGE" sh -c "
  sed -i \"s/^primary_conninfo = '\(.*\)'/primary_conninfo = '\1 application_name=$STANDBY_NAME'/\" \
    /var/lib/postgresql/data/postgresql.auto.conf
  grep -q 'application_name=$STANDBY_NAME' /var/lib/postgresql/data/postgresql.auto.conf"

echo "== Запускаю"
$COMPOSE up -d "$DB_SERVICE"
sleep 5
# Поднимаем ВСЁ, а не только базу с приложением: без frontend и edge узел
# не отвечает на 443, то есть после возврата в строй сайт на нём молчит.
# Проверка соседа тоже ходит на 80 порт — без edge узел выглядит мёртвым.
$COMPOSE up -d backend worker frontend edge

echo ""
echo "Готово. Проверьте здесь:"
echo "  $COMPOSE exec db psql -U postgres -c 'SELECT pg_is_in_recovery();'   -> должно быть t"
echo "И на главном сервере:"
echo "  docker compose -f docker-compose.prod.yml exec db psql -U postgres \\"
echo "    -c 'SELECT application_name, state, sync_state FROM pg_stat_replication;'"
echo "  -> должна появиться строка '$STANDBY_NAME | streaming | sync'"
echo "     (или '... | streaming | async' — это норма при SYNC_REPLICATION=false,"
echo "      когда серверы стоят далеко друг от друга. Главное слово — streaming:"
echo "      если там 'catchup', резерв ещё догоняет, дождитесь streaming.)"
