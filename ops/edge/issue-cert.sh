#!/usr/bin/env bash
# Выпустить сертификат для flow.cargo-ibragim.ru на этом сервере.
#
#   sudo EMAIL=you@example.com ./ops/edge/issue-cert.sh
#
# Выпускать нужно на КАЖДОМ сервере отдельно: у каждого свой том с
# сертификатами. Домен на момент выпуска должен указывать на тот сервер, где
# запускается скрипт, — Let's Encrypt проверяет владение доменом, обращаясь
# по нему извне. Порядок такой: выпустили на A → перевели домен на B →
# выпустили на B → вернули домен на A.
#
# Если сертификат куплен, а не выпускается через Let's Encrypt, этот скрипт
# не нужен: положите fullchain.pem и privkey.pem в том certs по пути
#   /etc/letsencrypt/live/flow.cargo-ibragim.ru/
# и перезапустите edge.
set -euo pipefail

COMPOSE="${COMPOSE:-docker compose -f docker-compose.prod.yml}"
DOMAIN="${DOMAIN:-flow.cargo-ibragim.ru}"
EMAIL="${EMAIL:?укажите EMAIL для уведомлений об истечении сертификата}"

echo "== Проверяю, что домен указывает сюда"
resolved="$(getent hosts "$DOMAIN" | awk '{print $1}' | head -1 || true)"
mine="$(curl -fsS --max-time 10 https://api.ipify.org || true)"
if [ -n "$resolved" ] && [ -n "$mine" ] && [ "$resolved" != "$mine" ]; then
  echo "ВНИМАНИЕ: $DOMAIN сейчас указывает на $resolved, а этот сервер — $mine."
  echo "Let's Encrypt проверяет домен снаружи и выпуск не пройдёт."
  read -r -p "Всё равно продолжить? [да/нет]: " answer
  [ "$answer" = "да" ] || exit 1
fi

# Петля первого запуска: nginx не стартует без файлов сертификата (в конфиге
# есть блок 443), а сертификат нельзя получить, пока nginx не отвечает на 80.
# Разрывается временным самоподписанным сертификатом — certbot заменит его
# настоящим через несколько строк. Заодно это страховка на будущее: если файлы
# сертификата когда-нибудь пропадут, edge поднимется и продолжит работать по
# HTTP, вместо того чтобы не стартовать вовсе.
echo "== Проверяю, есть ли чем запустить nginx"
$COMPOSE run --rm --entrypoint sh certbot -c "
  set -e
  d=/etc/letsencrypt/live/$DOMAIN
  if [ -f \$d/fullchain.pem ]; then
    echo '   сертификат на месте'
  else
    echo '   сертификата нет — кладу временный самоподписанный на 1 день'
    mkdir -p \$d
    openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
      -keyout \$d/privkey.pem -out \$d/fullchain.pem \
      -subj '/CN=$DOMAIN' 2>/dev/null
  fi
"

echo "== Поднимаю edge на 80 порту (нужен для проверки владения доменом)"
$COMPOSE up -d edge

echo "== Запрашиваю сертификат"
$COMPOSE run --rm --entrypoint certbot certbot \
  certonly --webroot -w /var/www/certbot \
  -d "$DOMAIN" --email "$EMAIL" \
  --agree-tos --no-eff-email --non-interactive

echo "== Перечитываю конфиг nginx"
$COMPOSE exec edge nginx -s reload

echo ""
echo "Готово. Проверка:"
echo "  curl -sI https://$DOMAIN | head -3"
echo "Продление берёт на себя контейнер certbot — проверяет дважды в сутки."
