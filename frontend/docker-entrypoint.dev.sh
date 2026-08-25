#!/bin/sh
# node_modules лежат в docker-томе, а не в образе: правка package.json не
# должна требовать ручной пересборки. Сверяем отпечаток package-lock.json —
# если зависимости менялись, ставим их сами. Без этого контейнер молча
# запускался бы со старыми пакетами.
set -e

STAMP=node_modules/.lock-hash
LOCK_HASH=$(md5sum package-lock.json | cut -d' ' -f1)

if [ ! -x node_modules/.bin/vite ] || [ "$(cat "$STAMP" 2>/dev/null)" != "$LOCK_HASH" ]; then
  echo "Зависимости изменились — ставлю (npm ci), это займёт пару минут…"
  npm ci
  printf '%s' "$LOCK_HASH" > "$STAMP"
fi

echo "Запускаю фронтенд на :5173…"
exec npm run dev -- --host 0.0.0.0
