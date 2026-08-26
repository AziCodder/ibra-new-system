#!/bin/sh
# Post-install скрипт для панели провайдера: выполняется от root при первом
# запуске нового сервера. Делает шаг 1 инструкции целиком, чтобы машина
# приезжала уже готовой.
#
# Вставляется в поле «Post-install скрипт» при заказе VPS. Одинаков для обоих
# серверов кластера — ничего специфичного для узла тут нет.
set -e

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get upgrade -y
apt-get install -y ca-certificates curl gnupg git ufw wireguard iputils-ping

# Docker ставим из репозитория Docker, а не из Ubuntu: пакета
# docker-compose-plugin в репозиториях 22.04 нет, и `apt install` на нём
# спотыкается. Заодно получаем свежую версию, а не отставшую на год.
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker

# Подкачка: на 2 ГБ единственный момент, когда память может кончиться, —
# часовой бэкап, который держит дамп целиком. Это подушка, а не решение.
#
# Проверяем ПОДКЛЮЧЁННЫЙ swap, а не наличие файла: в образах некоторых
# провайдеров /swapfile лежит с завода, но не подключён и не прописан в
# fstab. Проверка «файл существует» такой образ пропускала, и сервер
# оставался вообще без подкачки — ровно там, где она и нужна.
if ! swapon --show 2>/dev/null | grep -q .; then
    swapoff /swapfile 2>/dev/null || true
    rm -f /swapfile
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
# Своппить только когда действительно припёрло: иначе база уедет в swap на
# ровном месте и всё станет медленным без всякой причины.
sysctl -w vm.swappiness=10
grep -q '^vm.swappiness' /etc/sysctl.conf || echo 'vm.swappiness=10' >> /etc/sysctl.conf

# Фаервол. Порядок важен: сначала разрешаем SSH, только потом включаем —
# наоборот означает закрыть себе доступ к серверу, до которого ещё не дошли.
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 51820/udp
ufw --force enable

# Порт PostgreSQL наружу не открывается: реплика ходит внутри туннеля.

echo "post-install готов: docker $(docker --version), swap $(free -h | awk '/Swap/ {print $2}')"
