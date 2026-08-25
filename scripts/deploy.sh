#!/usr/bin/env bash
# Выкладка боевого стека: тянем готовые образы и перезапускаем.
#
#   ./scripts/deploy.sh                # последняя собранная версия
#   IMAGE_TAG=<sha> ./scripts/deploy.sh  # откат на конкретную сборку
#
# Образы здесь НЕ собираются. На сервере 2 ГБ памяти, сборке фронтенда нужно
# 1.5-2.5 ГБ — `--build` упал бы по OOM в момент выкладки. Собирает CI после
# прогона тестов, сюда приезжает готовое.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -f .env ]; then
  echo "Нет .env — скопируйте backend/.env.production.example и заполните."
  exit 1
fi

COMPOSE="docker compose -f docker-compose.prod.yml"

echo "== Тяну образы (${IMAGE_TAG:-latest})"
$COMPOSE pull

echo "== Перезапускаю"
$COMPOSE up -d

echo "== Жду, пока backend ответит"
for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${HTTP_PORT:-8080}/api/cluster/ping" >/dev/null 2>&1; then
    echo "   готов"
    break
  fi
  [ "$i" = "30" ] && { echo "   НЕ ОТВЕТИЛ за 60 c — смотрите $COMPOSE logs backend"; exit 1; }
  sleep 2
done

echo ""
$COMPOSE ps
echo ""
echo "Откат на предыдущую сборку: IMAGE_TAG=<sha предыдущего коммита> ./scripts/deploy.sh"
