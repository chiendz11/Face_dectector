#!/bin/sh
set -eu

RATE_LIMIT_ENABLED=$(printf '%s' "${NGINX_RATE_LIMIT_ENABLED:-true}" | tr '[:upper:]' '[:lower:]')
RATE_LIMIT_ZONE_RATE="${NGINX_RATE_LIMIT_ZONE_RATE:-5r/s}"
RATE_LIMIT_BURST="${NGINX_RATE_LIMIT_BURST:-10}"
RATE_LIMIT_MODE="${NGINX_RATE_LIMIT_MODE:-nodelay}"

if [ "$RATE_LIMIT_ENABLED" = "true" ] || [ "$RATE_LIMIT_ENABLED" = "1" ] || [ "$RATE_LIMIT_ENABLED" = "yes" ]; then
  NGINX_LIMIT_REQ_ZONE_DIRECTIVE="limit_req_zone \$binary_remote_addr zone=api_req:10m rate=${RATE_LIMIT_ZONE_RATE};"
  if [ -n "$RATE_LIMIT_MODE" ]; then
    NGINX_LIMIT_REQ_DIRECTIVE="limit_req zone=api_req burst=${RATE_LIMIT_BURST} ${RATE_LIMIT_MODE};"
  else
    NGINX_LIMIT_REQ_DIRECTIVE="limit_req zone=api_req burst=${RATE_LIMIT_BURST};"
  fi
  NGINX_LIMIT_REQ_STATUS_DIRECTIVE="limit_req_status 429;"
else
  NGINX_LIMIT_REQ_ZONE_DIRECTIVE=""
  NGINX_LIMIT_REQ_DIRECTIVE=""
  NGINX_LIMIT_REQ_STATUS_DIRECTIVE=""
fi

export NGINX_LIMIT_REQ_ZONE_DIRECTIVE
export NGINX_LIMIT_REQ_DIRECTIVE
export NGINX_LIMIT_REQ_STATUS_DIRECTIVE

envsubst '${NGINX_LIMIT_REQ_ZONE_DIRECTIVE} ${NGINX_LIMIT_REQ_DIRECTIVE} ${NGINX_LIMIT_REQ_STATUS_DIRECTIVE}' \
  < /etc/nginx/templates/nginx.conf.template \
  > /etc/nginx/nginx.conf

exec nginx -g 'daemon off;'
