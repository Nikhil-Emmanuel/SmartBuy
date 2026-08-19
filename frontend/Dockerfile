# Frontend image: build the SPA, serve the static output with nginx.
# Only used by docker-compose. Vercel builds from source and needs no Dockerfile.

FROM node:20-alpine AS build
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

# Vite inlines VITE_* at build time, so the API URL is fixed into the bundle
# here and cannot be changed later by an environment variable on the running
# container. That is a property of Vite, not a choice.
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
