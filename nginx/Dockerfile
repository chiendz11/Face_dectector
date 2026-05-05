FROM alpine:3.20 AS config

WORKDIR /tmp/nginx
COPY nginx.conf.template ./nginx.conf.template
COPY docker-entrypoint.sh ./docker-entrypoint.sh
RUN chmod +x ./docker-entrypoint.sh

FROM nginx:1.27-alpine AS runtime

RUN apk upgrade --no-cache \
	&& apk add --no-cache gettext
COPY --from=config /tmp/nginx/nginx.conf.template /etc/nginx/templates/nginx.conf.template
COPY --from=config /tmp/nginx/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
