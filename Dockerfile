FROM node:20-alpine
WORKDIR /app
RUN npm i express @actual-app/api
COPY server.js .
ENV PORT=8000
EXPOSE 8000
CMD ["node","server.js"]