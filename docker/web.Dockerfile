FROM node:22-alpine AS build
WORKDIR /srv/photo2craft/apps/web
COPY apps/web/package*.json ./
RUN npm ci
COPY apps/web/ ./
COPY shared/ /srv/photo2craft/shared/
RUN npm run build
FROM nginx:1.27-alpine
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /srv/photo2craft/apps/web/dist /usr/share/nginx/html
EXPOSE 80
