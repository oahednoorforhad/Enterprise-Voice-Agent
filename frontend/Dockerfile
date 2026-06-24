# Stage 1: Build React app
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --silent

COPY . .

# VITE_API_URL is injected at build time — Vite bakes it into the JS bundle
# NOTE: passed inline in RUN to force Docker cache invalidation when the ARG changes
ARG VITE_API_URL=http://localhost:8000
ARG VITE_SENTRY_DSN=""

RUN VITE_API_URL=$VITE_API_URL VITE_SENTRY_DSN=$VITE_SENTRY_DSN npm run build

# Stage 2: Serve with Nginx
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
