FROM node:26-bookworm-slim AS deps

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --include=optional \
    && npm install --no-save @rolldown/binding-linux-x64-gnu lightningcss-linux-x64-gnu @rollup/rollup-linux-x64-gnu

FROM node:26-bookworm-slim AS build

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY package.json package-lock.json ./

COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.27-alpine

USER root

RUN apk upgrade --no-cache

COPY --from=build /app/dist /usr/share/nginx/html

USER 101
