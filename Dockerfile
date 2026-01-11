FROM node:20-alpine

WORKDIR /app

COPY package.json .
RUN npm install

COPY server.js .

VOLUME ["/data"]

EXPOSE 8000
CMD ["node", "server.js"]

