# Build stage
FROM node:18-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG REACT_APP_API_URL=http://localhost:5001
ENV REACT_APP_API_URL=$REACT_APP_API_URL

RUN npm run build

# Serve stage
FROM nginx:alpine

COPY --from=build /app/build /usr/share/nginx/html

# SPA fallback: serve index.html for all routes
RUN echo 'server { \
    listen 80; \
    location / { \
        root /usr/share/nginx/html; \
        index index.html; \
        try_files $uri $uri/ /index.html; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
