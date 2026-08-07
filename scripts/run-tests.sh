#!/bin/sh
# Run the backend test suite against a throwaway `ibra_test` database inside the
# running compose stack — never against the live `ibra_orders` data.
#
#   scripts/run-tests.sh                  # whole suite
#   scripts/run-tests.sh tests/test_products.py -x
set -e

PROJECT_DIR=$(cd "$(dirname "$0")/.." && pwd)
DB_URL="postgresql+asyncpg://postgres:${POSTGRES_PASSWORD:-48017efbda6a9aa5244dd160caa3bf6d}@db:5432/ibra_test"

docker run --rm \
  --entrypoint sh \
  --network ibra-new-system_default \
  -v "$PROJECT_DIR:/proj" \
  -w /proj/backend \
  -e APP_ENV=development \
  -e DATABASE_URL="$DB_URL" \
  -e SESSION_SECRET=test-secret-not-used-in-production-0123456789 \
  -e UPLOAD_DIR=/tmp/uploads \
  ibra-new-system-backend \
  -c "python -m alembic upgrade head >/dev/null && python -m pytest $*"
