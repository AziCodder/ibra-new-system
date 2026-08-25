# Образ для локальной разработки: внутри живёт dev-сервер Vite.
# Версия node та же, что в Dockerfile.prod, — расхождение версий даёт
# «у меня собирается, на сервере нет».
FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

# Отпечаток лок-файла: по нему entrypoint понимает, что зависимости в томе
# устарели. Пишется после установки, иначе первый запуск ставил бы всё заново.
RUN md5sum package-lock.json | cut -d' ' -f1 | tr -d '\n' > node_modules/.lock-hash

COPY . .

CMD ["sh", "./docker-entrypoint.dev.sh"]
