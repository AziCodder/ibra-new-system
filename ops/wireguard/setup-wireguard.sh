#!/usr/bin/env bash
# Шифрованный туннель между двумя серверами.
#
# Зачем он нужен. Серверы стоят у РАЗНЫХ провайдеров, значит весь обмен между
# ними идёт через открытый интернет: и поток репликации PostgreSQL (это все
# ваши данные, в открытом виде), и проверки «жив ли сосед». Туннель решает
# сразу две задачи: трафик шифруется, и у каждого узла появляется постоянный
# внутренний адрес (10.8.0.1 и 10.8.0.2), не зависящий от провайдера.
#
# Запускать на КАЖДОМ сервере:
#   sudo ./setup-wireguard.sh A <публичный-IP-сервера-B>
#   sudo ./setup-wireguard.sh B <публичный-IP-сервера-A>
#
# Скрипт печатает публичный ключ этого сервера — его нужно вписать на втором
# (переменная PEER_PUBLIC_KEY) и наоборот. Порядок: запустить на обоих,
# обменяться ключами, запустить повторно с ключом соседа.
set -euo pipefail

ROLE="${1:?укажите роль: A или B}"
PEER_ENDPOINT="${2:?укажите публичный IP второго сервера}"
PEER_PUBLIC_KEY="${PEER_PUBLIC_KEY:-}"
WG_PORT="${WG_PORT:-51820}"
# MTU туннеля. Автоопределение исходит из локального маршрута, а на длинном
# международном пути реальный MTU нередко меньше — и тогда крупные пакеты
# репликации молча теряются: связь «есть», ping идёт, а поток встаёт на
# больших транзакциях. 1380 с запасом проходит такие маршруты.
WG_MTU="${WG_MTU:-1380}"

case "$ROLE" in
  A) SELF_IP=10.8.0.1; PEER_IP=10.8.0.2 ;;
  B) SELF_IP=10.8.0.2; PEER_IP=10.8.0.1 ;;
  *) echo "Роль должна быть A или B"; exit 1 ;;
esac

if ! command -v wg >/dev/null 2>&1; then
  echo "== Ставлю wireguard"
  apt-get update -qq
  apt-get install -y -qq wireguard
fi

mkdir -p /etc/wireguard
chmod 700 /etc/wireguard

if [ ! -f /etc/wireguard/private.key ]; then
  umask 077
  wg genkey | tee /etc/wireguard/private.key | wg pubkey > /etc/wireguard/public.key
fi

SELF_PRIVATE_KEY="$(cat /etc/wireguard/private.key)"
SELF_PUBLIC_KEY="$(cat /etc/wireguard/public.key)"

if [ -z "$PEER_PUBLIC_KEY" ]; then
  echo ""
  echo "Публичный ключ этого сервера ($ROLE): $SELF_PUBLIC_KEY"
  echo "Скопируйте его на второй сервер и запустите там:"
  echo "  PEER_PUBLIC_KEY=$SELF_PUBLIC_KEY sudo ./setup-wireguard.sh <роль> <IP этого сервера>"
  echo ""
  echo "Затем вернитесь сюда и запустите с ключом соседа."
  exit 0
fi

cat > /etc/wireguard/wg0.conf <<EOF
# Туннель между серверами кластера. Создан setup-wireguard.sh
[Interface]
Address = $SELF_IP/24
PrivateKey = $SELF_PRIVATE_KEY
ListenPort = $WG_PORT
MTU = $WG_MTU

[Peer]
PublicKey = $PEER_PUBLIC_KEY
Endpoint = $PEER_ENDPOINT:$WG_PORT
AllowedIPs = $PEER_IP/32
# Держим канал живым через NAT и фаерволы провайдеров: без этого туннель
# «засыпает», и первая же проверка соседа выглядит как его смерть.
PersistentKeepalive = 25
EOF
chmod 600 /etc/wireguard/wg0.conf

systemctl enable --now "wg-quick@wg0" >/dev/null 2>&1 || systemctl restart "wg-quick@wg0"

echo "== Туннель поднят: этот сервер $SELF_IP, сосед $PEER_IP"
echo "Публичный ключ этого сервера: $SELF_PUBLIC_KEY"
echo ""
echo "Проверка связи:"
ping -c 3 -W 2 "$PEER_IP" || echo "ВНИМАНИЕ: сосед не отвечает — проверьте ключи, порт $WG_PORT/udp и фаервол"

# Отдельно проверяем БОЛЬШИЕ пакеты. Обычный ping ходит мелкими и проходит
# почти всегда — а поток репликации состоит из крупных. Если этот тест не
# проходит, туннель будет выглядеть живым, но база на резерв не поедет.
#
# Проверка требует ping из iputils: у варианта из GNU inetutils нет флага
# -M do (запрет фрагментации), и без него тест «не проходит» для ЛЮБОГО
# размера — то есть врёт про MTU на ровном месте. В образах разных
# провайдеров стоит то один, то другой, поэтому нужный доставляем сами.
if ! ping -c 1 -M do -s 100 "$PEER_IP" >/dev/null 2>&1 && ! ping -M do -V >/dev/null 2>&1; then
  case "$(ping -V 2>&1)" in
    *inetutils*)
      echo "== Ставлю iputils-ping (у inetutils нет флага -M do)"
      apt-get install -y -qq iputils-ping >/dev/null 2>&1 || true
      ;;
  esac
fi

echo ""
echo "Проверка больших пакетов (MTU $WG_MTU):"
if ping -c 2 -W 2 -M do -s "$((WG_MTU - 28))" "$PEER_IP" >/dev/null 2>&1; then
  echo "  ок — пакеты полного размера проходят"
else
  echo "  ВНИМАНИЕ: пакеты размером $WG_MTU не проходят. Репликация будет"
  echo "  вставать на больших транзакциях, хотя ping и покажет, что всё живо."
  echo "  Понижайте MTU и повторяйте: WG_MTU=1280 sudo ./setup-wireguard.sh ..."
fi
