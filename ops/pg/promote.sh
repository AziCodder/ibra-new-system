#!/usr/bin/env bash
# Повысить резерв до главного вручную.
#
# Обычно это делает автоматика (сторож в воркере), но переключение должно
# быть доступно и руками — на учениях, при плановых работах и в случае,
# когда автоматика выключена или не сработала.
#
#   sudo ./ops/pg/promote.sh
#
# После повышения обязательно переведите домен на этот сервер (или убедитесь,
# что это сделала автоматика) и НЕ поднимайте старого главного как главного:
# два главных — это разъехавшиеся данные. Возврат делается через
# rejoin-as-standby.sh на бывшем главном.
set -euo pipefail

COMPOSE="${COMPOSE:-docker compose -f docker-compose.prod.yml}"
DB_SERVICE="${DB_SERVICE:-db}"
PG_USER="${POSTGRES_USER:-postgres}"

in_recovery="$($COMPOSE exec -T "$DB_SERVICE" psql -U "$PG_USER" -tAc 'SELECT pg_is_in_recovery()')"
if [ "$in_recovery" != "t" ]; then
  echo "Этот узел уже главный — повышать нечего."
  exit 0
fi

echo "== Повышаю реплику до главного"
$COMPOSE exec -T "$DB_SERVICE" psql -U "$PG_USER" -tAc 'SELECT pg_promote(true, 60)'

echo "== Проверка"
$COMPOSE exec -T "$DB_SERVICE" psql -U "$PG_USER" -tAc 'SELECT pg_is_in_recovery()'
echo "(f = узел стал главным)"

echo ""
echo "Дальше:"
echo "  1. Переведите домен на IP этого сервера (если автоматика не сделала)."
echo "  2. Проверьте, что приложение пишет: откройте админку, создайте запись."
echo "  3. Бывшего главного возвращайте в строй ТОЛЬКО как резерв:"
echo "     ./ops/pg/rejoin-as-standby.sh"
