# syntax=docker/dockerfile:1.7

FROM node:20-alpine AS build
WORKDIR /app

COPY package.json package-lock.json* pnpm-lock.yaml* ./
RUN if [ -f package-lock.json ]; then npm ci --legacy-peer-deps; else npm install --legacy-peer-deps; fi

COPY . .
ARG VITE_API_URL=""
ENV NODE_ENV=production
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

FROM nginx:1.27-alpine AS runtime
WORKDIR /usr/share/nginx/html

# Default backend target for same-origin proxy in standalone deployments.
# Override at runtime with: -e API_UPSTREAM=http://your-backend:8000
ENV API_UPSTREAM=http://api:8000

COPY nginx.default.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist/public/ ./

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD wget -q -O - http://127.0.0.1/ >/dev/null || exit 1
