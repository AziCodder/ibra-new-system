#!/bin/sh
# Тесты гоняются в том же контейнере, что и приложение, на отдельной базе
# `ibra_test` — никогда на живых данных `ibra_orders`.
#
#   scripts/run-tests.sh                  # весь набор
#   scripts/run-tests.sh tests/test_products.py -x
#
# Имена сети и образа не зашиты: `docker compose run` берёт их у проекта сам,
# иначе после переименования папки скрипт молча переставал находить сеть.
set -e

cd "$(dirname "$0")/.."

exec docker compose run --rm \
  --entrypoint sh \
  -e APP_ENV=development \
  -e DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:-postgres}@db:5432/ibra_test" \
  -e SESSION_SECRET=test-secret-not-used-in-production-0123456789 \
  -e UPLOAD_DIR=/tmp/uploads \
  backend \
  -c "python -m alembic upgrade head >/dev/null && python -m pytest $*"
