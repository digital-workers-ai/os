FROM node:20-alpine AS build
ARG APP
WORKDIR /build
COPY app/${APP}/package.json app/${APP}/package-lock.json ./
RUN npm ci
COPY app/${APP}/ ./
RUN npm run build

FROM node:22-alpine
ENV PORT=8080
WORKDIR /app
COPY app/preview/web/server.mjs app/preview/web/main.mjs ./
COPY --from=build /build/dist ./dist
USER node
CMD ["node", "main.mjs"]
