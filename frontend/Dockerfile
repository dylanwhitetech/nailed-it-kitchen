# syntax=docker/dockerfile:1
# Build the static app on the native build platform (fast under buildx), then
# copy the platform-independent files into a multi-arch, non-root nginx image.
FROM --platform=$BUILDPLATFORM node:26-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Docker Compose checks only: the parser tests read the golden cases shared with recipes/validate.py.
FROM build AS checks
COPY --from=recipe-tests paste_cases.json /recipes/tests/paste_cases.json

FROM nginxinc/nginx-unprivileged:stable-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
USER 101
