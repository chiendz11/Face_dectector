FROM alpine:3.20 AS config

WORKDIR /tmp/nginx
COPY nginx.conf.template ./nginx.conf.template
COPY docker-entrypoint.sh ./docker-entrypoint.sh
RUN sed -i 's/\r$//' ./docker-entrypoint.sh ./nginx.conf.template \
    && chmod +x ./docker-entrypoint.sh

FROM nginxinc/nginx-unprivileged:1.29-alpine AS runtime

USER root

RUN apk upgrade --no-cache \
    && apk add --no-cache gettext
COPY --from=config /tmp/nginx/nginx.conf.template /etc/nginx/templates/nginx.conf.template
COPY --from=config /tmp/nginx/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

USER 101

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
