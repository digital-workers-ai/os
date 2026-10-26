FROM node:22-alpine@sha256:fe4f6d74e20370acb04ad889077d14d0f64a9c8ea6a42bc60cddf1e844699914 AS build
ARG APP
WORKDIR /build
COPY app/${APP}/package.json app/${APP}/package-lock.json ./
RUN npm ci
COPY app/${APP}/ ./
RUN npm run build

FROM node:22-alpine@sha256:fe4f6d74e20370acb04ad889077d14d0f64a9c8ea6a42bc60cddf1e844699914
ENV PORT=8080
WORKDIR /app
COPY app/preview/web/server.mjs app/preview/web/main.mjs ./
COPY --from=build /build/dist ./dist
USER node
CMD ["node", "main.mjs"]
